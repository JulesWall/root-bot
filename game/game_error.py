"""
Exceptions métier du jeu Root.

Toutes les erreurs fonctionnelles (fonds insuffisants, cible invalide, cooldowns...)
héritent ou utilisent GameError. Cette classe transporte :
- Une clé symbolique (ex: 'insufficient_funds', 'no_network', 'cooldown').
- Des valeurs de substitution dynamiques (ex: until, level, amount).
Ces informations sont résolues dans la langue du joueur via utils.text et lang/.
"""


from discord.ext import commands


class GameError(commands.CommandError):
    """
    Erreur métier traduite par l'interface Discord.
    
    Attributes:
        key (str): Clé de traduction (préfixée par 'g_error_' lors de l'affichage).
        values (dict): Paramètres nommés injectés dans le template de texte localisé.
    """

    def __init__(self, key: str, **values):
        self.key = key
        self.values = values
        super().__init__(key)

