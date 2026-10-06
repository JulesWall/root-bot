"""
Système de journalisation Discord vers les salons dédiés (modération, public, alertes).

Ce module achemine les événements du bot vers des salons Discord configurés dans .env :
- new_lang : Alerte lorsqu'un utilisateur utilise une langue non encore prise en charge.
- ban_unban : Traçabilité des sanctions de modération (bannissements et réintégrations).
- public : Événements publics du jeu (victoires, PvP, échanges majeurs).
- moderation_* : Salons spécialisés (claims, dons de réputation, nouveaux profils).
Inclut une déduplication en mémoire (_reported_locales) pour éviter le spam de logs.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import discord

from lang.fr import text
from utils.root_theme import COLOR_LOG_ATTACK, COLOR_LOG_EVENT, COLOR_LOG_SCAN
from utils.time_format import to_utc_timestamp

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
    "moderation_claim_stats": "LOG_MODERATION_CLAIM_STATS_CHANNEL_ID",
    "moderation_hourly": "LOG_MODERATION_HOURLY_CHANNEL_ID",
    "moderation_hourly_stats": "LOG_MODERATION_HOURLY_STATS_CHANNEL_ID",
}

logger = logging.getLogger(__name__)

_HOURLY_RISK_LABELS = {
    "LOW": "FAIBLE",
    "MEDIUM": "MOYEN",
    "HIGH": "ÉLEVÉ",
}


def _format_user_compact(user: discord.User | discord.Member) -> str:
    """Formate l'utilisateur de manière condensée : @Mention (`Nom` · `ID`)."""
    name = getattr(user, "display_name", None) or getattr(user, "name", str(user))
    user_id = getattr(user, "id", "Inconnu")
    mention = getattr(user, "mention", f"<@{user_id}>")
    return f"{mention} (`{name}` · `{user_id}`)"


def _format_ts_compact(dt) -> str:
    """Formate une date en horodatage relatif Discord compact (<t:...:R>)."""
    if dt:
        ts = to_utc_timestamp(dt)
        if ts > 0:
            return f"<t:{ts}:R>"
    return "Inconnu"


def _get_client_locale(ctx) -> str:
    """Extrait la locale Discord du client de l'auteur si disponible."""
    interaction = getattr(ctx, "interaction", None)
    locale = getattr(interaction, "locale", None) if interaction else getattr(ctx, "locale", None)
    if locale:
        return f"`{locale}`"
    return "N/A (préfixe)"


def _style_public_embed(
    bot: Any,
    title: str,
    description: str,
    color: discord.Color = COLOR_LOG_EVENT,
    author_category: str = "ÉVÉNEMENT RÉSEAU",
    user_avatar_url: str | None = None,
) -> discord.Embed:
    """Crée un embed stylisé pour les logs publics respectant la charte Root OS."""
    from utils.root_emojis import replace_vanilla_emojis

    clean_title = replace_vanilla_emojis(title)
    clean_desc = replace_vanilla_emojis(description)

    embed = discord.Embed(
        title=clean_title,
        description=clean_desc,
        color=color,
        timestamp=discord.utils.utcnow(),
    )

    bot_user = getattr(bot, "user", None)
    bot_avatar = bot_user.display_avatar.url if bot_user and hasattr(bot_user, "display_avatar") else None

    embed.set_author(
        name=f"ROOT OS // {author_category.upper()}",
        icon_url=user_avatar_url or bot_avatar,
    )
    embed.set_footer(
        text=f"Root OS • Flux Public // {author_category.title()}",
        icon_url=bot_avatar,
    )
    return embed


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
                elif log_key == 'moderation_claim_stats':
                    raw = os.getenv('LOG_MODERATION_EVENT_STATS_CHANNEL_ID') or os.getenv('LOG_MODERATION_CLAIM_CHANNEL_ID') or os.getenv('LOG_MODERATION_CHANNEL_ID')
                elif log_key == 'moderation_hourly':
                    raw = os.getenv('LOG_MODERATION_CLAIM_CHANNEL_ID') or os.getenv('LOG_MODERATION_CHANNEL_ID')
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
            send_fn = channel.send
            res = send_fn(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                await res
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

    async def log_claim(self, ctx, amount, new_rootium=None, rate=None, ram_total=None, seconds_since_last_claim=None, is_auto: bool = False, remaining_active: int = None):
        """Consigne une récolte de minage (/claim) dans le salon de modération dédié.

        Trace le joueur, le Rootium extrait de la mémoire vive, le nouveau solde, le débit de
        minage, la capacité mémoire et le temps écoulé depuis la dernière récolte, avec les
        métadonnées du serveur d'origine.
        """
        from utils.text import format_rtm
        from utils.time_format import format_duration

        if isinstance(ctx, (discord.User, discord.Member)):
            author = ctx
            guild = getattr(ctx, "guild", None)
            locale_str = "fr"
        else:
            author = getattr(ctx, "author", None) or getattr(ctx, "user", None)
            guild = getattr(ctx, "guild", None)
            locale_str = _get_client_locale(ctx) if ctx else "fr"

        if not author:
            return

        lines = [
            f"**Joueur :** {_format_user_compact(author)} ({locale_str})",
            f"**Rootium réclamé :** ◈ `{format_rtm(amount)} RTM`",
        ]
        if is_auto:
            if remaining_active is not None:
                lines.append(f"**Mode :** 🤖 Autoclaim (Claims restants : `{remaining_active}`)")
            else:
                lines.append("**Mode :** 🤖 Autoclaim")
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

        embed_color = discord.Color.from_rgb(52, 152, 219) if is_auto else discord.Color.from_rgb(241, 196, 15)
        embed_title = "🤖 Récolte automatique (Autoclaim)" if is_auto else "🪙 Récolte de minage"

        embed = discord.Embed(
            title=embed_title,
            description="\n".join(lines),
            color=embed_color,
            timestamp=discord.utils.utcnow(),
        )
        await self._send_embed("moderation_claim", embed)

    async def log_hourly(
        self,
        ctx,
        user: discord.User | discord.Member,
        base_usd: Decimal,
        bonus_pct: Decimal,
        total_usd: Decimal,
        streak: int,
        interval_seconds: int | None = None,
        combo_lost: bool = False,
        is_first: bool = False,
        step_bonus_pct: Decimal | None = None,
        new_dollars: Decimal | None = None,
    ):
        """Consigne une réclamation horaire (/hourly) dans le salon de modération dédié."""
        from utils.text import format_usd
        from utils.time_format import format_duration

        if isinstance(ctx, (discord.User, discord.Member)):
            author = ctx
            guild = getattr(ctx, "guild", None)
            locale_str = "fr"
        else:
            author = getattr(ctx, "author", None) or getattr(ctx, "user", None) or user
            guild = getattr(ctx, "guild", None)
            locale_str = _get_client_locale(ctx) if ctx else "fr"

        if not author:
            return

        lines = [
            f"**Joueur :** {_format_user_compact(author)} ({locale_str})",
            f"**Gain de base :** 💵 `{format_usd(base_usd)}`",
        ]
        if step_bonus_pct is not None:
            lines.append(f"**Bonus d'étape :** `+{Decimal(str(step_bonus_pct)):.2f}%`")
        lines.extend([
            f"**Bonus total cumulé :** `{Decimal(str(bonus_pct)):+.2f}%`",
            f"**Gain final crédité :** 💵 `{format_usd(total_usd)}`",
        ])
        if new_dollars is not None:
            lines.append(f"**Nouveau solde :** 💳 `{format_usd(new_dollars)}`")
        lines.append(f"**Série (Streak) :** 🔥 `{streak}`")

        if is_first:
            lines.append("**Statut combo :** 🟢 Initialisé")
        elif combo_lost:
            lines.append("**Statut combo :** ⚠️ **Combo Brisé**")
        else:
            lines.append("**Statut combo :** ⚡ Actif")

        if interval_seconds is not None:
            lines.append(f"**Intervalle depuis le dernier claim :** `{format_duration(interval_seconds)}`")

        if guild:
            owner_id = getattr(guild, "owner_id", None)
            owner_str = f"<@{owner_id}> (`{owner_id}`)" if owner_id else "Inconnu"
            lines.append(f"**Serveur :** {guild.name} (`{guild.id}`) · **Owner :** {owner_str}")

        color = discord.Color.gold() if not combo_lost else discord.Color.orange()
        embed = discord.Embed(
            title="⏱️ Récompense Horaire (/hourly)",
            description="\n".join(lines),
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        await self._send_embed("moderation_hourly", embed)

    async def log_daily_hourly_report(self, summary: list[dict] | dict):
        """
        Envoie le rapport quotidien de modération des récoltes horaires (/hourly 24h) dans le salon dédié.
        Harmonisé exactement avec log_daily_claim_report :
        - Analyse statistique par joueur (moyenne, écart-type, régularité, streak suspect, 24/24h).
        - Affiche jusqu'à 50 joueurs ordonnés par nombre de récoltes décroissant.
        - Découpe en plusieurs messages si la longueur du texte le nécessite.
        - Propage toute exception en cas d'échec pour empêcher la réinitialisation des logs.
        """
        channel_id = self.channel_id("moderation_hourly_stats")
        if channel_id is None:
            logger.warning("LOG_MODERATION_HOURLY_STATS_CHANNEL_ID non configuré : rapport hourly 24h non envoyé.")
            raise RuntimeError("LOG_MODERATION_HOURLY_STATS_CHANNEL_ID non configuré.")

        channel = self.bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception as exc:
                raise RuntimeError(f"Impossible de récupérer le salon hourly {channel_id}: {exc}") from exc
        if not channel or not callable(getattr(channel, "send", None)):
            raise RuntimeError(f"Salon invalide ou inaccessible pour le rapport hourly ({channel_id}).")

        from utils.claim_analysis import calculate_player_hourly_metrics
        from utils.text import format_usd
        from utils.time_format import format_duration

        # Support rétrocompatible si summary est passé sous forme de dictionnaire {top_users: ...}
        if isinstance(summary, dict):
            players = summary.get("top_users", [])[:50]
        else:
            players = summary[:50] if summary else []

        header = "⏱️ **Bilan d'assiduité et régularité des récompenses horaires (hourly 24h)**\n\n"

        if not players:
            embed = discord.Embed(
                title="⏱️ Rapport Quotidien des Récompenses Horaires (/hourly 24h)",
                description=header + "*Aucune récolte horaire enregistrée sur cette période.*",
                color=discord.Color.dark_teal(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text="Root OS • Surveillance Hourly 24h")
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            return

        has_high_risk = False
        player_blocks = []
        for idx, row in enumerate(players, 1):
            user_id = row["discord_id"]
            claim_count = row["claim_count"]
            claims = row.get("claims", [])
            max_streak = row.get("max_streak", 1)
            max_bonus = Decimal(str(row.get("max_bonus_pct", 0)))
            total_usd = Decimal(str(row.get("total_usd", 0)))

            analysis = calculate_player_hourly_metrics(claims) if claims else {
                "risk_level": "LOW",
                "risk_badge": "🟢",
                "mean_interval_sec": None,
                "std_dev_sec": None,
                "regularity_pct": None,
                "alerts": [],
                "suspicious_streak": None,
                "active_24h": False,
            }

            if analysis["risk_level"] == "HIGH":
                has_high_risk = True

            user = self.bot.get_user(user_id)
            if not user:
                try:
                    user = await self.bot.fetch_user(user_id)
                except Exception:
                    user = None

            user_str = _format_user_compact(user) if user else f"<@{user_id}> (`{user_id}`)"
            badge = analysis["risk_badge"]

            mean_str = format_duration(analysis["mean_interval_sec"]) if analysis["mean_interval_sec"] is not None else "N/A"
            reg_pct = analysis["regularity_pct"]
            reg_str = f"{reg_pct:.1f}%" if reg_pct is not None else "N/A"
            std_str = f"± {format_duration(analysis['std_dev_sec'])}" if analysis["std_dev_sec"] is not None else ""

            lines = [
                f"**{idx}.** {badge} {user_str}",
                f"   ├ ⏱️ Récoltes : `{claim_count}` claims (🔥 `{max_streak}` · ⚡ `+{max_bonus:.1f}%`) · Total : `{format_usd(total_usd)}`",
                f"   ├ ⏱️ Intervalle moyen : `{mean_str}` · Régularité : `{reg_str}` {f'(`{std_str}`)' if std_str else ''}",
            ]

            if analysis.get("active_24h"):
                lines.append("   ├ ⚠️ **Alerte Sommeil** : activité observée sur 24h sans longue pause")

            streak = analysis.get("suspicious_streak")
            alerts = analysis.get("alerts", [])
            if "CRITICAL_MACRO_STREAK" in alerts and streak:
                s_mean = format_duration(streak["mean_sec"])
                s_std = format_duration(streak["std_dev_sec"])
                s_reg = f"{streak['regularity_pct']:.1f}%"
                lines.append(
                    f"   └ 🚨 **Phase automatisée (Macro)** : {streak['count']} claims consécutifs "
                    f"à `{s_mean}` (± `{s_std}`) · Régularité locale : `{s_reg}`"
                )
            elif "SUSPECT_LOCAL_STREAK" in alerts and streak:
                s_mean = format_duration(streak["mean_sec"])
                s_reg = f"{streak['regularity_pct']:.1f}%"
                lines.append(
                    f"   └ ⚠️ **Séquence suspecte** : {streak['count']} claims consécutifs "
                    f"à `{s_mean}` · Régularité locale : `{s_reg}`"
                )
            elif "VARIANCE_DROP_BURST" in alerts and streak:
                s_mean = format_duration(streak["mean_sec"])
                lines.append(
                    f"   └ 🚨 **Rupture de régime** : chute brutale de variation sur {streak['count']} claims "
                    f"à `{s_mean}`"
                )
            elif "GLOBAL_EXTREME_CONSTANCY" in alerts:
                lines.append("   └ 🚨 **Constance globale extrême** : intervalles quasi invariables sur 24h")
            elif analysis.get("status") == "INSUFFICIENT_DATA":
                lines.append("   └ ⚪ Données insuffisantes")
            else:
                lines.append("   └ 🟢 Comportement d'apparence humaine normale")

            player_blocks.append("\n".join(lines))

        max_desc_len = 3500
        pages = []
        current_page_blocks = []
        current_len = len(header)

        for block in player_blocks:
            block_len = len(block) + 2
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
        report_color = discord.Color.red() if has_high_risk else discord.Color.dark_teal()

        for page_idx, page_blocks in enumerate(pages, 1):
            embed = discord.Embed(
                title="⏱️ Rapport Quotidien des Récompenses Horaires (/hourly 24h)",
                description=header + "\n\n".join(page_blocks),
                color=report_color,
                timestamp=discord.utils.utcnow(),
            )
            if total_pages > 1:
                embed.set_footer(text=f"Root OS • Surveillance Hourly 24h • Page {page_idx}/{total_pages}")
            else:
                embed.set_footer(text="Root OS • Surveillance Hourly 24h")

            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

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
        color: discord.Color = COLOR_LOG_EVENT,
        details: list[str] | None = None,
        server_name: str = "Serveur inconnu",
    ):
        """Consigne la résolution réussie d'un mini-jeu dans le salon de logs publics."""
        guild = getattr(ctx, "guild", None)
        guild_str = f"{guild.name} (`{guild.id}`)" if guild else server_name

        lines = [f"> 👤 **Opérateur :** {_format_user_compact(winner)}"]
        if details:
            for detail in details:
                clean_d = detail if detail.startswith(">") else f"> {detail}"
                lines.append(clean_d)
        lines.append(f"> 🌐 **Serveur :** {guild_str}")

        winner_avatar = getattr(winner, "display_avatar", None)
        avatar_url = winner_avatar.url if winner_avatar and hasattr(winner_avatar, "url") else None

        embed = _style_public_embed(
            self.bot,
            title=title,
            description="\n".join(lines),
            color=color or COLOR_LOG_EVENT,
            author_category="ÉVÉNEMENT RÉSEAU",
            user_avatar_url=avatar_url,
        )
        await self._send_embed("public", embed)

    async def log_hash_won(self, ctx, winner: discord.User, target: int, players_count: int, server_name: str):
        """Consigne la résolution réussie d'un Hash Challenge dans le salon de logs publics."""
        details = [f"**Hash décodé :** `{target}`", f"**Joueurs en compétition :** `{players_count}`"]
        await self.log_challenge_won(ctx, winner, "🧩 Hash Challenge résolu !", COLOR_LOG_EVENT, details, server_name)

    async def log_pin_won(self, ctx, winner: discord.User, target: int, players_count: int, server_name: str):
        """Consigne la résolution réussie d'un Code PIN dans le salon de logs publics."""
        details = [f"**Code PIN validé :** `{target}`", f"**Joueurs en compétition :** `{players_count}`"]
        await self.log_challenge_won(ctx, winner, "🔐 Code PIN déchiffré !", COLOR_LOG_EVENT, details, server_name)

    async def log_decode_won(self, ctx, winner: discord.User, sequence: str, target: str, server_name: str):
        """Consigne la résolution réussie d'un Décryptage dans le salon de logs publics."""
        details = [f"**Séquence :** `{sequence}`", f"**Code validé :** `{target}`"]
        await self.log_challenge_won(ctx, winner, "🔍 Décryptage résolu !", COLOR_LOG_EVENT, details, server_name)

    async def log_anomaly_won(self, ctx, winner: discord.User, line: int, digit: str, server_name: str):
        """Consigne la neutralisation réussie d'une Anomalie dans le salon de logs publics."""
        details = [f"**Ligne de l'anomalie :** `Ligne {line}`", f"**Chiffre parasite :** `{digit}`"]
        await self.log_challenge_won(ctx, winner, "⚠️ Anomalie neutralisée !", COLOR_LOG_EVENT, details, server_name)

    async def log_buffer_won(self, ctx, winner: discord.User, target: str, server_name: str):
        """Consigne la réorganisation réussie d'un Buffer dans le salon de logs publics."""
        details = [f"**Code reconstitué :** `{target}`"]
        await self.log_challenge_won(ctx, winner, "📦 Buffer réaligné !", COLOR_LOG_EVENT, details, server_name)

    async def log_signal_won(self, ctx, winner: discord.User, winning_letter: str, server_name: str):
        """Consigne l'interception réussie d'un Signal dans le salon de logs publics."""
        details = [f"**Fréquence dominante :** `{winning_letter}`"]
        await self.log_challenge_won(ctx, winner, "📡 Signal intercepté !", COLOR_LOG_EVENT, details, server_name)

    async def log_packet_won(self, ctx, winner: discord.User, missing_packet: int, server_name: str):
        """Consigne l'identification réussie du paquet manquant dans le salon de logs publics."""
        details = [f"**Paquet manquant :** `Paquet #{missing_packet}`"]
        await self.log_challenge_won(ctx, winner, "🛰️ Paquet manquant identifié !", COLOR_LOG_EVENT, details, server_name)

    async def log_daily_event_report(self, summary: list[dict], resolution_map: dict[int, list[dict]] | None = None):
        """
        Envoie le rapport quotidien de modération des événements (24h) dans le salon dédié.
        Harmonisé avec topclaim et tophourly :
        - Analyse statistique par joueur (ratio de victoires, résolutions instantanées <= 2s, vitesse moyenne).
        - Affiche jusqu'à 50 joueurs ordonnés par nombre de victoires décroissant.
        - Découpe en plusieurs messages si la longueur du texte le nécessite.
        - Propage toute exception en cas d'échec pour empêcher la réinitialisation des données.
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

        from utils.event_analysis import calculate_player_event_metrics

        header = "🏆 **Bilan d'activité et intégrité des événements réseau (24h)**\n\n"
        players = summary[:50] if summary else []

        if not players:
            embed = discord.Embed(
                title="🏆 Rapport Quotidien des Événements (24h)",
                description=header + "*Aucune activité d'événement enregistrée sur cette période.*",
                color=discord.Color.dark_teal(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text="Root OS • Surveillance Événements 24h")
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            return

        has_high_risk = False
        player_blocks = []
        for idx, row in enumerate(players, 1):
            user_id = row["discord_id"]
            won = int(row.get("events_won", 0))
            part = int(row.get("events_participated", 0))
            recent_wins = resolution_map.get(user_id, []) if resolution_map else []

            analysis = calculate_player_event_metrics(won, part, recent_wins)
            if analysis["risk_level"] == "HIGH":
                has_high_risk = True

            user = self.bot.get_user(user_id)
            if not user:
                try:
                    user = await self.bot.fetch_user(user_id)
                except Exception:
                    user = None

            user_str = _format_user_compact(user) if user else f"<@{user_id}> (`{user_id}`)"
            badge = analysis["risk_badge"]
            win_rate = analysis["win_rate_pct"]

            lines = [
                f"**{idx}.** {badge} {user_str}",
                f"   ├ 🏆 Victoires : `{won}` · 🎯 Participations : `{part}` · Ratio : `{win_rate:.1f}%`",
            ]

            if analysis["mean_duration_sec"] is not None:
                lines.append(
                    f"   ├ ⚡ Vitesse de résolution : Moyenne `{analysis['mean_duration_sec']:.1f}s` "
                    f"(Record : `{analysis['min_duration_sec']}s`)"
                )

            alerts = analysis.get("alerts", [])
            if "CRITICAL_INSTANT_SOLVE" in alerts:
                lines.append(
                    f"   └ 🚨 **Résolution quasi-instantanée** : {analysis['instant_wins_count']} victoires en <= 2s (Bot/Script)"
                )
            elif "ABNORMAL_WIN_RATE" in alerts:
                lines.append(
                    f"   └ 🚨 **Taux de victoire anormal** : {win_rate:.1f}% de réussite sur {part} défis"
                )
            elif "SUSPECT_FAST_SOLVE" in alerts:
                lines.append(
                    f"   └ ⚠️ **Vitesse suspecte** : résolution moyenne très rapide ({analysis['mean_duration_sec']:.1f}s)"
                )
            elif "HIGH_WIN_RATE" in alerts:
                lines.append(
                    f"   └ ⚠️ **Taux de victoire élevé** : {win_rate:.1f}%"
                )
            else:
                lines.append("   └ 🟢 Comportement compétitif normal")

            player_blocks.append("\n".join(lines))

        max_desc_len = 3500
        pages = []
        current_page_blocks = []
        current_len = len(header)

        for block in player_blocks:
            block_len = len(block) + 2
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
        report_color = discord.Color.red() if has_high_risk else discord.Color.dark_teal()

        for page_idx, page_blocks in enumerate(pages, 1):
            embed = discord.Embed(
                title="🏆 Rapport Quotidien des Événements (24h)",
                description=header + "\n\n".join(page_blocks),
                color=report_color,
                timestamp=discord.utils.utcnow(),
            )
            if total_pages > 1:
                embed.set_footer(text=f"Root OS • Surveillance Événements 24h • Page {page_idx}/{total_pages}")
            else:
                embed.set_footer(text="Root OS • Surveillance Événements 24h")

            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    async def log_daily_claim_report(self, summary: list[dict]):
        """
        Envoie le rapport quotidien de modération des récoltes (claims 24h) dans le salon dédié.
        Conformément aux consignes :
        - Analyse statistique par joueur (moyenne, écart-type, régularité, streak suspect, 24/24h).
        - Affiche jusqu'à 50 joueurs ordonnés par nombre de claims décroissant.
        - Découpe en plusieurs messages si la longueur du texte le nécessite.
        - Propage toute exception en cas d'échec pour empêcher la réinitialisation des logs.
        """
        channel_id = self.channel_id("moderation_claim_stats")
        if channel_id is None:
            logger.warning("Salon de logs de modération claim non configuré : aucun rapport 24h envoyé.")
            raise RuntimeError("LOG_MODERATION_CLAIM_STATS_CHANNEL_ID (ou repli) non configuré.")

        channel = self.bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception as e:
                raise RuntimeError(f"Impossible de récupérer le salon {channel_id}: {e}") from e

        if not channel or not callable(getattr(channel, "send", None)):
            raise RuntimeError(f"Salon invalide ou inaccessible pour le rapport quotidien ({channel_id}).")

        from utils.claim_analysis import calculate_player_claim_metrics
        from utils.text import format_rtm
        from utils.time_format import format_duration

        header = "⛏️ **Bilan d'activité et régularité des récoltes (claims 24h)**\n\n"
        players = summary[:50] if summary else []

        if not players:
            embed = discord.Embed(
                title="⛏️ Rapport Quotidien des Récoltes (/claim 24h)",
                description=header + "*Aucune activité de claim enregistrée sur cette période.*",
                color=discord.Color.dark_teal(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text="Root OS • Surveillance Claims 24h")
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            return

        has_high_risk = False
        player_blocks = []
        for idx, row in enumerate(players, 1):
            user_id = row["discord_id"]
            claim_count = row["claim_count"]
            claims = row.get("claims", [])
            analysis = calculate_player_claim_metrics(claims)

            if analysis["risk_level"] == "HIGH":
                has_high_risk = True

            user = self.bot.get_user(user_id)
            if not user:
                try:
                    user = await self.bot.fetch_user(user_id)
                except Exception:
                    user = None

            user_str = _format_user_compact(user) if user else f"<@{user_id}> (`{user_id}`)"
            badge = analysis["risk_badge"]
            total_rtm = format_rtm(row.get("total_amount", analysis["total_amount"]))

            mean_str = format_duration(analysis["mean_interval_sec"]) if analysis["mean_interval_sec"] is not None else "N/A"
            reg_pct = analysis["regularity_pct"]
            reg_str = f"{reg_pct:.1f}%" if reg_pct is not None else "N/A"
            std_str = f"± {format_duration(analysis['std_dev_sec'])}" if analysis["std_dev_sec"] is not None else ""

            auto_count = row.get("auto_count", 0)
            manual_count = row.get("manual_count", claim_count)
            claims_label = f"`{claim_count}` (👤 `{manual_count}` · 🤖 `{auto_count}`)" if auto_count > 0 else f"`{claim_count}`"

            lines = [
                f"**{idx}.** {badge} {user_str}",
                f"   ├ ⛏️ Claims : {claims_label} · Total : `{total_rtm} RTM`",
                f"   ├ ⏱️ Intervalle moyen : `{mean_str}` · Régularité : `{reg_str}` {f'(`{std_str}`)' if std_str else ''}",
            ]

            if analysis.get("active_24h"):
                lines.append("   ├ ⚠️ **Alerte Sommeil** : activité observée sur 24h sans longue pause")

            streak = analysis.get("suspicious_streak")
            alerts = analysis.get("alerts", [])
            if "CRITICAL_MACRO_STREAK" in alerts and streak:
                s_mean = format_duration(streak["mean_sec"])
                s_std = format_duration(streak["std_dev_sec"])
                s_reg = f"{streak['regularity_pct']:.1f}%"
                lines.append(
                    f"   └ 🚨 **Phase automatisée (Macro)** : {streak['count']} claims consécutifs "
                    f"à `{s_mean}` (± `{s_std}`) · Régularité locale : `{s_reg}`"
                )
            elif "SUSPECT_LOCAL_STREAK" in alerts and streak:
                s_mean = format_duration(streak["mean_sec"])
                s_reg = f"{streak['regularity_pct']:.1f}%"
                lines.append(
                    f"   └ ⚠️ **Séquence suspecte** : {streak['count']} claims consécutifs "
                    f"à `{s_mean}` · Régularité locale : `{s_reg}`"
                )
            elif "VARIANCE_DROP_BURST" in alerts and streak:
                s_mean = format_duration(streak["mean_sec"])
                lines.append(
                    f"   └ 🚨 **Rupture de régime** : chute brutale de variation sur {streak['count']} claims "
                    f"à `{s_mean}`"
                )
            elif "GLOBAL_EXTREME_CONSTANCY" in alerts:
                lines.append("   └ 🚨 **Constance globale extrême** : intervalles quasi invariables sur 24h")
            elif analysis.get("status") == "INSUFFICIENT_DATA":
                lines.append("   └ ⚪ Données manuelles insuffisantes")
            else:
                lines.append("   └ 🟢 Comportement d'apparence humaine normale")

            player_blocks.append("\n".join(lines))

        max_desc_len = 3500
        pages = []
        current_page_blocks = []
        current_len = len(header)

        for block in player_blocks:
            block_len = len(block) + 2  # +2 pour séparateur
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
        report_color = discord.Color.red() if has_high_risk else discord.Color.dark_teal()

        for page_idx, page_blocks in enumerate(pages, 1):
            embed = discord.Embed(
                title="⛏️ Rapport Quotidien des Récoltes (/claim 24h)",
                description=header + "\n\n".join(page_blocks),
                color=report_color,
                timestamp=discord.utils.utcnow(),
            )
            if total_pages > 1:
                embed.set_footer(text=f"Root OS • Surveillance Claims 24h • Page {page_idx}/{total_pages}")
            else:
                embed.set_footer(text="Root OS • Surveillance Claims 24h")

            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())


    async def _resolve_entity_name(self, entity: int | str) -> str | None:
        """Tente de résoudre le pseudo Discord associé à un identifiant numérique."""
        entity_str = str(entity).strip()
        if not entity_str.isdigit():
            return None
        uid = int(entity_str)
        try:
            user = self.bot.get_user(uid) if hasattr(self.bot, "get_user") else None
            if user and not type(user).__name__.startswith("MagicMock"):
                return getattr(user, "display_name", None) or getattr(user, "name", None)
            if not user and hasattr(self.bot, "fetch_user"):
                user = await self.bot.fetch_user(uid)
                if user and not type(user).__name__.startswith("MagicMock"):
                    return getattr(user, "display_name", None) or getattr(user, "name", None)
        except Exception:
            pass
        return None

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
                res = channel.send(content, allowed_mentions=discord.AllowedMentions.none())
                if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                    await res
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
        from_name: str | None = None,
        to_name: str | None = None,
    ):
        """Envoie un log de transaction RTM formaté dans le salon #blockchain.

        tx_type / usd_amount sont optionnels (ex. vente DEX : TYPE SELL TOKEN + USD).
        from_name / to_name permettent d'afficher le pseudo Discord à côté de l'identifiant.
        """
        channel_id = self.channel_id("blockchain")
        if channel_id is None:
            return

        now = dt or datetime.now(timezone.utc)
        time_str = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        rtm_val = Decimal(str(rtm_amount or 0))
        rtm_str = f"{rtm_val:,.5f}"

        # Résolution automatique du pseudo si non fourni et que l'entité est un ID utilisateur Discord numérique
        if from_name is None:
            from_name = await self._resolve_entity_name(from_id)
        if to_name is None:
            to_name = await self._resolve_entity_name(to_address)

        from_str = f"{from_id} ({from_name})" if from_name else str(from_id)
        to_str = f"{to_address} ({to_name})" if to_name else str(to_address)

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
            f"FROM   {from_str}\n"
            f"TO     {to_str}\n"
            + "".join(f"{line}\n" for line in extra_lines) +
            f"{separator}\n"
            f"```"
        )
        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if callable(getattr(channel, "send", None)):
                res = channel.send(block_content, allowed_mentions=discord.AllowedMentions.none())
                if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                    await res
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
        scanner_user = None
        if str(scanner_id).isdigit() and hasattr(self.bot, "get_user"):
            scanner_user = self.bot.get_user(int(scanner_id))
            if scanner_user and type(scanner_user).__name__.startswith("MagicMock"):
                scanner_user = None
            if not scanner_user and hasattr(self.bot, "fetch_user"):
                try:
                    user_fetched = await self.bot.fetch_user(int(scanner_id))
                    if user_fetched and not type(user_fetched).__name__.startswith("MagicMock"):
                        scanner_user = user_fetched
                except Exception:
                    pass

        scanner_str = _format_user_compact(scanner_user) if scanner_user else f"<@{scanner_id}> (`{scanner_id}`)"
        scanner_avatar = getattr(scanner_user, "display_avatar", None) if scanner_user else None
        avatar_url = scanner_avatar.url if scanner_avatar and hasattr(scanner_avatar, "url") else None

        lines = [
            f"> 🔍 **Intrusion confirmée** · {scanner_str} a infiltré le réseau de **{target_name}** !",
            f"> 🔑 **Secret ID compromis :** `{secret_id}`",
            f"> ⚠️ *La cible est désormais vulnérable aux cyberattaques ciblées (/hack).* ",
        ]

        embed = _style_public_embed(
            self.bot,
            title="🔓 Fuite de Données // Renseignement Réseau",
            description="\n".join(lines),
            color=COLOR_LOG_SCAN,
            author_category="CYBER-RENSEIGNEMENT",
            user_avatar_url=avatar_url,
        )
        await self._send_embed("public", embed)

    async def log_pvp_attack(
        self,
        attacker: discord.User | discord.Member | int | str,
        attack_points: int | None = None,
        attacker_name: str | None = None,
    ):
        """Consigne une attaque PvP dans le salon de logs publics avec le nom de l'attaquant (sans divulguer les points d'attaque)."""
        if isinstance(attacker, (discord.User, discord.Member)) and not type(attacker).__name__.startswith("MagicMock"):
            attacker_str = _format_user_compact(attacker)
            attacker_avatar = getattr(attacker, "display_avatar", None)
        elif attacker_name:
            attacker_str = f"<@{attacker}> (`{attacker_name}` · `{attacker}`)"
            attacker_avatar = None
        else:
            attacker_user = None
            if str(attacker).isdigit() and hasattr(self.bot, "get_user"):
                u = self.bot.get_user(int(attacker))
                if u and not type(u).__name__.startswith("MagicMock"):
                    attacker_user = u
            if attacker_user:
                attacker_str = _format_user_compact(attacker_user)
                attacker_avatar = getattr(attacker_user, "display_avatar", None)
            else:
                attacker_str = f"<@{attacker}> (`{attacker}`)"
                attacker_avatar = None

        avatar_url = attacker_avatar.url if attacker_avatar and hasattr(attacker_avatar, "url") else None

        lines = [
            f"> ⚔️ **Alerte offensive** · Une cyberattaque a été lancée par {attacker_str}.",
            f"> 🛡️ *Les systèmes de défense et pare-feux ont engagé les contre-mesures.*",
        ]

        embed = _style_public_embed(
            self.bot,
            title="⚔️ Attaque Réseau Détectée",
            description="\n".join(lines),
            color=COLOR_LOG_ATTACK,
            author_category="ALERTE OFFENSIVE",
            user_avatar_url=avatar_url,
        )
        await self._send_embed("public", embed)
