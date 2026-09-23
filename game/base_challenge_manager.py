"""
Classe de base abstraite pour les gestionnaires des 7 mini-jeux communautaires de Root.

Ce module factorise le cycle de vie transactionnel et métier :
- Gestion de ChallengeResource (pattern 2-phase commit en mémoire vive).
- Vérification du cooldown MySQL (check_challenge_cooldown).
- Enregistrement des participations journalières (DailyEventStatsDB.record_participation).
- Règlement de victoire unifié (settle_challenge_win).
- Gestion des défis à réponse exacte unique via SingleTargetChallengeManager.
"""

import threading
from typing import Any

from game.challenge_utils import ChallengeResource, check_challenge_cooldown, settle_challenge_win
from game.db.daily_event_stats import DailyEventStatsDB


class BaseChallengeManager:
    """Classe de base fournissant la gestion transactionnelle 2-phase pour un mini-jeu."""

    event_name: str
    config_key: str
    _active_challenge: dict | None = None
    _lock: threading.RLock

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Chaque sous-classe possède son propre état en mémoire vive et son propre verrou
        cls._active_challenge = None
        cls._lock = threading.RLock()

    @classmethod
    def _create_new_challenge(cls) -> dict:
        """Génère une nouvelle instance de défi. À surcharger obligatoirement par les sous-classes."""
        raise NotImplementedError

    @classmethod
    def process(cls, tx, actor: int, guild_name: str | None, guess: Any = None, resource: ChallengeResource | None = None) -> dict:
        """
        Traite une proposition ou une consultation pour le mini-jeu.
        Gère le cycle de vie complet de la ressource transactionnelle (begin, commit, rollback).
        """
        if resource is None:
            auto_res = ChallengeResource(cls)
            auto_res.begin(tx)
            try:
                result = cls._process_staged(tx, actor, guild_name, guess, auto_res)
            except Exception:
                auto_res.rollback()
                raise
            else:
                auto_res.finish()
                return result
        return cls._process_staged(tx, actor, guild_name, guess, resource)

    @classmethod
    def _process_staged(cls, tx, actor: int, guild_name: str | None, guess: Any, resource: ChallengeResource) -> dict:
        """Méthode métier exécutée sous verrou et transaction active. À implémenter ou spécialiser."""
        raise NotImplementedError


class SingleTargetChallengeManager(BaseChallengeManager):
    """
    Spécialisation pour les 5 mini-jeux à réponse directe exacte :
    decode, anomaly, buffer, signal, packet.
    """

    target_key: str

    @classmethod
    def _normalize_guess(cls, raw_guess: Any) -> Any:
        """Normalise la proposition (suppression d'espaces, conversion majuscules par défaut)."""
        if raw_guess is None:
            return None
        if isinstance(raw_guess, int):
            return raw_guess
        return str(raw_guess).strip().upper()

    @classmethod
    def _format_active_info(cls, challenge: dict) -> dict:
        """Formate les données renvoyées lors d'une simple consultation sans réponse."""
        res = {"status": "active_info", "reward": challenge["reward"]}
        for k in ("block_display", "grid_display", "buffer_display", "letters"):
            if k in challenge:
                res[k] = challenge[k]
        if "sequence_str" in challenge:
            res["sequence"] = challenge["sequence_str"]
        elif "sequence" in challenge:
            res["sequence"] = challenge["sequence"]
        return res

    @classmethod
    def _format_wrong(cls, clean_guess: Any, challenge: dict) -> dict:
        """Formate les données renvoyées en cas d'échec."""
        res = {"status": "wrong", "guess": clean_guess}
        for k in ("block_display", "grid_display", "buffer_display"):
            if k in challenge:
                res[k] = challenge[k]
        if "sequence_str" in challenge:
            res["sequence"] = challenge["sequence_str"]
        elif "sequence" in challenge:
            res["sequence"] = challenge["sequence"]
        return res

    @classmethod
    def _format_won(cls, settlement: dict, challenge: dict, actor: int) -> dict:
        """Formate les données de victoire après règlement MySQL."""
        res = {
            "status": "won",
            "winner": actor,
            "reward": settlement["final_reward"],
            "base_reward": settlement["base_reward"],
            "multiplier": settlement["multiplier"],
            "next_at": settlement["next_at"],
            "last_found_on": settlement["server_name"],
        }
        for k in ("line", "digit", "target", "winning_letter", "missing_packet"):
            if k in challenge:
                res[k] = challenge[k]
        if "sequence_str" in challenge:
            res["sequence"] = challenge["sequence_str"]
            res["sequence_str"] = challenge["sequence_str"]
        elif "sequence" in challenge:
            seq_val = challenge["sequence"]
            res["sequence"] = " · ".join(seq_val) if isinstance(seq_val, (list, tuple)) else str(seq_val)
            res["sequence_str"] = res["sequence"]
        return res

    @classmethod
    def _process_staged(cls, tx, actor: int, guild_name: str | None, guess: Any, resource: ChallengeResource) -> dict:
        now = tx.now

        # 1. Vérification du cooldown réseau
        cooldown = check_challenge_cooldown(tx, cls.event_name, now)
        if cooldown:
            resource.stage(None)
            return cooldown

        # 2. Défi actif ou initialisation
        challenge = resource.staged_challenge
        if challenge is None:
            challenge = cls._create_new_challenge()
            resource.stage(challenge)

        # 3. Consultation sans proposition
        if guess is None:
            return cls._format_active_info(challenge)

        # 4. Enregistrement de la participation quotidienne
        DailyEventStatsDB.record_participation(tx, actor)

        # 5. Normalisation et vérification
        clean_guess = cls._normalize_guess(guess)
        target = challenge[cls.target_key]

        if clean_guess != target:
            return cls._format_wrong(clean_guess, challenge)

        # 6. Victoire
        settlement = settle_challenge_win(
            tx, cls.event_name, cls.config_key, actor, challenge["reward"], now, guild_name
        )
        resource.stage(None)
        return cls._format_won(settlement, challenge, actor)
