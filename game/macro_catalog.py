"""
Catalogue des commandes admissibles dans les macros de joueurs.

Définit :
- Les spécifications des paramètres attendus pour chaque commande (ParamSpec).
- La liste des commandes autorisées et leurs paramètres forcés (ex: confirm=True).
- La liste explicite des commandes exclues.
- La validation et conversion typée des arguments pour les macros.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable

from game.game_error import GameError


@dataclass(frozen=True)
class ParamSpec:
    """Spécification d'un paramètre d'une commande admissible."""
    name: str
    type: str  # 'str', 'int', 'decimal', 'choice', 'user'
    label_fr: str
    label_en: str
    required: bool = True
    default: Any = None
    choices: list[str] = field(default_factory=list)
    min_val: int | float | Decimal | None = None
    max_val: int | float | Decimal | None = None


@dataclass(frozen=True)
class MacroCommandSpec:
    """Spécification d'une commande admissible en macro."""
    method: str
    label_fr: str
    label_en: str
    params: list[ParamSpec] = field(default_factory=list)
    force_args: dict[str, Any] = field(default_factory=dict)


# Commandes formellement exclues par les règles du jeu ou la spécification
EXCLUDED_COMMANDS = frozenset({
    # Événements réseau
    "event",
    "hash",
    "pin",
    "decode",
    "anomaly",
    "buffer",
    "signal",
    "packet",
    # Sauvegarde interactive ponctuelle
    "hourly_save",
    "hourly_save_combo",
    # Prévention de la récursion
    "macro",
    "macro-create",
    "macro-delete",
    # Utilitaire hors gameplay
    "set_language",
})


MACRO_CATALOG: dict[str, MacroCommandSpec] = {
    "claim": MacroCommandSpec(
        method="claim",
        label_fr="Récolter le Rootium miné",
        label_en="Claim mined Rootium",
    ),
    "hourly": MacroCommandSpec(
        method="hourly",
        label_fr="Récompense horaire USD",
        label_en="Claim hourly USD reward",
    ),
    "upgrade": MacroCommandSpec(
        method="upgrade",
        label_fr="Améliorer l'infrastructure",
        label_en="Upgrade infrastructure",
        force_args={"confirm": True},
    ),
    "buy": MacroCommandSpec(
        method="buy",
        label_fr="Acheter un module",
        label_en="Buy module",
        params=[
            ParamSpec(
                name="kind",
                type="choice",
                label_fr="Type de module",
                label_en="Module type",
                choices=["mining", "attack", "defense"],
            ),
            ParamSpec(
                name="tier",
                type="choice",
                label_fr="Tier (1-6)",
                label_en="Tier (1-6)",
                choices=["1", "2", "3", "4", "5", "6"],
            ),
            ParamSpec(
                name="count",
                type="str",
                label_fr="Quantité ou 'all'",
                label_en="Quantity or 'all'",
                required=False,
                default="1",
            ),
        ],
        force_args={"confirm": True},
    ),
    "convert": MacroCommandSpec(
        method="convert",
        label_fr="Convertir Rootium en USD",
        label_en="Sell Rootium for USD",
        params=[
            ParamSpec(
                name="amount",
                type="str",
                label_fr="Montant ou 'all'",
                label_en="Amount or 'all'",
                default="all",
            ),
        ],
        force_args={"confirm": True},
    ),
    "compile": MacroCommandSpec(
        method="compile",
        label_fr="Produire des points ATK",
        label_en="Produce ATK points",
        params=[
            ParamSpec(
                name="atk",
                type="str",
                label_fr="Points ATK ou 'all'",
                label_en="ATK points or 'all'",
                default="all",
            ),
            ParamSpec(
                name="method_name",
                type="choice",
                label_fr="Méthode de compilation",
                label_en="Compile method",
                required=False,
                default="skilled",
                choices=["unskilled", "skilled", "ai"],
            ),
        ],
        force_args={"confirm": True},
    ),
    "contract": MacroCommandSpec(
        method="contract",
        label_fr="Contrat de travail",
        label_en="Work contract",
        params=[
            ParamSpec(
                name="action",
                type="choice",
                label_fr="Action",
                label_en="Action",
                choices=["collect", "view", "start"],
                default="collect",
            ),
            ParamSpec(
                name="duration",
                type="choice",
                label_fr="Durée (si start)",
                label_en="Duration (if start)",
                required=False,
                default=None,
                choices=["short", "medium", "long"],
            ),
        ],
    ),
    "claim_auto": MacroCommandSpec(
        method="claim_auto",
        label_fr="Activer l'autoclaim",
        label_en="Start autoclaim",
        params=[
            ParamSpec(
                name="count",
                type="str",
                label_fr="Crédits ou 'all'",
                label_en="Credits or 'all'",
                required=False,
                default="all",
            ),
        ],
    ),
    "claim_cancel": MacroCommandSpec(
        method="claim_cancel",
        label_fr="Annuler l'autoclaim",
        label_en="Cancel autoclaim",
    ),
    "scan": MacroCommandSpec(
        method="scan",
        label_fr="Scanner un réseau",
        label_en="Scan network",
        params=[
            ParamSpec(
                name="target",
                type="user",
                label_fr="Joueur ciblé (ID Discord)",
                label_en="Target player (Discord ID)",
            ),
        ],
    ),
    "hack": MacroCommandSpec(
        method="hack",
        label_fr="Lancer une attaque PvP",
        label_en="Launch PvP hack",
        params=[
            ParamSpec(
                name="secret_id",
                type="str",
                label_fr="Identifiant secret adverse",
                label_en="Target secret ID",
            ),
            ParamSpec(
                name="attack_points",
                type="int",
                label_fr="Points ATK engagés",
                label_en="ATK points engaged",
                min_val=1,
            ),
            ParamSpec(
                name="target",
                type="choice",
                label_fr="Cible du hack",
                label_en="Target zone",
                choices=["mining", "attack"],
            ),
        ],
    ),
    "reputation": MacroCommandSpec(
        method="reputation",
        label_fr="Donner un point de réputation",
        label_en="Give reputation point",
        params=[
            ParamSpec(
                name="target",
                type="user",
                label_fr="Joueur bénéficiaire (ID Discord)",
                label_en="Beneficiary player (Discord ID)",
            ),
        ],
    ),
    "trade": MacroCommandSpec(
        method="trade",
        label_fr="Initier un échange de ressources",
        label_en="Initiate trade",
        params=[
            ParamSpec(
                name="target",
                type="user",
                label_fr="Partenaire d'échange (ID Discord)",
                label_en="Trade partner (Discord ID)",
            ),
            ParamSpec(
                name="send_usd",
                type="decimal",
                label_fr="USD envoyés",
                label_en="USD sent",
                required=False,
                default=0,
                min_val=0,
            ),
            ParamSpec(
                name="send_rtm",
                type="decimal",
                label_fr="Rootium envoyé",
                label_en="Rootium sent",
                required=False,
                default=0,
                min_val=0,
            ),
            ParamSpec(
                name="receive_usd",
                type="decimal",
                label_fr="USD demandés",
                label_en="USD requested",
                required=False,
                default=0,
                min_val=0,
            ),
            ParamSpec(
                name="receive_rtm",
                type="decimal",
                label_fr="Rootium demandé",
                label_en="Rootium requested",
                required=False,
                default=0,
                min_val=0,
            ),
        ],
    ),
    "network": MacroCommandSpec(
        method="network",
        label_fr="Consulter son terminal réseau",
        label_en="Inspect network terminal",
    ),
    "top": MacroCommandSpec(
        method="top",
        label_fr="Consulter le classement",
        label_en="View leaderboard",
        params=[
            ParamSpec(
                name="category",
                type="choice",
                label_fr="Catégorie",
                label_en="Category",
                required=False,
                default="reputation",
                choices=["reputation", "dollars", "rootium"],
            ),
        ],
    ),
    "rmd": MacroCommandSpec(
        method="rmd",
        label_fr="Consulter ou programmer un rappel",
        label_en="View or set reminder",
        params=[
            ParamSpec(
                name="action",
                type="choice",
                label_fr="Action de rappel",
                label_en="Reminder action",
                choices=["list", "create", "cancel"],
                default="list",
            ),
            ParamSpec(
                name="target",
                type="choice",
                label_fr="Cible intelligente (si create)",
                label_en="Smart target (if create)",
                required=False,
                default=None,
                choices=["hourly", "claim", "events", "all"],
            ),
        ],
    ),
}


def validate_step_args(method: str, raw_args: dict | None) -> dict:
    """
    Valide et normalise les arguments d'une étape de macro à partir de sa spécification.
    Lève GameError('macro_excluded') si la commande est bannie,
    ou GameError('macro_invalid_args') si des paramètres sont incorrects.
    """
    clean_method = (method or "").strip().lower()
    if clean_method in EXCLUDED_COMMANDS:
        raise GameError("macro_excluded", command=clean_method)

    spec = MACRO_CATALOG.get(clean_method)
    if not spec:
        raise GameError("macro_unknown_command", command=clean_method)

    raw = raw_args or {}
    validated = dict(spec.force_args)

    for p in spec.params:
        val = raw.get(p.name)

        # Valeur absente
        if val is None or val == "":
            if p.required:
                if p.default is not None:
                    val = p.default
                else:
                    raise GameError("macro_invalid_args", param=p.name, reason="missing_required")
            else:
                val = p.default

        # Traitement selon le type si valeur non nulle
        if val is not None:
            if p.type == "choice":
                val_str = str(val).strip().lower()
                if p.choices and val_str not in p.choices:
                    raise GameError(
                        "macro_invalid_args",
                        param=p.name,
                        reason=f"must_be_one_of_{','.join(p.choices)}",
                    )
                val = val_str
            elif p.type == "int":
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    raise GameError("macro_invalid_args", param=p.name, reason="must_be_integer")
                if p.min_val is not None and val < p.min_val:
                    raise GameError("macro_invalid_args", param=p.name, reason=f"min_{p.min_val}")
                if p.max_val is not None and val > p.max_val:
                    raise GameError("macro_invalid_args", param=p.name, reason=f"max_{p.max_val}")
            elif p.type == "decimal":
                try:
                    val = Decimal(str(val))
                except Exception:
                    raise GameError("macro_invalid_args", param=p.name, reason="must_be_decimal")
                if p.min_val is not None and val < Decimal(str(p.min_val)):
                    raise GameError("macro_invalid_args", param=p.name, reason=f"min_{p.min_val}")
                # Serialisation JSON compatible
                val = str(val)
            elif p.type == "user":
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    raise GameError("macro_invalid_args", param=p.name, reason="must_be_user_id")
            elif p.type == "str":
                val = str(val).strip()

        validated[p.name] = val

    # Cas particulier : commande buy
    if clean_method == "buy":
        raw_cnt = raw.get("count", raw.get("amount", validated.get("count", "1")))
        raw_cnt_str = str(raw_cnt).strip().lower()
        if raw_cnt_str in ("all", "max", "tout"):
            validated["all"] = True
            validated.pop("count", None)
        else:
            try:
                cnt_int = int(raw_cnt_str)
                validated["count"] = max(1, cnt_int)
                validated.pop("all", None)
            except (ValueError, TypeError):
                validated["count"] = 1
                validated.pop("all", None)

        # conversion de tier en entier si possible
        if "tier" in validated:
            try:
                validated["tier"] = int(validated["tier"])
            except (ValueError, TypeError):
                validated["tier"] = 1

    # Forcer les arguments prioritaires du catalogue (ex: confirm=True)
    validated.update(spec.force_args)
    return validated

