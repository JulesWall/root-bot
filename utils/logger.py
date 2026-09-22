"""
Système de journalisation Discord vers les salons dédiés (modération, public, alertes).

Ce module achemine les événements du bot vers des salons Discord configurés dans .env :
- new_lang : Alerte lorsqu'un utilisateur utilise une langue non encore prise en charge.
- ban_unban : Traçabilité des sanctions de modération (bannissements et réintégrations).
- public : Événements publics du jeu (victoires, PvP, échanges majeurs).
- moderation_* : Salons spécialisés (claims, dons de réputation, nouveaux profils).
Inclut une déduplication en mémoire (_reported_locales) pour éviter le spam de logs.
"""

import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

import discord

from lang.fr import text

# Mapping entre les clés logicielles et les noms des variables d'environnement
LOG_CHANNELS = {
    "new_lang": "LOG_NEW_LANGUAGE_CHANNEL_ID",
    "ban_unban": "LOG_MODERATION_BAN_CHANNEL_ID",
    "public": "LOG_PUBLIC_CHANNEL_ID",
    "moderation_claim": "LOG_MODERATION_CLAIM_CHANNEL_ID",
    "moderation_reputation": "LOG_MODERATION_REP_CHANNEL_ID",
    "moderation_new_player": "LOG_MODERATION_NEW_PLAYER_CHANNEL_ID",
    "moderation_event_stats": "LOG_MODERATION_EVENT_STATS_CHANNEL_ID",
    "guild_events": "LOG_MODERATION_JOIN_GUILD",
    "blockchain": "LOG_BLOCKCHAIN_CHANNEL_ID",
    "moderation_trade": "LOG_MODERATION_TRADE_CHANNEL_ID",
}

logger = logging.getLogger(__name__)


def _format_user_compact(user: discord.User | discord.Member) -> str:
    """Formate l'utilisateur de manière condensée : @Mention (`Nom` · `ID`)."""
    name = getattr(user, "name", str(user))
    user_id = getattr(user, "id", "Inconnu")
    mention = getattr(user, "mention", f"<@{user_id}>")
    return f"{mention} (`{name}` · `{user_id}`)"


def _format_ts_compact(dt) -> str:
    """Formate une date en horodatage relatif Discord compact (<t:...:R>)."""
    if dt and hasattr(dt, "timestamp"):
        return f"<t:{int(dt.timestamp())}:R>"
    return "Inconnu"


def _get_client_locale(ctx) -> str:
    """Extrait la locale Discord du client de l'auteur si disponible."""
    interaction = getattr(ctx, "interaction", None)
    locale = getattr(interaction, "locale", None) if interaction else getattr(ctx, "locale", None)
    if locale:
        return f"`{locale}`"
    return "N/A (préfixe)"


class Logger:
    """Gestionnaire d'expédition des journaux d'événements vers les salons Discord."""

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def channel_id(log_key: str) -> int | None:
        """Résout l'identifiant du salon Discord depuis les variables d'environnement."""
        variable = LOG_CHANNELS.get(log_key)
        if not variable:
            return None
        try:
            # Repli historique sur LOG_MODERATION_CHANNEL_ID pour les bans, ou LOG_PUBLIC_CHANNEL_ID pour les guildes
            raw = os.getenv(variable)
            if not raw:
                if log_key == 'ban_unban':
                    raw = os.getenv('LOG_MODERATION_CHANNEL_ID')
                elif log_key == 'guild_events':
                    raw = os.getenv('LOG_PUBLIC_CHANNEL_ID')
            value = int(raw or 0)
            return value if value > 0 else None
        except ValueError:
            logger.warning('Identifiant de salon invalide dans %s', variable)
            return None

    async def send_queued(self, channel_id: int, template: str, payload: dict):
        """Envoie un événement en file d'attente formaté avec les textes de jeu en français."""
        from lang.game_fr import text as game_text, labels
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
        values = dict(payload)
        for key in ('status', 'kind'):
            if key in values:
                values[key] = labels.get(values[key], values[key])

        embed = discord.Embed(
            title=game_text['g_log_title'],
            description=game_text['g_' + template].format(**values),
            color=discord.Color.dark_teal(),
            timestamp=discord.utils.utcnow()
        )
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    async def _send_embed(self, log_key: str, embed: discord.Embed):
        """Méthode interne générique d'envoi sécurisé d'un embed de log."""
        channel_id = self.channel_id(log_key)
        if channel_id is None:
            return
        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if not callable(getattr(channel, "send", None)):
                logger.warning("Le salon %s ne permet pas l'envoi de logs", channel_id)
                return
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except (discord.HTTPException, discord.Forbidden, discord.NotFound, OSError):
            logger.exception("Impossible d'envoyer le log %s", log_key)
        except Exception:
            logger.exception("Erreur inattendue lors de l'envoi du log %s", log_key)

    async def _send_log_embed(self, log_key: str, title: str, description: str, color: discord.Color):
        """Méthode interne d'envoi d'un embed texte simple."""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=discord.utils.utcnow()
        )
        await self._send_embed(log_key, embed)

    async def log_new_language(self, user, locale):
        """
        Signale aux administrateurs la détection d'une langue Discord non supportée.
        Déduplication par session pour éviter de spammer si l'utilisateur enchaîne les commandes.
        """
        user_id = getattr(user, "id", "inconnu")
        user_mention = getattr(user, "mention", str(user))

        loc_key = (str(user_id), str(locale).lower())
        reported = getattr(self.bot, "_reported_locales", None)
        if reported is None:
            reported = set()
            self.bot._reported_locales = reported
        if loc_key in reported:
            return
        reported.add(loc_key)

        logger.info("Nouvelle langue détectée : %s pour l'utilisateur %s (%s)", locale, user, user_id)
        await self._send_log_embed(
            "new_lang", text["log_language_title"],
            text["log_language_description"].format(user=user_mention, user_id=user_id, locale=locale),
            discord.Color.orange(),
        )

    async def log_ban_unban(self, user: discord.User, action: str, admin: discord.User):
        """Enregistre un bannissement ou débannissement avec mention de l'administrateur responsable."""
        await self._send_log_embed(
            "ban_unban", text[f"log_{action}_title"],
            text["log_moderation_description"].format(
                user=user.mention, user_id=user.id, admin=admin.mention,
            ),
            discord.Color.red() if action == "ban" else discord.Color.green(),
        )

    async def log_new_player(self, ctx, result: dict):
        """Consigne la création d'un profil joueur via /network en format compact."""
        author = getattr(ctx, "author", None) or getattr(ctx, "user", None)
        if not author:
            return

        guild = getattr(ctx, "guild", None)
        lines = [
            f"**Joueur :** {_format_user_compact(author)}",
            f"**Compte :** {_format_ts_compact(getattr(author, 'created_at', None))} · **Langue :** {_get_client_locale(ctx)}",
        ]
        if guild:
            owner_id = getattr(guild, "owner_id", None)
            owner_str = f"<@{owner_id}>" if owner_id else "Inconnu"
            lines.append(f"**Serveur :** {guild.name} (`{guild.id}`) · **Owner :** {owner_str}")
            lines.append(f"**Membres :** `{getattr(guild, 'member_count', '?')}` · **Créé :** {_format_ts_compact(getattr(guild, 'created_at', None))}")

        embed = discord.Embed(
            title="👤 Nouveau profil créé",
            description="\n".join(lines),
            color=discord.Color.from_rgb(0, 220, 200),
            timestamp=discord.utils.utcnow(),
        )
        await self._send_embed("moderation_new_player", embed)

    async def log_reputation(self, ctx, giver: discord.User, recipient: discord.User, points: int = 1):
        """Consigne le don de réputation via /rep en format compact avec métadonnées serveur."""
        guild = getattr(ctx, "guild", None)
        lines = [
            f"**Donneur :** {_format_user_compact(giver)} ({_get_client_locale(ctx)})",
            f"**Bénéficiaire :** {_format_user_compact(recipient)}",
            f"**Points :** `+{points}`",
        ]
        if guild:
            owner_id = getattr(guild, "owner_id", None)
            owner_str = f"<@{owner_id}> (`{owner_id}`)" if owner_id else "Inconnu"
            lines.append(f"**Serveur :** {guild.name} (`{guild.id}`) · **Owner :** {owner_str}")
            lines.append(f"**Membres :** `{getattr(guild, 'member_count', '?')}` · **Créé :** {_format_ts_compact(getattr(guild, 'created_at', None))}")

        embed = discord.Embed(
            title="⭐ Don de réputation",
            description="\n".join(lines),
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow(),
        )
        await self._send_embed("moderation_reputation", embed)

    async def log_claim(self, ctx, amount, new_rootium=None, rate=None, ram_total=None, seconds_since_last_claim=None):
        """Consigne une récolte de minage (/claim) dans le salon de modération dédié.

        Trace le joueur, le Rootium extrait de la mémoire vive, le nouveau solde, le débit de
        minage, la capacité mémoire et le temps écoulé depuis la dernière récolte, avec les
        métadonnées du serveur d'origine.
        """
        from utils.text import format_rtm
        from utils.time_format import format_duration

        author = getattr(ctx, "author", None) or getattr(ctx, "user", None)
        if not author:
            return

        guild = getattr(ctx, "guild", None)
        lines = [
            f"**Joueur :** {_format_user_compact(author)} ({_get_client_locale(ctx)})",
            f"**Rootium réclamé :** ◈ `{format_rtm(amount)} RTM`",
        ]
        if new_rootium is not None:
            lines.append(f"**Nouveau solde :** ◈ `{format_rtm(new_rootium)} RTM`")
        if rate is not None:
            lines.append(f"**Débit de minage :** `{format_rtm(rate)} RTM/min`")
        if seconds_since_last_claim is not None:
            lines.append(f"**Temps depuis le dernier claim :** `{format_duration(seconds_since_last_claim)}`")
        if ram_total:
            lines.append(f"**Mémoire vive :** `{ram_total}`")
        if guild:
            owner_id = getattr(guild, "owner_id", None)
            owner_str = f"<@{owner_id}> (`{owner_id}`)" if owner_id else "Inconnu"
            lines.append(f"**Serveur :** {guild.name} (`{guild.id}`) · **Owner :** {owner_str}")
            lines.append(f"**Membres :** `{getattr(guild, 'member_count', '?')}` · **Créé :** {_format_ts_compact(getattr(guild, 'created_at', None))}")

        embed = discord.Embed(
            title="🪙 Récolte de minage",
            description="\n".join(lines),
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=discord.utils.utcnow(),
        )
        await self._send_embed("moderation_claim", embed)

    async def log_guild_join(self, guild: discord.Guild, total_guilds: int):
        """Consigne l'arrivée du bot sur un serveur en format compact."""
        owner_id = getattr(guild, "owner_id", None)
        owner_str = f"<@{owner_id}> (`{owner_id}`)" if owner_id else "Inconnu"
        lines = [
            f"**Serveur :** {guild.name} (`{guild.id}`)",
            f"**Owner :** {owner_str} · **Membres :** `{getattr(guild, 'member_count', '?')}`",
            f"**Créé :** {_format_ts_compact(getattr(guild, 'created_at', None))} · **Total serveurs :** `{total_guilds}`",
        ]

        embed = discord.Embed(
            title="📥 Serveur rejoint",
            description="\n".join(lines),
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        await self._send_embed("guild_events", embed)

    async def log_guild_remove(self, guild: discord.Guild, total_guilds: int):
        """Consigne le départ du bot d'un serveur en format compact."""
        owner_id = getattr(guild, "owner_id", None)
        owner_str = f"<@{owner_id}> (`{owner_id}`)" if owner_id else "Inconnu"
        lines = [
            f"**Serveur :** {guild.name} (`{guild.id}`)",
            f"**Owner :** {owner_str} · **Membres :** `{getattr(guild, 'member_count', '?')}`",
            f"**Créé :** {_format_ts_compact(getattr(guild, 'created_at', None))} · **Total restant :** `{total_guilds}`",
        ]

        embed = discord.Embed(
            title="📤 Serveur quitté",
            description="\n".join(lines),
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        await self._send_embed("guild_events", embed)

    async def log_challenge_won(
        self,
        ctx,
        winner: discord.User,
        title: str,
        color: discord.Color,
        details: list[str],
        server_name: str = "Serveur inconnu",
    ):
        """Consigne la résolution réussie d'un mini-jeu dans le salon de logs publics."""
        guild = getattr(ctx, "guild", None)
        guild_str = f"{guild.name} (`{guild.id}`)" if guild else server_name

        lines = [f"**Joueur :** {_format_user_compact(winner)}"]
        lines.extend(details)
        lines.append(f"**Serveur :** {guild_str}")

        embed = discord.Embed(
            title=title,
            description="\n".join(lines),
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        await self._send_embed("public", embed)

    async def log_hash_won(self, ctx, winner: discord.User, target: int, players_count: int, server_name: str):
        """Consigne la résolution réussie d'un Hash Challenge dans le salon de logs publics."""
        details = [f"**Hash décodé :** `{target}`", f"**Joueurs en compétition :** `{players_count}`"]
        await self.log_challenge_won(ctx, winner, "🧩 Hash Challenge résolu !", discord.Color.from_rgb(0, 200, 255), details, server_name)

    async def log_pin_won(self, ctx, winner: discord.User, target: int, players_count: int, server_name: str):
        """Consigne la résolution réussie d'un Code PIN dans le salon de logs publics."""
        details = [f"**Code PIN validé :** `{target}`", f"**Joueurs en compétition :** `{players_count}`"]
        await self.log_challenge_won(ctx, winner, "🔐 Code PIN déchiffré !", discord.Color.gold(), details, server_name)

    async def log_decode_won(self, ctx, winner: discord.User, sequence: str, target: str, server_name: str):
        """Consigne la résolution réussie d'un Décryptage dans le salon de logs publics."""
        details = [f"**Séquence :** `{sequence}`", f"**Code validé :** `{target}`"]
        await self.log_challenge_won(ctx, winner, "🔍 Décryptage résolu !", discord.Color.from_rgb(155, 89, 182), details, server_name)

    async def log_anomaly_won(self, ctx, winner: discord.User, line: int, digit: str, server_name: str):
        """Consigne la neutralisation réussie d'une Anomalie dans le salon de logs publics."""
        details = [f"**Ligne de l'anomalie :** `Ligne {line}`", f"**Chiffre parasite :** `{digit}`"]
        await self.log_challenge_won(ctx, winner, "⚠️ Anomalie neutralisée !", discord.Color.from_rgb(231, 76, 60), details, server_name)

    async def log_buffer_won(self, ctx, winner: discord.User, target: str, server_name: str):
        """Consigne la réorganisation réussie d'un Buffer dans le salon de logs publics."""
        details = [f"**Code reconstitué :** `{target}`"]
        await self.log_challenge_won(ctx, winner, "📦 Buffer réaligné !", discord.Color.from_rgb(41, 128, 185), details, server_name)

    async def log_signal_won(self, ctx, winner: discord.User, winning_letter: str, server_name: str):
        """Consigne l'interception réussie d'un Signal dans le salon de logs publics."""
        details = [f"**Fréquence dominante :** `{winning_letter}`"]
        await self.log_challenge_won(ctx, winner, "📡 Signal intercepté !", discord.Color.from_rgb(26, 188, 156), details, server_name)

    async def log_packet_won(self, ctx, winner: discord.User, missing_packet: int, server_name: str):
        """Consigne l'identification réussie du paquet manquant dans le salon de logs publics."""
        details = [f"**Paquet manquant :** `Paquet #{missing_packet}`"]
        await self.log_challenge_won(ctx, winner, "🛰️ Paquet manquant identifié !", discord.Color.from_rgb(230, 126, 34), details, server_name)

    async def log_daily_event_report(self, summary: list[dict]):
        """
        Envoie le rapport quotidien de modération des événements (24h) dans le salon dédié.
        Conformément aux consignes :
        - Affiche jusqu'à 50 joueurs.
        - Découpe en plusieurs messages si la longueur du texte le nécessite.
        - Propage toute exception en cas d'échec pour empêcher la réinitialisation des compteurs.
        """
        channel_id = self.channel_id("moderation_event_stats")
        if channel_id is None:
            logger.warning("LOG_MODERATION_EVENT_STATS_CHANNEL_ID non configuré : aucun rapport de modération 24h envoyé.")
            raise RuntimeError("LOG_MODERATION_EVENT_STATS_CHANNEL_ID non configuré.")

        channel = self.bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception as e:
                raise RuntimeError(f"Impossible de récupérer le salon {channel_id}: {e}") from e

        if not channel or not callable(getattr(channel, "send", None)):
            raise RuntimeError(f"Salon invalide ou inaccessible pour le rapport quotidien ({channel_id}).")

        header = "📊 **Bilan d'activité des mini-jeux sur les dernières 24 heures**\n\n"
        players = summary[:50] if summary else []

        if not players:
            embed = discord.Embed(
                title="🏆 Rapport Quotidien des Événements (24h)",
                description=header + "*Aucune activité d'événement enregistrée sur cette période.*",
                color=discord.Color.dark_teal(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text="Root OS • Événements 24h")
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            return

        player_blocks = []
        for idx, row in enumerate(players, 1):
            user_id = row["discord_id"]
            won = int(row.get("events_won", 0))
            part = int(row.get("events_participated", 0))

            user = self.bot.get_user(user_id)
            if not user:
                try:
                    user = await self.bot.fetch_user(user_id)
                except Exception:
                    user = None

            user_str = _format_user_compact(user) if user else f"<@{user_id}> (`{user_id}`)"
            block = (
                f"**{idx}.** {user_str}\n"
                f"   └ 🏆 Victoires : `{won}` · 🎯 Participations : `{part}`"
            )
            player_blocks.append(block)

        # Découpage dynamique selon la longueur réelle du contenu (seuil de sécurité à 3500 car. par embed)
        max_desc_len = 3500
        pages = []
        current_page_blocks = []
        current_len = len(header)

        for block in player_blocks:
            block_len = len(block) + 1  # +1 pour le saut de ligne
            if current_page_blocks and (current_len + block_len > max_desc_len):
                pages.append(current_page_blocks)
                current_page_blocks = [block]
                current_len = len(header) + block_len
            else:
                current_page_blocks.append(block)
                current_len += block_len

        if current_page_blocks:
            pages.append(current_page_blocks)

        total_pages = len(pages)
        for page_idx, page_blocks in enumerate(pages, 1):
            embed = discord.Embed(
                title="🏆 Rapport Quotidien des Événements (24h)",
                description=header + "\n".join(page_blocks),
                color=discord.Color.dark_teal(),
                timestamp=discord.utils.utcnow(),
            )
            if total_pages > 1:
                embed.set_footer(text=f"Root OS • Événements 24h • Page {page_idx}/{total_pages}")
            else:
                embed.set_footer(text="Root OS • Événements 24h")

            # Si l'envoi échoue, l'exception est levée et non absorbée
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    async def log_blockchain_ready(self):
        """Envoie le message d'initialisation lore-friendly dans le salon #blockchain à chaque démarrage."""
        channel_id = self.channel_id("blockchain")
        if channel_id is None:
            return
        content = (
            "Connexion au réseau Rootium…\n"
            "Connecté.\n"
            "Transactions Rootium en direct :"
        )
        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if callable(getattr(channel, "send", None)):
                await channel.send(content, allowed_mentions=discord.AllowedMentions.none())
        except Exception:
            logger.exception("Impossible d'envoyer le statut de connexion blockchain")

    async def log_blockchain_transaction(
        self,
        from_id: int | str,
        to_address: str,
        rtm_amount: float | Decimal | str,
        dt: datetime | None = None,
        tx_type: str | None = None,
        usd_amount: float | Decimal | str | None = None,
    ):
        """Envoie un log de transaction RTM formaté dans le salon #blockchain.

        tx_type / usd_amount sont optionnels (ex. vente DEX : TYPE SELL TOKEN + USD).
        """
        channel_id = self.channel_id("blockchain")
        if channel_id is None:
            return

        now = dt or datetime.now(timezone.utc)
        time_str = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        rtm_val = Decimal(str(rtm_amount or 0))
        rtm_str = f"{rtm_val:,.5f}"

        extra_lines = []
        if tx_type:
            extra_lines.append(f"TYPE   {tx_type}")
        extra_lines.append(f"RTM    {rtm_str}")
        if usd_amount is not None:
            from utils.text import format_usd
            extra_lines.append(f"USD    {format_usd(usd_amount)}")

        separator = "═" * 68
        block_content = (
            f"```text\n"
            f"{separator}\n"
            f"⏱  {time_str}\n"
            f"FROM   {from_id}\n"
            f"TO     {to_address}\n"
            + "".join(f"{line}\n" for line in extra_lines) +
            f"{separator}\n"
            f"```"
        )
        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if callable(getattr(channel, "send", None)):
                await channel.send(block_content, allowed_mentions=discord.AllowedMentions.none())
        except Exception:
            logger.exception("Impossible d'envoyer le log blockchain pour la transaction")

    async def log_trade(
        self,
        initiator: discord.User | discord.Member,
        target: discord.User | discord.Member,
        send_usd: Decimal | float,
        send_rtm: Decimal | float,
        rec_usd: Decimal | float,
        rec_rtm: Decimal | float,
        guild: discord.Guild | None = None,
    ):
        """Consigne un échange de ressources validé dans le salon de modération dédié avec métadonnées serveur."""
        lines = [
            f"**Envoyeur :** {_format_user_compact(initiator)}",
            f"**Récepteur :** {_format_user_compact(target)}",
        ]
        if guild:
            owner_id = getattr(guild, "owner_id", None)
            owner_str = f"<@{owner_id}> (`{owner_id}`)" if owner_id else "Inconnu"
            lines.append(f"**Serveur :** {guild.name} (`{guild.id}`) · **Owner :** {owner_str}")
            lines.append(f"**Membres :** `{getattr(guild, 'member_count', '?')}` · **Créé :** {_format_ts_compact(getattr(guild, 'created_at', None))}")

        lines.append("")
        s_usd = Decimal(str(send_usd or 0))
        s_rtm = Decimal(str(send_rtm or 0))
        r_usd = Decimal(str(rec_usd or 0))
        r_rtm = Decimal(str(rec_rtm or 0))

        init_sends = []
        if s_usd > 0:
            init_sends.append(f"💵 `{s_usd:,.2f} USD`")
        if s_rtm > 0:
            init_sends.append(f"◈ `{s_rtm:,.5f} RTM`")

        target_sends = []
        if r_usd > 0:
            target_sends.append(f"💵 `{r_usd:,.2f} USD`")
        if r_rtm > 0:
            target_sends.append(f"◈ `{r_rtm:,.5f} RTM`")

        lines.append(f"📤 **Transfert Envoyeur ➔ Récepteur :**\n> {', '.join(init_sends) if init_sends else '*Aucune ressource*'}")
        lines.append(f"📥 **Transfert Récepteur ➔ Envoyeur :**\n> {', '.join(target_sends) if target_sends else '*Aucune ressource*'}")

        embed = discord.Embed(
            title="🤝 Échange de ressources validé",
            description="\n".join(lines),
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=discord.utils.utcnow(),
        )
        await self._send_embed("moderation_trade", embed)

    async def log_scan_exposed(self, scanner_id: int | str, target_name: str, secret_id: str):
        """Consigne l'exposition publique du Secret ID d'un joueur suite à un scan réussi."""
        embed = discord.Embed(
            title="🔓 FUITE DE DONNÉES",
            description=f"**Intrusion confirmée** · <@{scanner_id}> a exposé le réseau de **{target_name}** !\n🔑 **Secret ID :** `{secret_id}`",
            color=discord.Color.from_rgb(220, 50, 50),
            timestamp=discord.utils.utcnow(),
        )
        await self._send_embed("public", embed)

    async def log_pvp_attack(self, attacker: discord.User | discord.Member | int | str, attack_points: int, attacker_name: str | None = None):
        """Consigne une attaque PvP dans le salon de logs publics avec le nom de l'attaquant et les points d'attaque engagés."""
        if isinstance(attacker, (discord.User, discord.Member)):
            attacker_str = _format_user_compact(attacker)
        elif attacker_name:
            attacker_str = f"<@{attacker}> (`{attacker_name}` · `{attacker}`)"
        else:
            attacker_str = f"<@{attacker}> (`{attacker}`)"

        embed = discord.Embed(
            title="⚔️ ATTAQUE RÉSEAU DÉTECTÉE",
            description=f"Une cyberattaque d'une puissance de **{int(attack_points):,} ATK** a été lancée par {attacker_str}.",
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=discord.utils.utcnow(),
        )
        await self._send_embed("public", embed)
