"""
Commande /rmd et !rmd — Système de rappels intelligents et temporisateurs Root OS.

Permet aux joueurs de planifier :
1. Des rappels automatiques sur le temps restant d'une mécanique :
   - !rmd hourly : alerte dès que la prime horaire est disponible.
   - !rmd events : alerte dès le début du prochain événement réseau (ou d'un event spécifique).
   - !rmd claim  : alerte dès que la mémoire vive (RAM) est saturée à 100 %.
2. Des rappels libres et personnalisés :
   - !rmd 30min pause-café
   - !rmd 2h check contrats
3. La gestion de ses rappels :
   - !rmd list : consulter ses rappels actifs.
   - !rmd cancel <id|all> : annuler un ou tous ses rappels.

Délivrance :
- Envoie une notification privée (MP).
- En cas de MP fermés (discord.Forbidden), repli sur le salon Discord d'origine avec mention.
"""

import logging
from datetime import datetime

import discord
from discord.ext import commands, tasks

import data
from commands.game.commandgame import BaseGameCog
from game.db.players import Player
from game.game_error import GameError
from lang.descslash import desc, desc_loc
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.time_format import format_duration, parse_duration, to_utc_timestamp

logger = logging.getLogger(__name__)


class Reminder(BaseGameCog):
    """Cog gérant les rappels intelligents et temporisateurs Root."""

    def __init__(self, bot):
        self.bot = bot
        self.check_reminders_loop.start()

    def cog_unload(self):
        """Arrête la tâche périodique de livraison au déchargement du Cog."""
        self.check_reminders_loop.cancel()

    # ── Boucle de livraison en arrière-plan ───────────────────────────────────
    @tasks.loop(seconds=10)
    async def check_reminders_loop(self):
        """Vérifie et délivre les rappels arrivés à échéance."""
        try:
            delivered = await self.service.deliver_due_reminders()
            if delivered:
                for item in delivered:
                    await self._deliver_single_reminder(item)
        except Exception:
            logger.exception("Erreur dans la boucle de livraison des rappels")

    @check_reminders_loop.before_loop
    async def before_check_reminders_loop(self):
        """Attend que le bot soit prêt avant de lancer la boucle."""
        import asyncio
        if hasattr(self.bot, "wait_until_ready") and callable(self.bot.wait_until_ready):
            res = self.bot.wait_until_ready()
            if asyncio.iscoroutine(res):
                await res

    async def _deliver_single_reminder(self, item: dict):
        """Délivre un rappel unique par MP ou repli salon."""
        discord_id = item.get("discord_id")
        if not discord_id:
            return

        message = item.get("message") or "Rappel"
        channel_id = item.get("channel_id")
        remind_at = item.get("remind_at")
        ts = to_utc_timestamp(remind_at)

        lang = await self.service.database.run(
            lambda tx: Player.get_language(tx, discord_id),
            readonly=True,
        ) or "fr"

        dm_content = text.get_for_lang(lang, "g_rmd_dm_notification", message=message, ts=ts)
        fallback_content = text.get_for_lang(
            lang,
            "g_rmd_fallback_notification",
            user=f"<@{discord_id}>",
            message=message,
        )

        sent = False
        try:
            user = self.bot.get_user(discord_id)
            if not user:
                user = await self.bot.fetch_user(discord_id)
            if user:
                await user.send(dm_content)
                sent = True
        except discord.Forbidden:
            logger.debug("MP bloqués pour l'utilisateur %s lors de la livraison du rappel", discord_id)
        except Exception:
            logger.exception("Erreur lors de l'envoi du MP de rappel à %s", discord_id)

        if not sent and channel_id:
            try:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    channel = await self.bot.fetch_channel(channel_id)
                if channel:
                    await channel.send(fallback_content)
            except Exception:
                logger.exception(
                    "Échec de l'envoi du rappel sur le salon de repli %s pour l'utilisateur %s",
                    channel_id,
                    discord_id,
                )

    # ── Slash Command Group (/rmd) ───────────────────────────────────────────
    rmd = discord.SlashCommandGroup(
        name="rmd",
        description=EN["rmd"],
        description_localizations={"fr": FR["rmd"]},
        guild_ids=data.GUILD_WHITELIST or None,
    )

    @rmd.command(
        name="auto",
        description=desc.get("rmd_sub_auto", "Activate automatic game reminders (hourly, claim, events, all)"),
        description_localizations=desc_loc.get("rmd_sub_auto", None),
    )
    async def rmd_auto(
        self,
        ctx,
        target: discord.Option(
            str,
            description=desc.get("rmd_target", "Smart target to track"),
            description_localizations=desc_loc.get("rmd_target", None),
            choices=[
                discord.OptionChoice(name="⚡ Tous les rappels de jeu possibles", value="all"),
                discord.OptionChoice(name="⏱️ Récompense horaire (Hourly)", value="hourly"),
                discord.OptionChoice(name="⛏️ Saturation mémoire vive (Claim RAM)", value="claim"),
                discord.OptionChoice(name="🌐 Prochains événements réseau (Events)", value="events"),
                discord.OptionChoice(name="🧩 Défi Hash", value="hash"),
                discord.OptionChoice(name="🔐 Défi Code PIN", value="pin"),
                discord.OptionChoice(name="📡 Défi Signal", value="signal"),
                discord.OptionChoice(name="🔍 Défi Decode", value="decode"),
                discord.OptionChoice(name="⚠️ Défi Anomaly", value="anomaly"),
                discord.OptionChoice(name="💾 Défi Buffer", value="buffer"),
                discord.OptionChoice(name="📦 Défi Packet", value="packet"),
            ],
            required=False,
            default="all",
        ) = "all",
    ):
        """Active un rappel automatique de jeu (hourly, claim, events ou tous)."""
        channel_id = ctx.channel.id if ctx.channel else None
        guild_id = ctx.guild.id if ctx.guild else None
        clean_target = "events" if target == "event" else target
        await self._invoke(
            ctx,
            "rmd",
            action="create_smart",
            target=clean_target,
            channel_id=channel_id,
            guild_id=guild_id,
        )

    @rmd.command(
        name="timer",
        description=desc.get("rmd_sub_timer", "Set a custom countdown timer (e.g. 30m, 2h, 45s)"),
        description_localizations=desc_loc.get("rmd_sub_timer", None),
    )
    async def rmd_timer(
        self,
        ctx,
        duration: discord.Option(
            str,
            description=desc.get("rmd_duration", "Timer duration (e.g. 30m, 2h, 45s, 1d)"),
            description_localizations=desc_loc.get("rmd_duration", None),
            required=True,
        ),
        message: discord.Option(
            str,
            description=desc.get("rmd_message", "Custom reminder note (e.g. Coffee break)"),
            description_localizations=desc_loc.get("rmd_message", None),
            required=False,
            default=None,
        ) = None,
    ):
        """Définit un minuteur libre avec compte à rebours et message personnalisé."""
        channel_id = ctx.channel.id if ctx.channel else None
        guild_id = ctx.guild.id if ctx.guild else None
        dur_sec = parse_duration(duration)
        if dur_sec is None:
            raise GameError("invalid_duration")
        await self._invoke(
            ctx,
            "rmd",
            action="create_custom",
            duration_sec=dur_sec,
            message=message,
            channel_id=channel_id,
            guild_id=guild_id,
        )

    @rmd.command(
        name="list",
        description=desc.get("rmd_sub_list", "View all your active reminders and timers"),
        description_localizations=desc_loc.get("rmd_sub_list", None),
    )
    async def rmd_list(self, ctx):
        """Affiche la liste de tous vos rappels et minuteurs actifs."""
        await self._invoke(ctx, "rmd", action="list")

    @rmd.command(
        name="cancel",
        description=desc.get("rmd_sub_cancel", "Cancel a specific reminder by ID or delete all"),
        description_localizations=desc_loc.get("rmd_sub_cancel", None),
    )
    async def rmd_cancel(
        self,
        ctx,
        reminder_id: discord.Option(
            str,
            description=desc.get("rmd_id", "Reminder ID to cancel, or 'all' to delete everything"),
            description_localizations=desc_loc.get("rmd_id", None),
            required=False,
            default="all",
        ) = "all",
    ):
        """Annule un rappel individuel par son ID ou supprime tous vos rappels."""
        await self._invoke(ctx, "rmd", action="cancel", reminder_id=reminder_id or "all")

    @rmd.command(
        name="help",
        description=desc.get("rmd_sub_help", "Show reminder syntax, shortcuts, and documentation"),
        description_localizations=desc_loc.get("rmd_sub_help", None),
    )
    async def rmd_help(self, ctx):
        """Affiche le guide complet d'utilisation des rappels."""
        await self._invoke(ctx, "rmd", action="help")

    # ── Commande Préfixe ─────────────────────────────────────────────────────
    @commands.command(name="rmd", aliases=["remind", "reminder"], help=FR["rmd"])
    async def prefix_rmd(self, ctx, *args):
        """Commande préfixe !rmd (syntaxe) ou !rmd [target|durée] [message] ou !rmd list / !rmd cancel <id|all>."""
        channel_id = ctx.channel.id if ctx.channel else None
        guild_id = ctx.guild.id if ctx.guild else None

        # 1. Sans argument : afficher la syntaxe claire de la commande
        if not args or args[0].lower() in ("help", "aide", "syntaxe", "?"):
            await self._invoke(ctx, "rmd", action="help")
            return

        first = args[0].lower()

        # 2. Liste des rappels
        if first in ("list", "liste", "all_list", "ls"):
            await self._invoke(ctx, "rmd", action="list")
            return

        # 3. Annulation
        if first in ("cancel", "del", "delete", "suppr", "rm"):
            rid = args[1] if len(args) > 1 else "all"
            await self._invoke(ctx, "rmd", action="cancel", reminder_id=rid)
            return

        if first in ("clear", "reset"):
            await self._invoke(ctx, "rmd", action="cancel", reminder_id="all")
            return

        # 4. Rappels automatiques de jeu (all, hourly, claim, events...)
        smart_targets = (
            "all",
            "hourly",
            "claim",
            "events",
            "event",
            "hash",
            "pin",
            "decode",
            "anomaly",
            "buffer",
            "signal",
            "packet",
        )
        if first in smart_targets:
            target = "events" if first == "event" else first
            await self._invoke(
                ctx,
                "rmd",
                action="create_smart",
                target=target,
                channel_id=channel_id,
                guild_id=guild_id,
            )
            return

        # 5. Minuteur libre (<durée> [sujet])
        parsed_sec = None
        msg_start_idx = 0
        for i in range(len(args), 0, -1):
            candidate = " ".join(args[:i])
            sec = parse_duration(candidate)
            if sec is not None:
                parsed_sec = sec
                msg_start_idx = i
                break

        if parsed_sec is None:
            raise GameError("invalid_duration")

        custom_msg = " ".join(args[msg_start_idx:]) if msg_start_idx < len(args) else None
        await self._invoke(
            ctx,
            "rmd",
            action="create_custom",
            duration_sec=parsed_sec,
            message=custom_msg,
            channel_id=channel_id,
            guild_id=guild_id,
        )

    # ── Rendu ────────────────────────────────────────────────────────────────
    async def _send(self, ctx, method, result):
        """Génère l'affichage stylisé du résultat de la commande /rmd."""
        status = result.get("status")

        if status == "help":
            prefix = getattr(ctx, "prefix", None) or data.DEFAULT_PREFIX
            content = text.get(ctx, "g_rmd_syntax", prefix=prefix)

        elif status == "list":
            reminders = result.get("reminders", [])
            if not reminders:
                content = text.get(ctx, "g_rmd_list_empty")
            else:
                items = []
                for r in reminders:
                    remind_at = r.get("remind_at")
                    ts = to_utc_timestamp(remind_at)
                    items.append(
                        text.get(
                            ctx,
                            "g_rmd_list_item",
                            id=r.get("id"),
                            ts=ts,
                            type=r.get("reminder_type"),
                            message=r.get("message"),
                        )
                    )
                content = f"{text.get(ctx, 'g_rmd_list_title')}\n\n" + "\n".join(items)

        elif status == "cancelled":
            content = text.get(ctx, "g_rmd_cancel_success", id=result.get("reminder_id"))

        elif status == "cancelled_all":
            content = text.get(ctx, "g_rmd_cancel_all_success", count=result.get("count", 0))

        elif status == "created_all":
            results = result.get("results", [])
            lines = [text.get(ctx, "g_rmd_created_all_title"), ""]
            target_names = {
                "hourly": "Hourly (/hourly)",
                "claim": "Claim RAM (/claim)",
                "events": "Événements (/event)",
            }
            cmd_map = {
                "hourly": "/hourly",
                "claim": "/claim",
                "events": "/event",
            }
            for item in results:
                t = item.get("target")
                target_ev = item.get("target_event")
                if target_ev:
                    is_fr = text.get_locale(ctx) == "fr"
                    prefix_ev = "Événement" if is_fr else "Event"
                    t_name = f"{prefix_ev} {target_ev}"
                else:
                    t_name = target_names.get(t, t.capitalize() if t else "Rappel")
                item_status = item.get("status")

                if item_status == "created":
                    rem_sec = item.get("remaining_seconds", 0)
                    dur_str = format_duration(rem_sec)
                    ts = to_utc_timestamp(item.get("remind_at"))
                    lines.append(text.get(ctx, "g_rmd_created_all_created", target_name=t_name, duration=dur_str, ts=ts))
                elif item_status == "already_available":
                    cmd = cmd_map.get(t, f"/{t}")
                    lines.append(text.get(ctx, "g_rmd_created_all_available", target_name=t_name, cmd=cmd))
                elif item_status == "already_scheduled":
                    ts = to_utc_timestamp(item.get("remind_at"))
                    lines.append(text.get(ctx, "g_rmd_created_all_already", target_name=t_name, ts=ts))
                elif item_status == "no_miner":
                    lines.append(text.get(ctx, "g_rmd_created_all_no_miner", target_name=t_name))

            content = "\n".join(lines)

        elif status == "already_available":
            target = result.get("target", "")
            cmd_map = {
                "hourly": "/hourly",
                "claim": "/claim",
                "events": "/event",
                "event": "/event",
            }
            cmd = cmd_map.get(target, f"/event action:submit event_name:{target}")
            target_name_map = {
                "hourly": "Hourly",
                "claim": "Claim RAM",
                "events": "Événement",
            }
            target_name = target_name_map.get(target, f"Événement {target}")
            content = text.get(ctx, "g_rmd_already_available", target_name=target_name, cmd=cmd)

        elif status == "created":
            remind_at = result.get("remind_at")
            ts = to_utc_timestamp(remind_at)
            dur_sec = result.get("duration_seconds") or result.get("remaining_seconds", 0)
            dur_str = format_duration(dur_sec)
            reminder = result.get("reminder", {})

            if reminder.get("reminder_type") == "custom":
                content = text.get(
                    ctx,
                    "g_rmd_created_custom",
                    duration=dur_str,
                    ts=ts,
                    message=reminder.get("message", ""),
                )
            else:
                target = result.get("target", "")
                target_event = result.get("target_event")
                target_label = f"Événement {target_event}" if target_event else target.capitalize()
                content = text.get(
                    ctx,
                    "g_rmd_created_smart",
                    target_name=target_label,
                    duration=dur_str,
                    ts=ts,
                )
        else:
            content = "OK"

        await self._send_embed(ctx, "rmd", content)


def setup(bot):
    """Enregistre le Cog Reminder auprès du bot."""
    bot.add_cog(Reminder(bot))
