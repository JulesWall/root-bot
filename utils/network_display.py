"""
Root OS - Rendu visuel du poste de commande /network.

Implémente les 4 vues unifiées :
1. Accueil (Overview) : identité, état, minage, ressources, infrastructure intégrée, progression.
2. Ferme (Farm) : débits, mémoire, détails des mineurs par tier, automatisation.
3. Matériel (Hardware) : inventaire Minage, Attaque, Défense par tier, totaux et accès d'achat.
4. Opérations (Operations) : stock ATK, détail modules ATK/DEF par tier, préparatifs, attaques et représailles.

Chacune des quatre vues inclut obligatoirement l'illustration du niveau courant d'infrastructure.
"""

from decimal import Decimal
import math
from typing import Any
import discord

from game.math_config import MathConfig
from utils import text
from utils.infrastructure_display import (
    get_infrastructure_attachment_url,
    get_infrastructure_file,
    get_infrastructure_name,
    sanitize_level,
)
from utils.root_emojis import get_emoji
from utils.root_theme import (
    COLOR_AMBER,
    COLOR_TURQUOISE,
    VisualState,
    build_footer_text,
)
from utils.time_format import format_duration, to_utc_timestamp


def _get_avatar_url(author: Any) -> str | None:
    if author and hasattr(author, 'display_avatar') and author.display_avatar:
        return author.display_avatar.url
    return None


def _format_time_relative(dt_or_ts: Any) -> str:
    """Convertit une datetime ou un timestamp Unix en format Discord relatif <t:...:R>."""
    if dt_or_ts is None:
        return "N/A"
    ts = to_utc_timestamp(dt_or_ts)
    return f"<t:{ts}:R>" if ts else "N/A"


def _format_time_short(dt_or_ts: Any) -> str:
    """Convertit une datetime ou un timestamp Unix en format Discord date/heure courte <t:...:f>."""
    if dt_or_ts is None:
        return "N/A"
    ts = to_utc_timestamp(dt_or_ts)
    return f"<t:{ts}:f>" if ts else "N/A"


def _build_ram_gauge(pct: float) -> str:
    """Construit une jauge mémoire de 10 blocs ▰ / ▱."""
    blocks = max(0, min(10, int(round(pct / 10.0))))
    return '▰' * blocks + '▱' * (10 - blocks)


# ─────────────────────────────────────────────────────────────────────────────
# VUE 1 : ACCUEIL (OVERVIEW)
# ─────────────────────────────────────────────────────────────────────────────

def build_overview_embed(
    result: dict,
    locale: str = 'fr',
    display_name: str = 'Opérateur',
    avatar_url: str | None = None,
) -> tuple[discord.Embed, discord.File | None]:
    """Construit l'embed et le fichier d'illustration pour la vue Accueil."""
    is_fr = (locale == 'fr')
    level = sanitize_level(result.get('firewall_level', 0))
    infra_name = get_infrastructure_name(level, locale=locale)

    stats = result.get('stats') or MathConfig.calculate_player_stats(result)
    mining_state = result.get('mining_state') or {}
    buffer_rtm = Decimal(str(mining_state.get('buffer', 0)))
    mem_pct = float(mining_state.get('memory_pct', 0))
    is_mem_full = bool(mining_state.get('is_full') or mem_pct >= 100.0)

    # Vérification présence de mineurs
    total_miners = sum(stats.get('bay_details', {}).get(t, {}).get('mining_count', 0) for t in range(1, 6))

    # État du minage & couleur
    if is_mem_full:
        mining_status = "Mémoire pleine · Récolte disponible" if is_fr else "Memory full · Claim available"
        color = COLOR_AMBER
    elif total_miners == 0:
        mining_status = "Aucun mineur installé · Ouvre Matériel pour t'équiper" if is_fr else "No miners installed · Open Hardware to equip"
        color = COLOR_TURQUOISE
    else:
        mining_status = "Production active" if is_fr else "Mining active"
        color = COLOR_TURQUOISE

    embed = discord.Embed(
        title=None,
        description=f"**{infra_name}** · {'Infrastructure' if is_fr else 'Infrastructure'} {level}/5\n*{mining_status}*",
        color=color,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_author(
        name=f"ROOT OS · {'Réseau de' if is_fr else 'Network of'} {display_name}",
        icon_url=avatar_url,
    )

    # 1. Ferme
    rate_per_min = Decimal(str(mining_state.get('rate_per_min', 0)))
    hourly_rtm = rate_per_min * Decimal('60')
    hashrate_str = stats.get('total_hashrate_formatted') or MathConfig.format_hashrate(stats.get('total_hashrate_hs', 0))
    rep_val = int(result.get('reputation') or 0)
    rep_pct = Decimal(str(rep_val)) * Decimal('0.5')

    farm_lines = [
        f"{get_emoji('root_puissance', True)}**Hashrate** : `{hashrate_str}`",
        f"{get_emoji('root_production', True)}**{'Production' if is_fr else 'Production'}** : `{text.format_rtm(hourly_rtm)} RTM/h`",
    ]
    if rep_val > 0:
        farm_lines.append(f"{get_emoji('root_production', True)}**{'Bonus de réputation' if is_fr else 'Reputation bonus'}** : `+{rep_pct:.1f}%`")
    embed.add_field(
        name=f"{get_emoji('root_ferme', True)}{'Ferme' if is_fr else 'Farm'}",
        value='\n'.join(farm_lines),
        inline=False,
    )

    # 2. Récolte et mémoire
    ram_gauge = _build_ram_gauge(mem_pct)
    used_ram = mining_state.get('memory_used_formatted', '0 o')
    total_ram = mining_state.get('total_ram_formatted', '0 o')
    fill_seconds = int(mining_state.get('seconds_to_full', 0) or 0)

    claim_lines = [
        f"{get_emoji('root_memoire', True)}**{'À récolter' if is_fr else 'To claim'}** : **{text.format_rtm(buffer_rtm)} RTM**",
        f"{get_emoji('root_memoire', True)}**{'Mémoire' if is_fr else 'Memory'}** : {ram_gauge} **{mem_pct:.1f}%** (`{used_ram} / {total_ram}`)",
    ]
    if total_miners > 0 and not is_mem_full and fill_seconds > 0:
        claim_lines.append(f"{get_emoji('root_temps', True)}**{'Plein dans' if is_fr else 'Full in'}** : `{format_duration(fill_seconds)}`")
    embed.add_field(
        name=f"{get_emoji('root_recolter', True)}{'Récolte et mémoire' if is_fr else 'Claim and memory'}",
        value='\n'.join(claim_lines),
        inline=False,
    )

    # 3. Ressources (Portefeuille)
    usd_str = text.format_usd(result.get('dollars') or 0)
    rtm_wallet = Decimal(str(result.get('rootium') or 0))
    embed.add_field(
        name=f"{get_emoji('root_bilan', True)}{'Ressources' if is_fr else 'Resources'}",
        value=f"{get_emoji('root_bilan', True)}**Solde USD** : `{usd_str}`\n{get_emoji('root_memoire', True)}**Portefeuille RTM** : `{text.format_rtm(rtm_wallet)} RTM`",
        inline=False,
    )

    # 4. Infrastructure et protection
    ndef = int(stats.get('network_defense', 0))
    bdef = int(stats.get('total_bay_defense', 0))
    tdef = int(stats.get('total_defense', ndef + bdef))
    max_tier_unlocked = max(1, min(5, level + 1))
    event_mult = level + 1
    hourly_mult = level + 1
    settings = MathConfig.load()
    base_detect = settings.get('pvp', {}).get('scan', {}).get('base_detection_chance', 0.20)
    detect_pct = int(round(base_detect * 100))

    protect_lines = [
        f"{get_emoji('root_firewall', True)}**{'Défense' if is_fr else 'Defense'}** : `{ndef} DEF` *({infra_name})* + `{bdef} DEF` *({'Modules' if is_fr else 'Modules'})* = **{tdef} DEF**",
        f"{get_emoji('root_materiel', True)}**{'Accès modules' if is_fr else 'Module access'}** : `T1` {'à' if is_fr else 'to'} `T{max_tier_unlocked}`",
        f"{get_emoji('root_connexions', True)}**{'Multiplicateurs' if is_fr else 'Multipliers'}** : `x{hourly_mult}` {'horaire/contrats' if is_fr else 'hourly/contracts'} · `x{event_mult}` {'events' if is_fr else 'events'}",
        f"{get_emoji('root_scan', True)}**{'Détection des scans' if is_fr else 'Scan detection'}** : `{detect_pct}%`",
    ]
    embed.add_field(
        name=f"{get_emoji('root_connexions', True)}{'Infrastructure et protection' if is_fr else 'Infrastructure and protection'}",
        value='\n'.join(protect_lines),
        inline=False,
    )

    # 5. Identifiant réseau
    secret_id = result.get('secret_id') or "------"
    secret_next_ts = result.get('secret_next_ts')
    next_rot_str = f"<t:{secret_next_ts}:R>" if secret_next_ts else ("Inconnue" if is_fr else "Unknown")
    embed.add_field(
        name=f"{get_emoji('root_terminal', True)}{'Identifiant réseau' if is_fr else 'Network identifier'}",
        value=f"{get_emoji('root_terminal', True)}**Secret ID** : ||`{secret_id}`||\n{get_emoji('root_temps', True)}**{'Prochaine rotation' if is_fr else 'Next rotation'}** : {next_rot_str}",
        inline=False,
    )

    # 6. Progression de l'infrastructure
    pending_up = result.get('pending_upgrade')
    if pending_up:
        target_lvl = sanitize_level(pending_up.get('target_level', level + 1))
        target_name = get_infrastructure_name(target_lvl, locale=locale)
        target_ts = _format_time_relative(pending_up.get('resolves_at'))
        prog_text = f"{get_emoji('root_connexions', True)}**{'Amélioration en cours' if is_fr else 'Upgrade in progress'}** : {target_name} *(Niveau {target_lvl})*\n{get_emoji('root_temps', True)}**{'Prêt' if is_fr else 'Ready'}** : {target_ts}"
    elif level < 5:
        next_lvl = level + 1
        next_name = get_infrastructure_name(next_lvl, locale=locale)
        prog_text = f"{get_emoji('root_connexions', True)}**{'Prochain niveau' if is_fr else 'Next level'}** : {next_name} *(Niveau {next_lvl}/5)*\n*Ouvre le devis via le bouton Améliorer ci-dessous.*" if is_fr else f"{get_emoji('root_connexions', True)}**Next level** : {next_name} *(Level {next_lvl}/5)*\n*Open quote via the Upgrade button below.*"
    else:
        prog_text = f"{get_emoji('root_connexions', True)}**Infrastructure maximale atteinte (Niveau 5/5)**" if is_fr else f"{get_emoji('root_connexions', True)}**Maximum infrastructure level reached (Level 5/5)**"

    embed.add_field(
        name=f"{get_emoji('root_connexions', True)}{'Progression' if is_fr else 'Progression'}",
        value=prog_text,
        inline=False,
    )

    # 7. En cours (synthèse des opérations en tâche de fond)
    active_tasks = []
    pending_compile = result.get('pending_hack')  # Compilation ATK
    if pending_compile:
        comp_atk = pending_compile.get('attack_points', 0)
        comp_rel = _format_time_relative(pending_compile.get('resolves_at'))
        active_tasks.append(f"{get_emoji('root_materiel', True)}**{'Compilation' if is_fr else 'Compilation'}** : `{comp_atk} ATK` · {comp_rel}")

    pending_scan = result.get('pending_scan')
    if pending_scan:
        scan_rel = _format_time_relative(pending_scan.get('resolves_at') or pending_scan.get('expires_at'))
        tgt_id = pending_scan.get('target_id')
        tgt_str = f" contre <@{tgt_id}>" if tgt_id else ""
        active_tasks.append(f"{get_emoji('root_scan', True)}**{'Scan PvP' if is_fr else 'PvP Scan'}**{tgt_str} : {scan_rel}")

    outgoing_attacks = result.get('outgoing_pvp_attacks') or []
    if outgoing_attacks:
        active_tasks.append(f"{get_emoji('root_operations', True)}**{'Attaques lancées' if is_fr else 'Outgoing attacks'}** : `{len(outgoing_attacks)}` {'en cours' if is_fr else 'active'}")

    retaliations = result.get('retaliations') or []
    if retaliations:
        retal_tgt = retaliations[0].get('attacker_id')
        active_tasks.append(f"{get_emoji('root_alerte', True)}**{'Riposte autorisée' if is_fr else 'Retaliation ready'}** : <@{retal_tgt}>")

    if active_tasks:
        embed.add_field(
            name=f"{get_emoji('root_operations', True)}{'Tâches en cours' if is_fr else 'Active tasks'}",
            value='\n'.join(active_tasks),
            inline=False,
        )

    # Image d'illustration et Footer
    embed.set_image(url=get_infrastructure_attachment_url(level))
    embed.set_footer(text=build_footer_text('Accueil' if is_fr else 'Overview'))

    file = get_infrastructure_file(level)
    return embed, file


# ─────────────────────────────────────────────────────────────────────────────
# VUE 2 : FERME (FARM)
# ─────────────────────────────────────────────────────────────────────────────

def build_farm_embed(
    result: dict,
    locale: str = 'fr',
    display_name: str = 'Opérateur',
    avatar_url: str | None = None,
) -> tuple[discord.Embed, discord.File | None]:
    """Construit l'embed et le fichier d'illustration pour la vue Ferme."""
    is_fr = (locale == 'fr')
    level = sanitize_level(result.get('firewall_level', 0))

    stats = result.get('stats') or MathConfig.calculate_player_stats(result)
    mining_state = result.get('mining_state') or {}
    buffer_rtm = Decimal(str(mining_state.get('buffer', 0)))
    mem_pct = float(mining_state.get('memory_pct', 0))
    is_mem_full = bool(mining_state.get('is_full') or mem_pct >= 100.0)

    color = COLOR_AMBER if is_mem_full else COLOR_TURQUOISE

    embed = discord.Embed(
        title=None,
        description="Production et stockage de ta ferme" if is_fr else "Production and storage of your farm",
        color=color,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_author(
        name=f"ROOT OS · {'Réseau de' if is_fr else 'Network of'} {display_name}",
        icon_url=avatar_url,
    )

    # 1. Production
    rate_per_min = Decimal(str(mining_state.get('rate_per_min', 0)))
    hourly_rtm = rate_per_min * Decimal('60')
    hashrate_str = stats.get('total_hashrate_formatted') or MathConfig.format_hashrate(stats.get('total_hashrate_hs', 0))
    rep_val = int(result.get('reputation') or 0)
    rep_pct = Decimal(str(rep_val)) * Decimal('0.5')

    prod_lines = [
        f"{get_emoji('root_puissance', True)}**Hashrate global** : `{hashrate_str}`",
        f"{get_emoji('root_production', True)}**{'Débit réel' if is_fr else 'Actual rate'}** : `{text.format_rtm(hourly_rtm)} RTM/h` *({text.format_rtm(rate_per_min)} RTM/min)*",
    ]
    if rep_val > 0:
        prod_lines.append(f"⭐ **{'Bonus de réputation' if is_fr else 'Reputation bonus'}** : `+{rep_pct:.1f}%`")
    embed.add_field(
        name=f"{get_emoji('root_ferme', True)}{'Production de minage' if is_fr else 'Mining production'}",
        value='\n'.join(prod_lines),
        inline=False,
    )

    # 2. Stockage et récolte
    ram_gauge = _build_ram_gauge(mem_pct)
    used_ram = mining_state.get('memory_used_formatted', '0 o')
    total_ram = mining_state.get('total_ram_formatted', '0 o')
    fill_seconds = int(mining_state.get('seconds_to_full', 0) or 0)

    claim_lines = [
        f"{get_emoji('root_recolter', True)}**{'À récolter' if is_fr else 'To claim'}** : **{text.format_rtm(buffer_rtm)} RTM**",
        f"{get_emoji('root_memoire', True)}**{'Mémoire vive' if is_fr else 'RAM Memory'}** : {ram_gauge} **{mem_pct:.1f}%** (`{used_ram} / {total_ram}`)",
    ]
    if is_mem_full:
        claim_lines.append("🔴 **Mémoire saturée · La récolte libère le stockage.**" if is_fr else "🔴 **Memory full · Claiming frees storage.**")
    elif fill_seconds > 0:
        claim_lines.append(f"{get_emoji('root_temps', True)}**{'Temps avant saturation' if is_fr else 'Time until full'}** : `{format_duration(fill_seconds)}`")
    embed.add_field(
        name=f"📦 {'Stockage et mémoire' if is_fr else 'Storage and memory'}",
        value='\n'.join(claim_lines),
        inline=False,
    )

    # 3. Mineurs par tier
    bay_details = stats.get('bay_details', {})
    miner_lines = []
    for tier in range(1, 6):
        bay = bay_details.get(tier, {})
        m_count = bay.get('mining_count', 0)
        if m_count > 0:
            m_hs = MathConfig.format_hashrate(bay.get('mining_hashrate', 0))
            m_ram = bay.get('mining_ram_formatted', '0 o')
            miner_lines.append(f"• **T{tier}** · `×{m_count}` · `{m_hs}` · `+{m_ram}`")

    if not miner_lines:
        miner_lines.append("Aucun mineur installé. Ouvre Matériel pour consulter la boutique." if is_fr else "No miners installed. Open Hardware to view the shop.")

    embed.add_field(
        name=f"⛏️ {'Mineurs installés' if is_fr else 'Installed miners'}",
        value='\n'.join(miner_lines),
        inline=False,
    )

    # 4. Automatisation
    autoclaim_credits = int(result.get('autoclaim_credits', 0) or 0)
    autoclaim_active = int(result.get('autoclaim_active', 0) or 0)
    combo_saver_credits = int(result.get('combo_saver_credits', 0) or 0)

    auto_lines = [
        f"🎫 **Autoclaim** : `{autoclaim_credits}` {'en réserve' if is_fr else 'in reserve'} · `{autoclaim_active}` {'programmé(s)' if is_fr else 'active'}",
        f"🛡️ **Combo Saver** : `{combo_saver_credits}` {'crédit(s) en réserve' if is_fr else 'credit(s) in reserve'}",
    ]
    embed.add_field(
        name=f"⚙️ {'Automatisation' if is_fr else 'Automation'}",
        value='\n'.join(auto_lines),
        inline=False,
    )

    embed.set_image(url=get_infrastructure_attachment_url(level))
    embed.set_footer(text=build_footer_text('Ferme' if is_fr else 'Farm'))

    file = get_infrastructure_file(level)
    return embed, file


# ─────────────────────────────────────────────────────────────────────────────
# VUE 3 : MATÉRIEL (HARDWARE)
# ─────────────────────────────────────────────────────────────────────────────

def build_hardware_embed(
    result: dict,
    locale: str = 'fr',
    display_name: str = 'Opérateur',
    avatar_url: str | None = None,
) -> tuple[discord.Embed, discord.File | None]:
    """Construit l'embed et le fichier d'illustration pour la vue Matériel."""
    is_fr = (locale == 'fr')
    level = sanitize_level(result.get('firewall_level', 0))
    stats = result.get('stats') or MathConfig.calculate_player_stats(result)
    bay_details = stats.get('bay_details', {})

    embed = discord.Embed(
        title=None,
        description="Équipements installés · Quantités regroupées par tier" if is_fr else "Installed equipment · Quantities grouped by tier",
        color=COLOR_TURQUOISE,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_author(
        name=f"ROOT OS · {'Réseau de' if is_fr else 'Network of'} {display_name}",
        icon_url=avatar_url,
    )

    # 1. Modules de Minage
    mining_lines = []
    for tier in range(1, 6):
        bay = bay_details.get(tier, {})
        count = bay.get('mining_count', 0)
        if count > 0:
            hs = MathConfig.format_hashrate(bay.get('mining_hashrate', 0))
            ram = bay.get('mining_ram_formatted', '0 o')
            mining_lines.append(f"• **T{tier}** · `×{count}` · `{hs}` · `+{ram}`")
    if not mining_lines:
        mining_lines.append("Aucun module installé" if is_fr else "No modules installed")
    embed.add_field(
        name=f"{get_emoji('root_ferme', True)}{'Minage' if is_fr else 'Mining'}",
        value='\n'.join(mining_lines),
        inline=False,
    )

    # 2. Modules d'Attaque
    atk_lines = []
    for tier in range(1, 6):
        bay = bay_details.get(tier, {})
        count = bay.get('attack_count', 0)
        if count > 0:
            pow_str = MathConfig.format_bits_per_s(bay.get('attack_bits_per_s', 0))
            atk_lines.append(f"• **T{tier}** · `×{count}` · `{pow_str}`")
    if not atk_lines:
        atk_lines.append("Aucun module installé" if is_fr else "No modules installed")
    embed.add_field(
        name=f"{get_emoji('root_puissance', True)}{'Attaque' if is_fr else 'Attack'}",
        value='\n'.join(atk_lines),
        inline=False,
    )

    # 3. Modules de Défense
    def_lines = []
    for tier in range(1, 6):
        bay = bay_details.get(tier, {})
        count = bay.get('bay_defense_count', 0)
        if count > 0:
            def_pow = bay.get('bay_defense_power', 0)
            def_lines.append(f"• **T{tier}** · `×{count}` · `{def_pow} DEF`")
    if not def_lines:
        def_lines.append("Aucun module installé" if is_fr else "No modules installed")
    embed.add_field(
        name=f"{get_emoji('root_materiel', True)}{'Défense' if is_fr else 'Defense'}",
        value='\n'.join(def_lines),
        inline=False,
    )

    # 4. Totaux matériel et accès
    tot_hs = stats.get('total_hashrate_formatted') or MathConfig.format_hashrate(stats.get('total_hashrate_hs', 0))
    tot_bits = stats.get('total_bits_per_s_formatted') or MathConfig.format_bits_per_s(stats.get('total_bits_per_s', 0))
    tot_bdef = stats.get('total_bay_defense', 0)
    max_tier_unlocked = max(1, min(5, level + 1))

    total_lines = [
        f"⚡ **{'Hashrate global' if is_fr else 'Global hashrate'}** : `{tot_hs}`",
        f"⚔️ **{'Puissance de compilation' if is_fr else 'Compilation power'}** : `{tot_bits}`",
        f"🛡️ **{'Défense des modules' if is_fr else 'Modules defense'}** : `{tot_bdef} DEF`",
        f"🛒 **{'Accès boutique' if is_fr else 'Shop access'}** : `T1` {'à' if is_fr else 'to'} `T{max_tier_unlocked}` *(Infrastructure {level})*",
    ]
    embed.add_field(
        name=f"{get_emoji('root_bilan', True)}{'Totaux matériel' if is_fr else 'Hardware totals'}",
        value='\n'.join(total_lines),
        inline=False,
    )

    embed.set_image(url=get_infrastructure_attachment_url(level))
    embed.set_footer(text=build_footer_text('Matériel' if is_fr else 'Hardware'))

    file = get_infrastructure_file(level)
    return embed, file


# ─────────────────────────────────────────────────────────────────────────────
# VUE 4 : OPÉRATIONS (OPERATIONS)
# ─────────────────────────────────────────────────────────────────────────────

def build_operations_embed(
    result: dict,
    locale: str = 'fr',
    display_name: str = 'Opérateur',
    page: int = 1,
    avatar_url: str | None = None,
) -> tuple[discord.Embed, discord.File | None, int]:
    """
    Construit l'embed et le fichier d'illustration pour la vue Opérations.
    Retourne (embed, file, total_pages).
    """
    is_fr = (locale == 'fr')
    level = sanitize_level(result.get('firewall_level', 0))
    stats = result.get('stats') or MathConfig.calculate_player_stats(result)
    bay_details = stats.get('bay_details', {})

    embed = discord.Embed(
        title=None,
        description="Opérations offensives, défensives et PvP" if is_fr else "Offensive, defensive, and PvP operations",
        color=COLOR_TURQUOISE,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_author(
        name=f"ROOT OS · {'Réseau de' if is_fr else 'Network of'} {display_name}",
        icon_url=avatar_url,
    )

    # 1. Capacité offensive
    atk_stock = int(result.get('attack_points', 0) or 0)
    tot_bits = stats.get('total_bits_per_s_formatted') or MathConfig.format_bits_per_s(stats.get('total_bits_per_s', 0))
    embed.add_field(
        name=f"{get_emoji('root_puissance', True)}{'Capacité offensive' if is_fr else 'Offensive capacity'}",
        value=f"🎯 **{'Stock ATK consommable' if is_fr else 'Consumable ATK stock'}** : `{atk_stock} ATK`\n⚡ **{'Puissance de compilation' if is_fr else 'Compilation power'}** : `{tot_bits}`",
        inline=False,
    )

    # 2. Modules d'attaque par tier
    atk_module_lines = []
    tot_atk_count = 0
    for tier in range(1, 6):
        bay = bay_details.get(tier, {})
        count = bay.get('attack_count', 0)
        tot_atk_count += count
        if count > 0:
            pow_str = MathConfig.format_bits_per_s(bay.get('attack_bits_per_s', 0))
            atk_module_lines.append(f"• **T{tier}** · `×{count}` · `{pow_str}`")

    if not atk_module_lines:
        atk_module_lines.append("Aucun module d'attaque installé" if is_fr else "No attack modules installed")
    else:
        atk_module_lines.append(f"**Total** : `{tot_atk_count}` {'modules' if is_fr else 'modules'} · `{tot_bits}`")

    embed.add_field(
        name=f"⚔️ {'Modules d’attaque' if is_fr else 'Attack modules'}",
        value='\n'.join(atk_module_lines),
        inline=False,
    )

    # 3. Modules de défense par tier
    def_module_lines = []
    tot_def_count = 0
    for tier in range(1, 6):
        bay = bay_details.get(tier, {})
        count = bay.get('bay_defense_count', 0)
        tot_def_count += count
        if count > 0:
            pow_val = bay.get('bay_defense_power', 0)
            def_module_lines.append(f"• **T{tier}** · `×{count}` · `{pow_val} DEF`")

    tot_bdef = stats.get('total_bay_defense', 0)
    ndef = stats.get('network_defense', 0)
    tdef = stats.get('total_defense', ndef + tot_bdef)

    if not def_module_lines:
        def_module_lines.append("Aucun module de défense installé" if is_fr else "No defense modules installed")
    else:
        def_module_lines.append(f"**Total modules** : `{tot_def_count}` · `{tot_bdef} DEF`")

    def_module_lines.append(f"🛡️ **{'Infrastructure' if is_fr else 'Infrastructure'}** : `{ndef} DEF` · **{'Total général' if is_fr else 'Total defense'}** : `{tdef} DEF`")

    embed.add_field(
        name=f"🛡️ {'Modules de défense' if is_fr else 'Defense modules'}",
        value='\n'.join(def_module_lines),
        inline=False,
    )

    # 4. Préparations (compilation & scan en cours)
    prep_lines = []
    pending_compile = result.get('pending_hack')
    if pending_compile:
        comp_method = pending_compile.get('mode', 'standard')
        comp_atk = pending_compile.get('attack_points', 0)
        comp_ts = _format_time_relative(pending_compile.get('resolves_at'))
        prep_lines.append(f"🔨 **{'Compilation' if is_fr else 'Compilation'}** (`{comp_method}`) : `+{comp_atk} ATK` · {comp_ts}")

    pending_scan = result.get('pending_scan')
    if pending_scan:
        scan_ts = _format_time_relative(pending_scan.get('resolves_at') or pending_scan.get('expires_at'))
        tgt_id = pending_scan.get('target_id')
        tgt_str = f" · Cible <@{tgt_id}>" if tgt_id else ""
        prep_lines.append(f"📡 **{'Scan PvP' if is_fr else 'PvP Scan'}**{tgt_str} : {scan_ts}")

    if not prep_lines:
        prep_lines.append("Aucune préparation en cours" if is_fr else "No preparations in progress")

    embed.add_field(
        name=f"⏱️ {'Préparations en cours' if is_fr else 'Active preparations'}",
        value='\n'.join(prep_lines),
        inline=False,
    )

    # 5. Attaques lancées et Représailles (avec pagination par 5)
    outgoing_attacks = result.get('outgoing_pvp_attacks') or []
    retaliations = result.get('retaliations') or []

    per_page = 5
    total_pages = max(1, math.ceil(max(len(outgoing_attacks), len(retaliations), 1) / per_page))
    cur_page = max(1, min(page, total_pages))
    start_idx = (cur_page - 1) * per_page
    end_idx = start_idx + per_page

    # Slice pour la page courante
    attacks_slice = outgoing_attacks[start_idx:end_idx]
    attack_lines = []
    for atk in attacks_slice:
        op_id = atk.get('id', '?')
        pts = atk.get('attack_points', 0)
        zone = atk.get('target', 'zone')
        res_rel = _format_time_relative(atk.get('resolves_at'))
        attack_lines.append(f"• **Op #{op_id}** · `{pts} ATK` · Zone `{zone}` · {res_rel}")

    if not attack_lines:
        attack_lines.append("Aucune attaque en cours" if is_fr else "No outgoing attacks")
    elif len(outgoing_attacks) > per_page:
        attack_lines.append(f"*Total : {len(outgoing_attacks)} opération(s)*" if is_fr else f"*Total: {len(outgoing_attacks)} operation(s)*")

    embed.add_field(
        name=f"🚀 {'Attaques lancées' if is_fr else 'Outgoing attacks'}",
        value='\n'.join(attack_lines),
        inline=False,
    )

    # Représailles
    retal_slice = retaliations[start_idx:end_idx]
    retal_lines = []
    for ret in retal_slice:
        target_id = ret.get('attacker_id')
        exp_val = ret.get('expires_at') or ret.get('delete_at')
        expires_rel = _format_time_relative(exp_val)
        retal_lines.append(f"• Riposte autorisée contre <@{target_id}> · Expire {expires_rel}" if is_fr else f"• Retaliation authorized against <@{target_id}> · Expires {expires_rel}")

    if not retal_lines:
        retal_lines.append("Aucun droit de représailles actif" if is_fr else "No active retaliation rights")
    elif len(retaliations) > per_page:
        retal_lines.append(f"*Total : {len(retaliations)} droit(s)*" if is_fr else f"*Total: {len(retaliations)} right(s)*")

    embed.add_field(
        name=f"{get_emoji('root_alerte', True)}{'Droits de représailles' if is_fr else 'Retaliation rights'}",
        value='\n'.join(retal_lines),
        inline=False,
    )

    embed.set_image(url=get_infrastructure_attachment_url(level))
    footer_text = f"Opérations · Page {cur_page}/{total_pages}" if total_pages > 1 else 'Opérations'
    if not is_fr:
        footer_text = f"Operations · Page {cur_page}/{total_pages}" if total_pages > 1 else 'Operations'
    embed.set_footer(text=build_footer_text(footer_text))

    file = get_infrastructure_file(level)
    return embed, file, total_pages


# ─────────────────────────────────────────────────────────────────────────────
# CONTAINERS DISCORD V2 (COMPONENTS V2) — RENDU IDENTIQUE AU MOCKUP
# ─────────────────────────────────────────────────────────────────────────────

def build_overview_container(
    result: dict,
    locale: str = 'fr',
    display_name: str = 'Opérateur',
    file_attachment_name: str | None = None,
) -> tuple[discord.ui.Container, discord.File | None]:
    """Construit le Container Discord V2 pour la vue Accueil correspondant au mockup utilisateur."""
    is_fr = (locale == 'fr')
    level = sanitize_level(result.get('firewall_level', 0))
    infra_name = get_infrastructure_name(level, locale=locale)
    file = get_infrastructure_file(level)
    img_name = file_attachment_name or (file.filename if file else f"niveau-{level}.png")

    stats = result.get('stats') or MathConfig.calculate_player_stats(result)
    mining_state = result.get('mining_state') or {}
    buffer_rtm = Decimal(str(mining_state.get('buffer', 0)))
    mem_pct = float(mining_state.get('memory_pct', 0))
    is_mem_full = bool(mining_state.get('is_full') or mem_pct >= 100.0)

    color = COLOR_AMBER if is_mem_full else COLOR_TURQUOISE
    c = discord.ui.Container(colour=color)

    # 1. Illustration panoramique au sommet
    if img_name:
        c.add_gallery(discord.MediaGalleryItem(f"attachment://{img_name}"))

    # 2. En-tête : >_ ROOT OS / USERNAME
    clean_name = display_name.upper()
    term_icon = get_emoji('root_terminal', True)
    subtitle = f"{infra_name} · {'Réseau personnel · Session active' if is_fr else 'Personal network · Active session'}"
    c.add_text(f"### {term_icon}ROOT OS / {clean_name}\n{subtitle}")
    c.add_separator(divider=True)

    # 3. Lignes de statistiques avec emojis stylisés
    total_miners = sum(stats.get('bay_details', {}).get(t, {}).get('mining_count', 0) for t in range(1, 6))
    hashrate_str = stats.get('total_hashrate_formatted') or MathConfig.format_hashrate(stats.get('total_hashrate_hs', 0))
    tot_bits = stats.get('total_bits_per_s_formatted') or MathConfig.format_bits_per_s(stats.get('total_bits_per_s', 0))
    ndef = int(stats.get('network_defense', 0))
    bdef = int(stats.get('total_bay_defense', 0))
    rate_per_min = Decimal(str(mining_state.get('rate_per_min', 0)))
    hourly_rtm = rate_per_min * Decimal('60')
    ram_gauge = _build_ram_gauge(mem_pct)
    used_ram = mining_state.get('memory_used_formatted', '0 o')
    total_ram = mining_state.get('total_ram_formatted', '0 o')
    usd_str = text.format_usd(result.get('dollars') or 0)
    rtm_wallet = Decimal(str(result.get('rootium') or 0))
    rep_val = int(result.get('reputation') or 0)

    stats_lines = [
        f"{get_emoji('root_materiel', True)}**{infra_name} · {'Niveau' if is_fr else 'Level'} {level}**",
        f"{get_emoji('root_ferme', True)}**{'Ferme de minage' if is_fr else 'Mining farm'}** · {total_miners} {'mineurs' if is_fr else 'miners'} ({hashrate_str})",
        f"{get_emoji('root_puissance', True)}**{'Puissance de calcul' if is_fr else 'Computing power'}** · {tot_bits}",
        f"{get_emoji('root_firewall', True)}**{'Défense' if is_fr else 'Defense'}** · {bdef} DEF ({'Baies' if is_fr else 'Bays'}) · {ndef} DEF ({'Réseau' if is_fr else 'Network'})",
        f"{get_emoji('root_production', True)}**{'Production' if is_fr else 'Production'}** · {text.format_rtm(hourly_rtm)} RTM/h",
        f"{get_emoji('root_memoire', True)}**{'Mémoire vive' if is_fr else 'RAM memory'}** · {ram_gauge} {mem_pct:.1f}% ({used_ram} / {total_ram})",
        f"{get_emoji('root_recolter', True)}**{'À récolter' if is_fr else 'To claim'}** · {text.format_rtm(buffer_rtm)} RTM",
        f"{get_emoji('root_bilan', True)}**{'Portefeuille' if is_fr else 'Wallet'}** · {usd_str} · {text.format_rtm(rtm_wallet)} RTM · {rep_val} {'pts réputation' if is_fr else 'reputation pts'}",
    ]
    c.add_text('\n'.join(stats_lines))
    c.add_separator(divider=True)

    # 4. Statut opérationnel
    status_text = f"{get_emoji('root_firewall', True)}**{'Système opérationnel' if is_fr else 'Operational system'}** · {'Surveillance active' if is_fr else 'Active monitoring'}"
    c.add_text(status_text)

    return c, file


def build_hardware_container(
    result: dict,
    locale: str = 'fr',
    display_name: str = 'Opérateur',
    file_attachment_name: str | None = None,
) -> tuple[discord.ui.Container, discord.File | None]:
    """Construit le Container Discord V2 pour la vue Matériel."""
    is_fr = (locale == 'fr')
    level = sanitize_level(result.get('firewall_level', 0))
    file = get_infrastructure_file(level)
    img_name = file_attachment_name or (file.filename if file else f"niveau-{level}.png")

    stats = result.get('stats') or MathConfig.calculate_player_stats(result)
    bay_details = stats.get('bay_details', {})
    max_tier_unlocked = max(1, min(5, level + 1))

    c = discord.ui.Container(colour=COLOR_TURQUOISE)

    if img_name:
        c.add_gallery(discord.MediaGalleryItem(f"attachment://{img_name}"))

    clean_name = display_name.upper()
    term_icon = get_emoji('root_terminal', True)
    c.add_text(f"### {term_icon}ROOT OS / {clean_name}\n{'Matériel & Équipements · Inventaire système' if is_fr else 'Hardware & Equipment · System inventory'}")
    c.add_separator(divider=True)

    lines = []
    # Minage
    lines.append(f"{get_emoji('root_ferme', True)}**{'Modules de Minage' if is_fr else 'Mining Modules'}**")
    mining_any = False
    for t in range(1, 6):
        b = bay_details.get(t, {})
        cnt = b.get('mining_count', 0)
        if cnt > 0:
            mining_any = True
            hs = MathConfig.format_hashrate(b.get('mining_hashrate', 0))
            ram = b.get('mining_ram_formatted', '0 o')
            lines.append(f"• **T{t}** · `×{cnt}` · `{hs}` · `+{ram}`")
    if not mining_any:
        lines.append(f"*{'Aucun module installé' if is_fr else 'No modules installed'}*")

    # Attaque
    lines.append(f"\n{get_emoji('root_operations', True)}**{'Modules d’Attaque' if is_fr else 'Attack Modules'}**")
    atk_any = False
    for t in range(1, 6):
        b = bay_details.get(t, {})
        cnt = b.get('attack_count', 0)
        if cnt > 0:
            atk_any = True
            pow_str = MathConfig.format_bits_per_s(b.get('attack_bits_per_s', 0))
            lines.append(f"• **T{t}** · `×{cnt}` · `{pow_str}`")
    if not atk_any:
        lines.append(f"*{'Aucun module installé' if is_fr else 'No modules installed'}*")

    # Défense
    lines.append(f"\n{get_emoji('root_firewall', True)}**{'Modules de Défense' if is_fr else 'Defense Modules'}**")
    def_any = False
    for t in range(1, 6):
        b = bay_details.get(t, {})
        cnt = b.get('bay_defense_count', 0)
        if cnt > 0:
            def_any = True
            lines.append(f"• **T{t}** · `×{cnt}` · `{b.get('bay_defense_power', 0)} DEF`")
    if not def_any:
        lines.append(f"*{'Aucun module installé' if is_fr else 'No modules installed'}*")

    lines.append(f"\n{get_emoji('root_materiel', True)}**{'Accès boutique' if is_fr else 'Shop access'}** · `T1` {'à' if is_fr else 'to'} `T{max_tier_unlocked}` *(Infrastructure {level})*")
    c.add_text('\n'.join(lines))
    c.add_separator(divider=True)
    c.add_text(f"{get_emoji('root_materiel', True)}**{'Boutique accessible via' if is_fr else 'Shop accessible via'}** `/buy`")

    return c, file


def build_operations_container(
    result: dict,
    locale: str = 'fr',
    display_name: str = 'Opérateur',
    file_attachment_name: str | None = None,
) -> tuple[discord.ui.Container, discord.File | None]:
    """Construit le Container Discord V2 pour la vue Opérations."""
    is_fr = (locale == 'fr')
    level = sanitize_level(result.get('firewall_level', 0))
    file = get_infrastructure_file(level)
    img_name = file_attachment_name or (file.filename if file else f"niveau-{level}.png")

    stats = result.get('stats') or MathConfig.calculate_player_stats(result)
    atk_stock = int(result.get('attack_points', 0) or 0)
    tot_bits = stats.get('total_bits_per_s_formatted') or MathConfig.format_bits_per_s(stats.get('total_bits_per_s', 0))
    ndef = int(stats.get('network_defense', 0))
    bdef = int(stats.get('total_bay_defense', 0))
    tdef = int(stats.get('total_defense', ndef + bdef))

    c = discord.ui.Container(colour=COLOR_TURQUOISE)

    if img_name:
        c.add_gallery(discord.MediaGalleryItem(f"attachment://{img_name}"))

    clean_name = display_name.upper()
    term_icon = get_emoji('root_terminal', True)
    c.add_text(f"### {term_icon}ROOT OS / {clean_name}\n{'Opérations & Sécurité · Surveillance active' if is_fr else 'Operations & Security · Active monitoring'}")
    c.add_separator(divider=True)

    lines = [
        f"{get_emoji('root_operations', True)}**{'Capacité offensive' if is_fr else 'Offensive capacity'}** · `{atk_stock} ATK` · `{tot_bits}`",
        f"{get_emoji('root_firewall', True)}**{'Défense globale' if is_fr else 'Total defense'}** · `{tdef} DEF` *({ndef} DEF infra + {bdef} DEF modules)*",
    ]

    # Préparations
    prep_lines = []
    pending_compile = result.get('pending_hack')
    if pending_compile:
        comp_method = pending_compile.get('mode', 'standard')
        comp_atk = pending_compile.get('attack_points', 0)
        comp_ts = _format_time_relative(pending_compile.get('resolves_at'))
        prep_lines.append(f"• {get_emoji('root_materiel', True)}**Compilation** (`{comp_method}`) : `+{comp_atk} ATK` · {comp_ts}")

    pending_scan = result.get('pending_scan')
    if pending_scan:
        scan_ts = _format_time_relative(pending_scan.get('resolves_at') or pending_scan.get('expires_at'))
        tgt_id = pending_scan.get('target_id')
        tgt_str = f" · Cible <@{tgt_id}>" if tgt_id else ""
        prep_lines.append(f"• {get_emoji('root_scan', True)}**Scan PvP**{tgt_str} : {scan_ts}")

    if prep_lines:
        lines.append(f"\n{get_emoji('root_temps', True)}**{'Préparations en cours' if is_fr else 'Active preparations'}** :\n" + '\n'.join(prep_lines))

    # Attaques lancées
    outgoing_attacks = result.get('outgoing_pvp_attacks') or []
    if outgoing_attacks:
        atk_lines = []
        for atk in outgoing_attacks[:5]:
            op_id = atk.get('id', '?')
            pts = atk.get('attack_points', 0)
            res_rel = _format_time_relative(atk.get('resolves_at'))
            atk_lines.append(f"• **Op #{op_id}** · `{pts} ATK` · {res_rel}")
        lines.append(f"\n{get_emoji('root_operations', True)}**{'Attaques lancées' if is_fr else 'Outgoing attacks'}** :\n" + '\n'.join(atk_lines))

    # Représailles
    retaliations = result.get('retaliations') or []
    if retaliations:
        retal_lines = []
        for ret in retaliations[:5]:
            tgt = ret.get('attacker_id')
            exp_val = ret.get('expires_at') or ret.get('delete_at')
            expires_rel = _format_time_relative(exp_val)
            retal_lines.append(f"• Riposte autorisée contre <@{tgt}> · Expire {expires_rel}")
        lines.append(f"\n{get_emoji('root_alerte', True)}**{'Droits de représailles' if is_fr else 'Retaliation rights'}** :\n" + '\n'.join(retal_lines))

    c.add_text('\n'.join(lines))
    c.add_separator(divider=True)
    c.add_text(f"{get_emoji('root_firewall', True)}**{'Système opérationnel' if is_fr else 'Operational system'}** · {'Surveillance active' if is_fr else 'Active monitoring'}")

    return c, file

