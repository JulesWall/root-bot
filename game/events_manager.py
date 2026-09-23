"""
Gestionnaire d'état et de consultation des événements réseau (/event).

Ce module centralise la lecture du statut de tous les mini-jeux et événements communautaires :
- Hash Challenge ('hash')
- Code PIN ('pin')

Chaque événement est évalué par rapport à l'horloge courante de la transaction SQL (tx.now)
pour déterminer s'il est actif en direct ou en période de rechargement (cooldown).
"""

from datetime import datetime, timezone
from decimal import Decimal
from game.db.events import EventsDB


class EventsManager:
    """Gestionnaire de consultation des événements du bot."""

    SUPPORTED_EVENTS = ["hash", "pin", "decode", "anomaly", "buffer", "signal", "packet"]

    @classmethod
    def get_all_events_status(cls, tx) -> dict:
        """
        Récupère l'état courant de tous les événements supportés,
        classés par ordre chronologique d'apparition :
        - Événements actifs en premier (du plus ancien au plus récent).
        - Événements en cooldown ensuite (du plus proche au plus lointain).
        
        Returns:
            dict: {
                'events': {
                    'hash': { 'status': 'active' | 'cooldown', ... },
                    ...
                }
            }
        """
        now = tx.now
        results = {}

        for event_name in cls.SUPPORTED_EVENTS:
            db_event = EventsDB.get(tx, event_name)
            if db_event and db_event.get("next_at"):
                next_at = db_event["next_at"]
                if next_at > now:
                    remaining_seconds = max(0, int((next_at - now).total_seconds()))
                    results[event_name] = {
                        "status": "cooldown",
                        "next_at": next_at,
                        "remaining_seconds": remaining_seconds,
                        "last_found_by": db_event.get("last_found_by"),
                        "last_found_on": db_event.get("last_found_on") or "Inconnu",
                        "last_reward": Decimal(str(db_event.get("last_reward") or "0.00")),
                    }
                    continue

            # Événement actif / disponible
            results[event_name] = {
                "status": "active",
                "next_at": db_event.get("next_at") if db_event else None,
                "remaining_seconds": 0,
            }

        def _sort_key(item):
            name, data = item
            is_active = data.get("status") == "active"
            nxt = data.get("next_at")
            if nxt is not None and getattr(nxt, "tzinfo", None) is not None:
                dt = nxt.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                dt = nxt
            idx = cls.SUPPORTED_EVENTS.index(name) if name in cls.SUPPORTED_EVENTS else 999
            if is_active:
                return (0, dt or datetime.min, idx)
            else:
                return (1, dt or datetime.max, idx)

        sorted_results = dict(sorted(results.items(), key=_sort_key))
        return {"events": sorted_results}

