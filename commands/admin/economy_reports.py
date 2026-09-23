"""
Cog EconomyReports : tâche périodique de publication des bilans économiques.

Envoie un embed dans chaque salon configuré toutes les 1h, 24h et 72h.
Séparation stricte transaction SQL / envoi Discord.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import discord
from discord.ext import commands, tasks

from game.db.economy_stats import EconomyStatsDB
from utils.time_format import format_duration

logger = logging.getLogger(__name__)

_PERIODS = (1, 24, 72)

_CHANNEL_ENV = {
    1:  'LOG_ECONOMY_1H_CHANNEL_ID',
    24: 'LOG_ECONOMY_24H_CHANNEL_ID',
    72: 'LOG_ECONOMY_72H_CHANNEL_ID',
}

_PERIOD_LABELS = {
    1:  '1 h',
    24: '24 h',
    72: '72 h',
}

_PERIOD_COLORS = {
    1:  0x3498DB,  # Bleu réseau (1h)
    24: 0x2ECC71,  # Vert émeraude (24h)
    72: 0x9B59B6,  # Violet améthyste (72h)
}


def _parse_channel_id(env_key: str) -> int | None:
    raw = os.getenv(env_key, '').strip()
    if raw.isdigit():
        return int(raw)
    return None


def _to_dec(val) -> Decimal:
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val or 0))


def _fmt_usd(val) -> str:
    return f"{_to_dec(val):,.2f} USD"


def _fmt_rtm(val) -> str:
    return f"{_to_dec(val):,.5f} RTM"


def _fmt_paris(dt: datetime) -> str:
    """Affiche une datetime UTC en heure de Paris (Europe/Paris), sans dépendance externe."""
    try:
        import zoneinfo
        paris = zoneinfo.ZoneInfo('Europe/Paris')
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone(paris)
    except Exception:
        # Repli sans zoneinfo : UTC+1 hiver / UTC+2 été (approximation)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        offset = timedelta(hours=2)  # heure d'été par défaut
        local = dt + offset
    return local.strftime('%d/%m à %H h')


def _make_ref(period_hours: int, period_start: datetime) -> str:
    label = {1: '1h', 24: '24h', 72: '72h'}.get(period_hours, f'{period_hours}h')
    if period_start.tzinfo is None:
        period_start = period_start.replace(tzinfo=timezone.utc)
    iso = period_start.strftime('%Y-%m-%dT%H:%MZ')
    return f"eco:{label}:{iso}"


def _build_embed(period_hours: int, data: dict, period_start: datetime, period_end: datetime) -> discord.Embed:
    """
    Construit l'embed Discord pour un bilan économique.
    data : dict avec les agrégats (montants en str ou Decimal).
    """
    label = _PERIOD_LABELS.get(period_hours, f'{period_hours} h')
    ref = _make_ref(period_hours, period_start)

    start_str = _fmt_paris(period_start)
    end_str = _fmt_paris(period_end)

    embed = discord.Embed(
        title=f"Bilan économique — {label}",
        description=f"Du {start_str} au {end_str} — heure de Paris",
        color=_PERIOD_COLORS.get(period_hours, 0x2B2D31),
    )

    active = int(data.get('active_players') or 0)
    new_pl = int(data.get('new_players') or 0)
    claims = int(data.get('claims') or 0)
    full_claims = int(data.get('full_claims') or 0)

    prev_active = int(data.get('prev_active_players') or 0)
    retained = int(data.get('retained_players') or 0)

    if prev_active > 0:
        retention_pct = round(100 * retained / prev_active, 1)
        retention_str = f"{retention_pct} % ({retained}/{prev_active} rejoueurs)"
    else:
        retention_str = "non applicable (0 joueur préc.)"

    if claims > 0:
        ram_pct = round(100 * full_claims / claims, 1)
        ram_str = f"{ram_pct} %"
    else:
        ram_str = "non applicable"

    # --- 1. Activité & Rétention ---
    act_block = (
        "```yaml\n"
        f"Actifs    : {active} joueur{'s' if active > 1 else ''} (+{new_pl} nouveau{'x' if new_pl > 1 else ''})\n"
        f"Rétention : {retention_str}\n"
        f"Claims    : {claims} récolte{'s' if claims > 1 else ''} (RAM pleine : {ram_str})\n"
        "```"
    )
    embed.add_field(
        name="👥 Activité & Rétention",
        value=act_block,
        inline=False,
    )

    # --- 2. Gains ---
    mining_rtm = _to_dec(data.get('mining_rtm'))
    if active > 0:
        rtm_per_active = (mining_rtm / active).quantize(Decimal('0.00001'))
        rtm_per_str = _fmt_rtm(rtm_per_active)
    else:
        rtm_per_str = "non applicable"

    event_cols = {
        'hash':    _to_dec(data.get('event_hash_usd')),
        'pin':     _to_dec(data.get('event_pin_usd')),
        'decode':  _to_dec(data.get('event_decode_usd')),
        'anomaly': _to_dec(data.get('event_anomaly_usd')),
        'buffer':  _to_dec(data.get('event_buffer_usd')),
        'signal':  _to_dec(data.get('event_signal_usd')),
        'packet':  _to_dec(data.get('event_packet_usd')),
    }
    event_total = sum(event_cols.values())
    event_detail_parts = [
        f"{name}: {val:,.2f}"
        for name, val in event_cols.items()
        if val > 0
    ]
    event_detail = f" ({', '.join(event_detail_parts)})" if event_detail_parts else ""

    grant_usd = _to_dec(data.get('grant_usd'))

    gains_block = (
        "```yaml\n"
        f"Minage RTM : {_fmt_rtm(mining_rtm)} ({rtm_per_str} / actif)\n"
        f"Mini-jeux  : {_fmt_usd(event_total)}{event_detail}\n"
        f"Dotations  : {_fmt_usd(grant_usd)}\n"
        "```"
    )
    embed.add_field(
        name="📥 Flux entrants (Gains)",
        value=gains_block,
        inline=False,
    )

    # --- 3. Dépenses ---
    miners_usd = _to_dec(data.get('miners_usd'))
    miners_rtm = _to_dec(data.get('miners_rtm'))
    combat_usd = _to_dec(data.get('combat_usd'))
    combat_rtm = _to_dec(data.get('combat_rtm'))
    upgrades_usd = _to_dec(data.get('upgrades_usd'))
    compile_rtm = _to_dec(data.get('compile_rtm'))
    scan_rtm = _to_dec(data.get('scan_rtm'))

    total_usd_spent = miners_usd + combat_usd + upgrades_usd
    total_rtm_spent = miners_rtm + combat_rtm + compile_rtm + scan_rtm

    usd_detail = []
    if miners_usd > 0:
        usd_detail.append(f"mineurs: {_fmt_usd(miners_usd)}")
    if combat_usd > 0:
        usd_detail.append(f"combat: {_fmt_usd(combat_usd)}")
    if upgrades_usd > 0:
        usd_detail.append(f"upgrades: {_fmt_usd(upgrades_usd)}")
    usd_detail_str = f" ({', '.join(usd_detail)})" if usd_detail else ""

    rtm_detail = []
    if combat_rtm > 0:
        rtm_detail.append(f"combat: {_fmt_rtm(combat_rtm)}")
    if compile_rtm > 0:
        rtm_detail.append(f"compil: {_fmt_rtm(compile_rtm)}")
    if scan_rtm > 0:
        rtm_detail.append(f"scan: {_fmt_rtm(scan_rtm)}")
    rtm_detail_str = f" ({', '.join(rtm_detail)})" if rtm_detail else ""

    depenses_block = (
        "```yaml\n"
        f"Total USD  : {_fmt_usd(total_usd_spent)}{usd_detail_str}\n"
        f"Total RTM  : {_fmt_rtm(total_rtm_spent)}{rtm_detail_str}\n"
        "```"
    )
    embed.add_field(
        name="📤 Flux sortants (Dépenses)",
        value=depenses_block,
        inline=False,
    )

    # --- 4. Disponibilité des événements ---
    event_avail = data.get('event_availability') or {}
    avail_lines = []
    for ev in ('hash', 'pin', 'decode', 'anomaly', 'buffer', 'signal', 'packet'):
        info = event_avail.get(ev)
        if not info:
            continue
        tot_sec = int(info.get('total_seconds') or 0)
        if tot_sec <= 0:
            continue
        dur_str = format_duration(tot_sec)
        wins = int(info.get('wins') or 0)
        ongoing = bool(info.get('ongoing'))
        tag = f"[{ev}]".ljust(10)
        if ongoing:
            avail_lines.append(f"{tag} {dur_str} (en cours)")
        elif wins > 1:
            avg_sec = int(info.get('avg_seconds') or 0)
            avg_str = format_duration(avg_sec)
            avail_lines.append(f"{tag} {dur_str} ({wins} manches • moy. {avg_str})")
        else:
            avail_lines.append(f"{tag} {dur_str}")

    if avail_lines:
        avail_block = "```ini\n" + "\n".join(avail_lines) + "\n```"
    else:
        avail_block = "```ini\nAucun événement actif sur cette période.\n```"

    embed.add_field(
        name="⏱️ Disponibilité des Événements",
        value=avail_block,
        inline=False,
    )

    # --- 5. Progression & circulation ---
    tiers_parts = []
    for t in range(1, 6):
        qty = int(data.get(f'miners_t{t}') or 0)
        if qty:
            tiers_parts.append(f"{qty} T{t}")
    tiers_str = ' · '.join(tiers_parts) if tiers_parts else "0"

    attack_bought = int(data.get('attack_bought') or 0)
    defense_bought = int(data.get('defense_bought') or 0)
    upgrades_started = int(data.get('upgrades_started') or 0)

    converted_rtm = _to_dec(data.get('converted_rtm'))
    converted_usd = _to_dec(data.get('converted_usd'))
    conversions = int(data.get('conversions') or 0)
    trades = int(data.get('trades') or 0)

    conv_str = (
        f"{_fmt_rtm(converted_rtm)} -> {_fmt_usd(converted_usd)} ({conversions} conv.)"
        if conversions > 0 else "0"
    )

    prog_block = (
        "```yaml\n"
        f"Mineurs     : {tiers_str}\n"
        f"Combat      : +{attack_bought} ATK · +{defense_bought} DEF\n"
        f"Upgrades    : {upgrades_started} démarrée(s)\n"
        f"Conversions : {conv_str}\n"
        f"Échanges    : {trades} transfert(s)\n"
        "```"
    )
    embed.add_field(
        name="🔄 Progression & Circulation",
        value=prog_block,
        inline=False,
    )

    # --- 6. Solde net ---
    net_usd = event_total + grant_usd + _to_dec(data.get('converted_usd')) - total_usd_spent
    net_rtm = mining_rtm - _to_dec(data.get('converted_rtm')) - total_rtm_spent

    usd_sign = "+" if net_usd >= 0 else "-"
    rtm_sign = "+" if net_rtm >= 0 else "-"

    usd_abs_str = f"{abs(net_usd):,.2f} USD"
    rtm_abs_str = f"{abs(net_rtm):,.5f} RTM"

    net_block = (
        "```diff\n"
        f"{usd_sign} USD : {usd_sign}{usd_abs_str}\n"
        f"{rtm_sign} RTM : {rtm_sign}{rtm_abs_str}\n"
        "```"
    )
    embed.add_field(
        name="⚖️ Solde Net de la Période",
        value=net_block,
        inline=False,
    )

    embed.set_footer(text=ref)
    return embed


class EconomyReports(commands.Cog):
    """Tâche périodique : publication des bilans économiques 1h, 24h et 72h."""

    def __init__(self, bot):
        self.bot = bot
        self._lock = asyncio.Lock()
        self.report_loop.start()

    def cog_unload(self):
        self.report_loop.cancel()

    @tasks.loop(minutes=1)
    async def report_loop(self):
        """Traite indépendamment les 3 destinations à chaque minute."""
        if self._lock.locked():
            return
        async with self._lock:
            root_service = getattr(self.bot, 'root_service', None)
            if root_service is None or not root_service.economy_enabled:
                return

            for period_hours in _PERIODS:
                try:
                    await self._process_period(root_service, period_hours)
                except Exception:
                    logger.exception(
                        "[EconomyReports] Erreur non gérée pour la période %dh.", period_hours
                    )

    @report_loop.before_loop
    async def before_report_loop(self):
        await self.bot.wait_until_ready()

    async def _process_period(self, root_service, period_hours: int) -> None:
        channel_id = _parse_channel_id(_CHANNEL_ENV[period_hours])
        if not channel_id:
            return

        # Étape 1 : préparer ou récupérer le bilan en attente (transaction SQL)
        report = await root_service.database.run(
            lambda tx: EconomyStatsDB.prepare_report(tx, period_hours, channel_id),
            locks=['economy-init'],
        )
        if report is None:
            return

        data = report['data']
        pending_end = report['pending_end']
        stored_channel_id = report['pending_channel_id'] or channel_id

        # Reconstruction des datetimes depuis le payload
        period_start_raw = data.get('period_start')
        period_end_raw = data.get('period_end')
        try:
            period_start = datetime.fromisoformat(period_start_raw)
            period_end = datetime.fromisoformat(period_end_raw)
        except Exception:
            logger.error(
                "[EconomyReports] Impossible de parser les dates du payload %dh : %s / %s",
                period_hours, period_start_raw, period_end_raw,
            )
            return

        # Reconstruction des Decimal depuis les str JSON
        dec_data = {}
        for k, v in data.items():
            if k in ('period_start', 'period_end'):
                dec_data[k] = v
            elif k in ('active_players', 'new_players', 'returning_players',
                       'prev_active_players', 'retained_players',
                       'claims', 'full_claims',
                       'miners_t1', 'miners_t2', 'miners_t3', 'miners_t4', 'miners_t5',
                       'attack_bought', 'defense_bought', 'upgrades_started',
                       'conversions', 'trades'):
                dec_data[k] = int(v or 0)
            elif k == 'event_availability':
                dec_data[k] = v if isinstance(v, dict) else {}
            else:
                try:
                    dec_data[k] = Decimal(str(v or 0))
                except Exception:
                    dec_data[k] = v

        # Étape 2 : construction de l'embed (hors transaction)
        embed = _build_embed(period_hours, dec_data, period_start, period_end)

        # Étape 3 : envoi Discord (hors transaction)
        channel = self.bot.get_channel(stored_channel_id)
        if channel is None:
            logger.warning(
                "[EconomyReports] Salon %s introuvable pour la période %dh. Envoi suspendu.",
                stored_channel_id, period_hours,
            )
            return

        try:
            message = await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.DiscordException:
            logger.exception(
                "[EconomyReports] Échec d'envoi Discord pour la période %dh. Retry au prochain cycle.",
                period_hours,
            )
            return

        # Étape 4 : accusé de réception (nouvelle transaction)
        expected_start = period_start
        expected_end = period_end
        message_id = message.id

        try:
            await root_service.database.run(
                lambda tx: EconomyStatsDB.ack_report(
                    tx, period_hours, expected_start, expected_end, message_id
                ),
                locks=['economy-init'],
            )
        except Exception:
            logger.exception(
                "[EconomyReports] Échec de l'accusé de réception pour la période %dh. "
                "Le message a été envoyé, un doublon possible au prochain cycle.",
                period_hours,
            )


def setup(bot):
    bot.add_cog(EconomyReports(bot))

