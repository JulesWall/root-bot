"""Classe de base générique pour les mini-jeux de Root (MiniGameCog).

Ce module mutualise l'intégralité de la logique commune aux 7 mini-jeux :
- Validation et parsing unifié des entrées joueurs selon le type de défi (_parse_guess).
- Routage unifié des invocations slash et préfixes (_run_slash, _run_prefix) avec préfixe dynamique.
- Résolution asynchrone sécurisée du profil du dernier vainqueur (_resolve_winner_display).
- Dispatching déclaratif des messages de réponse texte ou embed (_send, _reply_text).
- Enregistrement des messages actifs et notification globale de victoire via ChallengeTracker.
- Journalisation automatique vers Logger selon la configuration du jeu (GameConfig).
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import discord

from commands.game.commandgame import BaseGameCog
from commands.game.game_config import GameConfig
from game.challenge_tracker import ChallengeTracker
from utils import text
from utils.logger import Logger
from utils.text import format_usd
from utils.time_format import format_duration, to_utc_timestamp


class MiniGameCog(BaseGameCog):
    """Cog parent générique pour les 7 mini-jeux de Root.

    Chaque sous-classe définit sa propre `config: GameConfig` issue de `GAMES`.
    """

    config: GameConfig

    def __init__(self, bot):
        self.bot = bot

    # ── Parsing et validation ────────────────────────────────────────────────
    def _parse_guess(self, raw: Any) -> Any:
        """Valide et convertit une proposition brute selon la configuration du jeu.

        Raises:
            ValueError: Si la valeur fournie ne respecte pas les critères de typage ou de bornes.
        """
        if raw is None:
            return None

        kind = self.config.guess_kind

        if kind == "int":
            if isinstance(raw, str):
                raw = raw.strip()
            return int(raw)

        if kind == "int_bounded":
            if isinstance(raw, str):
                raw = raw.strip()
            val = int(raw)
            if self.config.bounds:
                low, high = self.config.bounds
                if val < low or val > high:
                    raise ValueError(f"Value {val} out of bounds [{low}, {high}]")
            return val

        if kind == "raw_str":
            if isinstance(raw, str):
                s = raw.strip()
                return s if s else None
            return str(raw)

        if kind == "letter":
            if isinstance(raw, str):
                clean = raw.strip().upper()
                if len(clean) != 1 or not clean.isalpha():
                    raise ValueError("Must be a single letter A-Z")
                return clean
            raise ValueError("Must be a single letter A-Z")

        return raw

    # ── Envoi sécurisé ───────────────────────────────────────────────────────
    async def _reply_text(self, ctx, content: str, view: discord.ui.View | None = None) -> discord.Message | None:
        """Envoie une réponse textuelle simple avec mentions désactivées et retourne le message."""
        kwargs: dict[str, Any] = {"allowed_mentions": discord.AllowedMentions.none()}
        if view is not None:
            kwargs["view"] = view
        if getattr(ctx, "interaction", None):
            res = await ctx.respond(content, **kwargs)
            try:
                return await ctx.interaction.original_response()
            except Exception:
                return getattr(res, "message", None) if hasattr(res, "message") else (res if isinstance(res, discord.Message) else None)
        else:
            return await ctx.send(content, **kwargs)

    async def _resolve_winner_display(self, user_id: int) -> str:
        """Résout le nom d'affichage d'un joueur à partir de son ID Discord."""
        winner_obj = self.bot.get_user(user_id)
        if not winner_obj:
            try:
                winner_obj = await self.bot.fetch_user(user_id)
            except Exception:
                winner_obj = None

        if winner_obj:
            winner_name = getattr(winner_obj, "name", str(user_id))
            return f"<@{user_id}> (`{winner_name}`)"
        return f"<@{user_id}>"

    # ── Exécution Slash et Préfixe ───────────────────────────────────────────
    async def _run_slash(self, ctx, value: Any = None):
        """Pipeline d'exécution standard d'une commande slash de mini-jeu."""
        try:
            parsed = self._parse_guess(value)
        except (ValueError, TypeError):
            await self._prefetch_lang(ctx.author.id)
            return await self._reply_text(ctx, text.get(ctx, f"g_error_{self.config.key}_usage", prefix="/"))

        guild_name = ctx.guild.name if ctx.guild else None
        await self._invoke(ctx, self.config.key, guess=parsed, guild_name=guild_name)

    async def _run_prefix(self, ctx, raw: Any = None):
        """Pipeline d'exécution standard d'une commande préfixe de mini-jeu."""
        prefix = getattr(ctx, "clean_prefix", None) or getattr(ctx, "prefix", "+r")
        try:
            parsed = self._parse_guess(raw)
        except (ValueError, TypeError):
            await self._prefetch_lang(ctx.author.id)
            return await self._reply_text(ctx, text.get(ctx, f"g_error_{self.config.key}_usage", prefix=prefix))

        guild_name = ctx.guild.name if ctx.guild else None
        await self._invoke(ctx, self.config.key, guess=parsed, guild_name=guild_name)

    # ── Rendu & Affichage ────────────────────────────────────────────────────
    async def _send(self, ctx, method: str, result: dict[str, Any]):
        """Dispatch générique des résultats de jeu selon la forme et les configurations."""
        status = result.get("status")
        is_slash = bool(getattr(ctx, "interaction", None))
        prefix = "/" if is_slash else (getattr(ctx, "clean_prefix", None) or getattr(ctx, "prefix", "+r"))

        # 1. Cooldown
        if status == "cooldown":
            remaining_str = format_duration(result.get("remaining_seconds", 0))
            next_at = result.get("next_at")
            timestamp = to_utc_timestamp(next_at)

            if result.get("last_found_by"):
                winner_display = await self._resolve_winner_display(result["last_found_by"])
                content = text.get(
                    ctx,
                    f"g_{self.config.key}_cooldown",
                    last_found_by=winner_display,
                    last_found_on=result.get("last_found_on", "Inconnu"),
                    remaining=remaining_str,
                    timestamp=timestamp,
                )
            else:
                content = text.get(
                    ctx,
                    f"g_{self.config.key}_cooldown_no_winner",
                    remaining=remaining_str,
                    timestamp=timestamp,
                )
            await self._reply_text(ctx, content)
            return

        # 1bis. Cooldown individuel joueur
        if status == "player_cooldown":
            remaining_str = format_duration(result.get("remaining_seconds", 0))
            next_guess_at = result.get("next_guess_at")
            timestamp = to_utc_timestamp(next_guess_at)
            content = text.get(
                ctx,
                f"g_{self.config.key}_player_cooldown",
                remaining=remaining_str,
                remaining_ts=f"<t:{timestamp}:R>",
                timestamp=timestamp,
                **result,
            )
            await self._reply_text(ctx, content)
            return

        # 2. Consultation sans proposition
        if status == "active_info":
            render_kwargs = dict(result)
            if self.config.key == "hash":
                remaining_sec = result.get("remaining_seconds", 0)
                next_guess_at = result.get("next_guess_at")
                if remaining_sec > 0:
                    if next_guess_at is None:
                        next_guess_at = datetime.now(timezone.utc) + timedelta(seconds=remaining_sec)
                    timestamp = to_utc_timestamp(next_guess_at)
                    remaining_str = format_duration(remaining_sec)
                    render_kwargs["remaining"] = remaining_str
                    render_kwargs["remaining_ts"] = f"<t:{timestamp}:R>"
                    render_kwargs["timestamp"] = timestamp
                    cooldown_status = text.get(
                        ctx,
                        "g_hash_cooldown_waiting",
                        remaining=remaining_str,
                        remaining_ts=f"<t:{timestamp}:R>",
                        timestamp=timestamp,
                    )
                else:
                    cooldown_status = text.get(ctx, "g_hash_cooldown_ready")
                render_kwargs["cooldown_status"] = cooldown_status
            else:
                render_kwargs.setdefault("cooldown_status", "")

            content = text.get(ctx, f"g_{self.config.key}_active_info", prefix=prefix, **render_kwargs)
            view = getattr(self, "_build_active_view", lambda c, r: None)(ctx, result)
            msg = None
            if self.config.active_info_mode == "embed":
                msg = await self._send_embed(ctx, self.config.key, content, view=view)
            else:
                msg = await self._reply_text(ctx, content, view=view)

            if msg:
                await ChallengeTracker.register_message(self.config.key, msg)
            return

        # 3. Mauvaises réponses (Narrowing)
        if status in ("too_low", "too_high"):
            content = text.get(ctx, f"g_{self.config.key}_{status}", **result)
            await self._reply_text(ctx, content)
            return

        # 4. Mauvaise réponse (Binaire)
        if status == "wrong":
            content = text.get(ctx, f"g_{self.config.key}_wrong", **result)
            await self._reply_text(ctx, content)
            return

        # 5. Victoire (Unifiée pour tous les jeux)
        if status == "won":
            reward_usd = format_usd(result["reward"])
            send_kwargs = {
                **result,
                "reward": reward_usd,
                "letter": result.get("winning_letter"),
                "missing": result.get("missing_packet"),
            }
            content = text.get(ctx, f"g_{self.config.key}_won", **send_kwargs)
            win_msg = await self._reply_text(ctx, content)

            # Notifier et éditer tous les messages actifs des autres joueurs
            solved_msg_id = getattr(win_msg, "id", None)
            await ChallengeTracker.notify_win(
                self.config.key,
                winner_id=ctx.author.id,
                next_at=result.get("next_at"),
                solved_message_id=solved_msg_id,
            )

            if self.config.log_method:
                log_fn = getattr(Logger(self.bot), self.config.log_method)
                server_name = result.get("last_found_on", ctx.guild.name if ctx.guild else "Inconnu")
                await log_fn(
                    ctx,
                    winner=ctx.author,
                    server_name=server_name,
                    **self.config.log_kwargs(result),
                )
            return


def setup(bot):
    """Pas de Cog concret à enregistrer directement pour cette classe abstraite."""
    pass
