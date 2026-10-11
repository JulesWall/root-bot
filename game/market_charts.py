"""
Génération des données et graphiques pour le marché RTM.

Composants :
1. Calcul de variation de période et sparkline Unicode textuelle.
2. Échantillonnage LTTB (Largest-Triangle-Three-Buckets) pour réduire la taille des séries.
3. Rendu hors thread d'images PNG optimisées aux couleurs Root OS via Matplotlib.
4. Système de cache sur disque avec mutualisation des rendus concurrents.
"""

import asyncio
from datetime import datetime
from decimal import Decimal
import os
from pathlib import Path
from typing import List, Tuple

# Constantes de période et design
PERIODS = {
    '24h': 24 * 3600,
    '7d': 7 * 86400,
    '30d': 30 * 86400,
}

SPARK_BARS = " ▂▃▄▅▆▇█"
THEME_VERSION = "v1"
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "market"

_render_locks: dict[str, asyncio.Future] = {}


def sparkline(values: List[Decimal | float], width: int = 30) -> str:
    """Génère une sparkline Unicode (ex:  ▂▃▅▆▇) sur une largeur fixe."""
    if not values:
        return "━" * width
    
    # Ré-échantillonnage simple sur 'width' points si besoin
    if len(values) > width:
        step = len(values) / width
        sampled = [float(values[int(i * step)]) for i in range(width)]
    else:
        sampled = [float(v) for v in values]
        if len(sampled) < width and len(sampled) > 0:
            # Répéter ou étirer pour remplir width si très peu de points
            step = (len(sampled) - 1) / (width - 1) if width > 1 else 0
            sampled = [sampled[int(round(i * step))] for i in range(width)]

    min_val, max_val = min(sampled), max(sampled)
    if min_val == max_val:
        return SPARK_BARS[3] * width

    res = []
    num_bars = len(SPARK_BARS) - 1
    for val in sampled:
        norm = (val - min_val) / (max_val - min_val)
        idx = int(round(norm * num_bars))
        idx = max(0, min(num_bars, idx))
        res.append(SPARK_BARS[idx])
    return "".join(res)


def period_change_pct(first_price: Decimal | float, last_price: Decimal | float) -> Decimal:
    """Calcule la variation en pourcentage entre le premier et le dernier cours : (last/first - 1) * 100."""
    p_first = Decimal(str(first_price or 0))
    p_last = Decimal(str(last_price or 0))
    if p_first <= 0:
        return Decimal('0')
    change = ((p_last / p_first) - Decimal('1')) * Decimal('100')
    return change.quantize(Decimal('0.01'))


def downsample_lttb(points: List[dict], threshold: int = 700) -> List[dict]:
    """
    Réduction LTTB (Largest Triangle Three Buckets).
    Chaque point est un dict {'market_ts': datetime, 'price_after': Decimal, ...}.
    """
    if len(points) <= threshold or threshold <= 2:
        return points

    # Convertir en (x_ts, y_price, point)
    raw = [
        (p['market_ts'].timestamp() if isinstance(p['market_ts'], datetime) else float(p['market_ts']),
         float(p['price_after']),
         p)
        for p in points
    ]

    sampled = [raw[0][2]]
    bucket_size = (len(raw) - 2) / (threshold - 2)

    a = 0
    for i in range(threshold - 2):
        # Bucket C : moyenne des points du bucket suivant
        c_start = int((i + 1) * bucket_size) + 1
        c_end = min(int((i + 2) * bucket_size) + 1, len(raw))
        if c_end <= c_start:
            avg_x = raw[c_start][0] if c_start < len(raw) else raw[-1][0]
            avg_y = raw[c_start][1] if c_start < len(raw) else raw[-1][1]
        else:
            avg_x = sum(raw[x][0] for x in range(c_start, c_end)) / (c_end - c_start)
            avg_y = sum(raw[x][1] for x in range(c_start, c_end)) / (c_end - c_start)

        # Bucket B : chercher le point formant le plus grand triangle avec A et C
        b_start = int(i * bucket_size) + 1
        b_end = min(int((i + 1) * bucket_size) + 1, len(raw))

        max_area = -1.0
        next_a = b_start
        ax, ay = raw[a][0], raw[a][1]

        for b in range(b_start, b_end):
            bx, by = raw[b][0], raw[b][1]
            area = abs((ax - avg_x) * (by - ay) - (ax - bx) * (avg_y - ay)) * 0.5
            if area > max_area:
                max_area = area
                next_a = b

        sampled.append(raw[next_a][2])
        a = next_a

    sampled.append(raw[-1][2])
    return sampled


def detect_gaps(points: List[dict], max_gap_seconds: int = 1800) -> List[Tuple[int, int]]:
    """Détecte les index entre lesquels il y a un trou supérieur à max_gap_seconds."""
    gaps = []
    for i in range(len(points) - 1):
        t1 = points[i]['market_ts']
        t2 = points[i + 1]['market_ts']
        ts1 = t1.timestamp() if isinstance(t1, datetime) else float(t1)
        ts2 = t2.timestamp() if isinstance(t2, datetime) else float(t2)
        if ts2 - ts1 > max_gap_seconds:
            gaps.append((i, i + 1))
    return gaps


def _render_chart_sync(points: List[dict], period_name: str, last_ts: str, source: str) -> bytes:
    """Rendu Matplotlib pur (synchrone, à exécuter dans un thread)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import io
    import numpy as np

    # Données temporelles et de prix
    dts = [p['market_ts'] for p in points]
    prices = [float(p['price_after']) for p in points]

    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=100)
    fig.patch.set_facecolor('#0E1621')
    ax.set_facecolor('#131F2E')

    # Tracé avec détection de trous
    gap_pairs = detect_gaps(points)
    gap_indices = {g[0] for g in gap_pairs}

    x_segments, y_segments = [[]], [[]]
    for idx, (dt, pr) in enumerate(zip(dts, prices)):
        x_segments[-1].append(dt)
        y_segments[-1].append(pr)
        if idx in gap_indices:
            x_segments.append([])
            y_segments.append([])

    # Ligne principale Turquoise Root OS
    color_line = '#54E2D1'
    for xs, ys in zip(x_segments, y_segments):
        if not xs:
            continue
        ax.plot(xs, ys, color=color_line, linewidth=2.2, zorder=3)
        ax.fill_between(xs, ys, min(prices) * 0.999, color=color_line, alpha=0.08, zorder=2)

    # Point marqueur sur la dernière valeur
    if dts:
        ax.scatter([dts[-1]], [prices[-1]], color='#FFFFFF', edgecolors=color_line, s=50, linewidth=2, zorder=4)

    # Grille et axes
    ax.grid(True, linestyle='--', alpha=0.15, color='#EEF1F5', zorder=1)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#2A3A4D')
    ax.spines['bottom'].set_color('#2A3A4D')

    ax.tick_params(colors='#8899A6', labelsize=9)
    if period_name == '24h':
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    elif period_name == '7d':
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%a %d'))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))

    # Titre et libellés
    p_start, p_end = prices[0], prices[-1]
    pct = ((p_end / p_start) - 1.0) * 100.0 if p_start > 0 else 0.0
    sign = "+" if pct >= 0 else ""
    title_text = f"ROOT OS / MARCHÉ  ·  1 RTM = {p_end:,.2f} USD  ({sign}{pct:.2f}% sur {period_name})"
    ax.set_title(title_text, color='#EEF1F5', fontsize=12, fontweight='bold', pad=14, loc='left')

    # Pied de figure (source joueur sans exchange externe ni crypto réelle)
    display_source = "Index Marché" if "binance" in str(source).lower() or "crypto" in str(source).lower() or source in ('seed', None, '') else str(source)
    footer_text = f"Période: {period_name.upper()}  ·  Source: {display_source}  ·  Dernier point: {last_ts} UTC"
    fig.text(0.12, 0.02, footer_text, color='#6C7D8F', fontsize=8, ha='left')

    fig.tight_layout(rect=[0, 0.05, 1, 0.96])

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    return buf.getvalue()


async def get_or_render_chart(points: List[dict], period_name: str, source: str) -> Path:
    """
    Retourne le chemin d'accès vers l'image PNG en cache disque.
    Si le fichier n'existe pas, lance le rendu sans bloquer l'event loop asyncio.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not points:
        raise ValueError("Aucun point pour le rendu.")

    last_pt = points[-1]
    last_dt = last_pt['market_ts']
    last_ts_str = last_dt.strftime('%Y%m%d_%H%M%S') if isinstance(last_dt, datetime) else str(last_dt)
    cache_key = f"{period_name}_{last_ts_str}_{THEME_VERSION}_1000x560"
    file_path = CACHE_DIR / f"{cache_key}.png"

    if file_path.exists():
        return file_path

    # Gestion de la concurrence pour éviter de lancer 2 rendus identiques
    future = _render_locks.get(cache_key)
    if future is not None:
        await future
        return file_path

    loop = asyncio.get_running_loop()
    new_future = loop.create_future()
    _render_locks[cache_key] = new_future

    try:
        # Échantillonnage
        sampled = downsample_lttb(points, threshold=800)
        # Rendu asynchrone hors de l'event loop
        png_bytes = await asyncio.to_thread(
            _render_chart_sync, sampled, period_name, last_ts_str, source
        )
        file_path.write_bytes(png_bytes)
        new_future.set_result(True)
    except Exception as e:
        new_future.set_exception(e)
        raise
    finally:
        _render_locks.pop(cache_key, None)

    return file_path

