"""
Configuration numérique et évaluateur arithmétique sécurisé sans eval() Python.

Ce module résout un problème critique de sécurité et de précision :
1. Sécurité (Zéro eval) :
   Permet d'éditer des formules mathématiques dans data/math.json sans risquer
   l'exécution arbitraire de code malveillant (RCE). L'expression est analysée via l'AST
   (Abstract Syntax Tree) de Python et validée par une liste blanche stricte de nœuds.
2. Précision économique (Decimal) :
   Tous les nombres manipulés sont convertis en instances de Decimal pour éliminer
   les imprécisions d'arrondis inhérentes aux nombres flottants binaires IEEE-754.
"""

import ast
import hashlib
import json
import operator
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path


class MathConfig:
    """Charge les règles d'équilibrage et évalue les formules de manière sécurisée."""

    path = Path(__file__).resolve().parent.parent / 'data' / 'math.json'
    _cached_values: dict | None = None
    _cached_mtime: float | None = None

    @classmethod
    def clear_cache(cls):
        """Force l'invalidation du cache en mémoire."""
        cls._cached_values = None
        cls._cached_mtime = None

    @classmethod
    def load(cls) -> dict:
        """
        Charge et valide le fichier data/math.json avec mise en cache mémoire.
        
        Vérifie le st_mtime du fichier : si inchangé, renvoie immédiatement le dictionnaire
        en mémoire (0 I/O disque, 0 parsing JSON, 0 parcours AST).
        Si le fichier a été modifié sur le disque, recharge et revalide automatiquement.
        """
        try:
            mtime = cls.path.stat().st_mtime
        except Exception:
            mtime = None

        if cls._cached_values is not None and mtime is not None and cls._cached_mtime == mtime:
            return cls._cached_values

        values = json.loads(cls.path.read_text(encoding='utf-8'))
        # Compilation préalable de toutes les formules, y compris les inutilisées
        for expression in values.get('formulas', {}).values():
            cls.validate(ast.parse(expression, mode='eval'))

        cls._cached_values = values
        cls._cached_mtime = mtime
        return values

    @classmethod
    def get_event_firewall_multiplier(cls, firewall_level: int) -> int:
        """Calcule le multiplicateur de gains d'événements conféré par le pare-feu.
        
        Suit le barème par niveau de data/math.json (actuellement x1 à x6).
        Le repli par défaut est (niveau + 1).
        """
        rules = cls.load()
        multipliers = rules.get("event_firewall_multipliers")
        if isinstance(multipliers, dict):
            lvl_key = str(int(firewall_level or 0))
            if lvl_key in multipliers:
                return max(1, int(multipliers[lvl_key]))

        # Rétrocompatibilité avec l'ancien format 'event_firewall_multiplier'
        legacy_cfg = rules.get("event_firewall_multiplier")
        if isinstance(legacy_cfg, dict) and "base" in legacy_cfg:
            base = int(legacy_cfg.get("base", 1))
            per_level = int(legacy_cfg.get("per_level", 1))
            return max(1, base + (int(firewall_level or 0) * per_level))

        # Fallback standard : niveau + 1 (1, 2, 3, 4, 5, 6...)
        lvl = max(0, int(firewall_level or 0))
        return lvl + 1

    @classmethod
    def get_module_stat(cls, kind: str, tier: int) -> int:
        """Retourne la statistique unitaire conférée par un module selon son type et son tier (1 à 5)."""
        rules = cls.load()
        stats_cfg = rules.get("module_stats", {})
        mapping = {
            "mining": "mining_hashrate_hs",
            "attack": "attack_bits_per_s",
            "bay_defense": "bay_defense_power",
            "defense": "bay_defense_power",
        }
        category = mapping.get(kind)
        if not category or category not in stats_cfg:
            return 0
        return int(stats_cfg[category].get(str(int(tier)), 0))

    @classmethod
    def get_module_ram(cls, tier: int) -> int:
        """Retourne la mémoire vive (en octets) conférée par un module de minage selon son tier (1 à 5).

        La mémoire vive détermine la capacité de stockage du Rootium miné : plus elle est
        importante, plus le module peut miner longtemps avant de saturer et d'exiger un /claim.
        """
        rules = cls.load()
        ram_cfg = rules.get("module_stats", {}).get("mining_ram_bytes", {})
        return int(ram_cfg.get(str(int(tier)), 0))

    @classmethod
    def get_firewall_network_defense(cls, firewall_level: int) -> int:
        """Retourne les points passifs de défense réseau conférés par le niveau de pare-feu."""
        rules = cls.load()
        def_map = rules.get("firewall_network_defense", {})
        lvl_key = str(max(0, min(5, int(firewall_level or 0))))
        return int(def_map.get(lvl_key, 0))

    @classmethod
    def format_hashrate(cls, hashrate_hs: int | float | Decimal) -> str:
        """Formate dynamiquement une puissance de hachage (H/s, KH/s, MH/s, GH/s, TH/s)."""
        val = Decimal(str(hashrate_hs or 0))
        if val >= Decimal('1000000000000'):
            return f"{val / Decimal('1000000000000'):,.2f} TH/s"
        if val >= Decimal('1000000000'):
            return f"{val / Decimal('1000000000'):,.2f} GH/s"
        if val >= Decimal('1000000'):
            return f"{val / Decimal('1000000'):,.2f} MH/s"
        if val >= Decimal('1000'):
            return f"{val / Decimal('1000'):,.2f} KH/s"
        return f"{int(val)} H/s"

    @classmethod
    def format_bits_per_s(cls, bits_per_s: int | float | Decimal) -> str:
        """Formate un débit d'attaque (Bit/s, KBit/s, MBit/s, GBit/s)."""
        val = Decimal(str(bits_per_s or 0))
        if val >= Decimal('1000000000'):
            return f"{val / Decimal('1000000000'):,.2f} GBit/s"
        if val >= Decimal('1000000'):
            return f"{val / Decimal('1000000'):,.2f} MBit/s"
        if val >= Decimal('1000'):
            return f"{val / Decimal('1000'):,.2f} KBit/s"
        return f"{int(val)} Bit/s"

    COMPILE_METHOD_ALIASES = {
        'unskilled': 'unskilled',
        'uns': 'unskilled',
        'non-qualifie': 'unskilled',
        'non-qualifies': 'unskilled',
        'nq': 'unskilled',
        'skilled': 'skilled',
        'sk': 'skilled',
        'qualifie': 'skilled',
        'qualifies': 'skilled',
        'q': 'skilled',
        'ai': 'ai',
        'ia': 'ai',
    }

    @classmethod
    def normalize_compile_method(cls, raw) -> str | None:
        """Normalise un identifiant de moyen de compile, ou None si inconnu."""
        token = str(raw or '').strip().lower().replace('é', 'e').replace('è', 'e')
        return cls.COMPILE_METHOD_ALIASES.get(token)

    @classmethod
    def compile_quote(cls, bits_per_s: int, atk_yield: int, method: str) -> dict:
        """Calcule coût RTM et durée d'une production d'ATK selon le débit matériel."""
        method = cls.normalize_compile_method(method) or method
        rules = cls.load()
        settings = rules.get('compile', {})
        spec = settings.get('methods', {}).get(method) or {}
        bits_per_atk = Decimal(str(settings.get('bits_per_atk', 1) or 1))
        multiplier = Decimal(str(spec.get('duration_multiplier', 1) or 1))
        rtm_per_atk = Decimal(str(spec.get('rtm_per_atk', spec.get('rtm_per_module', 0)) or 0))
        places = int(rules.get('rtm_decimal_places', 5))
        quantum = Decimal('1').scaleb(-places)

        atk = max(0, int(atk_yield))
        bits = max(0, int(bits_per_s))
        rtm_paid = (rtm_per_atk * Decimal(str(atk))).quantize(quantum, rounding=ROUND_HALF_UP)
        if bits > 0 and atk > 0:
            duration_raw = (Decimal(str(atk)) / Decimal(str(bits))) * bits_per_atk * multiplier
            duration_seconds = max(1, int(duration_raw.to_integral_value(rounding=ROUND_CEILING)))
        else:
            duration_seconds = 1
        return {
            'method': method,
            'bits_per_s': bits,
            'atk_yield': atk,
            'rtm_paid': rtm_paid,
            'duration_seconds': duration_seconds,
        }

    @classmethod
    def format_memory(cls, num_bytes: int | float | Decimal) -> str:
        """Formate dynamiquement une quantité de mémoire vive (o, Ko, Mo, Go, To, Po).

        Utilise des paliers décimaux (1 Ko = 1000 o) pour une lecture conviviale de type système.
        """
        val = Decimal(str(num_bytes or 0))
        units = ['o', 'Ko', 'Mo', 'Go', 'To', 'Po']
        step = Decimal('1000')
        idx = 0
        while val >= step and idx < len(units) - 1:
            val /= step
            idx += 1
        if idx == 0:
            return f"{int(val)} o"
        return f"{val:,.2f} {units[idx]}"

    @classmethod
    def rtm_to_usd_rate(cls) -> Decimal:
        """Retourne le taux fixe de conversion RTM → USD (1 RTM = N dollars)."""
        rate = Decimal(str(cls.load().get('conversion', {}).get('rtm_to_usd', 0)))
        return rate if rate > 0 else Decimal('0')

    @classmethod
    def convert_rtm_to_usd(cls, rtm_amount) -> Decimal:
        """Convertit un montant de Rootium en USD au taux fixe, arrondi à 2 décimales."""
        places = int(cls.load().get('usd_decimal_places', 2))
        quantum = Decimal('1').scaleb(-places)
        usd = Decimal(str(rtm_amount or 0)) * cls.rtm_to_usd_rate()
        return usd.quantize(quantum, rounding=ROUND_HALF_UP)

    @classmethod
    def compute_mining_progress(cls, player_row: dict, stats: dict, now) -> dict:
        """Calcule l'état de minage courant d'un joueur (production, mémoire, temps avant saturation).

        Modèle économique :
        - Le débit de minage (RTM/min) est proportionnel au hashrate total.
        - Chaque Rootium miné occupe `bytes_per_rtm` octets de mémoire vive.
        - La mémoire vive totale (somme des modules) fixe la capacité maximale de stockage.
        - Le minage s'accumule dans un tampon (buffer) jusqu'à saturation de la mémoire,
          après quoi il faut /claim pour vider la mémoire et créditer le Rootium.

        Args:
            player_row: Ligne joueur (contient mining_buffer et mining_last_update_at).
            stats: Résultat de calculate_player_stats (fournit total_hashrate_hs et total_ram_bytes).
            now: Horodatage courant (datetime) servant de référence à l'accumulation.

        Returns:
            dict: État détaillé du minage prêt à être affiché ou crédité par /claim.
        """
        rules = cls.load()
        mining_cfg = rules.get("mining", {})
        rate_per_hs = Decimal(str(mining_cfg.get("rootium_per_hs_per_minute", 0)))
        bytes_per_rtm = Decimal(str(mining_cfg.get("bytes_per_rtm", 1) or 1))

        total_hashrate = Decimal(str(stats.get('total_hashrate_hs', 0)))
        total_ram_bytes = Decimal(str(stats.get('total_ram_bytes', 0)))

        # Bonus de réputation : +0,5 % par point de réputation (+0.005 additif)
        rep_count = int(player_row.get('reputation', 0) or 0)
        rep_bonus_per_point = Decimal(str(mining_cfg.get("reputation_bonus_per_point", "0.005") or "0.005"))
        rep_multiplier = Decimal('1') + (Decimal(str(rep_count)) * rep_bonus_per_point)

        base_rate_per_min = total_hashrate * rate_per_hs
        rate_per_min = base_rate_per_min * rep_multiplier
        capacity_rtm = (total_ram_bytes / bytes_per_rtm) if bytes_per_rtm > 0 else Decimal('0')

        stored = Decimal(str(player_row.get('mining_buffer') or 0))
        last = player_row.get('mining_last_update_at')

        elapsed_seconds = Decimal('0')
        if last is not None and hasattr(last, 'timestamp'):
            now_ref = now
            # Alignement des fuseaux horaires pour une soustraction cohérente
            if getattr(last, 'tzinfo', None) is not None and getattr(now_ref, 'tzinfo', None) is None:
                from datetime import timezone as _tz
                now_ref = now_ref.replace(tzinfo=_tz.utc)
            elif getattr(last, 'tzinfo', None) is None and getattr(now_ref, 'tzinfo', None) is not None:
                last = last.replace(tzinfo=now_ref.tzinfo)
            elapsed_seconds = Decimal(str(max(0.0, (now_ref - last).total_seconds())))

        produced = rate_per_min * (elapsed_seconds / Decimal('60'))
        buffer = stored + produced
        if capacity_rtm > 0:
            buffer = min(buffer, capacity_rtm)
        else:
            buffer = Decimal('0')

        # Arrondi à la précision RTM (5 décimales)
        buffer = buffer.quantize(Decimal('0.00001'))

        memory_used_bytes = buffer * bytes_per_rtm
        memory_pct = (buffer / capacity_rtm * Decimal('100')) if capacity_rtm > 0 else Decimal('0')
        is_full = capacity_rtm > 0 and buffer >= capacity_rtm

        remaining_rtm = (capacity_rtm - buffer) if capacity_rtm > 0 else Decimal('0')
        if rate_per_min > 0 and capacity_rtm > 0 and remaining_rtm > 0:
            seconds_to_full = int((remaining_rtm / rate_per_min * Decimal('60')).to_integral_value())
        else:
            seconds_to_full = 0

        # Temps total de remplissage (de 0 % à 100 %), indépendant du tampon courant :
        # c'est la cadence de /claim du réseau (capacité / débit).
        if rate_per_min > 0 and capacity_rtm > 0:
            seconds_to_fill_total = int((capacity_rtm / rate_per_min * Decimal('60')).to_integral_value())
        else:
            seconds_to_fill_total = 0

        return {
            'rate_per_min': rate_per_min,
            'base_rate_per_min': base_rate_per_min,
            'reputation_points': rep_count,
            'reputation_multiplier': rep_multiplier,
            'reputation_bonus_pct': (Decimal(str(rep_count)) * rep_bonus_per_point * Decimal('100')),
            'total_ram_bytes': int(total_ram_bytes),
            'total_ram_formatted': cls.format_memory(total_ram_bytes),
            'capacity_rtm': capacity_rtm,
            'buffer': buffer,
            'memory_used_bytes': int(memory_used_bytes),
            'memory_used_formatted': cls.format_memory(memory_used_bytes),
            'memory_pct': memory_pct,
            'is_full': is_full,
            'seconds_to_full': seconds_to_full,
            'seconds_to_fill_total': seconds_to_fill_total,
        }

    @classmethod
    def calculate_player_stats(cls, player_row: dict) -> dict:
        """Calcule l'ensemble des statistiques matérielles et défensives d'un joueur."""
        total_hashrate = 0
        total_ram = 0
        total_bits_per_s = 0
        total_bay_defense = 0
        bay_details = {}

        for tier in range(1, 6):
            m_count = int(player_row.get(f'mining_t{tier}', 0) or 0)
            a_count = int(player_row.get(f'attack_t{tier}', 0) or 0)
            d_count = int(player_row.get(f'bay_defense_t{tier}', 0) or 0)

            m_unit = cls.get_module_stat('mining', tier)
            m_ram_unit = cls.get_module_ram(tier)
            a_unit = cls.get_module_stat('attack', tier)
            d_unit = cls.get_module_stat('bay_defense', tier)

            m_hashrate = m_count * m_unit
            m_ram = m_count * m_ram_unit
            a_bits = a_count * a_unit
            d_power = d_count * d_unit

            total_hashrate += m_hashrate
            total_ram += m_ram
            total_bits_per_s += a_bits
            total_bay_defense += d_power

            bay_details[tier] = {
                'mining_count': m_count,
                'mining_hashrate': m_hashrate,
                'mining_ram': m_ram,
                'mining_ram_formatted': cls.format_memory(m_ram),
                'attack_count': a_count,
                'attack_bits_per_s': a_bits,
                'bay_defense_count': d_count,
                'bay_defense_power': d_power,
            }

        fw_level = int(player_row.get('firewall_level', 0) or 0)
        net_def = cls.get_firewall_network_defense(fw_level)
        total_def = total_bay_defense + net_def

        return {
            'total_hashrate_hs': total_hashrate,
            'total_hashrate_formatted': cls.format_hashrate(total_hashrate),
            'total_ram_bytes': total_ram,
            'total_ram_formatted': cls.format_memory(total_ram),
            'total_bits_per_s': total_bits_per_s,
            'total_bits_per_s_formatted': cls.format_bits_per_s(total_bits_per_s),
            'total_bay_defense': total_bay_defense,
            'network_defense': net_def,
            'total_defense': total_def,
            'bay_details': bay_details,
        }

    @classmethod
    def code(cls, values: dict) -> str:
        """
        Calcule une empreinte cryptographique (hash SHA-256 tronqué à 12 caractères)
        du fichier d'équilibrage. Permet de s'assurer de la cohérence de la version des règles.
        """
        return values['version'] + '-' + hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()[:12]

    @classmethod
    def validate(cls, node: ast.AST):
        """
        Vérification de sécurité par liste blanche (White-listing) de l'arbre syntaxique (AST).
        
        N'autorise que :
        - Les opérations arithmétiques basiques (+, -, *, /, **, %).
        - Les identifiants de variables (Name).
        - Les constantes numériques entières ou flottantes.
        - Un ensemble restreint de fonctions mathématiques : exp(), min(), max().
        Rejette immédiatement tout import, appel d'attribut (__class__, etc.) ou mot-clé suspect.
        """
        allowed = (
            ast.Expression, ast.BinOp, ast.UnaryOp, ast.Name, ast.Load, ast.Constant,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.USub, ast.UAdd, ast.Call
        )
        for child in ast.walk(node):
            if not isinstance(child, allowed):
                raise ValueError('Unsupported formula syntax')
            # Seules les fonctions pures 'exp', 'min' et 'max' sans arguments nommés sont autorisées
            if isinstance(child, ast.Call) and (not isinstance(child.func, ast.Name) or child.func.id not in ('exp', 'min', 'max') or child.keywords):
                raise ValueError('Unsupported formula function')
            # Les constantes doivent obligatoirement être numériques
            if isinstance(child, ast.Constant) and type(child.value) not in (int, float):
                raise ValueError('Formula constants must be numeric')

    @classmethod
    def formula(cls, rules: dict, name: str, **values) -> Decimal:
        """
        Évalue une formule nommée depuis les règles avec les paramètres passés en kwargs.
        
        Parcourt récursivement l'arbre AST et effectue les calculs directement
        avec des objets Decimal pour une précision absolue.
        """
        tree = ast.parse(rules['formulas'][name], mode='eval')
        cls.validate(tree)
        operations = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.Mod: operator.mod
        }

        def visit(node):
            if isinstance(node, ast.Expression):
                return visit(node.body)
            if isinstance(node, ast.Constant):
                return Decimal(str(node.value))
            if isinstance(node, ast.Name):
                return Decimal(str(values[node.id]))
            if isinstance(node, ast.BinOp):
                return operations[type(node.op)](visit(node.left), visit(node.right))
            if isinstance(node, ast.UnaryOp):
                return -visit(node.operand) if isinstance(node.op, ast.USub) else visit(node.operand)
            if isinstance(node, ast.Call):
                # Mapping sécurisé des fonctions autorisées
                fn = {'exp': lambda v: v.exp(), 'min': min, 'max': max}[node.func.id]
                return fn(*[visit(arg) for arg in node.args])
            raise ValueError('Unsupported formula')

        return visit(tree)

    @classmethod
    def get_contracts_config(cls) -> dict:
        """Retourne la configuration globale du système de contrats."""
        return cls.load().get('contracts', {})

    @classmethod
    def get_contract_tier(cls, tier: str) -> dict | None:
        """Retourne les paramètres d'un tier de contrat donné ('short', 'medium', 'long')."""
        return cls.get_contracts_config().get('tiers', {}).get(tier)

    # -------------------------------------------------------------------------
    # Accesseurs PvP V2
    # -------------------------------------------------------------------------

    @classmethod
    def get_pvp_v2(cls) -> dict:
        """Retourne la section pvp_v2 complète.

        Lève ValueError si la section est absente — un démarrage sans configuration PvP V2
        est une erreur de configuration, pas un état silencieusement acceptable.
        """
        cfg = cls.load().get('pvp_v2')
        if cfg is None:
            raise ValueError("Section 'pvp_v2' absente de data/math.json.")
        return cfg

    @classmethod
    def get_pvp_v2_fingerprint(cls) -> dict:
        """Retourne la configuration de génération des empreintes courtes.

        Valide : alphabet non vide (str), longueur entière positive,
        max_generation_attempts entier positif.
        """
        fp = cls.get_pvp_v2().get('fingerprint')
        if not isinstance(fp, dict):
            raise ValueError("pvp_v2.fingerprint doit être un objet JSON.")
        alphabet = fp.get('alphabet', '')
        length = fp.get('length', 0)
        attempts = fp.get('max_generation_attempts', 0)
        if not isinstance(alphabet, str) or len(alphabet) < 2:
            raise ValueError("pvp_v2.fingerprint.alphabet doit être une chaîne d'au moins 2 caractères.")
        if not isinstance(length, int) or length < 1:
            raise ValueError("pvp_v2.fingerprint.length doit être un entier >= 1.")
        if not isinstance(attempts, int) or attempts < 1:
            raise ValueError("pvp_v2.fingerprint.max_generation_attempts doit être un entier >= 1.")
        return fp

    @classmethod
    def get_pvp_v2_families(cls) -> list:
        """Retourne la liste des familles de logiciels PvP V2 reconnues.

        Valide : liste non vide de chaînes.
        """
        families = cls.get_pvp_v2().get('families')
        if not isinstance(families, list) or not families:
            raise ValueError("pvp_v2.families doit être une liste non vide.")
        for f in families:
            if not isinstance(f, str) or not f:
                raise ValueError(f"pvp_v2.families : entrée invalide {f!r}.")
        return families

    @classmethod
    def get_pvp_v2_tiers(cls) -> list:
        """Retourne la liste des tiers matériels valides pour le PvP V2.

        Valide : liste d'entiers strictement positifs.
        """
        tiers = cls.get_pvp_v2().get('tiers')
        if not isinstance(tiers, list) or not tiers:
            raise ValueError("pvp_v2.tiers doit être une liste non vide.")
        for t in tiers:
            if not isinstance(t, int) or t < 1:
                raise ValueError(f"pvp_v2.tiers : tier invalide {t!r} (doit être int >= 1).")
        return tiers

    @classmethod
    def get_pvp_v2_eligibility(cls) -> dict:
        """Retourne les règles d'éligibilité et de représailles.

        Valide : min_infrastructure_level_attacker int >= 0,
        retaliation_window_hours int > 0.
        """
        elig = cls.get_pvp_v2().get('eligibility')
        if not isinstance(elig, dict):
            raise ValueError("pvp_v2.eligibility doit être un objet JSON.")
        min_lvl = elig.get('min_infrastructure_level_attacker', -1)
        ret_hours = elig.get('retaliation_window_hours', 0)
        if not isinstance(min_lvl, int) or min_lvl < 0:
            raise ValueError("pvp_v2.eligibility.min_infrastructure_level_attacker doit être int >= 0.")
        if not isinstance(ret_hours, int) or ret_hours <= 0:
            raise ValueError("pvp_v2.eligibility.retaliation_window_hours doit être int > 0.")
        return elig

    @classmethod
    def get_pvp_v2_dev_costs(cls, tier: int) -> dict:
        """Retourne les coûts RTM de développement (recherche/compilation offensive et défensive) pour un tier.

        Valide : toutes les clés présentes, toutes valeurs float/int > 0.
        tier doit être dans pvp_v2.tiers.
        """
        valid_tiers = cls.get_pvp_v2_tiers()
        if tier not in valid_tiers:
            raise ValueError(f"pvp_v2 : tier {tier} inconnu (valides : {valid_tiers}).")
        costs_cfg = cls.get_pvp_v2().get('development', {}).get('costs_by_tier', {})
        tier_str = str(tier)
        required_keys = ['research_rtm', 'compile_rtm', 'patch_research_rtm', 'patch_compile_rtm']
        result = {}
        for key in required_keys:
            val = costs_cfg.get(key, {}).get(tier_str)
            if val is None:
                raise ValueError(f"pvp_v2.development.costs_by_tier.{key}.{tier_str} manquant.")
            if not isinstance(val, (int, float)) or val <= 0:
                raise ValueError(f"pvp_v2.development.costs_by_tier.{key}.{tier_str} doit être > 0.")
            result[key] = Decimal(str(val))
        return result

    @classmethod
    def get_pvp_v2_installation_duration(cls, tier: int) -> int:
        """Retourne la durée de base d'installation (secondes) pour un tier donné.

        Valide : entier positif.
        """
        valid_tiers = cls.get_pvp_v2_tiers()
        if tier not in valid_tiers:
            raise ValueError(f"pvp_v2 : tier {tier} inconnu.")
        tier_str = str(tier)
        durations = cls.get_pvp_v2().get('installation', {}).get('base_duration_seconds_by_tier', {})
        val = durations.get(tier_str)
        if val is None:
            raise ValueError(f"pvp_v2.installation.base_duration_seconds_by_tier.{tier_str} manquant.")
        if not isinstance(val, int) or val <= 0:
            raise ValueError(f"pvp_v2.installation.base_duration_seconds_by_tier.{tier_str} doit être int > 0.")
        return val

    @classmethod
    def get_pvp_v2_defense_slowdown(cls) -> tuple:
        """Retourne (defense_divisor, max_multiplier) pour le calcul du ralentissement défensif.

        Valide : defense_slowdown_divisor int > 0, defense_slowdown_max_multiplier int >= 1.
        """
        inst = cls.get_pvp_v2().get('installation', {})
        divisor = inst.get('defense_slowdown_divisor')
        max_mult = inst.get('defense_slowdown_max_multiplier')
        if not isinstance(divisor, int) or divisor <= 0:
            raise ValueError("pvp_v2.installation.defense_slowdown_divisor doit être int > 0.")
        if not isinstance(max_mult, int) or max_mult < 1:
            raise ValueError("pvp_v2.installation.defense_slowdown_max_multiplier doit être int >= 1.")
        return divisor, max_mult

    @classmethod
    def get_pvp_v2_hostile_miner(cls) -> dict:
        """Retourne la configuration Hostile Miner.

        Valide : siphon_rate float dans (0, 1], cumulative_cap_per_tier float dans (0, 1].
        """
        cfg = cls.get_pvp_v2().get('hostile_miner')
        if not isinstance(cfg, dict):
            raise ValueError("pvp_v2.hostile_miner doit être un objet JSON.")
        siphon = cfg.get('siphon_rate')
        cap = cfg.get('cumulative_cap_per_tier')
        if not isinstance(siphon, (int, float)) or not (0 < siphon <= 1):
            raise ValueError("pvp_v2.hostile_miner.siphon_rate doit être dans (0, 1].")
        if not isinstance(cap, (int, float)) or not (0 < cap <= 1):
            raise ValueError("pvp_v2.hostile_miner.cumulative_cap_per_tier doit être dans (0, 1].")
        return cfg

    @classmethod
    def get_pvp_v2_ransomware(cls) -> dict:
        """Retourne la configuration Ransomware.

        Valide : blocked_commands liste non vide, always_allowed_commands liste non vide,
        ransom_usd_by_tier dict avec toutes les clés de tiers, max_duration_hours int > 0,
        post_resolution_immunity_hours int >= 0.
        """
        cfg = cls.get_pvp_v2().get('ransomware')
        if not isinstance(cfg, dict):
            raise ValueError("pvp_v2.ransomware doit être un objet JSON.")
        blocked = cfg.get('blocked_commands')
        allowed = cfg.get('always_allowed_commands')
        ransom = cfg.get('ransom_usd_by_tier', {})
        max_dur = cfg.get('max_duration_hours', 0)
        immunity = cfg.get('post_resolution_immunity_hours', -1)
        if not isinstance(blocked, list) or not blocked:
            raise ValueError("pvp_v2.ransomware.blocked_commands doit être une liste non vide.")
        if not isinstance(allowed, list) or not allowed:
            raise ValueError("pvp_v2.ransomware.always_allowed_commands doit être une liste non vide.")
        for tier in cls.get_pvp_v2_tiers():
            val = ransom.get(str(tier))
            if val is None or not isinstance(val, (int, float)) or val <= 0:
                raise ValueError(f"pvp_v2.ransomware.ransom_usd_by_tier.{tier} manquant ou invalide.")
        if not isinstance(max_dur, int) or max_dur <= 0:
            raise ValueError("pvp_v2.ransomware.max_duration_hours doit être int > 0.")
        if not isinstance(immunity, int) or immunity < 0:
            raise ValueError("pvp_v2.ransomware.post_resolution_immunity_hours doit être int >= 0.")
        return cfg

    @classmethod
    def get_pvp_v2_currency_theft(cls) -> dict:
        """Retourne la configuration Vol de monnaie.

        Valide : taux dans (0, 1], plafond USD > 0, plancher USD >= 0,
        cooldown int > 0, fee_rate dans [0, 1).
        """
        cfg = cls.get_pvp_v2().get('currency_theft')
        if not isinstance(cfg, dict):
            raise ValueError("pvp_v2.currency_theft doit être un objet JSON.")
        rate = cfg.get('exposed_reserve_rate')
        max_usd = cfg.get('max_per_operation_usd')
        min_bal = cfg.get('victim_minimum_balance_usd')
        cooldown = cfg.get('attacker_cooldown_per_victim_hours')
        daily_cap = cfg.get('cumulative_daily_cap_rate')
        fee = cfg.get('fee_rate')
        if not isinstance(rate, (int, float)) or not (0 < rate <= 1):
            raise ValueError("pvp_v2.currency_theft.exposed_reserve_rate doit être dans (0, 1].")
        if not isinstance(max_usd, (int, float)) or max_usd <= 0:
            raise ValueError("pvp_v2.currency_theft.max_per_operation_usd doit être > 0.")
        if not isinstance(min_bal, (int, float)) or min_bal < 0:
            raise ValueError("pvp_v2.currency_theft.victim_minimum_balance_usd doit être >= 0.")
        if not isinstance(cooldown, int) or cooldown <= 0:
            raise ValueError("pvp_v2.currency_theft.attacker_cooldown_per_victim_hours doit être int > 0.")
        if not isinstance(daily_cap, (int, float)) or not (0 < daily_cap <= 1):
            raise ValueError("pvp_v2.currency_theft.cumulative_daily_cap_rate doit être dans (0, 1].")
        if not isinstance(fee, (int, float)) or not (0 <= fee < 1):
            raise ValueError("pvp_v2.currency_theft.fee_rate doit être dans [0, 1).")
        return cfg

    @classmethod
    def get_pvp_v2_saturation(cls) -> dict:
        """Retourne la configuration Saturation.

        Valide : taux dans (0, 1), plafond dans (0, 1], durée > 0.
        """
        cfg = cls.get_pvp_v2().get('saturation')
        if not isinstance(cfg, dict):
            raise ValueError("pvp_v2.saturation doit être un objet JSON.")
        red_rate = cfg.get('offensive_reduction_rate')
        cap = cfg.get('cumulative_cap')
        hours = cfg.get('duration_hours')
        if not isinstance(red_rate, (int, float)) or not (0 < red_rate < 1):
            raise ValueError("pvp_v2.saturation.offensive_reduction_rate doit être dans (0, 1).")
        if not isinstance(cap, (int, float)) or not (0 < cap <= 1):
            raise ValueError("pvp_v2.saturation.cumulative_cap doit être dans (0, 1].")
        if not isinstance(hours, (int, float)) or hours <= 0:
            raise ValueError("pvp_v2.saturation.duration_hours doit être > 0.")
        return cfg

    @classmethod
    def get_pvp_v2_market(cls) -> dict:
        """Retourne la configuration du marché PvP V2.

        Valide : prix min/max cohérents, fee_rate dans [0, 1),
        max_active_listings_per_player int >= 1.
        """
        cfg = cls.get_pvp_v2().get('market')
        if not isinstance(cfg, dict):
            raise ValueError("pvp_v2.market doit être un objet JSON.")
        min_p = cfg.get('min_price_usd')
        max_p = cfg.get('max_price_usd')
        fee = cfg.get('fee_rate')
        max_list = cfg.get('max_active_listings_per_player')
        if not isinstance(min_p, (int, float)) or min_p <= 0:
            raise ValueError("pvp_v2.market.min_price_usd doit être > 0.")
        if not isinstance(max_p, (int, float)) or max_p <= min_p:
            raise ValueError("pvp_v2.market.max_price_usd doit être > min_price_usd.")
        if not isinstance(fee, (int, float)) or not (0 <= fee < 1):
            raise ValueError("pvp_v2.market.fee_rate doit être dans [0, 1).")
        if not isinstance(max_list, int) or max_list < 1:
            raise ValueError("pvp_v2.market.max_active_listings_per_player doit être int >= 1.")
        return cfg

    @classmethod
    def validate_pvp_v2_config(cls) -> None:
        """Valide exhaustivement toute la section pvp_v2.

        Appelle chaque accesseur typé pour déclencher une erreur au démarrage
        ou lors des tests si un paramètre est absent, de mauvais type ou hors bornes.
        Ne lève rien si tout est correct.
        """
        cls.get_pvp_v2_fingerprint()
        cls.get_pvp_v2_families()
        tiers = cls.get_pvp_v2_tiers()
        cls.get_pvp_v2_eligibility()
        for t in tiers:
            cls.get_pvp_v2_dev_costs(t)
            cls.get_pvp_v2_installation_duration(t)
        cls.get_pvp_v2_defense_slowdown()
        cls.get_pvp_v2_hostile_miner()
        cls.get_pvp_v2_ransomware()
        cls.get_pvp_v2_currency_theft()
        cls.get_pvp_v2_saturation()
        cls.get_pvp_v2_market()

