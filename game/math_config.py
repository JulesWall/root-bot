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
    def get_event_firewall_multiplier(cls, firewall_level: int) -> float | int:
        """Calcule le multiplicateur de gains conféré par l'infrastructure (firewall).
        
        Suit le barème exponentiel de data/math.json (base 1.5^niveau : 1.0, 1.5, 2.25, 3.375, 5.0625, 7.59375).
        """
        rules = cls.load()
        multipliers = rules.get("event_firewall_multipliers")
        if isinstance(multipliers, dict):
            lvl_key = str(int(firewall_level or 0))
            if lvl_key in multipliers:
                val = float(multipliers[lvl_key])
                return int(val) if val.is_integer() else val

        # Rétrocompatibilité avec l'ancien format 'event_firewall_multiplier'
        legacy_cfg = rules.get("event_firewall_multiplier")
        if isinstance(legacy_cfg, dict) and "base" in legacy_cfg:
            base = float(legacy_cfg.get("base", 1))
            per_level = float(legacy_cfg.get("per_level", 1))
            val = base + (int(firewall_level or 0) * per_level)
            return int(val) if val.is_integer() else val

        # Fallback standard : 1.5 ** lvl (1, 1.5, 2.25, 3.375, 5.0625, 7.59375...)
        lvl = max(0, int(firewall_level or 0))
        val = 1.5 ** lvl
        return int(val) if float(val).is_integer() else round(val, 5)

    get_firewall_multiplier = get_event_firewall_multiplier

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

    # Cours RTM → USD courant, alimenté par le service marché (None = pas encore chargé).
    _market_rate: Decimal | None = None

    @classmethod
    def set_market_rate(cls, rate) -> None:
        """Met à jour le cours courant en mémoire (appelé par le service marché)."""
        value = Decimal(str(rate)) if rate is not None else None
        cls._market_rate = value if value is not None and value > 0 else None

    @classmethod
    def market_settings(cls) -> dict:
        """Retourne la section `market` de data/math.json, validée et complétée."""
        cfg = dict(cls.load().get('market', {}) or {})
        symbols = cfg.get('symbols') or []
        if cfg.get('enabled') and len(symbols) != 3:
            raise ValueError("market.symbols doit contenir exactement 3 paires (BTC, ETH, SOL).")
        cfg.setdefault('enabled', False)
        cfg.setdefault('timeframe', '15m')
        cfg.setdefault('interval_seconds', 900)
        cfg.setdefault('close_margin_seconds', 10)
        cfg.setdefault('retry_seconds', 60)
        cfg.setdefault('max_staleness_seconds', 1500)
        cfg.setdefault('fetch_limit', 6)
        cfg.setdefault('start_price', cls.load().get('conversion', {}).get('rtm_to_usd', 0))
        cfg.setdefault('price_decimal_places', 8)
        cfg.setdefault('max_change_pct', None)
        cfg.setdefault('history_retention_days', 90)
        cfg.setdefault('alerts_enabled', True)
        cfg.setdefault('alerts_max_per_player', 5)
        cfg.setdefault('alerts_default_cooldown_minutes', 60)
        cfg.setdefault('alerts_min_cooldown_minutes', 15)
        cfg.setdefault('auto_sell_enabled', True)
        cfg.setdefault('auto_sell_max_per_player', 3)
        cfg.setdefault('auto_sell_default_cooldown_minutes', 60)
        cfg.setdefault('auto_sell_min_cooldown_minutes', 15)
        return cfg

    @classmethod
    def market_formula(cls, name: str, **values) -> Decimal:
        """Évalue une formule `market_*` via l'évaluateur AST sécurisé (jamais eval)."""
        return cls.formula(cls.load(), name, **values)

    @classmethod
    def pvp_reference_rate(cls) -> Decimal:
        """Taux de référence PvP, indépendant du cours variable du marché."""
        conv = cls.load().get('conversion', {})
        rate = Decimal(str(conv.get('pvp_reference_rate', conv.get('rtm_to_usd', 0))))
        return rate if rate > 0 else Decimal('0')

    @classmethod
    def rtm_to_usd_rate(cls) -> Decimal:
        """Retourne le cours courant RTM → USD (1 RTM = N dollars).

        Priorité : cours persistant chargé en mémoire par le service marché, puis
        valeur d'amorçage `market.start_price`, puis ancien taux fixe `conversion.rtm_to_usd`.
        """
        if cls._market_rate is not None:
            return cls._market_rate
        rules = cls.load()
        raw = rules.get('market', {}).get('start_price') or rules.get('conversion', {}).get('rtm_to_usd', 0)
        rate = Decimal(str(raw or 0))
        return rate if rate > 0 else Decimal('0')

    @classmethod
    def convert_rtm_to_usd(cls, rtm_amount, rate=None) -> Decimal:
        """Convertit un montant de Rootium en USD au cours courant (ou `rate`), arrondi à 2 décimales."""
        places = int(cls.load().get('usd_decimal_places', 2))
        quantum = Decimal('1').scaleb(-places)
        applied = Decimal(str(rate)) if rate is not None else cls.rtm_to_usd_rate()
        usd = Decimal(str(rtm_amount or 0)) * applied
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
        - Un ensemble restreint de fonctions mathématiques : exp(), min(), max(), sqrt().
        Rejette immédiatement tout import, appel d'attribut (__class__, etc.) ou mot-clé suspect.
        """
        allowed = (
            ast.Expression, ast.BinOp, ast.UnaryOp, ast.Name, ast.Load, ast.Constant,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.USub, ast.UAdd, ast.Call
        )
        for child in ast.walk(node):
            if not isinstance(child, allowed):
                raise ValueError('Unsupported formula syntax')
            # Seules les fonctions pures 'exp', 'min', 'max' et 'sqrt' sans arguments nommés sont autorisées
            if isinstance(child, ast.Call) and (not isinstance(child.func, ast.Name) or child.func.id not in ('exp', 'min', 'max', 'sqrt') or child.keywords):
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
                fn = {
                    'exp': lambda v: v.exp(),
                    'min': min,
                    'max': max,
                    'sqrt': lambda v: v.sqrt() if hasattr(v, 'sqrt') else Decimal(str(v)).sqrt(),
                }[node.func.id]
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

    @classmethod
    def calculate_pvp_overrun_threshold(cls, attacker_firewall_tier: int) -> Decimal:
        """Calcule le seuil d'overrun PvP V(T) selon le tier de pare-feu de l'attaquant.
        
        La formule est configurée et modifiable dans data/math.json (clé formulas.pvp_overrun_threshold) :
        V = (mining_cost_usd / (atk_cost_rtm * rtm_to_usd)) * overrun_multiplier * sqrt(bits_per_s * overrun_time_factor)
        """
        rules = cls.load()
        tier = max(1, min(5, int(attacker_firewall_tier or 1)))

        mining_base = Decimal(str(rules.get('mining', {}).get('cost_t1_usd', 200)))
        mining_mult = Decimal(str(rules.get('mining', {}).get('cost_multiplier', 5)))
        mining_cost_usd = mining_base * (mining_mult ** (tier - 1))

        beta = rules.get('beta', {})
        atk_base_rtm = Decimal(str(beta.get('attack_price_t1_rtm', '0.005')))
        atk_mult = Decimal(str(beta.get('cost_multiplier', 2)))
        atk_cost_rtm = atk_base_rtm * (atk_mult ** (tier - 1))

        # Taux de référence indépendant du cours variable du marché (équilibrage PvP stable)
        rtm_to_usd = cls.pvp_reference_rate() or Decimal('43567')
        atk_cost_usd = atk_cost_rtm * rtm_to_usd

        bits = Decimal(str(rules.get('module_stats', {}).get('attack_bits_per_s', {}).get(str(tier), 0)))

        pvp_cfg = rules.get('pvp', {})
        overrun_multiplier = Decimal(str(pvp_cfg.get('overrun_multiplier', 10)))
        overrun_time_factor = Decimal(str(pvp_cfg.get('overrun_time_factor', 30)))

        formula_name = pvp_cfg.get('overrun_formula', 'pvp_overrun_threshold')
        if formula_name in rules.get('formulas', {}):
            return cls.formula(
                rules,
                formula_name,
                mining_cost_usd=mining_cost_usd,
                atk_cost_rtm=atk_cost_rtm,
                atk_cost_usd=atk_cost_usd,
                rtm_to_usd=rtm_to_usd,
                bits_per_s=bits,
                bits=bits,
                overrun_multiplier=overrun_multiplier,
                overrun_time_factor=overrun_time_factor,
                tier=tier,
                cout_module_minage_usd=mining_cost_usd,
                cout_module_atk_rtm=atk_cost_rtm,
            )

        if atk_cost_usd <= 0:
            return Decimal('1')

        ratio = mining_cost_usd / atk_cost_usd
        return ratio * overrun_multiplier * (bits * overrun_time_factor).sqrt()

    @classmethod
    def calculate_pvp_captured_modules_count(
        cls,
        attack_points: int,
        total_defense: int,
        attacker_firewall_tier: int,
    ) -> int:
        """Calcule le nombre de modules capturés ou détruits lors d'une intrusion PvP.
        
        - Si attack_points <= total_defense : 0 module (échec intrusion).
        - Si intrusion réussie : 1 module de base + int((attack_points - total_defense) // seuil).
        """
        delta = int(attack_points) - int(total_defense)
        if delta <= 0:
            return 0
        threshold = cls.calculate_pvp_overrun_threshold(attacker_firewall_tier)
        if threshold <= 0:
            return 1
        extra = int(Decimal(str(delta)) // threshold)
        return max(1, 1 + extra)

    @classmethod
    def get_pvp_critical_damage_cap_percent(cls) -> int:
        """Retourne le pourcentage maximal de modules pouvant être perdus lors d'une attaque PvP (0 à 100)."""
        rules = cls.load()
        val = int(rules.get('pvp', {}).get('critical_damage_cap_percent', 60))
        return max(0, min(100, val))

    @classmethod
    def get_pvp_critical_lock_duration_hours(cls) -> int:
        """Retourne la durée en heures du verrouillage de sauvegarde en cas de dégâts critiques."""
        rules = cls.load()
        val = int(rules.get('pvp', {}).get('critical_lock_duration_hours', 48))
        return max(1, val)

