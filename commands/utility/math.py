"""Module de commande /math et !math (alias !calc).

Ce module fournit un moteur de calcul mathématique sécurisé basé sur l'analyse syntaxique (AST) :
- Zéro utilisation d'eval() : isolation totale contre l'exécution de code arbitraire (RCE).
- Support des opérations arithmétiques fondamentales (+, -, *, /, //, %, **, ^).
- Support des fonctions mathématiques courantes (sqrt, abs, round, sin, cos, tan, log, exp, factorial, etc.).
- Constantes universelles (pi, e, tau).
- Protections strictes contre les attaques par déni de service (DoS) :
  - Limitation de la taille de l'expression.
  - Plafond sur le nombre de nœuds syntaxiques.
  - Protection contre les puissances et factorielles disproportionnées.
- Dualité Slash Command (@discord.slash_command) et Prefix Command (@commands.command).
- Internationalisation complète (FR / EN).
"""

import ast
from decimal import Decimal
import logging
import math
import operator
import re

import discord
from discord.ext import commands

from data import GUILD_WHITELIST
from lang.descslash import desc, desc_loc
from utils import text
from utils.language_manager import fetch_user_language

logger = logging.getLogger(__name__)


class MathEvaluationError(Exception):
    """Exception levée lors d'une erreur d'évaluation mathématique."""

    def __init__(self, key: str, item: str = ""):
        super().__init__(key)
        self.key = key
        self.item = item


class SafeMathEvaluator:
    """Évaluateur d'expressions mathématiques sécurisé via arbre syntaxique (AST)."""

    MAX_EXPR_LEN = 500
    MAX_NODES = 150
    MAX_EXPONENT = 1000
    MAX_FACTORIAL = 100

    SAFE_BIN_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.BitXor: operator.pow,  # Permet d'utiliser 2^8 comme 2**8
    }

    SAFE_UNARY_OPS = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    SAFE_CONSTANTS = {
        "pi": math.pi,
        "e": math.e,
        "tau": math.tau,
    }

    SAFE_FUNCTIONS = {
        "sqrt": math.sqrt,
        "cbrt": getattr(math, "cbrt", lambda x: x ** (1.0 / 3.0)),
        "abs": abs,
        "round": round,
        "floor": math.floor,
        "ceil": math.ceil,
        "trunc": math.trunc,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "asin": math.asin,
        "acos": math.acos,
        "atan": math.atan,
        "atan2": math.atan2,
        "degrees": math.degrees,
        "radians": math.radians,
        "deg": math.degrees,
        "rad": math.radians,
        "log": math.log,
        "ln": math.log,
        "log10": math.log10,
        "log2": math.log2,
        "exp": math.exp,
        "pow": math.pow,
        "factorial": math.factorial,
        "fact": math.factorial,
        "gcd": math.gcd,
        "lcm": getattr(math, "lcm", None),
        "min": min,
        "max": max,
    }

    @classmethod
    def evaluate(cls, expression: str):
        """Évalue une expression mathématique et renvoie le résultat numérique.

        Raises:
            MathEvaluationError: Si l'expression est invalide, non autorisée ou dépasse les limites.
        """
        if not expression or not expression.strip():
            raise MathEvaluationError("math_error_empty")

        raw = expression.strip()
        if len(raw) > cls.MAX_EXPR_LEN:
            raise MathEvaluationError("math_error_too_large")

        # Remplacement de caractères typographiques courants
        normalized = (
            raw.replace("×", "*")
            .replace("÷", "/")
            .replace("−", "-")
            .replace("—", "-")
            .replace("·", "*")
        )

        try:
            tree = ast.parse(normalized, mode="eval")
        except SyntaxError:
            raise MathEvaluationError("math_error_invalid")

        nodes = list(ast.walk(tree))
        if len(nodes) > cls.MAX_NODES:
            raise MathEvaluationError("math_error_too_large")

        return cls._eval_node(tree.body)

    @classmethod
    def _eval_node(cls, node):
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise MathEvaluationError("math_error_invalid")
            return node.value

        elif isinstance(node, ast.UnaryOp):
            op_cls = type(node.op)
            if op_cls not in cls.SAFE_UNARY_OPS:
                raise MathEvaluationError("math_error_unsupported", item=str(op_cls.__name__))
            operand = cls._eval_node(node.operand)
            try:
                return cls.SAFE_UNARY_OPS[op_cls](operand)
            except OverflowError:
                raise MathEvaluationError("math_error_too_large")

        elif isinstance(node, ast.BinOp):
            op_cls = type(node.op)
            if op_cls not in cls.SAFE_BIN_OPS:
                raise MathEvaluationError("math_error_unsupported", item=str(op_cls.__name__))

            left = cls._eval_node(node.left)
            right = cls._eval_node(node.right)

            # Vérification des puissances pour éviter les attaques DoS (ex: 9**9999999)
            if op_cls in (ast.Pow, ast.BitXor):
                if isinstance(right, (int, float)) and abs(right) > cls.MAX_EXPONENT:
                    raise MathEvaluationError("math_error_too_large")
                if isinstance(left, (int, float)) and abs(left) > 1e10 and right > 10:
                    raise MathEvaluationError("math_error_too_large")

            try:
                return cls.SAFE_BIN_OPS[op_cls](left, right)
            except ZeroDivisionError:
                raise MathEvaluationError("math_error_div_zero")
            except OverflowError:
                raise MathEvaluationError("math_error_too_large")

        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise MathEvaluationError("math_error_invalid")

            fn_name = node.func.id.lower()
            if fn_name not in cls.SAFE_FUNCTIONS or cls.SAFE_FUNCTIONS[fn_name] is None:
                raise MathEvaluationError("math_error_unsupported", item=fn_name)

            args = [cls._eval_node(arg) for arg in node.args]

            # Contrôle de sécurité spécifique pour les factorielles
            if fn_name in ("factorial", "fact"):
                if len(args) != 1 or not isinstance(args[0], int) or args[0] < 0 or args[0] > cls.MAX_FACTORIAL:
                    raise MathEvaluationError("math_error_too_large")

            try:
                res = cls.SAFE_FUNCTIONS[fn_name](*args)
                return res
            except ZeroDivisionError:
                raise MathEvaluationError("math_error_div_zero")
            except (ValueError, OverflowError):
                raise MathEvaluationError("math_error_too_large")

        elif isinstance(node, ast.Name):
            name = node.id.lower()
            if name not in cls.SAFE_CONSTANTS:
                raise MathEvaluationError("math_error_unsupported", item=name)
            return cls.SAFE_CONSTANTS[name]

        else:
            raise MathEvaluationError("math_error_invalid")


def format_math_result(val) -> str:
    """Formate un résultat numérique pour un affichage lisible et propre."""
    if isinstance(val, bool):
        return str(val)

    if isinstance(val, int):
        s = f"{val:,}".replace(",", " ")
        if len(s) > 1500:
            return s[:1500] + "... (tronqué)"
        return s

    if isinstance(val, float):
        if math.isnan(val):
            return "NaN"
        if math.isinf(val):
            return "∞" if val > 0 else "-∞"

        # Nombre entier stocké en float (ex: 4.0)
        if val.is_integer() and abs(val) < 1e15:
            return f"{int(val):,}".replace(",", " ")

        # Élimination du bruit d'arrondi flottant (ex: 0.1 + 0.2 = 0.3)
        rounded = round(val, 10)
        s = f"{rounded:.10f}".rstrip("0").rstrip(".")

        # Notation scientifique pour les grandeurs extrêmes
        if abs(val) > 1e12 or (0 < abs(val) < 1e-4):
            s = f"{val:.8e}"

        return s

    return str(val)


class Math(commands.Cog):
    """Cog utilitaire permettant d'effectuer des calculs mathématiques."""

    def __init__(self, bot):
        self.bot = bot

    async def _math_logic(self, ctx, expression: str | None):
        """Logique mutualisée pour l'évaluation et l'affichage d'un calcul."""
        user = getattr(ctx, "author", None) or getattr(ctx, "user", None)
        if user and getattr(user, "id", None):
            try:
                await fetch_user_language(user.id)
            except Exception:
                pass

        prefix = getattr(ctx, "prefix", None) or "!"

        if not expression or not expression.strip():
            msg = text.get(ctx, "math_usage", prefix=prefix)
            if hasattr(ctx, "respond"):
                await ctx.respond(msg)
            else:
                await ctx.send(msg)
            return

        raw_expr = expression.strip()
        try:
            val = SafeMathEvaluator.evaluate(raw_expr)
            res_str = format_math_result(val)
            resp = text.get(ctx, "math_result", expression=raw_expr, result=res_str)
        except MathEvaluationError as err:
            resp = text.get(ctx, err.key, item=err.item, prefix=prefix)
        except Exception:
            logger.exception("Erreur inattendue lors du calcul mathématique: %s", raw_expr)
            resp = text.get(ctx, "math_error_invalid")

        mentions = discord.AllowedMentions.none()
        if hasattr(ctx, "respond"):
            await ctx.respond(resp, allowed_mentions=mentions)
        else:
            await ctx.send(resp, allowed_mentions=mentions)

    # ── Version Commande Slash ───────────────────────────────────────────────────
    @discord.slash_command(
        name="math",
        guild_ids=GUILD_WHITELIST or None,
        description=desc["math"],
        description_localizations=desc_loc["math"],
    )
    async def math_slash(
        self,
        ctx,
        expression: discord.Option(
            str,
            description=desc["math_expression"],
            description_localizations=desc_loc["math_expression"],
            required=True,
        ),
    ):
        """Commande Slash /math <expression>."""
        await self._math_logic(ctx, expression)

    # ── Version Commande avec Préfixe ────────────────────────────────────────────
    @commands.command(name="math", aliases=["calc", "calculate", "calcul"])
    async def prefix_math(self, ctx, *, expression: str = None):
        """Commande préfixe !math <expression> (alias !calc, !calcul)."""
        await self._math_logic(ctx, expression)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Math(bot))

