"""Configuration centralisée pour tous les mini-jeux de Root.

Ce module définit la configuration déclarative (GameConfig) pour chaque défi
cryptographique ou d'intégrité de Root, incluant les alias, les règles de parsing,
la typologie de réponse (narrowing vs binaire), le mode d'affichage de active_info,
et les hooks de journalisation vers Logger.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Literal


@dataclass(frozen=True)
class GameConfig:
    """Modèle déclaratif de configuration d'un mini-jeu.

    Attributes:
        key: Identifiant unique du jeu (ex: 'hash', 'pin', 'anomaly').
        aliases: Liste des alias de commandes préfixes (ex: ['h'], ['p']).
        param_name: Nom du paramètre de réponse de la commande.
        guess_kind: Type de conversion/validation attendu ('int', 'int_bounded', 'raw_str', 'letter').
        bounds: Bornes inclusives (min, max) pour 'int_bounded', None sinon.
        shape: Mécanique de jeu ('narrowing' avec trop haut/bas, 'binary' avec faux/gagné).
        active_info_mode: Mode de rendu pour active_info ('text' pour message simple, 'embed' pour RootEmbed).
        log_method: Nom de la méthode de Logger à appeler sur victoire.
        log_kwargs: Fonction extrayant les arguments spécifiques pour Logger à partir du résultat métier.
    """

    key: str
    aliases: list[str]
    param_name: str
    guess_kind: Literal["int", "int_bounded", "raw_str", "letter"]
    bounds: tuple[int, int] | None = None
    shape: Literal["narrowing", "binary"] = "binary"
    active_info_mode: Literal["text", "embed"] = "text"
    log_method: str = ""
    log_kwargs: Callable[[dict[str, Any]], dict[str, Any]] = field(default=lambda r: {})


GAMES: dict[str, GameConfig] = {
    "hash": GameConfig(
        key="hash",
        aliases=["h"],
        param_name="guess",
        guess_kind="int",
        shape="narrowing",
        active_info_mode="text",
        log_method="log_hash_won",
        log_kwargs=lambda r: {"target": r["target"], "players_count": r.get("players_count", 1)},
    ),
    "pin": GameConfig(
        key="pin",
        aliases=["p"],
        param_name="guess",
        guess_kind="int",
        shape="narrowing",
        active_info_mode="text",
        log_method="log_pin_won",
        log_kwargs=lambda r: {"target": r["target"], "players_count": r.get("players_count", 1)},
    ),
    "decode": GameConfig(
        key="decode",
        aliases=["d"],
        param_name="code",
        guess_kind="raw_str",
        shape="binary",
        active_info_mode="embed",
        log_method="log_decode_won",
        log_kwargs=lambda r: {"sequence": r.get("sequence", r.get("sequence_str", "")), "target": r.get("target", "")},
    ),
    "anomaly": GameConfig(
        key="anomaly",
        aliases=["a"],
        param_name="line",
        guess_kind="int_bounded",
        bounds=(1, 10),
        shape="binary",
        active_info_mode="embed",
        log_method="log_anomaly_won",
        log_kwargs=lambda r: {"line": r.get("line", 0), "digit": r.get("digit", "")},
    ),
    "buffer": GameConfig(
        key="buffer",
        aliases=["b"],
        param_name="code",
        guess_kind="raw_str",
        shape="binary",
        active_info_mode="embed",
        log_method="log_buffer_won",
        log_kwargs=lambda r: {"target": r.get("target", "")},
    ),
    "signal": GameConfig(
        key="signal",
        aliases=["s"],
        param_name="letter",
        guess_kind="letter",
        shape="binary",
        active_info_mode="embed",
        log_method="log_signal_won",
        log_kwargs=lambda r: {"winning_letter": r.get("winning_letter", "")},
    ),
    "packet": GameConfig(
        key="packet",
        aliases=["pa"],
        param_name="guess",
        guess_kind="int_bounded",
        bounds=(1, 10),
        shape="binary",
        active_info_mode="embed",
        log_method="log_packet_won",
        log_kwargs=lambda r: {"missing_packet": r.get("missing_packet", 0)},
    ),
}


def setup(bot):
    """Pas de Cog concret à enregistrer pour ce fichier de configuration."""
    pass

