"""
Gestionnaire de persistance et de requêtes pour la table SQL 'hourly_logs'.

Permet le suivi, la journalisation et l'audit anti-triche des récompenses horaires (/hourly) :
- Enregistrement de chaque exécution validée (horodatage, gain, bonus, série, statut de combo).
- Synthèse globale et classement (top) des joueurs les plus assidus sur 24h pour la modération.
- Extraction des journaux chronologiques d'un joueur pour l'audit en direct (!hourlyaudit).
- Calcul des métriques statistiques de dispersion et de risque d'automatisation (bot).
"""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import math
from typing import Any


def _normalize_hourly_row(row: dict) -> dict:
    """Normalise une ligne hourly_logs (Decimal, bool, types stables)."""
    return {
        "id": row.get("id"),
        "discord_id": row["discord_id"],
        "claimed_at": row.get("claimed_at"),
        "interval_seconds": row.get("interval_seconds"),
        "base_usd": Decimal(str(row.get("base_usd") or 0)),
        "bonus_pct": Decimal(str(row.get("bonus_pct") or 0)),
        "total_usd": Decimal(str(row.get("total_usd") or 0)),
        "streak": int(row.get("streak") or 0),
        "combo_lost": bool(row.get("combo_lost", 0)),
    }


class HourlyStatsDB:
    """Accès aux données pour la table hourly_logs."""

    @staticmethod
    def record_hourly(
        tx,
        discord_id: int,
        claimed_at: datetime,
        interval_seconds: int | None,
        base_usd: Decimal,
        bonus_pct: Decimal,
        total_usd: Decimal,
        streak: int,
        combo_lost: bool = False,
    ) -> None:
        """Enregistre une récompense /hourly réussie pour un joueur."""
        tx.execute(
            """
            INSERT INTO hourly_logs (discord_id, claimed_at, interval_seconds, base_usd, bonus_pct, total_usd, streak, combo_lost)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                discord_id,
                claimed_at,
                interval_seconds,
                base_usd,
                bonus_pct,
                total_usd,
                streak,
                1 if combo_lost else 0,
            ),
        )

    @staticmethod
    def get_summary(tx, limit_users: int = 50) -> dict[str, Any]:
        """Retourne la synthèse de la période en cours (depuis la dernière purge de minuit).

        Returns:
            dict avec :
            - 'total_claims': int
            - 'total_usd': Decimal
            - 'unique_players': int
            - 'top_users': list[dict]
        """
        # Période courante : hourly_logs est purgée chaque minuit après envoi du rapport.
        global_stats = tx.one(
            """
            SELECT 
                COUNT(*) AS total_claims,
                COALESCE(SUM(total_usd), 0.00) AS total_usd,
                COUNT(DISTINCT discord_id) AS unique_players
            FROM hourly_logs
            """
        ) or {}

        top_users = tx.all(
            """
            SELECT 
                discord_id,
                COUNT(*) AS claim_count,
                COALESCE(SUM(total_usd), 0.00) AS total_usd,
                MAX(streak) AS max_streak,
                MAX(bonus_pct) AS max_bonus_pct
            FROM hourly_logs
            GROUP BY discord_id
            ORDER BY claim_count DESC, total_usd DESC
            LIMIT %s
            """,
            (limit_users,),
        ) or []

        recent_rows = tx.all(
            """
            SELECT id, discord_id, claimed_at, interval_seconds, base_usd, bonus_pct, total_usd, streak, combo_lost
            FROM hourly_logs
            ORDER BY claimed_at ASC
            """
        ) or []
        recent_logs = [_normalize_hourly_row(r) for r in recent_rows]
        grouped: dict[int, list[dict]] = defaultdict(list)
        for row in recent_logs:
            grouped[int(row["discord_id"])].append(row)

        top_streaks = sorted(
            (
                {
                    "discord_id": uid,
                    "max_streak": max((r["streak"] for r in rows), default=0),
                    "claim_count": len(rows),
                }
                for uid, rows in grouped.items()
            ),
            key=lambda item: (item["max_streak"], item["claim_count"]),
            reverse=True,
        )[:10]
        top_bonuses = sorted(
            (
                {
                    "discord_id": uid,
                    "max_bonus_pct": max((r["bonus_pct"] for r in rows), default=Decimal("0")),
                    "claim_count": len(rows),
                }
                for uid, rows in grouped.items()
            ),
            key=lambda item: (item["max_bonus_pct"], item["claim_count"]),
            reverse=True,
        )[:10]

        suspects = []
        for uid, rows in grouped.items():
            metrics = calculate_player_hourly_metrics(rows)
            if metrics["risk_level"] == "LOW":
                continue
            suspects.append({
                "discord_id": uid,
                "claim_count": metrics["claim_count"],
                "risk_level": metrics["risk_level"],
                "risk_badge": metrics["risk_badge"],
                "regularity_pct": metrics["regularity_pct"],
                "std_dev_sec": metrics["std_dev_sec"],
                "alerts": list(metrics.get("alerts") or []),
            })
        suspects.sort(key=lambda item: (0 if item["risk_level"] == "HIGH" else 1, -item["claim_count"]))

        return {
            "total_claims": int(global_stats.get("total_claims") or 0),
            "total_usd": Decimal(str(global_stats.get("total_usd") or 0)),
            "unique_players": int(global_stats.get("unique_players") or 0),
            "top_users": top_users,
            "top_streaks": top_streaks,
            "top_bonuses": top_bonuses,
            "suspects": suspects,
        }

    @staticmethod
    def reset(tx) -> None:
        """Supprime l'historique hourly_logs après l'envoi réussi du rapport de minuit.

        Le combo joueur (hourly_last_at, hourly_combo_bonus, hourly_streak) n'est pas touché.
        """
        tx.execute("DELETE FROM hourly_logs")

    @staticmethod
    def get_last_report_date(tx) -> str | None:
        """Retourne la date (YYYY-MM-DD) du dernier rapport quotidien hourly consigné."""
        row = tx.one("SELECT last_found_on FROM events WHERE event = 'daily_hourly_report'")
        return row["last_found_on"] if row else None

    @staticmethod
    def set_last_report_date(tx, date_str: str, now_dt: datetime) -> None:
        """Enregistre la date (YYYY-MM-DD) du dernier rapport quotidien hourly."""
        tx.execute(
            """
            INSERT INTO events (event, next_at, last_found_on, last_reward)
            VALUES ('daily_hourly_report', %s, %s, 0.00)
            ON DUPLICATE KEY UPDATE
                next_at = VALUES(next_at),
                last_found_on = VALUES(last_found_on)
            """,
            (now_dt, date_str),
        )

    @staticmethod
    def get_user_hourly_logs(tx, discord_id: int, limit: int = 50) -> list[dict]:
        """Récupère l'historique chronologique des exécutions /hourly d'un joueur."""
        rows = tx.all(
            """
            SELECT id, discord_id, claimed_at, interval_seconds, base_usd, bonus_pct, total_usd, streak, combo_lost
            FROM hourly_logs
            WHERE discord_id = %s
            ORDER BY claimed_at DESC
            LIMIT %s
            """,
            (discord_id, limit),
        ) or []
        # Les N plus récents, restitués du plus ancien au plus récent.
        return list(reversed([_normalize_hourly_row(r) for r in rows]))


def extract_hourly_intervals(logs: list[dict]) -> list[float]:
    """Extrait la série des intervalles temporels (en secondes) entre exécutions successives."""
    if len(logs) <= 1:
        return []

    intervals = []
    for i in range(1, len(logs)):
        prev_dt = logs[i - 1]["claimed_at"]
        curr_dt = logs[i]["claimed_at"]

        if prev_dt and curr_dt:
            if getattr(prev_dt, "tzinfo", None) is not None and getattr(curr_dt, "tzinfo", None) is None:
                curr_dt = curr_dt.replace(tzinfo=timezone.utc)
            elif getattr(prev_dt, "tzinfo", None) is None and getattr(curr_dt, "tzinfo", None) is not None:
                prev_dt = prev_dt.replace(tzinfo=timezone.utc)
            delta = max(0.0, (curr_dt - prev_dt).total_seconds())
            intervals.append(delta)
        else:
            sec = logs[i].get("interval_seconds")
            intervals.append(float(sec) if sec is not None else 0.0)

    return intervals


def calculate_player_hourly_metrics(logs: list[dict]) -> dict[str, Any]:
    """Calcule les métriques d'audit et le niveau de risque d'automatisation pour /hourly.

    Args:
        logs: Liste chronologique des exécutions hourly du joueur.

    Returns:
        Dictionnaire synthétique avec moyennes, écart-type, constance et niveau de risque.
    """
    total_claims = len(logs)
    total_usd = sum((l.get("total_usd") or Decimal("0") for l in logs), Decimal("0"))
    max_streak = max((l.get("streak", 0) for l in logs), default=0)
    max_bonus_pct = max((l.get("bonus_pct", Decimal("0")) for l in logs), default=Decimal("0"))

    intervals = extract_hourly_intervals(logs)

    metrics: dict[str, Any] = {
        "claim_count": total_claims,
        "total_usd": total_usd,
        "max_streak": max_streak,
        "max_bonus_pct": max_bonus_pct,
        "intervals_count": len(intervals),
        "mean_interval_sec": None,
        "std_dev_sec": None,
        "regularity_pct": None,
        "risk_level": "LOW",  # 'LOW', 'MEDIUM', 'HIGH'
        "risk_badge": "🟢",
        "alerts": [],
        "min_interval_sec": min(intervals) if intervals else None,
        "max_interval_sec": max(intervals) if intervals else None,
    }

    if not intervals:
        return metrics

    m = len(intervals)
    mean_val = sum(intervals) / m
    metrics["mean_interval_sec"] = mean_val

    if m >= 2:
        variance = sum((x - mean_val) ** 2 for x in intervals) / m
        std_dev = math.sqrt(variance)
        metrics["std_dev_sec"] = std_dev

        # Indice de régularité
        cv = std_dev / mean_val if mean_val > 0 else 0.0
        reg_pct = max(0.0, min(100.0, (1.0 - cv) * 100.0))
        metrics["regularity_pct"] = reg_pct

        # Détection d'automatisation par bot
        if std_dev <= 5.0 and m >= 4:
            metrics["risk_level"] = "HIGH"
            metrics["risk_badge"] = "🔴"
            metrics["alerts"].append("Variance quasi-nulle (std dev <= 5s) : forte probabilité de bot/macro.")
        elif std_dev <= 15.0 and m >= 5:
            metrics["risk_level"] = "MEDIUM"
            metrics["risk_badge"] = "🟡"
            metrics["alerts"].append("Grande régularité des intervalles (std dev <= 15s).")
        elif reg_pct >= 95.0 and m >= 6:
            metrics["risk_level"] = "MEDIUM"
            metrics["risk_badge"] = "🟡"
            metrics["alerts"].append("Indice de constance très élevé (>= 95%).")

    # Détection de sommeil / activité ininterrompue sur 14+ claims consécutifs (14h d'affilée sans pause > 2h)
    if m >= 12:
        long_sleep = any(iv >= 7200 for iv in intervals)
        if not long_sleep:
            if metrics["risk_level"] == "LOW":
                metrics["risk_level"] = "MEDIUM"
                metrics["risk_badge"] = "🟡"
            metrics["alerts"].append("Activité continue sur 12+ heures sans pause sommeil (> 2h).")

    return metrics

