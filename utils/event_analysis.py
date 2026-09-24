"""
Module d'analyse anti-triche et de qualification des statistiques d'événements (/event).

Permet la détection de comportements frauduleux ou automatisés sur les mini-jeux réseau :
1. Calcul du ratio de victoire (events_won / events_participated).
2. Détection des résolutions ultra-rapides (<= 2 secondes : macros, socket bots, scrapers).
3. Calcul de la vitesse moyenne et minimale de résolution.
4. Détection de domination anormale et qualification du niveau de risque (HIGH 🔴, MEDIUM 🟡, LOW 🟢).
"""

from decimal import Decimal
from typing import Any


def calculate_player_event_metrics(
    won_count: int,
    participated_count: int,
    recent_wins: list[dict] | None = None,
) -> dict[str, Any]:
    """Calcule les métriques d'audit et le niveau de risque anti-triche pour un joueur d'événements.

    Args:
        won_count: Nombre total d'événements gagnés sur la période.
        participated_count: Nombre total de participations/tentatives enregistrées.
        recent_wins: Liste des victoires récentes issues de event_availability_logs,
                     chacune contenant au moins 'duration_seconds', 'event', 'reward', 'solved_at'.

    Returns:
        Dictionnaire des métriques calculées avec alertes et badge de risque.
    """
    total_participations = max(won_count, participated_count)
    win_rate = (won_count / total_participations * 100.0) if total_participations > 0 else 0.0

    wins = recent_wins or []
    durations = [int(w.get("duration_seconds") or 0) for w in wins if w.get("duration_seconds") is not None]

    instant_wins = [d for d in durations if d <= 2]
    fast_wins = [d for d in durations if 2 < d <= 5]

    mean_duration = (sum(durations) / len(durations)) if durations else None
    min_duration = min(durations) if durations else None

    metrics: dict[str, Any] = {
        "events_won": won_count,
        "events_participated": total_participations,
        "win_rate_pct": win_rate,
        "recorded_wins_count": len(wins),
        "instant_wins_count": len(instant_wins),
        "fast_wins_count": len(fast_wins),
        "mean_duration_sec": mean_duration,
        "min_duration_sec": min_duration,
        "risk_level": "LOW",
        "risk_badge": "🟢",
        "alerts": [],
    }

    # ── Qualification des Alertes ───────────────────────────────────────────
    # 1. Résolution ultra-rapide (Macro / Bot socket)
    if len(instant_wins) >= 1:
        metrics["alerts"].append("CRITICAL_INSTANT_SOLVE")
    elif len(fast_wins) >= 3 or (durations and mean_duration is not None and mean_duration <= 4.0 and len(durations) >= 3):
        metrics["alerts"].append("SUSPECT_FAST_SOLVE")

    # 2. Taux de victoire statistiquement anormal en environnement multijoueur
    if won_count >= 5:
        if win_rate >= 85.0:
            metrics["alerts"].append("ABNORMAL_WIN_RATE")
        elif win_rate >= 65.0:
            metrics["alerts"].append("HIGH_WIN_RATE")
    elif won_count >= 10:
        if win_rate >= 50.0:
            metrics["alerts"].append("HIGH_WIN_RATE")

    # 3. Qualification finale du niveau de risque
    if "CRITICAL_INSTANT_SOLVE" in metrics["alerts"] or "ABNORMAL_WIN_RATE" in metrics["alerts"]:
        metrics["risk_level"] = "HIGH"
        metrics["risk_badge"] = "🔴"
    elif "SUSPECT_FAST_SOLVE" in metrics["alerts"] or "HIGH_WIN_RATE" in metrics["alerts"]:
        metrics["risk_level"] = "MEDIUM"
        metrics["risk_badge"] = "🟡"
    else:
        metrics["risk_level"] = "LOW"
        metrics["risk_badge"] = "🟢"

    return metrics

