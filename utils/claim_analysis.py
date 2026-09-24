"""
Module d'analyse statistique et de détection d'automatisation des activités temporelles (/claim et /hourly).

Fonctionnalités :
1. Extraction ordonnée des intervalles temporels entre actions consécutives.
2. Statistiques globales : moyenne, écart-type, coefficient de variation (CV), indice de constance.
3. Détection par fenêtre glissante (Rolling Streak Analysis) de sous-séquences automatisées (K >= 5).
4. Détection de rupture de régime (chute locale de variance masquée par le reste de la journée).
5. Détection d'activité continue 24h/24 sans pause de sommeil.
6. Qualification unifiée des niveaux de risque (HIGH 🔴, MEDIUM 🟡, LOW 🟢).
"""

from datetime import datetime, timezone
from decimal import Decimal
import math
from typing import Any


def extract_intervals(records: list[dict]) -> list[float]:
    """Extrait la série ordonnée des intervalles temporels (en secondes) entre enregistrements successifs.

    Args:
        records: Liste chronologique de dictionnaires contenant au moins 'claimed_at'
                 et éventuellement 'interval_seconds'.

    Returns:
        Liste des intervalles temporels en secondes (flottants positifs).
    """
    if len(records) <= 1:
        return []

    intervals = []
    for i in range(1, len(records)):
        prev_dt = records[i - 1].get("claimed_at")
        curr_dt = records[i].get("claimed_at")

        if prev_dt and curr_dt:
            if getattr(prev_dt, "tzinfo", None) is not None and getattr(curr_dt, "tzinfo", None) is None:
                curr_dt = curr_dt.replace(tzinfo=timezone.utc)
            elif getattr(prev_dt, "tzinfo", None) is None and getattr(curr_dt, "tzinfo", None) is not None:
                prev_dt = prev_dt.replace(tzinfo=timezone.utc)
            delta = max(0.0, (curr_dt - prev_dt).total_seconds())
            intervals.append(delta)
        else:
            sec = records[i].get("interval_seconds")
            intervals.append(float(sec) if sec is not None else 0.0)

    return intervals


extract_claim_intervals = extract_intervals
extract_hourly_intervals = extract_intervals


def _compute_rolling_streak(
    intervals: list[float],
    records: list[dict],
    min_streak_size: int,
) -> dict[str, Any] | None:
    """Recherche la sous-séquence glissante de taille min_streak_size ayant la variance minimale."""
    m = len(intervals)
    if m < min_streak_size:
        return None

    best_streak = None
    for i in range(m - min_streak_size + 1):
        sub = intervals[i : i + min_streak_size]
        sub_mean = sum(sub) / min_streak_size
        sub_var = sum((x - sub_mean) ** 2 for x in sub) / min_streak_size
        sub_std = math.sqrt(sub_var)
        sub_cv = (sub_std / sub_mean) if sub_mean > 0 else 0.0

        diffs = [abs(sub[j + 1] - sub[j]) for j in range(len(sub) - 1)]
        mean_diff = sum(diffs) / len(diffs) if diffs else 0.0

        streak_info = {
            "start_idx": i,
            "end_idx": i + min_streak_size,
            "count": min_streak_size + 1,
            "mean_sec": sub_mean,
            "std_dev_sec": sub_std,
            "cv": sub_cv,
            "mean_diff_sec": mean_diff,
            "regularity_pct": max(0.0, min(100.0, (1.0 - sub_cv) * 100.0)),
            "start_time": records[i].get("claimed_at"),
            "end_time": records[i + min_streak_size].get("claimed_at"),
        }

        if best_streak is None or sub_cv < best_streak["cv"]:
            best_streak = streak_info

    return best_streak


def _has_uninterrupted_24h_activity(
    records: list[dict],
    max_gap_sec: float,
    min_actions: int = 12,
) -> bool:
    """Recherche si une sous-séquence chronologique sans longue interruption atteint au moins 24h.

    Conditions :
    - La séquence est coupée dès qu'un intervalle atteint max_gap_sec (ex: 3h30 pour claim, 2h30 pour hourly).
    - Pour déclencher, la séquence doit compter au moins min_actions (>= 12 actions).
    - La durée entre la première et la dernière action de cette séquence active doit être >= 24h (86400s).

    Args:
        records: Liste d'enregistrements (avec 'claimed_at' ou 'interval_seconds').
        max_gap_sec: Seuil de coupure (en secondes). Tout intervalle >= max_gap_sec coupe la séquence.
        min_actions: Nombre minimal d'actions requises dans la séquence continue.

    Returns:
        True si une séquence active continue couvre au moins 24 heures et min_actions.
    """
    if len(records) < min_actions:
        return False

    has_datetimes = all(isinstance(r.get("claimed_at"), datetime) for r in records)
    if has_datetimes:
        sorted_records = sorted(records, key=lambda r: r["claimed_at"])
    else:
        sorted_records = list(records)

    current_start_dt = sorted_records[0].get("claimed_at")
    current_count = 1
    current_elapsed = 0.0

    for i in range(1, len(sorted_records)):
        prev_r = sorted_records[i - 1]
        curr_r = sorted_records[i]

        prev_dt = prev_r.get("claimed_at")
        curr_dt = curr_r.get("claimed_at")

        if prev_dt and curr_dt:
            if getattr(prev_dt, "tzinfo", None) is not None and getattr(curr_dt, "tzinfo", None) is None:
                curr_dt = curr_dt.replace(tzinfo=timezone.utc)
            elif getattr(prev_dt, "tzinfo", None) is None and getattr(curr_dt, "tzinfo", None) is not None:
                prev_dt = prev_dt.replace(tzinfo=timezone.utc)
            delta = max(0.0, (curr_dt - prev_dt).total_seconds())
        else:
            sec = curr_r.get("interval_seconds")
            delta = float(sec) if sec is not None else 0.0

        if delta >= max_gap_sec:
            # Coupure de la séquence dès que la pause atteint le seuil
            current_start_dt = curr_dt
            current_count = 1
            current_elapsed = 0.0
        else:
            current_count += 1
            if current_start_dt and curr_dt:
                duration = (curr_dt - current_start_dt).total_seconds()
            else:
                current_elapsed += delta
                duration = current_elapsed

            if duration >= 86400.0 and current_count >= min_actions:
                return True

    return False


def calculate_player_claim_metrics(claims: list[dict], min_streak_size: int = 5) -> dict[str, Any]:
    """Analyse complète des récoltes de minage (/claim) pour évaluer la suspicion d'automatisation."""
    claim_count = len(claims)
    manual_claims = [c for c in claims if not c.get("is_auto")]
    auto_claims = [c for c in claims if c.get("is_auto")]

    # Seules les actions manuelles sont analysées pour la détection de bot/macro
    analysis_claims = manual_claims
    intervals = extract_intervals(analysis_claims)
    total_amount = sum((c.get("amount") or 0 for c in claims), 0)

    metrics: dict[str, Any] = {
        "claim_count": claim_count,
        "manual_claim_count": len(manual_claims),
        "auto_claim_count": len(auto_claims),
        "total_amount": total_amount,
        "intervals_count": len(intervals),
        "mean_interval_sec": None,
        "std_dev_sec": None,
        "cv": None,
        "regularity_pct": None,
        "risk_level": "LOW",
        "risk_badge": "🟢",
        "alerts": [],
        "suspicious_streak": None,
        "active_24h": False,
        "max_interval_sec": max(intervals) if intervals else None,
        "min_interval_sec": min(intervals) if intervals else None,
    }

    if len(manual_claims) < 2 or not intervals:
        metrics["status"] = "INSUFFICIENT_DATA"
        return metrics

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

    best_streak = _compute_rolling_streak(intervals, analysis_claims, min_streak_size)
    metrics["suspicious_streak"] = best_streak

    # Détection d'activité observée sur 24h sans pause >= 3h30 (sur claims manuels uniquement)
    if _has_uninterrupted_24h_activity(manual_claims, max_gap_sec=3.5 * 3600, min_actions=12):
        metrics["active_24h"] = True
        metrics["alerts"].append("NO_SLEEP_24H")

    if best_streak:
        if (best_streak["std_dev_sec"] <= 8.0 or best_streak["cv"] <= 0.05) and best_streak["mean_diff_sec"] <= 5.0:
            metrics["alerts"].append("CRITICAL_MACRO_STREAK")
        elif best_streak["cv"] <= 0.12 or best_streak["std_dev_sec"] <= 20.0:
            metrics["alerts"].append("SUSPECT_LOCAL_STREAK")

        if metrics["cv"] is not None and metrics["cv"] >= 0.35 and best_streak["cv"] <= 0.06:
            metrics["alerts"].append("VARIANCE_DROP_BURST")

    if metrics["cv"] is not None and m >= 8:
        if metrics["cv"] <= 0.10:
            metrics["alerts"].append("GLOBAL_EXTREME_CONSTANCY")
        elif metrics["cv"] <= 0.20:
            metrics["alerts"].append("GLOBAL_HIGH_REGULARITY")

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


def calculate_player_hourly_metrics(logs: list[dict], min_streak_size: int = 5) -> dict[str, Any]:
    """Analyse complète des récoltes horaires (/hourly) pour évaluer la suspicion d'automatisation."""
    total_claims = len(logs)
    total_usd = sum((Decimal(str(l.get("total_usd") or 0)) for l in logs), Decimal("0"))
    max_streak = max((int(l.get("streak", 0) or 0) for l in logs), default=0)
    max_bonus_pct = max((Decimal(str(l.get("bonus_pct") or 0)) for l in logs), default=Decimal("0"))

    intervals = extract_intervals(logs)

    metrics: dict[str, Any] = {
        "claim_count": total_claims,
        "total_usd": total_usd,
        "max_streak": max_streak,
        "max_bonus_pct": max_bonus_pct,
        "intervals_count": len(intervals),
        "mean_interval_sec": None,
        "std_dev_sec": None,
        "cv": None,
        "regularity_pct": None,
        "risk_level": "LOW",
        "risk_badge": "🟢",
        "alerts": [],
        "suspicious_streak": None,
        "active_24h": False,
        "min_interval_sec": min(intervals) if intervals else None,
        "max_interval_sec": max(intervals) if intervals else None,
    }

    if not intervals:
        metrics["status"] = "INSUFFICIENT_DATA"
        return metrics

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

    best_streak = _compute_rolling_streak(intervals, logs, min_streak_size)
    metrics["suspicious_streak"] = best_streak

    # Détection d'automatisation par bot pour les récompenses horaires
    # 1. Variance quasi-nulle ou écart-type minimal sur sous-séquence (bot appelant à 3600s pile)
    if best_streak:
        if (best_streak["std_dev_sec"] <= 5.0 or best_streak["cv"] <= 0.02) and best_streak["mean_diff_sec"] <= 3.0:
            metrics["alerts"].append("CRITICAL_MACRO_STREAK")
        elif best_streak["std_dev_sec"] <= 15.0 or best_streak["cv"] <= 0.05:
            metrics["alerts"].append("SUSPECT_LOCAL_STREAK")

        if metrics["cv"] is not None and metrics["cv"] >= 0.20 and best_streak["cv"] <= 0.02:
            metrics["alerts"].append("VARIANCE_DROP_BURST")

    if metrics["std_dev_sec"] is not None:
        if metrics["std_dev_sec"] <= 5.0 and m >= 4:
            if "CRITICAL_MACRO_STREAK" not in metrics["alerts"]:
                metrics["alerts"].append("GLOBAL_EXTREME_CONSTANCY")
        elif metrics["std_dev_sec"] <= 15.0 and m >= 5:
            if "SUSPECT_LOCAL_STREAK" not in metrics["alerts"]:
                metrics["alerts"].append("GLOBAL_HIGH_REGULARITY")

    if metrics["regularity_pct"] is not None and metrics["regularity_pct"] >= 95.0 and m >= 6:
        if "GLOBAL_HIGH_REGULARITY" not in metrics["alerts"]:
            metrics["alerts"].append("GLOBAL_HIGH_REGULARITY")

    # Détection d'activité observée sur 24h sans pause >= 2h30 pour les hourly
    if _has_uninterrupted_24h_activity(logs, max_gap_sec=2.5 * 3600, min_actions=12):
        metrics["active_24h"] = True
        metrics["alerts"].append("NO_SLEEP_24H")

    # Qualification du niveau de risque
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
