"""Module de commande /ping et !ping.

Ce module permet de mesurer et d'afficher la latence du bot Discord (Heartbeat WebSocket Discord Gateway).
Il respecte l'architecture du projet :
- Zéro SQL (simple commande utilitaire).
- Aucun texte codé en dur : le message de réponse provient de `lang/` via `utils.text.get()`.
- Dualité Slash Command (@discord.slash_command) et Prefix Command (@commands.command).
"""

import discord
from discord.ext import commands
from data import GUILD_WHITELIST
from lang.descslash import desc, desc_loc
from utils import text


class Ping(commands.Cog):
    """Cog regroupant les commandes utilitaires de test de réactivité (Ping).

    Attributes:
        bot (commands.Bot): L'instance principale du bot Discord.
    """

    def __init__(self, bot):
        self.bot = bot

    async def _ping_logic(self, ctx):
        """Logique d'exécution mutualisée pour les commandes slash et avec préfixe.

        Calcul de la latence :
        - `ctx.bot.latency` renvoie le temps d'aller-retour moyen (RTT) entre le bot
          et la passerelle WebSocket de Discord (en secondes).
        - Multiplié par 1000 et arrondi à l'entier le plus proche pour un affichage en millisecondes (ms).

        Internationalisation :
        - La clé 'ping_response' est résolue dynamiquement selon la langue de l'utilisateur/contexte.

        Compatibilité d'envoi :
        - Dans Pycord, `ApplicationContext` (slash) et `Context` (préfixe) supportent tous deux
          la méthode `respond()`. Si l'objet de contexte ne possède pas `respond`, repli sur `send()`.
        """
        # Calcul du temps de réponse en millisecondes
        latency = round(ctx.bot.latency * 1000)

        # Récupération de la chaîne localisée formatée avec la valeur de latence
        resp = text.get(ctx, "ping_response", latency=latency)

        # Envoi de la réponse adapté au type de contexte (ApplicationContext vs commands.Context)
        if hasattr(ctx, 'respond'):
            await ctx.respond(resp)
        else:
            await ctx.send(resp)

    # ── Version Commande Slash ───────────────────────────────────────────────────
    @discord.slash_command(
        guild_ids=GUILD_WHITELIST or None,
        description=desc["ping"],
        description_localizations=desc_loc["ping"]
    )
    async def ping(self, ctx):
        """Commande Slash /ping."""
        await self._ping_logic(ctx)

    # ── Version Commande avec Préfixe ────────────────────────────────────────────
    @commands.command(name="ping")
    async def prefix_ping(self, ctx):
        """Commande avec préfixe !ping (ou préfixe personnalisé du serveur)."""
        await self._ping_logic(ctx)


def setup(bot):
    """Point d'entrée standard de chargement de l'extension Pycord."""
    bot.add_cog(Ping(bot))
