"""
Persistance et résolution des attaques PvP (table SQL `pvp_attacks`).

Ce module gère le cycle de vie complet d'une attaque /hack :
- Création du job différé de 45 minutes
- Résolution transactionnelle atomique avec double verrou ordonné
- Destruction ordonnée des modules de défense
- Test d'intrusion strict (attack_points > total_defense)
- Destruction d'un module d'attaque ou transfert d'un module de minage (tier le plus haut)
- Enregistrement des droits de représailles (table `consequence`)
- Suppression de l'entrée temporaire après traitement
"""

import logging
from datetime import datetime
from decimal import Decimal

from game.db.consequence import ConsequenceDB
from game.db.database import player_lock_name
from game.math_config import MathConfig


logger = logging.getLogger(__name__)


class PvpDB:
    """Accès aux données et logique de résolution pour la table pvp_attacks."""

    @staticmethod
    def get_active_for_victim(tx, victim_id: int) -> dict | None:
        """Retourne l'attaque en cours ciblant ce joueur s'il y en a une."""
        return tx.one(
            'SELECT * FROM pvp_attacks WHERE victim_id = %s',
            (int(victim_id),),
        )

    @staticmethod
    def get_active_for_attacker(tx, attacker_id: int) -> list[dict]:
        """Retourne les attaques actives lancées par ce joueur."""
        return tx.all(
            'SELECT * FROM pvp_attacks WHERE attacker_id = %s ORDER BY resolves_at ASC',
            (int(attacker_id),),
        )

    @staticmethod
    def create(
        tx,
        attacker_id: int,
        victim_id: int,
        attack_points: int,
        target: str,
        resolves_at: datetime,
    ) -> dict:
        """Insère une attaque PvP dans la table pvp_attacks."""
        pvp_id = tx.execute(
            """
            INSERT INTO pvp_attacks (
                attacker_id, victim_id, attack_points, target, started_at, resolves_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                int(attacker_id),
                int(victim_id),
                int(attack_points),
                str(target),
                tx.now,
                resolves_at,
            ),
        )
        return {
            'id': pvp_id,
            'attacker_id': int(attacker_id),
            'victim_id': int(victim_id),
            'attack_points': int(attack_points),
            'target': str(target),
            'started_at': tx.now,
            'resolves_at': resolves_at,
        }

    @staticmethod
    def get_expired_ids(tx) -> list[int]:
        """Retourne la liste des IDs des attaques arrivées à échéance."""
        rows = tx.all(
            'SELECT id FROM pvp_attacks WHERE resolves_at <= %s ORDER BY resolves_at ASC',
            (tx.now,),
        )
        return [int(r['id']) for r in rows]

    @staticmethod
    def resolve_single_attack(tx, attack_id: int) -> dict | None:
        """
        Résout une unique attaque PvP de façon strictement atomique.
        Acquiert les verrous joueur nécessaires dans l'ordre croissant anti-deadlock.
        """
        from game.db.players import _settle_mining, UpdatePlayer

        # Verrouillage de la ligne d'attaque
        attack = tx.one(
            'SELECT * FROM pvp_attacks WHERE id = %s FOR UPDATE',
            (int(attack_id),),
        )
        if not attack:
            return None

        attacker_id = int(attack['attacker_id'])
        victim_id = int(attack['victim_id'])
        attack_points = int(attack['attack_points'])
        target_choice = str(attack['target'])

        # Double verrou joueur déterministe (ordre croissant)
        first_id, second_id = min(attacker_id, victim_id), max(attacker_id, victim_id)
        tx.acquire_lock(player_lock_name(first_id))
        tx.acquire_lock(player_lock_name(second_id))

        # Re-vérification avec SELECT FOR UPDATE sur les profils réels à cet instant exact
        attacker = tx.one('SELECT * FROM players WHERE discord_id = %s FOR UPDATE', (attacker_id,))
        victim = tx.one('SELECT * FROM players WHERE discord_id = %s FOR UPDATE', (victim_id,))

        if not attacker or not victim:
            # Si un compte a disparu entre-temps, nettoyage propre sans erreur
            tx.execute('DELETE FROM pvp_attacks WHERE id = %s', (int(attack_id),))
            return None

        # 1. Calcul de la défense totale initiale de la victime
        module_def_points = 0
        bay_counts = {}
        for tier in range(1, 7):
            cnt = int(victim.get(f'bay_defense_t{tier}') or 0)
            bay_counts[tier] = cnt
            unit_def = MathConfig.get_module_stat('bay_defense', tier)
            module_def_points += cnt * unit_def

        victim_fw = int(victim.get('firewall_level') or 0)
        firewall_def_points = MathConfig.get_firewall_network_defense(victim_fw)
        total_defense = module_def_points + firewall_def_points

        # 2. Destruction des modules de défense (T1 -> T6)
        destroyed_defense = 0
        destroyed_modules_by_tier = {}
        updates_victim = {}

        for tier in range(1, 7):
            cnt = bay_counts[tier]
            unit_def = MathConfig.get_module_stat('bay_defense', tier)
            if unit_def <= 0 or cnt <= 0:
                continue

            destroyed_in_tier = 0
            while destroyed_in_tier < cnt:
                if destroyed_defense + unit_def <= attack_points:
                    destroyed_in_tier += 1
                    destroyed_defense += unit_def
                else:
                    break

            if destroyed_in_tier > 0:
                destroyed_modules_by_tier[tier] = destroyed_in_tier
                new_cnt = cnt - destroyed_in_tier
                updates_victim[f'bay_defense_t{tier}'] = new_cnt
                victim[f'bay_defense_t{tier}'] = new_cnt

            # Si on ne peut même pas détruire un module de ce tier, les tiers supérieurs sont encore plus chers
            if destroyed_defense + unit_def > attack_points and cnt > destroyed_in_tier:
                break

        # 3. Réussite de l'intrusion (strictement supérieur avant application des destructions)
        intrusion_success = attack_points > total_defense

        destroyed_attack_tier = None
        captured_mining_tier = None
        updates_attacker = {}

        if intrusion_success:
            if target_choice == 'attack':
                # Détruire un module d'attaque du tier le plus haut (T6 -> T1)
                for tier in range(6, 0, -1):
                    atk_cnt = int(victim.get(f'attack_t{tier}') or 0)
                    if atk_cnt > 0:
                        updates_victim[f'attack_t{tier}'] = atk_cnt - 1
                        victim[f'attack_t{tier}'] = atk_cnt - 1
                        destroyed_attack_tier = tier
                        break
            elif target_choice == 'mining':
                # Transférer un module de minage du tier le plus haut (T6 -> T1)
                for tier in range(6, 0, -1):
                    min_cnt = int(victim.get(f'mining_t{tier}') or 0)
                    if min_cnt > 0:
                        # Figer le minage des deux joueurs avant tout changement de matériel
                        _settle_mining(tx, victim, tx.now)
                        _settle_mining(tx, attacker, tx.now)

                        updates_victim[f'mining_t{tier}'] = min_cnt - 1
                        victim[f'mining_t{tier}'] = min_cnt - 1

                        att_cnt = int(attacker.get(f'mining_t{tier}') or 0)
                        updates_attacker[f'mining_t{tier}'] = att_cnt + 1
                        attacker[f'mining_t{tier}'] = att_cnt + 1

                        captured_mining_tier = tier
                        break

        # Application des modifications en base de données
        if updates_victim:
            UpdatePlayer.set(tx, victim_id, **updates_victim)
        if updates_attacker:
            UpdatePlayer.set(tx, attacker_id, **updates_attacker)

        # 4. Enregistrement des droits de représailles (72h)
        cfg = MathConfig.load().get('pvp', {})
        retaliation_hours = int(cfg.get('retaliation_window_hours', 72))
        ConsequenceDB.insert(tx, victim_id=victim_id, attacker_id=attacker_id, window_hours=retaliation_hours)

        # 5. Renouvellement immédiat du Secret ID de la victime
        from game.db.secret_ids import rotate_player_secret
        new_victim_secret = rotate_player_secret(tx, victim_id)

        # 6. Suppression de l'entrée temporaire de l'attaque
        tx.execute('DELETE FROM pvp_attacks WHERE id = %s', (int(attack_id),))

        return {
            'attack_id': int(attack_id),
            'attacker_id': attacker_id,
            'victim_id': victim_id,
            'attack_points': attack_points,
            'target': target_choice,
            'initial_total_defense': total_defense,
            'firewall_def_points': firewall_def_points,
            'module_def_points': module_def_points,
            'destroyed_defense_points': destroyed_defense,
            'destroyed_defense_modules': destroyed_modules_by_tier,
            'intrusion_success': intrusion_success,
            'destroyed_attack_tier': destroyed_attack_tier,
            'captured_mining_tier': captured_mining_tier,
            'victim_fw': victim_fw,
            'new_victim_secret': new_victim_secret,
            'attacker_lang': attacker.get('lang') or 'fr',
            'victim_lang': victim.get('lang') or 'fr',
        }

    @staticmethod
    def complete_and_delete_expired(tx) -> list[dict]:
        """
        Trouve toutes les attaques arrivées à échéance et les résout une par une.
        """
        expired_ids = PvpDB.get_expired_ids(tx)
        results = []
        for aid in expired_ids:
            res = PvpDB.resolve_single_attack(tx, aid)
            if res:
                results.append(res)
        return results

