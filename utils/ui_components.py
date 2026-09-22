"""
Composants d'interface utilisateur standardisés pour Root OS.

Ce module centralise la création et le stylage des boutons interactifs :
- Boutons de confirmation (✅ Confirmer / Valider) en vert (ButtonStyle.success).
- Boutons d'annulation ou de refus (❌ Annuler / Refuser) en rouge (ButtonStyle.danger) ou neutre (ButtonStyle.secondary).
- Harmonisation des libellés selon la langue active du contexte.
"""

from typing import Callable, Coroutine
import discord

from utils import text


def create_confirm_button(
    ctx,
    label: str | None = None,
    style: discord.ButtonStyle = discord.ButtonStyle.success,
    emoji: str = "✅",
    custom_id: str | None = None,
    callback: Callable[[discord.Interaction], Coroutine] | None = None,
) -> discord.ui.Button:
    """Crée un bouton standard de confirmation."""
    btn_label = label or text.get(ctx, "g_confirm")
    btn = discord.ui.Button(label=btn_label, emoji=emoji, style=style, custom_id=custom_id)
    if callback:
        btn.callback = callback
    return btn


def create_cancel_button(
    ctx,
    label: str | None = None,
    style: discord.ButtonStyle = discord.ButtonStyle.danger,
    emoji: str = "❌",
    custom_id: str | None = None,
    callback: Callable[[discord.Interaction], Coroutine] | None = None,
) -> discord.ui.Button:
    """Crée un bouton standard d'annulation ou de refus."""
    btn_label = label or text.get(ctx, "g_cancel")
    btn = discord.ui.Button(label=btn_label, emoji=emoji, style=style, custom_id=custom_id)
    if callback:
        btn.callback = callback
    return btn


def create_trade_buttons(ctx, on_validate, on_refuse) -> tuple[discord.ui.Button, discord.ui.Button]:
    """Crée la paire de boutons harmonisés pour les échanges de ressources."""
    val_label = text.get(ctx, "g_trade_btn_validate")
    ref_label = text.get(ctx, "g_trade_btn_refuse")
    btn_validate = create_confirm_button(ctx, label=val_label, callback=on_validate)
    btn_refuse = create_cancel_button(ctx, label=ref_label, style=discord.ButtonStyle.danger, callback=on_refuse)
    return btn_validate, btn_refuse

