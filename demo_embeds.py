"""Demo visuelle autonome : lancer ce fichier, puis /demo_root dans Discord.

Variables d'environnement :
  DISCORD_DEMO_TOKEN     Token d'un bot de test (pas celui du jeu).
  DISCORD_DEMO_GUILD_ID  Facultatif : serveur ou publier la commande rapidement.

Dependance : py-cord >= 2.7 (composants Discord V2).
La banniere design/root-os-banner.png est utilisee si aucune image n'est jointe.
Aucun acces aux donnees du jeu.
"""

import asyncio
import os
from pathlib import Path

import discord


GREEN = 0x54E2D1
AMBER = 0xFFC15A
PAGES = ("Poste", "Anomalie", "Opération")
PAGE_ICONS = ("terminal", "alerte", "operations")
FALLBACKS = {
    "terminal": "🖥️", "firewall": "🛡️", "ferme": "🗄️",
    "puissance": "⚙️", "production": "📊", "memoire": "💾",
    "temps": "⏱️", "recolter": "📥", "materiel": "⚙️",
    "logiciels": "💻", "operations": "📋", "journal": "📄",
    "alerte": "⚠️", "scan": "🔍", "connexions": "🌐",
    "retour": "↩️", "bilan": "📊",
}


def select_emojis(emojis):
    """Prefer an animated, usable emoji when static and GIF names coincide."""
    selected = {}
    for emoji in sorted(emojis, key=lambda item: (item.animated, item.id)):
        name = emoji.name.removeprefix("root_")
        if emoji.name.startswith("root_") and name in FALLBACKS and emoji.is_usable():
            selected[name] = emoji
    return selected


class DemoView(discord.ui.DesignerView):
    def __init__(self, image_url=None, emojis=None):
        super().__init__(timeout=600, disable_on_timeout=True)
        self.image_url = image_url
        self.emojis = emojis or {}
        self.page = 0
        self.detail = None
        self.collected = False
        self.diagnosed = False
        self.isolated = False
        self.lock = asyncio.Lock()
        self.rebuild()

    def emoji(self, name):
        return self.emojis.get(name, FALLBACKS[name])

    def button(self, label, icon, command, *, disabled=False, style=None):
        button = discord.ui.Button(
            label=label, emoji=self.emoji(icon), custom_id=f"root_demo:{command}",
            style=style or discord.ButtonStyle.secondary, disabled=disabled,
        )

        async def callback(interaction):
            # Bind the action, not the current page: this panel is shared publicly.
            async with self.lock:
                if command == "collect":
                    self.collected = True
                elif command == "scan":
                    self.diagnosed = True
                elif command == "isolate" and self.diagnosed:
                    self.isolated = True
                elif command.startswith("page:"):
                    self.page = int(command.split(":")[1])
                    self.detail = None
                elif command.startswith("detail:"):
                    self.detail = command.split(":")[1]
                elif command == "back":
                    self.detail = None
                self.rebuild()
                await interaction.response.edit_message(view=self)

        button.callback = callback
        return button

    def rebuild(self):
        self.clear_items()
        e = self.emoji
        panel = discord.ui.Container(
            color=AMBER if self.page == 1 and not self.isolated else GREEN,
        )
        # Les composants V2 respectent cet ordre, contrairement aux embeds.
        if self.image_url:
            gallery = discord.ui.MediaGallery()
            gallery.add_item(self.image_url, description="Le poste de contrôle de Nox")
            panel.add_item(gallery)

        def text(content):
            panel.add_item(discord.ui.TextDisplay(content))

        def separator():
            panel.add_item(discord.ui.Separator())

        text(f"## {e('terminal')} ROOT OS / NOX\n-# ATLAS · Réseau personnel · Session active")
        separator()
        actions = []
        if self.detail == "hardware":
            text(f"### {e('materiel')} Matériel\nStation ATLAS · Firewall **3**")
            text(
                f"{e('ferme')} **Ferme T3**\n4 mineurs reliés à ATLAS\n\n"
                f"{e('puissance')} **Puissance totale** · 2 500 H/s\n"
                f"{e('memoire')} **Capacité mémoire** · 0,00875 RTM"
            )
            text("-# ATLAS → Ferme T3 → Mémoire locale")
        elif self.detail == "software":
            text(f"### {e('logiciels')} Logiciels\nBibliothèque locale / ATLAS")
            text(
                f"{e('scan')} **Scanner réseau** · Prêt\n"
                f"{e('firewall')} **Surveillance** · Active\n\n"
                f"{e('temps')} **Correctif Écho** · Compilation en cours\n"
                "Fin estimée dans **18 min** · Pas encore installé"
            )
        elif self.detail == "connections":
            text(f"### {e('connexions')} Connexions\nATLAS / Ferme T3")
            text("**Réseau local** · 4 mineurs connectés\n**Pool de minage** · Liaison établie")
            if self.isolated:
                text(f"{e('firewall')} **Liaison inconnue** · Coupée\nTrace Écho conservée dans le journal.")
            elif self.diagnosed:
                text(f"{e('alerte')} **Liaison inconnue** · Intrusion Écho\n5 % de la production détournés.")
                actions.append(self.button("Isoler la connexion", "firewall", "isolate", style=discord.ButtonStyle.danger))
            else:
                text(f"{e('alerte')} **Liaison inconnue** · À identifier")
                actions.append(self.button("Diagnostiquer", "scan", "scan", style=discord.ButtonStyle.primary))
        elif self.detail == "journal":
            text(f"### {e('journal')} Journal d’opération\nÉcho / Cible K-4821")
            text("`14:00`  Opération engagée\n`14:45`  Accès aux mineurs T3\n`15:05`  Connexion coupée par la cible")
            text("-# Session archivée · Aucune connexion restante")
        elif self.page == 0:
            text(f"{e('firewall')} **Firewall 3** · Poste en ligne\n-# ATLAS → Ferme T3 → Mémoire locale")
            memory = "0" if self.collected else "0,005"
            production = "0,015" if self.isolated else "0,01425"
            text(
                f"{e('ferme')} **Ferme** · 4 mineurs T3\n"
                f"{e('puissance')} **Puissance** · 2 500 H/s\n"
                f"{e('production')} **Production reçue** · {production} RTM/h\n"
                f"{e('memoire')} **Mémoire** · {memory} / 0,00875 RTM"
            )
            separator()
            text(f"{e('temps')} **Correctif Écho**\nCompilation en cours · encore **18 min**")
            if self.collected:
                text(f"{e('recolter')} **Transfert effectué** · 0,005 RTM\n-# Mémoire libérée. Production maintenue.")
            else:
                text(f"-# {e('journal')} Dernier événement · Liaison avec le pool établie.")
            actions.extend([
                self.button("Récolté" if self.collected else "Récolter", "recolter", "collect", disabled=self.collected, style=discord.ButtonStyle.success),
                self.button("Matériel", "materiel", "detail:hardware"),
                self.button("Logiciels", "logiciels", "detail:software"),
            ])
        elif self.page == 1:
            if self.isolated:
                text(f"### {e('firewall')} Connexion isolée\nFerme T3 / Débit rétabli")
            elif self.diagnosed:
                text(f"### {e('alerte')} Intrusion identifiée\nÉcho / Mineurs T3")
            else:
                text(f"### {e('alerte')} Rendement inhabituel\nFerme T3 / Une liaison reste à identifier")
            received = "0,015" if self.isolated else "0,01425"
            gap = "0 %" if self.isolated else "−5 %"
            text(f"{e('production')} **Production attendue** · 0,015 RTM/h\n**Production reçue** · {received} RTM/h\n**Écart** · {gap}")
            separator()
            if self.isolated:
                text("La liaison a été coupée. Tes mineurs produisent normalement.\n-# La faille reste ouverte tant que le correctif n’est pas installé.")
            elif self.diagnosed:
                text("Un logiciel détourne **5 %** de ta production.\n-# Une coupure arrête ce transfert, sans corriger la faille.")
            else:
                text("Tes mineurs répondent, mais une partie du rendement manque.")
            actions.extend([
                self.button("Connexion isolée" if self.isolated else "Isoler la connexion" if self.diagnosed else "Diagnostiquer",
                            "firewall" if self.diagnosed else "scan", "isolate" if self.diagnosed else "scan",
                            disabled=self.isolated, style=discord.ButtonStyle.primary),
                self.button("Connexions", "connexions", "detail:connections"),
            ])
        else:
            text(f"### {e('operations')} Écho / K-4821\nOpération terminée · Connexion fermée")
            text(
                f"{e('connexions')} **Cible** · Ferme T3 de K-4821\n"
                f"{e('temps')} **Accès actif** · 14:45 → 15:05\n"
                f"{e('bilan')} **Durée effective** · 20 min"
            )
            separator()
            text(f"{e('recolter')} **0,00025 RTM récupéré**\nLa cible a détecté puis coupé la liaison.")
            actions.append(self.button("Journal", "journal", "detail:journal"))

        if self.detail:
            actions.append(self.button("Retour", "retour", "back"))
        if actions:
            panel.add_item(discord.ui.ActionRow(*actions))
        self.add_item(panel)
        navigation = discord.ui.ActionRow()
        for index, label in enumerate(PAGES):
            navigation.add_item(self.button(label, PAGE_ICONS[index], f"page:{index}", disabled=index == self.page and self.detail is None))
        self.add_item(navigation)
        self.add_item(discord.ui.TextDisplay("-# Simulation publique · Données fictives · Aucun effet sur le jeu"))


async def send_demo(ctx, illustration=None):
    if ctx.guild is None:
        await ctx.respond("Lance cette démo dans un salon du serveur.", ephemeral=False)
        return
    if illustration and not (illustration.content_type or "").startswith("image/"):
        await ctx.respond("Choisis une image pour l’illustration.", ephemeral=False)
        return
    await ctx.defer(ephemeral=False)
    try:
        emojis = await ctx.guild.fetch_emojis()
    except discord.HTTPException:
        emojis = ctx.guild.emojis
    image_url = illustration.url if illustration else None
    files = []
    banner = Path(__file__).parent / "design" / "root-os-banner.png"
    if not image_url and banner.is_file():
        files.append(discord.File(banner, filename="root-os-banner.png"))
        image_url = "attachment://root-os-banner.png"
    view = DemoView(image_url=image_url, emojis=select_emojis(emojis))
    try:
        await ctx.respond(view=view, files=files, ephemeral=False,
                          allowed_mentions=discord.AllowedMentions.none())
        view.message = await ctx.interaction.original_response()
    finally:
        for file in files:
            file.close()


def main():
    token = "ODUwODA3NjE0ODk1MjkyNDc2.GTwhWi.N7RdTvjPwdzvR6nSh2qj_AG-puhxO1VO9qD7bo"
    if not token:
        raise SystemExit("Définis DISCORD_DEMO_TOKEN avec le token de ton bot de test.")
    guild_id = os.getenv("DISCORD_DEMO_GUILD_ID")
    bot = discord.Bot(
        intents=discord.Intents.default(),
        debug_guilds=[int(guild_id)] if guild_id else None,
    )

    @bot.slash_command(name="demo_root", description="Tester les trois écrans fictifs de Root OS")
    async def demo_root(ctx: discord.ApplicationContext, illustration: discord.Attachment = None):
        await send_demo(ctx, illustration)

    bot.run(token)


if __name__ == "__main__":
    main()
