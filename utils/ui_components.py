"""
Composants d'interface utilisateur standardisés pour Root OS.

Ce module centralise la création et le stylage des boutons interactifs :
- Boutons de confirmation (Valider) en vert (ButtonStyle.success) ou danger si critique.
- Boutons d'annulation ou de retour en style secondaire neutre (ButtonStyle.secondary).
- Harmonisation des libellés et résolution des emojis via le registre root_emojis.
"""

from typing import Callable, Coroutine, Any
import discord

from utils import text
from utils.root_emojis import get_button_emoji


def create_confirm_button(
    ctx: Any,
    label: str | None = None,
    style: discord.ButtonStyle = discord.ButtonStyle.success,
    emoji: Any = "✅",
    custom_id: str | None = None,
    callback: Callable[[discord.Interaction], Coroutine] | None = None,
) -> discord.ui.Button:
    """Crée un bouton standard de confirmation."""
    btn_label = label or text.get(ctx, "g_confirm")
    btn = discord.ui.Button(label=btn_label[:80], emoji=emoji, style=style, custom_id=custom_id)
    if callback:
        btn.callback = callback
    return btn


def create_cancel_button(
    ctx: Any,
    label: str | None = None,
    style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    emoji: Any = "❌",
    custom_id: str | None = None,
    callback: Callable[[discord.Interaction], Coroutine] | None = None,
) -> discord.ui.Button:
    """Crée un bouton standard d'annulation (style secondaire par défaut selon la charte)."""
    btn_label = label or text.get(ctx, "g_cancel")
    btn = discord.ui.Button(label=btn_label[:80], emoji=emoji, style=style, custom_id=custom_id)
    if callback:
        btn.callback = callback
    return btn


def create_return_button(
    ctx: Any,
    label: str | None = None,
    style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    custom_id: str | None = None,
    callback: Callable[[discord.Interaction], Coroutine] | None = None,
) -> discord.ui.Button:
    """Crée un bouton Retour utilisant l'emoji animé root_retour si disponible."""
    is_fr = text.get_locale(ctx) == 'fr' if ctx else True
    btn_label = label or ("Retour" if is_fr else "Back")
    emoji = get_button_emoji("root_retour") or "↩️"
    btn = discord.ui.Button(label=btn_label[:80], emoji=emoji, style=style, custom_id=custom_id)
    if callback:
        btn.callback = callback
    return btn


def create_trade_buttons(ctx: Any, on_validate, on_refuse) -> tuple[discord.ui.Button, discord.ui.Button]:
    """Crée la paire de boutons harmonisés pour les échanges de ressources."""
    val_label = text.get(ctx, "g_trade_btn_validate")
    ref_label = text.get(ctx, "g_trade_btn_refuse")
    btn_validate = create_confirm_button(ctx, label=val_label, style=discord.ButtonStyle.success, callback=on_validate)
    btn_refuse = create_cancel_button(ctx, label=ref_label, style=discord.ButtonStyle.secondary, callback=on_refuse)
    return btn_validate, btn_refuse

