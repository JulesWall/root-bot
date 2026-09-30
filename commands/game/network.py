"""Commande /network et !network (alias !n) — Consultation et initialisation du réseau joueur.

Ce module constitue l'interface principale du joueur avec son infrastructure informatique virtuelle :
- Création automatique du compte joueur si le joueur n'existe pas encore.
- Affichage du statut complet :
  - Économie : solde en dollars (USD) et Rootium (RTM).
  - Défense : niveau de Firewall avec barre graphique ASCII (ex: ▰▰▰▱▱), défense de réseau, réputation.
  - Baies de serveurs : état des modules installés (minage, attaque, défense) pour chaque tier de 1 à 6.
- Affichage clair et structuré en Embed Discord pleine largeur.

Architecture & Règles :
- Strictement serveur uniquement (les DMs sont bloqués en amont par le `global_check` de `main.py`).
- Zéro SQL direct : tous les calculs et sélections passent par `service.execute(..., 'network')`.
- Tous les textes proviennent des dictionnaires `lang/`.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import discord
from discord.ext import commands, tasks

import data
from commands.game.claim import log_claim_events
from commands.game.commandgame import BaseGameCog
from game.math_config import MathConfig
from lang.game_en import descriptions as EN
from lang.game_fr import descriptions as FR
from utils import text
from utils.check import Check
from utils.language_manager import set_user_language
from utils.logger import Logger
from utils.time_format import format_duration

logger = logging.getLogger(__name__)

COLOR_TURQUOISE = 0x54E2D1
COLOR_AMBER = 0xFFC15A

FALLBACKS = {
    "terminal": "🖥️", "firewall": "🛡️", "ferme": "🗄️",
    "puissance": "⚙️", "production": "📊", "memoire": "💾",
    "temps": "⏱️", "recolter": "📥", "materiel": "⚙️",
    "logiciels": "💻", "operations": "📋", "journal": "📄",
    "alerte": "⚠️", "scan": "🔍", "connexions": "🌐",
    "retour": "↩️", "bilan": "📊", "dollars": "💵",
}

INFRASTRUCTURE_IMAGES = {
    0: "niveau-0-smartphone.png",
    1: "niveau-1-pc-assemble.png",
    2: "niveau-2-station-de-travail.png",
    3: "niveau-3-serveur-dedie.png",
    4: "niveau-4-salle-des-serveurs.png",
    5: "niveau-5-datacenter.png",
}


def get_infrastructure_image_path(level: int) -> Path | None:
    """Retourne le chemin local de l'illustration de l'infrastructure si elle existe sur disque."""
    lvl = max(0, min(5, int(level or 0)))
    filename = INFRASTRUCTURE_IMAGES.get(lvl)
    if not filename:
        return None
    p = Path(__file__).resolve().parent.parent.parent / "design" / "infrastructures-controle" / filename
    return p if p.exists() else None


def select_emojis(emojis) -> dict:
    """Résout les emojis personnalisés root_* en priorisant les versions animées utilisables."""
    selected = {}
    if not emojis:
        return selected
    for emoji in sorted(emojis, key=lambda item: (getattr(item, 'animated', False), getattr(item, 'id', 0))):
        name = getattr(emoji, 'name', '')
        if name.startswith("root_"):
            clean_name = name.removeprefix("root_")
            if clean_name in FALLBACKS:
                is_usable = getattr(emoji, 'is_usable', None)
                if is_usable is None or is_usable():
                    selected[clean_name] = emoji
    return selected


def _secret_id_check_interval() -> int:
    """Intervalle de la boucle de rotation, lu depuis data/math.json."""
    return int(MathConfig.load().get('secret_id', {}).get('check_interval_seconds', 30))


_LANG_BUTTONS = {
    'en': ('🇬🇧', 'English'),
    'fr': ('🇫🇷', 'Français'),
}


def _slash_or_english(ctx) -> str:
    """Langue du client slash si elle est supportée, sinon anglais (préfixe / locale inconnue)."""
    interaction = getattr(ctx, 'interaction', None)
    locale = getattr(interaction, 'locale', None) if interaction else None
    if locale:
        code = str(locale)[:2].lower()
        if code in data.SUPPORTED_LANGS:
            return code
    return 'en'


def _command_prefix(ctx) -> str:
    """Préfixe à afficher dans l'intro : `/` en slash, sinon le préfixe du serveur."""
    if getattr(ctx, 'interaction', None):
        return '/'
    return getattr(ctx, 'clean_prefix', None) or getattr(ctx, 'prefix', '!')


def _format_retaliation_countdown(until, now=None) -> str:
    """Formate le compte à rebours précis sous forme '2j 23h 45min' ou '4h 12min' ou '45s'."""
    if until is None:
        return ""
    if now is None:
        now = datetime.now(timezone.utc)
    if not hasattr(until, 'tzinfo'):
        try:
            until = datetime.fromisoformat(str(until))
        except Exception:
            return ""
    if until.tzinfo is not None and getattr(now, 'tzinfo', None) is None:
        until = until.replace(tzinfo=None)
    elif until.tzinfo is None and getattr(now, 'tzinfo', None) is not None:
        until = until.replace(tzinfo=now.tzinfo)

    total_seconds = max(0, int((until - now).total_seconds()))
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}j")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}min")
    if not parts or (days == 0 and hours == 0):
        parts.append(f"{secs}s")
    return " ".join(parts)


class WelcomeLanguageView(discord.ui.View):
    """Sélecteur de langue au premier réseau : anglais, plus la langue du client slash si elle diffère."""

    def __init__(self, author_id: int, prompt_lang: str, prefix: str):
        super().__init__(timeout=300)
        self.author_id = int(author_id)
        self.prompt_lang = prompt_lang
        self.prefix = prefix
        self.done = False
        self.message = None

        codes = []
        if prompt_lang in data.SUPPORTED_LANGS:
            codes.append(prompt_lang)
        if 'en' not in codes:
            codes.append('en')
        for extra in data.SUPPORTED_LANGS:
            if extra not in codes:
                codes.append(extra)

        for code in codes:
            emoji, label = _LANG_BUTTONS.get(code, ('🌐', code.upper()))
            button = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.primary)
            button.callback = self._callback_for(code)
            self.add_item(button)

    def _callback_for(self, lang: str):
        async def _on_click(interaction: discord.Interaction):
            await self._choose(interaction, lang)
        return _on_click

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                text.get_for_lang(self.prompt_lang, 'no_permission'),
                ephemeral=True,
            )
            return False
        return True

    async def _choose(self, interaction: discord.Interaction, lang: str):
        if self.done:
            await interaction.response.send_message(
                text.get_for_lang(lang, 'g_already_handled'),
                ephemeral=True,
            )
            return
        self.done = True
        self.stop()
        await set_user_language(self.author_id, lang)
        tip = text.get_for_lang(lang, 'g_welcome_onboarding', prefix=self.prefix)
        await interaction.response.edit_message(content=tip, view=None)

    async def on_timeout(self):
        if self.done:
            return
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class NetworkActionView(discord.ui.View):
    """Boutons interactifs sous le terminal /network : Récolte et Actualisation."""

    def __init__(self, cog, ctx, result):
        timeout = 180
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            timeout = None
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.author_id = getattr(ctx, 'author', None) and ctx.author.id or (getattr(ctx, 'user', None) and ctx.user.id)
        self.lock = asyncio.Lock()
        self.message = None
        self._update_buttons(result)

    def _update_buttons(self, result):
        self.clear_items()
        mining_state = result.get('mining_state') or {}
        buffer_val = Decimal(str(mining_state.get('buffer', 0)))
        has_buffer = buffer_val > 0

        # Bouton Récolter
        btn_claim_label = text.get(self.ctx, 'g_net_btn_claim')
        if has_buffer:
            buf_str = text.format_rtm(buffer_val)
            label = f"{btn_claim_label} ({buf_str} RTM)"
            claim_btn = discord.ui.Button(
                label=label[:80],
                emoji="🪙",
                style=discord.ButtonStyle.success,
                disabled=False,
            )
        else:
            claim_btn = discord.ui.Button(
                label=btn_claim_label[:80],
                emoji="🪙",
                style=discord.ButtonStyle.secondary,
                disabled=True,
            )
        claim_btn.callback = self._on_claim
        self.add_item(claim_btn)

        # Bouton Actualiser
        btn_refresh_label = text.get(self.ctx, 'g_net_btn_refresh')
        refresh_btn = discord.ui.Button(
            label=btn_refresh_label[:80],
            emoji="🔄",
            style=discord.ButtonStyle.primary,
        )
        refresh_btn.callback = self._on_refresh
        self.add_item(refresh_btn)

    async def _on_claim(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return
        checks = Check()
        allowed, err_key = await checks.check_interaction_access(self.cog.bot, interaction, allow_network=False)
        if not allowed:
            await interaction.response.send_message(text.get(self.ctx, err_key), ephemeral=True)
            return
        async with self.lock:
            await interaction.response.defer()
            try:
                claim_res = await self.cog.service.execute(
                    self.author_id,
                    interaction.guild.id if interaction.guild else None,
                    'claim',
                )
                if claim_res.get('claimed'):
                    amount = Decimal(str(claim_res.get('amount', 0)))
                    toast = text.get(self.ctx, 'g_net_claim_toast', amount=text.format_rtm(amount))
                    await interaction.followup.send(toast, ephemeral=True)
                    log_ctx = interaction if getattr(interaction, 'guild', None) else self.ctx
                    await log_claim_events(self.cog.bot, log_ctx, amount, claim_res)
            except Exception as err:
                if hasattr(err, 'key'):
                    err_msg = text.get(self.ctx, 'g_error_' + err.key, **getattr(err, 'values', {}))
                else:
                    err_msg = str(err)
                await interaction.followup.send(err_msg, ephemeral=True)
                return

            # Recharger network
            net_res = await self.cog.service.execute(
                self.author_id,
                interaction.guild.id if interaction.guild else None,
                'network',
            )
            embed = self.cog._build_network_embed(self.ctx, net_res)
            self._update_buttons(net_res)
            try:
                await interaction.message.edit(embed=embed, view=self)
            except Exception:
                pass

    async def _on_refresh(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return
        async with self.lock:
            await interaction.response.defer()
            net_res = await self.cog.service.execute(
                self.author_id,
                interaction.guild.id if interaction.guild else None,
                'network',
            )
            embed = self.cog._build_network_embed(self.ctx, net_res)
            self._update_buttons(net_res)
            try:
                await interaction.message.edit(embed=embed, view=self)
            except Exception:
                pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


class NetworkDesignerView(discord.ui.DesignerView):
    """Panneau Discord Components V2 représentant l'infrastructure de contrôle du joueur."""

    def __init__(self, cog, ctx, result, emojis=None, image_url=None):
        timeout = 600
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            timeout = None
        super().__init__(timeout=timeout, disable_on_timeout=True)
        self.cog = cog
        self.ctx = ctx
        self.result = result
        self.emojis = emojis or {}
        self.image_url = image_url
        self.author_id = int(result.get('discord_id') or (getattr(ctx, 'author', None) and ctx.author.id) or 0)
        self.detail = None
        self.library_data = None
        self.lock = asyncio.Lock()
        self.message = None
        self.rebuild()

    def emoji(self, name: str):
        return self.emojis.get(name, FALLBACKS.get(name, "⚙️"))

    def rebuild(self):
        self.clear_items()
        e = self.emoji
        ctx = self.ctx
        result = self.result

        author = getattr(ctx, 'author', None) or getattr(ctx, 'user', None)
        author_name = getattr(author, 'display_name', str(result.get('discord_id', '')))

        infra_level = int(result.get('infrastructure_level', result.get('firewall_level', 0)) or 0)
        infra_level = max(0, min(5, infra_level))
        infra_name = text.get(ctx, f'g_infra_name_{infra_level}')

        stats = result.get('stats') or MathConfig.calculate_player_stats(result)
        mining_state = result.get('mining_state')
        if mining_state is None:
            mining_state = MathConfig.compute_mining_progress(result, stats, datetime.now(timezone.utc))

        mem_pct = float(mining_state.get('memory_pct', 0))
        is_mem_full = mem_pct >= 100.0 or bool(mining_state.get('is_full'))
        panel_color = COLOR_AMBER if is_mem_full else COLOR_TURQUOISE

        panel = discord.ui.Container(color=panel_color)

        if self.image_url:
            gallery = discord.ui.MediaGallery()
            gallery.add_item(self.image_url, description=infra_name)
            panel.add_item(gallery)

        def text_elem(content: str):
            panel.add_item(discord.ui.TextDisplay(content))

        def separator():
            panel.add_item(discord.ui.Separator())

        actions = []

        if self.detail == "hardware":
            header = text.get(ctx, 'g_net_v2_header', name=author_name.upper())
            sub = text.get(ctx, 'g_net_v2_sub_hardware', infra_name=infra_name)
            text_elem(f"## {e('terminal')} {header}\n-# {sub}")
            separator()

            hw_title = text.get(ctx, 'g_net_v2_hardware_title')
            text_elem(f"### {e('materiel')} {hw_title}")

            max_tier_unlocked = max(1, min(5, infra_level + 1))
            tier_rows = []
            for tier in range(1, 6):
                bay = stats['bay_details'].get(tier, {})
                m_count = bay.get('mining_count', 0)
                a_count = bay.get('attack_count', 0)
                d_count = bay.get('bay_defense_count', 0)

                if tier <= max_tier_unlocked or m_count > 0 or a_count > 0 or d_count > 0:
                    m_hs = MathConfig.format_hashrate(bay.get('mining_hashrate', 0))
                    a_pow = MathConfig.format_bits_per_s(bay.get('attack_bits_per_s', 0))
                    d_pow = f"{bay.get('bay_defense_power', 0)} DEF"
                    row_txt = text.get(
                        ctx, 'g_net_v2_hardware_tier_row',
                        tier=tier,
                        m_count=m_count, m_power=m_hs,
                        a_count=a_count, a_power=a_pow,
                        d_count=d_count, d_power=d_pow,
                    )
                    tier_rows.append(f"> {row_txt}")

            if not tier_rows:
                tier_rows.append(f"> {text.get(ctx, 'g_net_v2_hardware_empty')}")
            text_elem("\n".join(tier_rows))
            separator()

            tot_hs = stats.get('total_hashrate_formatted', '0 H/s')
            tot_atk = stats.get('total_bits_per_s_formatted', '0 Bit/s')
            tot_bdef = stats.get('total_bay_defense', 0)
            tot_ndef = stats.get('network_defense', 0)
            tot_ram = mining_state.get('total_ram_formatted', '0 o')
            text_elem(
                f"{e('puissance')} **Hashrate total** · {tot_hs}\n"
                f"{e('puissance')} **Attaque totale** · {tot_atk}\n"
                f"{e('firewall')} **Défense** · {tot_bdef} DEF (Baies) · {tot_ndef} DEF (Réseau)\n"
                f"{e('memoire')} **Mémoire vive totale** · {tot_ram}"
            )

            btn_back_label = text.get(ctx, 'g_net_v2_btn_back')
            back_btn = discord.ui.Button(
                label=btn_back_label,
                emoji=e('retour'),
                style=discord.ButtonStyle.secondary,
                custom_id="root_net:back",
            )
            back_btn.callback = self._on_back
            actions.append(back_btn)

        elif self.detail == "software":
            header = text.get(ctx, 'g_net_v2_header', name=author_name.upper())
            sub = text.get(ctx, 'g_pvp_v2_library_title')
            text_elem(f"## 💾 {header}\n-# {sub}")
            separator()

            lib = self.library_data or {}
            active_jobs = lib.get('active_jobs', [])
            folders = lib.get('research_folders', [])
            copies = lib.get('software_copies', [])
            patches = lib.get('patches', [])

            # 1. Jobs actifs
            job_lines = [f"### ⏳ {text.get(ctx, 'g_pvp_v2_library_active_jobs')}"]
            if not active_jobs:
                job_lines.append(f"> *{text.get(ctx, 'g_pvp_v2_library_no_active_jobs')}*")
            else:
                for j in active_jobs:
                    res_at = j.get('resolves_at')
                    ts = int(res_at.replace(tzinfo=timezone.utc).timestamp()) if res_at and hasattr(res_at, 'timestamp') else 0
                    fp_part = f" (`{j.get('fingerprint')}`)" if j.get('fingerprint') else ""
                    job_lines.append(f"> • **[{j['channel'].upper()}]** `{j['job_type']}` · {j['family']} T{j['tier']}{fp_part} — fin <t:{ts}:R>")
            text_elem("\n".join(job_lines))
            separator()

            # 2. Dossiers de recherche
            folder_lines = [f"### 📁 {text.get(ctx, 'g_pvp_v2_library_folders')}"]
            if not folders:
                folder_lines.append(f"> *{text.get(ctx, 'g_pvp_v2_library_no_folders')}*")
            else:
                for f in folders:
                    folder_lines.append(f"> • 📁 **{f['family']}** T{f['tier']} · Empreinte : `{f['fingerprint']}` ({f['channel']})")
            text_elem("\n".join(folder_lines))
            separator()

            # 3. Copies de logiciels
            copy_lines = [f"### 💿 {text.get(ctx, 'g_pvp_v2_library_copies')}"]
            if not copies:
                copy_lines.append(f"> *{text.get(ctx, 'g_pvp_v2_library_no_copies')}*")
            else:
                for c in copies:
                    resell = "Revente autorisée" if c.get('resellable') else "Non revendable"
                    copy_lines.append(f"> • 💾 **{c['family']}** T{c['tier']} · Empreinte : `{c['fingerprint']}` ({resell})")
            text_elem("\n".join(copy_lines))
            separator()

            # 4. Correctifs (patches)
            patch_lines = [f"### 🛡️ {text.get(ctx, 'g_pvp_v2_library_patches')}"]
            uninstalled_patches = [p for p in patches if not p.get('installed')]
            if not patches:
                patch_lines.append(f"> *{text.get(ctx, 'g_pvp_v2_library_no_patches')}*")
            else:
                for p in patches:
                    st = "🛡️ **Installé**" if p.get('installed') else "📦 *Non installé*"
                    patch_lines.append(f"> • 🩹 **{p['family']}** · Empreinte : `{p['fingerprint']}` — {st}")
            text_elem("\n".join(patch_lines))

            # Boutons d'installation pour les patches non installés (max 2)
            for p in uninstalled_patches[:2]:
                inst_btn = discord.ui.Button(
                    label=text.get(ctx, 'g_pvp_v2_btn_install', fp=p['fingerprint']),
                    emoji="🛡️",
                    style=discord.ButtonStyle.success,
                    custom_id=f"root_net:install_{p['id']}",
                )
                inst_btn.callback = self._make_install_callback(p['id'])
                actions.append(inst_btn)

            btn_back_label = text.get(ctx, 'g_net_v2_btn_back')
            back_btn = discord.ui.Button(
                label=btn_back_label,
                emoji=e('retour'),
                style=discord.ButtonStyle.secondary,
                custom_id="root_net:back",
            )
            back_btn.callback = self._on_back
            actions.append(back_btn)

        else:
            header = text.get(ctx, 'g_net_v2_header', name=author_name.upper())
            sub = text.get(ctx, 'g_net_v2_sub', infra_name=infra_name)
            text_elem(f"## {e('terminal')} {header}\n-# {sub}")
            separator()

            infra_heading = text.get(ctx, 'g_net_v2_infra_title', infra_name=infra_name, level=infra_level)
            text_elem(f"### {e('materiel')} {infra_heading}")

            total_miners = sum(stats['bay_details'][t]['mining_count'] for t in range(1, 6))
            hashrate = stats.get('total_hashrate_formatted', '0 H/s')
            atk_power = stats.get('total_bits_per_s_formatted', '0 Bit/s')
            bay_def = stats.get('total_bay_defense', 0)
            net_def = stats.get('network_defense', 0)

            rate_per_min = Decimal(str(mining_state.get('rate_per_min', 0)))
            rtm_per_h = (rate_per_min * Decimal('60')).quantize(Decimal('0.00001'))
            rtm_h_str = text.format_rtm(rtm_per_h)

            bar_blocks = max(0, min(10, int(round(mem_pct / 10.0))))
            ram_bar = '▰' * bar_blocks + '▱' * (10 - bar_blocks)
            used_str = mining_state.get('memory_used_formatted', '0 o')
            total_ram_str = mining_state.get('total_ram_formatted', '0 o')
            pending_rtm = text.format_rtm(mining_state.get('buffer', 0))

            usd_str = text.format_usd(result.get('dollars') or 0)
            rtm_balance = f"{Decimal(str(result.get('rootium') or 0)):,.5f}"
            reputation = int(result.get('reputation') or 0)
            rep_bonus_pct = Decimal(str(reputation)) * Decimal('0.5')
            rep_bonus_str = f" *(+{rep_bonus_pct:.1f}% minage)*" if reputation > 0 else ""

            farm_line = text.get(ctx, 'g_net_v2_farm_stat', count=total_miners, hashrate=hashrate)
            compute_line = text.get(ctx, 'g_net_v2_compute_stat', power=atk_power)
            defense_line = text.get(ctx, 'g_net_v2_defense_stat', bay_def=bay_def, net_def=net_def)
            prod_line = text.get(ctx, 'g_net_v2_prod_stat', rate=rtm_h_str)
            mem_line = text.get(ctx, 'g_net_v2_memory_stat', bar=ram_bar, pct=f"{mem_pct:.1f}", used=used_str, total=total_ram_str)
            claim_line = text.get(ctx, 'g_net_v2_claim_stat', buffer=pending_rtm)
            balances_line = text.get(ctx, 'g_net_v2_balances_stat', usd=usd_str, rtm=rtm_balance, reputation=reputation, rep_bonus_str=rep_bonus_str)

            stats_block = (
                f"{e('ferme')} {farm_line}\n"
                f"{e('puissance')} {compute_line}\n"
                f"{e('firewall')} {defense_line}\n"
                f"{e('production')} {prod_line}\n"
                f"{e('memoire')} {mem_line}\n"
                f"{e('recolter')} {claim_line}\n"
                f"{e('dollars')} {balances_line}"
            )
            text_elem(stats_block)
            separator()

            status_lines = []
            pending_up = result.get('pending_upgrade')
            if pending_up:
                exp = pending_up.get('expires_at')
                up_ts = int(exp.replace(tzinfo=timezone.utc).timestamp()) if exp and hasattr(exp, 'timestamp') else 0
                status_lines.append(f"{e('temps')} Amélioration vers Niveau **{pending_up.get('target_level')}** en cours (<t:{up_ts}:R>)")

            pending_hack = result.get('pending_hack')
            if pending_hack:
                exp = pending_hack.get('expires_at')
                hack_ts = int(exp.replace(tzinfo=timezone.utc).timestamp()) if exp and hasattr(exp, 'timestamp') else 0
                atk_yield = int(pending_hack.get('atk_yield') or 0)
                status_lines.append(f"{e('temps')} Compilation de **{atk_yield} ATK** en cours (<t:{hack_ts}:R>)")

            pending_scan = result.get('pending_scan')
            if pending_scan:
                exp = pending_scan.get('expires_at')
                scan_ts = int(exp.replace(tzinfo=timezone.utc).timestamp()) if exp and hasattr(exp, 'timestamp') else 0
                status_lines.append(f"{e('scan')} Scan en cours sur <@{pending_scan.get('target_id')}> (<t:{scan_ts}:R>)")

            retaliations = result.get('retaliations') or []
            if retaliations:
                for r in retaliations[:2]:
                    rem_str = _format_retaliation_countdown(r.get('delete_at'))
                    status_lines.append(f"{e('alerte')} Riposte autorisée contre <@{r.get('attacker_id')}> ({rem_str})")

            pending_dev_jobs = result.get('pending_dev_jobs') or []
            for j in pending_dev_jobs:
                res_at = j.get('resolves_at')
                ts = int(res_at.replace(tzinfo=timezone.utc).timestamp()) if res_at and hasattr(res_at, 'timestamp') else 0
                fp_part = f" (`{j.get('fingerprint')}`)" if j.get('fingerprint') else ""
                status_lines.append(f"{e('temps')} Dev [{j['channel'].upper()}] `{j['job_type']}` · {j['family']} T{j['tier']}{fp_part} (<t:{ts}:R>)")

            if is_mem_full:
                status_lines.append(f"{e('alerte')} {text.get(ctx, 'g_net_v2_status_alert')}")

            if not status_lines:
                status_lines.append(f"{e('firewall')} {text.get(ctx, 'g_net_v2_status_operational')}")

            text_elem("\n".join(status_lines))

            buffer_val = Decimal(str(mining_state.get('buffer', 0)))
            has_buffer = buffer_val > 0
            btn_claim_label = text.get(ctx, 'g_net_v2_btn_claim')
            if has_buffer:
                claim_label = f"{btn_claim_label} ({pending_rtm} RTM)"
                claim_btn = discord.ui.Button(
                    label=claim_label[:80],
                    emoji=e('recolter'),
                    style=discord.ButtonStyle.success,
                    disabled=False,
                    custom_id="root_net:claim",
                )
            else:
                claim_btn = discord.ui.Button(
                    label=btn_claim_label,
                    emoji=e('recolter'),
                    style=discord.ButtonStyle.secondary,
                    disabled=True,
                    custom_id="root_net:claim_disabled",
                )
            claim_btn.callback = self._on_claim
            actions.append(claim_btn)

            btn_hw_label = text.get(ctx, 'g_net_v2_btn_hardware')
            hw_btn = discord.ui.Button(
                label=btn_hw_label,
                emoji=e('materiel'),
                style=discord.ButtonStyle.secondary,
                custom_id="root_net:hardware",
            )
            hw_btn.callback = self._on_hardware
            actions.append(hw_btn)

            sw_btn = discord.ui.Button(
                label=text.get(ctx, 'g_pvp_v2_btn_library'),
                emoji="💾",
                style=discord.ButtonStyle.secondary,
                custom_id="root_net:software",
            )
            sw_btn.callback = self._on_software
            actions.append(sw_btn)

        refresh_btn = discord.ui.Button(
            label=text.get(ctx, 'g_net_v2_btn_refresh'),
            emoji="🔄",
            style=discord.ButtonStyle.primary,
            custom_id="root_net:refresh",
        )
        refresh_btn.callback = self._on_refresh
        actions.append(refresh_btn)

        if actions:
            panel.add_item(discord.ui.ActionRow(*actions))

        self.add_item(panel)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                text.get(self.ctx, 'no_permission'),
                ephemeral=True,
            )
            return False
        return True

    async def _on_claim(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return
        checks = Check()
        allowed, err_key = await checks.check_interaction_access(self.cog.bot, interaction, allow_network=False)
        if not allowed:
            await interaction.response.send_message(text.get(self.ctx, err_key), ephemeral=True)
            return
        async with self.lock:
            await interaction.response.defer()
            try:
                claim_res = await self.cog.service.execute(
                    self.author_id,
                    interaction.guild.id if interaction.guild else None,
                    'claim',
                )
                if claim_res.get('claimed'):
                    amount = Decimal(str(claim_res.get('amount', 0)))
                    toast = text.get(self.ctx, 'g_net_claim_toast', amount=text.format_rtm(amount))
                    await interaction.followup.send(toast, ephemeral=True)
                    log_ctx = interaction if getattr(interaction, 'guild', None) else self.ctx
                    await log_claim_events(self.cog.bot, log_ctx, amount, claim_res)
            except Exception as err:
                if hasattr(err, 'key'):
                    err_msg = text.get(self.ctx, 'g_error_' + err.key, **getattr(err, 'values', {}))
                else:
                    err_msg = str(err)
                await interaction.followup.send(err_msg, ephemeral=True)
                return

            self.result = await self.cog.service.execute(
                self.author_id,
                interaction.guild.id if interaction.guild else None,
                'network',
            )
            self.rebuild()
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass

    async def _on_hardware(self, interaction: discord.Interaction):
        async with self.lock:
            self.detail = "hardware"
            self.rebuild()
            await interaction.response.edit_message(view=self)

    async def _on_software(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
            return
        async with self.lock:
            await interaction.response.defer()
            self.detail = "software"
            try:
                self.library_data = await self.cog.service.execute(
                    self.author_id,
                    interaction.guild.id if interaction.guild else None,
                    'pvp_v2_library',
                )
            except Exception:
                self.library_data = None
            self.rebuild()
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass

    def _make_install_callback(self, patch_id: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.author_id:
                await interaction.response.send_message(text.get(self.ctx, 'no_permission'), ephemeral=True)
                return
            async with self.lock:
                await interaction.response.defer()
                try:
                    await self.cog.service.execute(
                        self.author_id,
                        interaction.guild.id if interaction.guild else None,
                        'pvp_v2_install_patch',
                        patch_id=patch_id,
                    )
                    self.library_data = await self.cog.service.execute(
                        self.author_id,
                        interaction.guild.id if interaction.guild else None,
                        'pvp_v2_library',
                    )
                except Exception as exc:
                    logger.exception("Erreur lors de l'installation du patch")
                self.rebuild()
                try:
                    await interaction.message.edit(view=self)
                except Exception:
                    pass
        return callback

    async def _on_back(self, interaction: discord.Interaction):
        async with self.lock:
            self.detail = None
            self.rebuild()
            await interaction.response.edit_message(view=self)

    async def _on_refresh(self, interaction: discord.Interaction):
        async with self.lock:
            await interaction.response.defer()
            self.result = await self.cog.service.execute(
                self.author_id,
                interaction.guild.id if interaction.guild else None,
                'network',
            )
            self.rebuild()
            try:
                await interaction.message.edit(view=self)
            except Exception:
                pass

    async def on_timeout(self):
        for child in self.walk_children():
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


def _build_compact_total_lines(ctx, stats, firewall: int, mining_state: dict, result: dict, is_mem_full: bool, rep_val: int, rep_bonus_pct: Decimal) -> str:
    """Génère l'affichage compact, lisible et coloré en blockquotes pour la section Total Infrastructure."""
    is_fr = (text.get_locale(ctx) == 'fr')

    tot_atk = stats.get('total_bits_per_s_formatted') or MathConfig.format_bits_per_s(
        stats.get('total_bits_per_s', 0)
    )
    tot_bdef = f"{stats['total_bay_defense']} DEF"
    tot_ndef = f"{stats['network_defense']} DEF"
    hashrate = stats['total_hashrate_formatted']

    mem_pct = float(mining_state.get('memory_pct', 0))
    bar_blocks = max(0, min(10, int(round(mem_pct / 10.0))))
    ram_bar = '▰' * bar_blocks + '▱' * (10 - bar_blocks)
    used_str = mining_state.get('memory_used_formatted', '0 o')
    total_ram_str = mining_state.get('total_ram_formatted', '0 o')
    rate_str = text.format_rtm(mining_state.get('rate_per_min', 0))
    pending_str = text.format_rtm(mining_state.get('buffer', 0))
    fill_str = format_duration(mining_state.get('seconds_to_full', 0))

    rep_note = f", +{rep_bonus_pct:.1f}% rep" if rep_val > 0 else ""
    autoclaim_credits = int(result.get('autoclaim_credits', 0) or 0)
    autoclaim_active = int(result.get('autoclaim_active', 0) or 0)
    combo_saver_credits = int(result.get('combo_saver_credits', 0) or 0)

    lines = []
    if is_mem_full:
        lines.append(text.get(ctx, 'g_net_ram_alert'))

    if is_fr:
        lines.append(f"> ⚡ **Hashrate global** : `{hashrate}`")
        lines.append(f"> ⚔️ **Attaque** : `{tot_atk}`")
        lines.append(f"> 🛡️ **Défense** : `{tot_bdef}` *(Baies)* · `{tot_ndef}` *(Réseau)*")
        lines.append(f"> 🧠 **Mémoire vive** : {ram_bar} **{mem_pct:.1f}%** (`{used_str} / {total_ram_str}`)")
        if is_mem_full:
            lines.append(f"> 🪙 **À récolter** : **{pending_str} RTM** · 🔴 **SATURÉ**")
        else:
            lines.append(f"> ⏱️ **Plein dans** : **{fill_str}** *({rate_str} RTM/min{rep_note})*")
            lines.append(f"> 🪙 **À récolter** : **{pending_str} RTM**")

        if autoclaim_active > 0:
            lines.append(f"> 🎫 **Autoclaim** : **{autoclaim_credits}** en réserve · **{autoclaim_active}** programmé(s)")
        else:
            lines.append(f"> 🎫 **Autoclaim** : **{autoclaim_credits}** crédit(s) en réserve")
        lines.append(f"> 🛡️ **Combo Saver** : **{combo_saver_credits}** crédit(s) en réserve")
    else:
        lines.append(f"> ⚡ **Global Hashrate**: `{hashrate}`")
        lines.append(f"> ⚔️ **Attack**: `{tot_atk}`")
        lines.append(f"> 🛡️ **Defense**: `{tot_bdef}` *(Bays)* · `{tot_ndef}` *(Network)*")
        lines.append(f"> 🧠 **Memory (RAM)**: {ram_bar} **{mem_pct:.1f}%** (`{used_str} / {total_ram_str}`)")
        if is_mem_full:
            lines.append(f"> 🪙 **To claim**: **{pending_str} RTM** · 🔴 **FULL**")
        else:
            lines.append(f"> ⏱️ **Full in**: **{fill_str}** *({rate_str} RTM/min{rep_note})*")
            lines.append(f"> 🪙 **To claim**: **{pending_str} RTM**")

        if autoclaim_active > 0:
            lines.append(f"> 🎫 **Autoclaim**: **{autoclaim_credits}** in reserve · **{autoclaim_active}** queued")
        else:
            lines.append(f"> 🎫 **Autoclaim**: **{autoclaim_credits}** credit(s) in reserve")
        lines.append(f"> 🛡️ **Combo Saver**: **{combo_saver_credits}** credit(s) in reserve")

    return '\n'.join(lines)


class Network(BaseGameCog):
    """Cog gérant la commande centrale /network et l'affichage du profil joueur."""

    def __init__(self, bot):
        self.bot = bot
        self.check_secret_rotation_loop.change_interval(seconds=_secret_id_check_interval())
        # Les tests d'embed isolés n'ont pas de boucle asyncio : ne pas démarrer alors.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            self.check_secret_rotation_loop.start()

    def cog_unload(self):
        """Arrête proprement la tâche périodique de rotation au déchargement du Cog."""
        self.check_secret_rotation_loop.cancel()

    @tasks.loop(seconds=_secret_id_check_interval())
    async def check_secret_rotation_loop(self):
        """Vérifie périodiquement si la rotation globale des secret ID est due."""
        try:
            result = await self.service.rotate_secret_ids_if_due()
            if result and result.get('rotated'):
                logger.info(
                    "%d identifiant(s) secret(s) régénéré(s), prochaine rotation %s",
                    result.get('count', 0),
                    result.get('next_at'),
                )
        except Exception:
            logger.exception("Erreur lors de la rotation des identifiants secrets")

    @check_secret_rotation_loop.before_loop
    async def before_check_secret_rotation_loop(self):
        """Attend que le bot soit prêt, puis rattrape immédiatement une rotation échue."""
        await self.bot.wait_until_ready()
        try:
            await self.service.rotate_secret_ids_if_due()
        except Exception:
            logger.exception("Erreur lors du rattrapage de rotation des identifiants secrets")

    # ── Slash ────────────────────────────────────────────────────────────────
    @discord.slash_command(
        name='network',
        description=EN['network'],
        description_localizations={"fr": FR['network']},
        guild_ids=data.GUILD_WHITELIST or None,
    )
    async def network(self, ctx):
        """Commande Slash /network."""
        await self._invoke(ctx, 'network')

    # ── Préfixe ──────────────────────────────────────────────────────────────
    @commands.command(name='network', aliases=['n'], help=FR['network'])
    async def prefix_network(self, ctx):
        """Commande préfixe !network ou !n."""
        await self._invoke(ctx, 'network')

    # ── Rendu de l'Embed ─────────────────────────────────────────────────────
    def _build_network_embed(self, ctx, result):
        """Construit l'Embed d'affichage complet du réseau joueur à partir du dictionnaire de résultat.

        Mise en forme des données :
        - Précision monétaire stricte : 2 décimales pour les USD, 5 décimales pour le RTM.
        - Barre de Firewall : 5 segments '▰' pleins ou '▱' vides représentant les niveaux 1 à 5.
        - Date de création formatée avec le timestamp Discord (<t:...:D>).
        - Matrice des baies : pour chaque tier de 1 à 6, affiche le nombre de modules installés.
        """
        author = getattr(ctx, 'author', None) or getattr(ctx, 'user', None)
        author_name = getattr(author, 'display_name', str(result.get('discord_id', '')))
        avatar_url = author.display_avatar.url if author and hasattr(author, 'display_avatar') else None

        # Formatage des montants monétaires et statistiques numériques
        usd      = text.format_usd(result.get('dollars') or 0)
        rtm      = f"{Decimal(str(result.get('rootium') or 0)):,.5f}"
        firewall = int(result.get('firewall_level') or 0)
        # Jauge graphique de 5 blocs
        bar      = '▰' * max(0, min(firewall, 5)) + '▱' * (5 - max(0, min(firewall, 5)))
        stats = result.get('stats') or MathConfig.calculate_player_stats(result)
        defense  = stats.get('total_defense', stats['network_defense'] + stats['total_bay_defense'])
        reputation = int(result.get('reputation') or 0)

        # Date de création du réseau (stockée en UTC naïf dans la BDD)
        created = result.get('created_at')
        if hasattr(created, 'timestamp'):
            created_ts = int(created.replace(tzinfo=timezone.utc).timestamp()) if created.tzinfo is None else int(created.timestamp())
            created_str = f"<t:{created_ts}:D>"
        else:
            created_str = str(created) if created else "?"

        # Calcul du minage et saturation mémoire vive pour coloration d'alerte
        mining_state = result.get('mining_state')
        if mining_state is None:
            mining_state = MathConfig.compute_mining_progress(result, stats, datetime.now(timezone.utc))
        mem_pct = float(mining_state.get('memory_pct', 0))
        is_mem_full = mem_pct >= 100.0 or bool(mining_state.get('is_full'))
        embed_color = discord.Color.from_rgb(255, 170, 0) if is_mem_full else discord.Color.from_rgb(0, 220, 200)

        # Construction de l'Embed Discord aux couleurs cyber (Cyan #00DCC8 ou Orange Alerte #FFAA00)
        embed = discord.Embed(
            description=text.get(ctx, 'g_net_status', created=created_str) + '\n\u200b',
            color=embed_color,
            timestamp=discord.utils.utcnow(),
        )
        if author:
            embed.set_author(name=text.get(ctx, 'g_net_author', name=author_name), icon_url=avatar_url)
            if avatar_url:
                embed.set_thumbnail(url=avatar_url)

        rep_val = int(result.get('reputation') or 0)
        rep_bonus_pct = Decimal(str(rep_val)) * Decimal('0.5')
        rep_bonus_str = f" *(+{rep_bonus_pct:.1f}% minage)*" if rep_val > 0 else ""

        # Champs principaux : 2 colonnes aérées pour éviter tout retour à la ligne forcé
        embed.add_field(
            name=text.get(ctx, 'g_net_economy'),
            value=text.get(ctx, 'g_net_economy_desc', usd=usd, rtm=rtm, reputation=reputation, rep_bonus_str=rep_bonus_str),
            inline=True,
        )

        # Sécurité & Système (avec statut d'amélioration directement rattaché au pare-feu)
        pending_up = result.get('pending_upgrade')
        defense_lines = [text.get(ctx, 'g_net_firewall', firewall=firewall, bar=bar)]
        if pending_up:
            exp = pending_up.get('expires_at')
            if exp and hasattr(exp, 'timestamp'):
                up_ts = int(exp.replace(tzinfo=timezone.utc).timestamp()) if exp.tzinfo is None else int(exp.timestamp())
            else:
                up_ts = 0
            defense_lines.append(text.get(ctx, 'g_net_upgrade_progress', level=pending_up.get('target_level'), timestamp=up_ts))
        defense_lines.append(text.get(ctx, 'g_net_network_defense', defense=defense))
        embed.add_field(name=text.get(ctx, 'g_net_defense'), value='\n'.join(defense_lines), inline=True)

        # Identifiant secret (pleine largeur) entre sécurité et baies — uniquement si présent
        secret_id = result.get('secret_id_display') or result.get('secret_id')
        secret_ts = result.get('secret_next_ts')
        if secret_id is not None and secret_ts is not None:
            embed.add_field(
                name=text.get(ctx, 'g_net_secret_name'),
                value=text.get(ctx, 'g_net_secret_desc', secret_id=secret_id, timestamp=secret_ts),
                inline=False,
            )

        # Stock ATK + production /compile en cours (pleine largeur, après le secret)
        atk_stock = int(result.get('attack_points') or 0)
        atk_lines = [text.get(ctx, 'g_net_atk_stock', atk=atk_stock)]
        pending_hack = result.get('pending_hack')
        if pending_hack:
            exp = pending_hack.get('expires_at')
            if exp and hasattr(exp, 'timestamp'):
                hack_ts = int(exp.replace(tzinfo=timezone.utc).timestamp()) if exp.tzinfo is None else int(exp.timestamp())
            else:
                hack_ts = int(pending_hack.get('timestamp') or 0)
            method_key = pending_hack.get('method') or 'unskilled'
            method_label = text.get(ctx, f'g_compile_method_{method_key}')
            atk_lines.append(text.get(
                ctx, 'g_net_hack_progress',
                method=method_label,
                atk=int(pending_hack.get('atk_yield') or 0),
                timestamp=hack_ts,
            ))

        # Scan en cours
        pending_scan = result.get('pending_scan')
        if pending_scan:
            exp = pending_scan.get('expires_at')
            if exp and hasattr(exp, 'timestamp'):
                scan_ts = int(exp.replace(tzinfo=timezone.utc).timestamp()) if exp.tzinfo is None else int(exp.timestamp())
            else:
                scan_ts = 0
            target_id = pending_scan.get('target_id')
            atk_lines.append(text.get(
                ctx, 'g_net_scan_progress',
                target=f"<@{target_id}>",
                timestamp=scan_ts,
            ))

        # Ripostes autorisées (affichées dans tous les cas avec identité de l'agresseur)
        retaliations = result.get('retaliations') or []
        if retaliations:
            seen = {}
            for r in retaliations:
                aid = r.get('attacker_id')
                dt = r.get('delete_at')
                if aid not in seen or (dt and dt > seen[aid]):
                    seen[aid] = dt
            for aid, dt in list(seen.items())[:3]:
                rem_str = _format_retaliation_countdown(dt)
                atk_lines.append(text.get(
                    ctx, 'g_net_retaliation_identified',
                    target=f"<@{aid}>",
                    remaining=rem_str,
                ))

        embed.add_field(
            name=text.get(ctx, 'g_net_atk'),
            value='\n'.join(atk_lines),
            inline=False,
        )

        # Infrastructure matérielle : Pleine largeur (inline=False)
        max_tier_unlocked = max(1, min(5, firewall + 1))
        bay_entries = []
        for tier in range(1, 6):
            bay = stats['bay_details'][tier]
            m_count = bay['mining_count']
            a_count = bay['attack_count']
            d_count = bay['bay_defense_count']

            # Afficher la baie si elle est débloquée à l'achat pour ce pare-feu,
            # OU si le joueur possède déjà au moins un module dans cette baie (ex: capture PvP via /hack).
            if tier <= max_tier_unlocked or m_count > 0 or a_count > 0 or d_count > 0:
                m_hs = MathConfig.format_hashrate(bay['mining_hashrate'])
                a_pow = MathConfig.format_bits_per_s(bay.get('attack_bits_per_s', 0))
                d_pow = f"{bay['bay_defense_power']} DEF"

                bay_entries.append(
                    f"> {text.get(ctx, 'g_net_rack_bay_title', tier=tier)}\n"
                    f"> {text.get(ctx, 'g_net_rack_bay_stats', m_count=m_count, m_power=m_hs, a_count=a_count, a_power=a_pow, d_count=d_count, d_power=d_pow)}"
                )

        embed.add_field(
            name=text.get(ctx, 'g_net_bays'),
            value='\n\n'.join(bay_entries),
            inline=False,
        )

        # Récapitulatif Total prenant toute la largeur en dessous (inline=False)
        total_text = _build_compact_total_lines(
            ctx=ctx,
            stats=stats,
            firewall=firewall,
            mining_state=mining_state,
            result=result,
            is_mem_full=is_mem_full,
            rep_val=rep_val,
            rep_bonus_pct=rep_bonus_pct,
        )

        embed.add_field(
            name=text.get(ctx, 'g_net_rack_total_title'),
            value=total_text,
            inline=False,
        )

        # Pied de page avec identifiant joueur et logo du bot
        bot_user = getattr(ctx, 'bot', None) and getattr(ctx.bot, 'user', None)
        bot_avatar = bot_user.display_avatar.url if bot_user and hasattr(bot_user, 'display_avatar') else None
        embed.set_footer(text=text.get(ctx, 'g_net_footer', discord_id=result.get('discord_id', '')), icon_url=bot_avatar)
        return embed

    async def _send(self, ctx, method, result):
        """Envoie le panneau Discord Components V2 d'affichage de l'infrastructure joueur."""
        guild = getattr(ctx, 'guild', None)
        emojis = {}
        if guild and hasattr(guild, 'emojis'):
            try:
                emojis = select_emojis(guild.emojis)
            except Exception:
                emojis = {}

        infra_level = int(result.get('infrastructure_level', result.get('firewall_level', 0)) or 0)
        img_path = get_infrastructure_image_path(infra_level)

        files = []
        image_url = None
        if img_path:
            filename = f"infrastructure-{infra_level}.png"
            file = discord.File(str(img_path), filename=filename)
            files.append(file)
            image_url = f"attachment://{filename}"

        view = NetworkDesignerView(self, ctx, result, emojis=emojis, image_url=image_url)
        kwargs = {'view': view, 'allowed_mentions': discord.AllowedMentions.none()}
        if files:
            kwargs['files'] = files

        if getattr(ctx, 'interaction', None):
            msg = await ctx.respond(**kwargs)
        else:
            msg = await ctx.send(**kwargs)
        view.message = getattr(msg, 'message', None) or msg

        if result.get('is_new'):
            await Logger(self.bot).log_new_player(ctx, result)
            await self._send_welcome_language(ctx)

    async def _send_welcome_language(self, ctx):
        """Propose le choix de langue au tout premier réseau, puis l'intro events / buy."""
        prompt_lang = _slash_or_english(ctx)
        prefix = _command_prefix(ctx)
        author = getattr(ctx, 'author', None) or getattr(ctx, 'user', None)
        view = WelcomeLanguageView(author.id, prompt_lang, prefix)
        content = text.get_for_lang(prompt_lang, 'g_welcome_lang_pick')
        send_kwargs = {
            'content': content,
            'view': view,
            'allowed_mentions': discord.AllowedMentions.none(),
        }
        if getattr(ctx, 'interaction', None):
            msg = await ctx.followup.send(**send_kwargs)
        else:
            msg = await ctx.send(**send_kwargs)
        view.message = getattr(msg, 'message', None) or msg


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Network(bot))
