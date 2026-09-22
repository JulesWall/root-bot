"""
Module d'analyse statistique et de détection d'automatisation des claims.

Fonctionnalités :
1. Calcul des statistiques globales sur la journée : moyenne, écart-type, coefficient de variation (CV).
2. Détection par fenêtre glissante (Rolling Streak Analysis) de sous-séquences suspectes (K >= 5 claims).
3. Détection de rupture de régime (baisse soudaine de variance masquée par le reste de la journée).
4. Détection d'activité 24/24 sans interruption de sommeil.
"""

from datetime import datetime, timezone
import math
from typing import Any


def extract_claim_intervals(claims: list[dict]) -> list[float]:
    """Extrait la série ordonnée des intervalles temporels (en secondes) entre claims successifs.

    Args:
        claims: Liste des dictionnaires de claims ordonnés chronologiquement,
                chacun contenant 'claimed_at' (datetime) et éventuellement 'interval_seconds'.

    Returns:
        Liste des intervalles en secondes (flottants positifs).
    """
    if len(claims) <= 1:
        return []

    intervals = []
    for i in range(1, len(claims)):
        prev_dt = claims[i - 1]["claimed_at"]
        curr_dt = claims[i]["claimed_at"]

        # Si les deux horodatages sont renseignés, on privilégie l'écart réel entre ces deux claims
        if prev_dt and curr_dt:
            # Harmonisation éventuelle des timezones
            if getattr(prev_dt, "tzinfo", None) is not None and getattr(curr_dt, "tzinfo", None) is None:
                curr_dt = curr_dt.replace(tzinfo=timezone.utc)
            elif getattr(prev_dt, "tzinfo", None) is None and getattr(curr_dt, "tzinfo", None) is not None:
                prev_dt = prev_dt.replace(tzinfo=timezone.utc)
            delta = max(0.0, (curr_dt - prev_dt).total_seconds())
            intervals.append(delta)
        else:
            # Repli sur interval_seconds enregistré en base
            sec = claims[i].get("interval_seconds")
            intervals.append(float(sec) if sec is not None else 0.0)

    return intervals


def calculate_player_claim_metrics(claims: list[dict], min_streak_size: int = 5) -> dict[str, Any]:
    """Analyse complète des récoltes d'un joueur pour évaluer la suspicion d'automatisation.

    Args:
        claims: Liste chronologique des claims du joueur sur la journée.
        min_streak_size: Taille minimale d'une sous-séquence pour la détection de micro-variabilité.

    Returns:
        Dictionnaire synthétique avec les métriques globales, les streaks suspects et le niveau de risque.
    """
    claim_count = len(claims)
    intervals = extract_claim_intervals(claims)
    total_amount = sum((c.get("amount") or 0 for c in claims), 0)

    metrics: dict[str, Any] = {
        "claim_count": claim_count,
        "total_amount": total_amount,
        "intervals_count": len(intervals),
        "mean_interval_sec": None,
        "std_dev_sec": None,
        "cv": None,
        "regularity_pct": None,
        "risk_level": "LOW",  # 'LOW', 'MEDIUM', 'HIGH'
        "risk_badge": "🟢",
        "alerts": [],
        "suspicious_streak": None,
        "active_24h": False,
        "max_interval_sec": max(intervals) if intervals else None,
        "min_interval_sec": min(intervals) if intervals else None,
    }

    if not intervals:
        metrics["status"] = "INSUFFICIENT_DATA"
        return metrics

    # ── 1. Statistiques Globales (Journée) ───────────────────────────────────
    m = len(intervals)
    mean_val = sum(intervals) / m
    metrics["mean_interval_sec"] = mean_val

    if m >= 2:
        variance = sum((x - mean_val) ** 2 for x in intervals) / m
        std_dev = math.sqrt(variance)
        cv = (std_dev / mean_val) if mean_val > 0 else 0.0
        reg_pct = max(0.0, min(100.0, (1.0 - cv) * 100.0))

        metrics["std_dev_sec"] = std_dev
        metrics["cv"] = cv
        metrics["regularity_pct"] = reg_pct
    else:
        metrics["std_dev_sec"] = 0.0
        metrics["cv"] = 0.0
        metrics["regularity_pct"] = 100.0

    # ── 2. Détection de Baisse de Variation par Fenêtre Glissante (Streak) ───
    best_streak = None
    if m >= min_streak_size:
        for i in range(m - min_streak_size + 1):
            sub = intervals[i : i + min_streak_size]
            sub_mean = sum(sub) / min_streak_size
            sub_var = sum((x - sub_mean) ** 2 for x in sub) / min_streak_size
            sub_std = math.sqrt(sub_var)
            sub_cv = (sub_std / sub_mean) if sub_mean > 0 else 0.0

            # Écart absolu consécutif moyen (|d_{j+1} - d_j|)
            diffs = [abs(sub[j + 1] - sub[j]) for j in range(len(sub) - 1)]
            mean_diff = sum(diffs) / len(diffs) if diffs else 0.0

            streak_info = {
                "start_idx": i,
                "end_idx": i + min_streak_size,
                "count": min_streak_size + 1,  # nombre de claims impliqués
                "mean_sec": sub_mean,
                "std_dev_sec": sub_std,
                "cv": sub_cv,
                "mean_diff_sec": mean_diff,
                "regularity_pct": max(0.0, min(100.0, (1.0 - sub_cv) * 100.0)),
                "start_time": claims[i]["claimed_at"],
                "end_time": claims[i + min_streak_size]["claimed_at"],
            }

            if best_streak is None or sub_cv < best_streak["cv"]:
                best_streak = streak_info

        metrics["suspicious_streak"] = best_streak

    # ── 3. Détection d'Activité 24/24 (Absence de pause sommeil) ─────────────
    # Si le joueur a beaucoup de claims (>= 12) et que sa plus longue pause de la journée est < 3.5h
    if claim_count >= 12 and metrics["max_interval_sec"] is not None:
        if metrics["max_interval_sec"] < 3.5 * 3600:
            metrics["active_24h"] = True
            metrics["alerts"].append("NO_SLEEP_24H")

    # ── 4. Qualification des Alertes et du Niveau de Risque ─────────────────
    # A. Analyse de la sous-séquence (baisse locale de variation)
    if best_streak:
        # Alerte critique : macro / script certain
        # Écart-type <= 8s ou CV <= 5%, ou variation moyenne entre deux claims <= 4s
        if (best_streak["std_dev_sec"] <= 8.0 or best_streak["cv"] <= 0.05) and best_streak["mean_diff_sec"] <= 5.0:
            metrics["alerts"].append("CRITICAL_MACRO_STREAK")
        # Alerte modérée : séquence très régulière
        elif best_streak["cv"] <= 0.12 or best_streak["std_dev_sec"] <= 20.0:
            metrics["alerts"].append("SUSPECT_LOCAL_STREAK")

        # Détection explicite de rupture de régime :
        # Joueur d'apparence globale humaine (CV >= 0.35) mais avec un pic d'automatisation
        if metrics["cv"] is not None and metrics["cv"] >= 0.35 and best_streak["cv"] <= 0.06:
            metrics["alerts"].append("VARIANCE_DROP_BURST")

    # B. Analyse de la régularité globale sur 24h
    if metrics["cv"] is not None and m >= 8:
        if metrics["cv"] <= 0.10:  # Régularité >= 90%
            metrics["alerts"].append("GLOBAL_EXTREME_CONSTANCY")
        elif metrics["cv"] <= 0.20:  # Régularité >= 80%
            metrics["alerts"].append("GLOBAL_HIGH_REGULARITY")

    # C. Synthèse du niveau de risque
    if (
        "CRITICAL_MACRO_STREAK" in metrics["alerts"]
        or "VARIANCE_DROP_BURST" in metrics["alerts"]
        or "GLOBAL_EXTREME_CONSTANCY" in metrics["alerts"]
    ):
        metrics["risk_level"] = "HIGH"
        metrics["risk_badge"] = "🔴"
    elif (
        "SUSPECT_LOCAL_STREAK" in metrics["alerts"]
        or "GLOBAL_HIGH_REGULARITY" in metrics["alerts"]
        or "NO_SLEEP_24H" in metrics["alerts"]
    ):
        metrics["risk_level"] = "MEDIUM"
        metrics["risk_badge"] = "🟡"
    else:
        metrics["risk_level"] = "LOW"
        metrics["risk_badge"] = "🟢"

    return metrics

