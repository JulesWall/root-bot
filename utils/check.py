"""
Contrôles d'accès universels au bot Root (permissions, rôles et bannissements).

Ce module centralise les règles d'habilitation :
1. is_player : Vérifie si un utilisateur possède un profil de jeu actif en base.
2. maintenance_enabled & can_bypass_maintenance : Mode maintenance filtrant les accès.
3. _has_role (is_op, can_bypass_maintenance) :
   - Vérifie la possession d'un rôle Discord spécifique sur le serveur maître ACCESS_GUILD_ID.
   - Utilise un appel REST direct guild.fetch_member(user_id) : cela prend immédiatement
     en compte les attributions/retraits de rôle sans dépendre du cache local ni nécessiter
     le Server Members Intent (intent privilégié).
4. is_banned & set_banned :
   - Gestion des exclusions locales dans data/banned.json avec mise en cache mémoire
     et écritures atomiques (.tmp -> replace).
"""

import inspect
import json
import logging
import os
from pathlib import Path
import threading

import discord

import data

BANNED_FILE = data.DATA_DIR / "banned.json"
BETA_ACCESS_FILE = data.DATA_DIR / "beta access.json"
ROOT_BETA_ACCESS_FILE = data.BASE_DIR / "beta access.json"
_beta_file_lock = threading.Lock()
logger = logging.getLogger(__name__)


def _get_beta_access_file() -> Path:
    """Retourne le chemin effectif du fichier beta access.json."""
    if ROOT_BETA_ACCESS_FILE.exists() and not BETA_ACCESS_FILE.exists():
        return ROOT_BETA_ACCESS_FILE
    return BETA_ACCESS_FILE


class Check:
    """Fournit l'ensemble des prédicats de vérification de sécurité."""

    # Cache en mémoire des identifiants bannis pour éviter les lectures disque répétées
    _banned_cache: 'list[int] | None' = None
    _beta_access_cache: 'set[int] | None' = None

    async def is_player(self, user_id: int, database=None) -> bool:
        """Vérifie si l'utilisateur possède un compte existant dans la table players."""
        from game.db.players import ExistPlayer
        return await ExistPlayer(database).fetch(user_id) is not None

    def maintenance_enabled(self) -> bool:
        """Vérifie si le mode maintenance globale est activé dans les variables d'environnement."""
        return os.getenv("MAINTENANCE", "false").strip().lower() in {"1", "true", "yes"}

    async def _has_role(self, bot: discord.Bot, user_id: int, role_variable: str) -> bool:
        """
        Vérifie si l'utilisateur possède le rôle spécifié par role_variable sur ACCESS_GUILD_ID.
        
        Technique :
        Effectue une requête REST (fetch_member) auprès de Discord pour obtenir l'état
        instantané des rôles du membre, même si la commande est tapée sur un autre serveur.
        """
        try:
            guild_id = int(os.getenv("ACCESS_GUILD_ID") or 0)
            role_id = int(os.getenv(role_variable) or 0)
        except ValueError:
            logger.warning("Identifiant invalide dans ACCESS_GUILD_ID ou %s", role_variable)
            return False

        if guild_id <= 0 or role_id <= 0:
            return False

        guild = bot.get_guild(guild_id)
        if guild is None:
            return False

        try:
            # Requête REST en direct : insensible aux retards de cache et sans intent privilégié
            member_res = guild.fetch_member(user_id)
            if inspect.isawaitable(member_res):
                member = await member_res
            else:
                member = member_res
        except discord.NotFound:
            return False
        except discord.HTTPException:
            logger.warning("Verification des roles impossible sur le serveur %s", guild.id, exc_info=True)
            return False

        if member is None or not hasattr(member, 'roles'):
            return False
        return any(role.id == role_id for role in member.roles)

    async def is_op(self, bot: discord.Bot, user_id: int) -> bool:
        """Vérifie si l'utilisateur détient le rôle OP (accès aux commandes ban, unban, guildinfo, shutdown)."""
        return await self._has_role(bot, user_id, "OP_ROLE_ID")

    async def can_bypass_maintenance(self, bot: discord.Bot, user_id: int) -> bool:
        """Vérifie si l'utilisateur possède le rôle autorisant le contournement de la maintenance ou le rôle OP."""
        if await self.is_op(bot, user_id):
            return True
        return await self._has_role(bot, user_id, "MAINTENANCE_BYPASS_ROLE_ID")

    def beta_enabled(self) -> bool:
        """Vérifie si le mode bêta globale est activé dans les variables d'environnement."""
        return os.getenv("BETA_MODE", os.getenv("BETA", "false")).strip().lower() in {"1", "true", "yes"}

    def load_beta_access(self) -> set[int]:
        """Charge la liste des identifiants autorisés pour la bêta depuis 'beta access.json'.
        
        Gère proprement un fichier absent ou corrompu (sans lever d'exception et sans ouvrir
        l'accès à tout le monde).
        """
        if Check._beta_access_cache is not None:
            return set(Check._beta_access_cache)

        file_path = _get_beta_access_file()
        if not file_path.exists():
            Check._beta_access_cache = set()
            return set()

        try:
            with file_path.open(encoding="utf-8") as file:
                data_list = json.load(file)
            if isinstance(data_list, list):
                parsed = set()
                for item in data_list:
                    try:
                        parsed.add(int(item))
                    except (ValueError, TypeError):
                        continue
                Check._beta_access_cache = parsed
                return set(parsed)
            else:
                logger.warning("Format invalide dans %s (attendu: liste JSON). Accès bêta verrouillé.", file_path)
                Check._beta_access_cache = set()
                return set()
        except Exception:
            logger.warning("Erreur lors de la lecture de %s. Accès bêta verrouillé.", file_path, exc_info=True)
            Check._beta_access_cache = set()
            return set()

    def grant_beta_access(self, user_id: int) -> bool:
        """
        Accorde de manière permanente et thread-safe l'accès à la bêta pour user_id.
        Met à jour 'beta access.json' de manière atomique (.tmp -> replace).
        Retourne True si l'accès vient d'être accordé, False s'il l'avait déjà.
        """
        user_id = int(user_id)
        with _beta_file_lock:
            file_path = _get_beta_access_file()
            existing = set()
            if file_path.exists():
                try:
                    with file_path.open(encoding="utf-8") as file:
                        raw = json.load(file)
                        if isinstance(raw, list):
                            for item in raw:
                                try:
                                    existing.add(int(item))
                                except (ValueError, TypeError):
                                    continue
                except Exception:
                    logger.warning("Échec de lecture de %s pendant grant_beta_access, initialisation nouvelle liste.", file_path)

            if user_id in existing:
                Check._beta_access_cache = set(existing)
                return False

            existing.add(user_id)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = file_path.with_suffix(".tmp")
            sorted_list = sorted(existing)
            temporary.write_text(json.dumps(sorted_list, indent=2) + "\n", encoding="utf-8")
            temporary.replace(file_path)
            Check._beta_access_cache = set(existing)
            return True

    async def has_beta_access(self, bot: discord.Bot, user_id: int) -> bool:
        """Vérifie si l'utilisateur possède l'accès bêta (présent dans beta access.json ou rôle OP)."""
        if int(user_id) in self.load_beta_access():
            return True
        if bot:
            return await self.is_op(bot, user_id)
        return False

    async def check_interaction_access(self, bot: discord.Bot, interaction: discord.Interaction, allow_network: bool = False) -> tuple[bool, str]:
        """
        Vérifie les permissions d'interaction UI (boutons, sélecteurs).
        Ordre de sécurité :
        1. Bannissement (no_permission)
        2. Maintenance globale (seuls maintenance bypass et OP peuvent agir)
        3. Mode Bêta (seuls beta access et OP peuvent agir, sauf si allow_network=True)
        """
        user_id = interaction.user.id
        if self.is_banned(user_id):
            return False, "no_permission"
        if self.maintenance_enabled() and not await self.can_bypass_maintenance(bot, user_id):
            return False, "no_permission"
        if self.beta_enabled() and not allow_network and not await self.has_beta_access(bot, user_id):
            return False, "g_error_beta_access_required"
        return True, ""

    def load_banned(self) -> list[int]:
        """Charge la liste des identifiants bannis depuis le cache mémoire ou le fichier banned.json."""
        if Check._banned_cache is not None:
            return list(Check._banned_cache)
        if not BANNED_FILE.exists():
            Check._banned_cache = []
            return []
        with BANNED_FILE.open(encoding="utf-8") as file:
            users = json.load(file)
        if not isinstance(users, list) or any(type(user) is not int for user in users):
            raise ValueError("banned.json doit contenir une liste d'identifiants entiers.")
        Check._banned_cache = users
        return list(users)

    def is_banned(self, user_id: int) -> bool:
        """Vérifie si un utilisateur est actuellement banni de l'accès au bot."""
        return user_id in self.load_banned()

    def set_banned(self, user_id: int, banned: bool) -> bool:
        """
        Bannit ou débannit un utilisateur.
        Met à jour de façon atomique le fichier data/banned.json et le cache en mémoire.
        Retourne True si l'état a changé, False si l'utilisateur avait déjà cet état.
        """
        users = self.load_banned()
        if (user_id in users) == banned:
            return False
        if banned:
            users.append(user_id)
        else:
            users.remove(user_id)
        BANNED_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = BANNED_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(users, indent=2) + "\n", encoding="utf-8")
        temporary.replace(BANNED_FILE)
        Check._banned_cache = users
        return True

