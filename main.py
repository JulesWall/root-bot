"""
Point d'entrée principal et orchestration du bot Root.

Ce fichier est le point de départ de l'application :
1. Initialisation de l'instance discord.ext.commands.Bot avec intents et statut dynamique.
2. Résolution dynamique du préfixe par serveur (guild_prefixes via MySQL).
3. Sas de sécurité global (global_check) vérifiant l'exclusion des MP, les bans, la maintenance, et l'inscription joueur.
4. Gestion universelle et centralisée des exceptions Discord et métier (GameError).
5. Chargement dynamique de toutes les extensions (Cogs) dans commands/.
"""

import asyncio
import logging

import discord
from discord.ext import commands

import data
from game.game_error import GameError
from game.root_service import RootService
from utils.logger import Logger
from utils.check import Check
from utils.prefix_manager import get_prefix_async
from utils.language_manager import fetch_user_language
from utils.presence_manager import get_presence_activity, update_bot_presence, start_presence_loop
from utils import text

logger = logging.getLogger(__name__)


async def get_prefix_for_bot(bot: commands.Bot, message: discord.Message):
    """
    Résout dynamiquement le préfixe pour chaque message textuel reçu.
    
    - Si le message provient d'un serveur (guild), lit le préfixe configuré en base via PrefixDB.
    - Repli automatique sur data.DEFAULT_PREFIX ('+r') en cas d'absence de configuration.
    - Permet également de mentionner le bot comme préfixe (@Bot commande).
    """
    prefix = await get_prefix_async(message.guild.id) if message.guild else data.DEFAULT_PREFIX
    return commands.when_mentioned_or(prefix)(bot, message)


def create_bot() -> commands.Bot:
    """
    Fabrique et configure l'instance complète du bot Root.
    
    Instancie les services transversaux (service de jeu, logger Discord),
    attache les vérifications globales et écouteurs d'événements, puis charge tous les Cogs.
    """
    checks = Check()
    
    # Configuration des intents Discord : Message Content et Server Members
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    
    bot = commands.Bot(
        command_prefix=get_prefix_for_bot,
        intents=intents,
        help_command=None,  # Désactivation de l'aide par défaut de discord.py
        activity=get_presence_activity(),
        # Statut Ne pas déranger (dnd) si le mode maintenance est actif, En ligne (online) sinon
        status=discord.Status.dnd if checks.maintenance_enabled() else discord.Status.online,
    )
    
    # Injection des dépendances centrales attachées à l'instance du bot
    bot.start_time = discord.utils.utcnow()
    bot.root_service = RootService()
    discord_logger = Logger(bot)
    bot.discord_logger = discord_logger

    @bot.check
    async def global_check(ctx):
        """
        Vérification globale exécutée avant chaque commande (Slash ou préfixe).
        
        Ordre des contrôles de sécurité :
        1. RÈGLE STRICTE MP : Interdiction absolue des commandes en MP. Le bot ne répond jamais en privé.
        2. Accusé de réception (defer) immédiat pour les Slash Commands pour éviter le timeout de 3s.
        3. Contrôle des utilisateurs bannis (sauf commandes admin pour permettre l'unban).
        4. Contrôle de maintenance globale (seul le rôle MAINTENANCE_BYPASS_ROLE_ID peut agir).
        5. Contrôle joueur : toute commande de jeu (commands.game.*) exige un profil créé via /network.
        6. Traçabilité des langues non supportées vers le salon de logs Discord.
        """
        # 1. AUCUNE COMMANDE EN MP : Le bot ne s'exécute JAMAIS en message privé
        if ctx.guild is None:
            return False

        command_module = getattr(ctx.command, "module", "") or ""
        is_admin_command = command_module.startswith("commands.admin.")
        is_game_command = command_module.startswith("commands.game.")
        is_network_command = is_game_command and getattr(ctx.command, "name", "") in ("network", "n")

        # 2. Vérification des bannissements locaux (data/banned.json)
        if not is_admin_command and checks.is_banned(ctx.author.id):
            return False

        # 3. Contrôle de maintenance globale : silence complet si non autorisé
        if checks.maintenance_enabled() and not await checks.can_bypass_maintenance(bot, ctx.author.id):
            return False

        # 4. Accuser réception (defer) immédiatement avant tout appel distant (BDD / rôles Discord)
        interaction = getattr(ctx, "interaction", None)
        if interaction and not interaction.response.is_done():
            await ctx.defer()

        # Préchargement de la préférence de langue du joueur vers le cache mémoire
        user = getattr(ctx, "author", None) or getattr(ctx, "user", None)
        user_id = getattr(user, "id", None)
        if user_id:
            try:
                await fetch_user_language(user_id)
            except Exception:
                pass

        # 5. Vérification du mode Bêta
        # Seuls les joueurs autorisés (beta access.json ou rôle OP) peuvent jouer.
        # Exception : /network (ou !n) reste accessible pour créer son profil et recevoir de la réputation.
        if checks.beta_enabled() and not is_admin_command:
            has_access = await checks.has_beta_access(bot, ctx.author.id)
            if not has_access and not is_network_command:
                raise GameError('beta_access_required')

        # 6. Vérification du compte joueur (seul /network permet d'initialiser sans être inscrit)
        if is_game_command and not is_network_command and not await checks.is_player(ctx.author.id):
            raise GameError('no_network')

        # 6. Détection et log des nouvelles langues Discord non supportées
        if interaction and getattr(interaction, "locale", None) and str(interaction.locale)[:2].lower() not in data.SUPPORTED_LANGS:
            await discord_logger.log_new_language(ctx.author, interaction.locale)

        return True

    @bot.event
    async def on_message(message: discord.Message):
        """
        Écouteur de messages textuels.
        Ignore systématiquement les bots et TOUT message reçu en MP (politique zéro MP).
        """
        if message.author.bot or message.guild is None:
            return
        await bot.process_commands(message)

    @bot.event
    async def on_message_edit(before: discord.Message, after: discord.Message):
        """
        Permet de re-déclencher une commande si l'utilisateur modifie son message avec préfixe.
        Ignore les MP et les messages de bots.
        """
        if after.author.bot or after.guild is None:
            return
        if before.content != after.content:
            await bot.process_commands(after)

    @bot.event
    async def on_ready():
        """
        Déclenché lorsque le bot est connecté à Discord et le cache synchronisé.
        Régule le statut de présence.
        """
        await update_bot_presence(bot)
        start_presence_loop(bot)
        logger.info("%s connecte : %s (maintenance=%s)", data.BOT_NAME, bot.user, checks.maintenance_enabled())
        await discord_logger.log_blockchain_ready()
        # Initialisation du suivi économique (no-op si ECONOMY_REPORTS_ENABLED=false)
        try:
            await bot.root_service.init_economy()
        except Exception:
            logger.exception("[EconomyStats] Échec de l'initialisation du suivi économique. Vérifier la migration SQL.")


    @bot.event
    async def on_guild_join(guild: discord.Guild):
        """Déclenché lorsque le bot rejoint un nouveau serveur Discord."""
        logger.info("Nouveau serveur rejoint : %s (ID: %s) | Total: %d", guild.name, guild.id, len(bot.guilds))
        await discord_logger.log_guild_join(guild, len(bot.guilds))

    @bot.event
    async def on_guild_remove(guild: discord.Guild):
        """Déclenché lorsque le bot est retiré d'un serveur Discord."""
        logger.info("Serveur quitté : %s (ID: %s) | Total: %d", guild.name, guild.id, len(bot.guilds))
        await discord_logger.log_guild_remove(guild, len(bot.guilds))

    async def report_command_error(ctx, error):
        """
        Gestionnaire universel des erreurs pour les commandes texte et slash.
        
        Traduit les exceptions en messages utilisateur localisés (FR/EN) :
        - GameError -> messages métier conviviaux (fonds insuffisants, pare-feu requis...).
        - CheckFailure -> accès refusé.
        - UserInputError -> syntaxe incorrecte.
        - Autres -> log d'anomalie système.
        Règle stricte : Ne jamais répondre en message privé (silence total si ctx.guild is None).
        """
        # Le bot ne doit JAMAIS répondre en MP
        if ctx.guild is None:
            return

        if isinstance(error, commands.CommandNotFound):
            return

        original = getattr(error, "original", error)
        if isinstance(original, GameError):
            if original.key == "database_unconfigured":
                logger.warning("Erreur base de donnees non configuree : aucun message envoye sur Discord.")
                return
            key = 'g_error_' + original.key
        elif isinstance(original, (commands.CheckFailure, discord.CheckFailure)):
            # En mode maintenance : silence total, aucun message envoyé sur Discord
            if checks.maintenance_enabled():
                return
            key = "no_permission"
        elif isinstance(original, commands.UserInputError):
            key = "command_invalid_input"
        else:
            key = "command_error"
            logger.error(
                "Erreur dans la commande %s", ctx.command,
                exc_info=(type(original), original, original.__traceback__),
            )

        try:
            user = getattr(ctx, "author", None) or getattr(ctx, "user", None)
            user_id = getattr(user, "id", None)
            if user_id:
                try:
                    await fetch_user_language(user_id)
                except Exception:
                    pass
            values = original.values if isinstance(original, GameError) else {}
            # Répondre soit via interaction Discord (slash), soit par message ordinaire (préfixe)
            if getattr(ctx, "interaction", None):
                await ctx.respond(text.get(ctx, key, **values))
            else:
                await ctx.send(text.get(ctx, key, **values))
        except Exception:
            logger.exception("Impossible d'envoyer la reponse d'erreur")

    @bot.event
    async def on_command_error(ctx, error):
        """Redirige les erreurs des commandes textuelles vers le handler centralisé."""
        await report_command_error(ctx, error)

    @bot.event
    async def on_application_command_error(ctx, error):
        """Redirige les erreurs des commandes Slash vers le handler centralisé."""
        await report_command_error(ctx, error)

    # Découverte et chargement dynamique de tous les modules Cogs dans commands/
    for path in sorted((data.BASE_DIR / "commands").rglob("*.py")):
        if path.name == "__init__.py":
            continue
        module = ".".join(path.relative_to(data.BASE_DIR).with_suffix("").parts)
        bot.load_extension(module)
        logger.info("Extension chargee : %s", module)

    return bot


async def main():
    """Point d'entrée asynchrone principal démarrant la boucle du bot."""
    if not data.TOKEN:
        raise SystemExit("Token introuvable : configurer DISCORD_TOKEN dans .env.")
    bot = create_bot()
    try:
        await bot.start(data.TOKEN)
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
