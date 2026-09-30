"""Create the player manual using Root OS's immersive embed assets."""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf/root-os-pvp-v2-manuel-immersif.pdf"
ASSETS = ROOT / "design"
W, H = 595.276, 841.89
M, INNER = 38, 519.276
C = {
    "bg": "#191B1E", "panel": "#24272B", "code": "#141618",
    "ink": "#EEF1F5", "muted": "#B4BBC4", "line": "#41464D",
    "accent": "#54E2D1", "amber": "#FFC15A",
}


def setup_fonts():
    fonts = Path("C:/Windows/Fonts")
    for name, filename in (
        ("Root", "arial.ttf"), ("RootBold", "arialbd.ttf"),
        ("RootItalic", "ariali.ttf"), ("Mono", "consola.ttf"),
    ):
        pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    pdfmetrics.registerFontFamily(
        "Root", normal="Root", bold="RootBold", italic="RootItalic",
        boldItalic="RootBold",
    )


class Manual:
    def __init__(self):
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        self.pdf = canvas.Canvas(str(OUTPUT), pagesize=(W, H), pageCompression=1)
        self.pdf.setTitle("ROOT OS | Manuel d'opérateur PvP V2")
        self.pdf.setAuthor("ROOT OS")
        self.pdf.setSubject("Reconnaissance, logiciels, opérations, défense et marché PvP")
        self.page = 0
        self.bounds = []

    def rect(self, x, y, w, h, color, radius=0):
        self.pdf.setFillColor(HexColor(C.get(color, color)))
        if radius:
            self.pdf.roundRect(x, H-y-h, w, h, radius, fill=1, stroke=0)
        else:
            self.pdf.rect(x, H-y-h, w, h, fill=1, stroke=0)

    def line(self, x, y, w, color="line"):
        self.pdf.setStrokeColor(HexColor(C[color]))
        self.pdf.setLineWidth(0.6)
        self.pdf.line(x, H-y, x+w, H-y)

    def text(self, text, x, y, width=INNER, size=10.6, color="ink",
             font="Root", leading=None):
        style = ParagraphStyle(
            "local", fontName=font, fontSize=size, leading=leading or size*1.4,
            textColor=HexColor(C.get(color, color)), spaceBefore=0, spaceAfter=0,
        )
        p = Paragraph(text, style)
        _, height = p.wrap(width, H)
        p.drawOn(self.pdf, x, H-y-height)
        self.bounds.append((self.page, y, y+height, text[:60]))
        if y+height > 779:
            raise ValueError(f"Content runs into footer on page {self.page}: {text}")
        return y+height

    def icon(self, name, x, y, size=20):
        self.pdf.drawImage(
            str(ASSETS / f"root-os-emojis/png/root_{name}.png"),
            x, H-y-size, size, size, mask="auto",
        )

    def label(self, text, x, y, color="accent", width=INNER):
        return self.text(text, x, y, width, 8.3, color, "Mono", 11)

    def header(self, number, section, title, subtitle, icon, alert=False):
        self.page = number
        accent = "amber" if alert else "accent"
        self.rect(0, 0, W, H, "bg")
        self.rect(0, 0, W, 4, accent)
        self.pdf.bookmarkPage(f"p{number}")
        self.pdf.addOutlineEntry(section, f"p{number}", level=0)
        self.icon("terminal", M, 27, 21)
        self.label("ROOT OS / MANUEL D'OPÉRATEUR", M+30, 31, "ink")
        self.label(f"PVP V2   /   {number:02d}", W-142, 31, accent, 110)
        self.line(M, 63, INNER)
        self.icon(icon, M, 84, 26)
        self.label(section.upper(), M+37, 85, accent)
        self.text(title, M, 112, INNER, 26, "ink", "RootBold", 30)
        self.text(subtitle, M, 154, INNER, 10.4, "muted")

    def footer(self, current):
        self.line(M, 791, INNER)
        self.pdf.setFont("Mono", 7.5)
        self.pdf.setFillColor(HexColor(C["muted"]))
        self.pdf.drawString(M, 33, "ROOT OS  /  PROTOCOLE PVP V2")
        self.pdf.drawRightString(W-M, 33, f"{current:02d} / 06")
        self.pdf.showPage()

    def panel(self, y, title, icon, body, *, accent="accent", x=M,
              width=INNER, tag=None, min_height=0):
        title_width = width-58
        title_style = ParagraphStyle("title", fontName="RootBold", fontSize=12,
                                     leading=16, textColor=HexColor(C["ink"]))
        title_p = Paragraph(title, title_style)
        _, th = title_p.wrap(title_width, H)
        style = ParagraphStyle("body", fontName="Root", fontSize=10.5,
                               leading=15, textColor=HexColor(C["ink"]))
        p = Paragraph(body, style)
        _, ph = p.wrap(width-34, H)
        content_h = 16+max(20, th)+10+ph+(23 if tag else 0)+16
        h = max(content_h, min_height)
        self.rect(x, y, width, h, "panel", 5)
        self.rect(x, y+7, 3, h-14, accent)
        self.icon(icon, x+17, y+15, 20)
        self.text(title, x+46, y+16, title_width, 12, font="RootBold", leading=16)
        self.text(body, x+17, y+16+max(20, th)+10, width-34, 10.5, leading=15)
        if tag:
            self.label(tag, x+17, y+h-27, accent, width-34)
        return y+h

    def code(self, y, lines, *, x=M, width=INNER, size=8.7):
        h = 20+len(lines)*12.5
        self.rect(x, y, width, h, "code", 4)
        for i, row in enumerate(lines):
            if pdfmetrics.stringWidth(row, "Mono", size) > width-24:
                raise ValueError(f"Command too wide: {row}")
            self.text(escape(row), x+12, y+10+i*12.5, width-24,
                      size, "accent", "Mono", 12.5)
        return y+h

    def note(self, y, title, body, accent="amber"):
        self.rect(M, y, 3, 44, accent)
        self.label(title, M+13, y, accent, INNER-13)
        return self.text(body, M+13, y+18, INNER-13, 10.1, "muted")

    def metric(self, x, y, value, caption, width):
        self.text(value, x, y, width, 23, "accent", "RootBold", 27)
        self.label(caption, x, y+33, "muted", width)


def briefing(d):
    d.page = 1
    d.rect(0, 0, W, H, "bg")
    d.rect(0, 0, W, 4, "accent")
    d.pdf.bookmarkPage("p1")
    d.pdf.addOutlineEntry("01 / Prise de poste", "p1", level=0)
    d.icon("terminal", M, 24, 22)
    d.label("ROOT OS / RÉSEAU PERSONNEL", M+32, 30, "ink")
    d.label("SESSION ACTIVE", W-146, 30, width=110)
    banner_height = INNER*727/2164
    d.pdf.drawImage(str(ASSETS / "root-os-banner.png"), M, H-64-banner_height,
                    INNER, banner_height)
    d.label("01 / PRISE DE POSTE", M, 253)
    d.text("ROOT OS", M, 274, INNER, 43, font="RootBold", leading=48)
    d.text("Manuel d'opérateur / PvP V2", M, 331, INNER, 20, font="RootBold")
    d.text(
        "Ton réseau produit. D'autres joueurs l'observent. À toi de lire le terrain, "
        "de préparer tes logiciels et de protéger ce que tu construis.",
        M, 375, INNER, 12, leading=17,
    )
    d.line(M, 428, INNER)
    d.label("UNE EMPREINTE. TROIS OBJETS.", M, 444)
    d.text(
        "Chaque faille porte un identifiant unique de <b>4 caractères</b>, comme "
        "<b>[K7M2]</b>. Il relie la recherche, les copies et le correctif adapté.",
        M, 466, INNER, 10.8,
    )
    rows = [
        ("journal", "Dossier", "La découverte d'origine. Elle permet de compiler plusieurs copies."),
        ("logiciels", "Copie compilée", "Le logiciel prêt à partir. Chaque attaque consomme une copie."),
        ("firewall", "Patch", "Le correctif qui neutralise une empreinte précise sur ton réseau."),
    ]
    for i, (icon, title, desc) in enumerate(rows):
        y = 515+i*48
        d.icon(icon, M, y+2, 22)
        d.text(title, M+34, y, 115, 11, font="RootBold")
        d.text(desc, M+162, y, INNER-162, 10.2, "muted", leading=14)
    d.line(M, 664, INNER)
    d.label("PARCOURS OPÉRATEUR", M, 680)
    links = [("02", "Reconnaissance", 2), ("03", "Préparation & déploiement", 3),
             ("04", "Les six familles", 4), ("05", "Défense & représailles", 5),
             ("06", "Marché & commandes", 6)]
    for i, (number, title, page) in enumerate(links):
        col, row = i % 2, i // 2
        x, y = M+col*270, 704+row*22
        d.text(f'<font color="{C["accent"]}">{number}</font>  {title}',
               x, y, 258, 10)
        d.pdf.linkRect("", f"p{page}", (x, H-y-17, x+250, H-y), relative=0, thickness=0)
    d.footer(1)


def reconnaissance(d):
    d.header(2, "Reconnaissance", "Lire le réseau adverse",
             "Une bonne cible se choisit sur un rapport, pas sur une intuition.", "scan")
    d.metric(M, 199, "0,005 RTM", "COÛT DU SCAN", 195)
    d.metric(M+208, 199, "90 s", "DÉLAI", 110)
    d.metric(M+351, 199, "Niv. 1", "INFRA MINIMALE", 168)
    y = d.code(262, ["/scan @cible", "!scan @cible"], size=10)
    y = d.text(
        "Tu peux scanner une infrastructure de niveau <b>supérieur ou égal au tien</b>. "
        "Un droit de représailles actif permet de dépasser cette restriction contre "
        "l'attaquant concerné pendant 72 h.", M, y+16,
    )
    y = d.panel(y+22, "Rapport de reconnaissance", "connexions",
        "<b>Infrastructure</b> · Niveau adverse et défense passive.<br/>"
        "<b>Ferme</b> · Matériel minier, tiers et hashrate total.<br/>"
        "<b>Mémoire</b> · Taux de remplissage de la RAM.<br/>"
        "<b>Signatures</b> · Logiciels et correctifs déjà déployés.",
        tag="LIVRAISON / MESSAGE PRIVÉ")
    y = d.text("Ce que tu cherches dans le rapport", M, y+24, INNER, 15,
               font="RootBold")
    y = d.text(
        "<b>Le potentiel.</b> Le matériel et la mémoire donnent du contexte à ton choix de cible.<br/>"
        "<b>Le délai.</b> Une défense élevée ralentit l'installation de ton logiciel.<br/>"
        "<b>Les protections.</b> Les signatures connues t'aident à choisir une empreinte adaptée.",
        M, y+12, INNER, 10.6, leading=17,
    )
    d.note(y+24, "SCAN OU DIAGNOSTIC ?",
        "<b>/scan</b> observe une cible. <b>/diag</b> recherche les infections sur ton propre réseau.",
        "accent")
    d.footer(2)


def preparation(d):
    d.header(3, "Préparation & déploiement", "Du dossier à l'opération",
             "Une recherche découvre la faille. La compilation produit la copie utilisable.",
             "logiciels")
    y = d.text(
        "<b>Deux canaux indépendants travaillent en parallèle.</b> L'offensif utilise "
        "les modules <b>attack_t*</b> pour rechercher et compiler. Le défensif utilise "
        "les modules <b>bay_defense_t*</b> pour préparer les patchs.", M, 194,
    )
    y = d.label("01 / RECHERCHER UNE FAILLE", M, y+18)
    y = d.code(y+9, [
        "/dev start job_type:research channel:offense family:hostile_miner tier:2",
        "!dev start research hostile_miner 2",
    ])
    y = d.text("Résultat : un dossier de recherche et son empreinte unique.", M, y+8,
               size=10, color="muted")
    y = d.label("02 / COMPILER UNE COPIE", M, y+15)
    y = d.code(y+9, [
        "/dev start job_type:compile channel:offense family:hostile_miner tier:2",
        "!dev start compile hostile_miner 2",
    ])
    y = d.text("Ouvre <b>/library</b> ou <b>!library</b> pour retrouver dossiers, copies et patchs.",
               M, y+8, size=10, color="muted")
    y = d.label("03 / DÉPLOYER LE LOGICIEL", M, y+15)
    y = d.code(y+9, [
        "/hack target:@cible family:<famille> [tier:<tier>] [confirm:confirm]",
        "!hack @cible [famille] [tier] [confirm]",
    ])
    y = d.text(
        "Les crochets signalent des paramètres facultatifs ; ne les saisis pas. "
        "Remplace les valeurs entre chevrons. L'installation se poursuit en arrière-plan.",
        M, y+8, size=9.7, color="muted",
    )
    y = d.panel(y+16, "La défense adverse te fait perdre du temps", "temps",
        "Durée = durée de base × <b>min(10 ; 1 + DEF / 500)</b>.<br/>"
        "Exemple : 500 DEF double le délai ; le multiplicateur ne dépasse jamais ×10.")
    d.note(y+16, "CAPACITÉ D'ENGAGEMENT",
        "<b>1 opération active par famille</b> et <b>3 opérations offensives actives</b> au maximum.",
        "accent")
    d.footer(3)


def families(d):
    d.header(4, "Les six familles", "Choisir l'effet recherché",
             "Détourner, bloquer, ralentir ou récupérer de l'information : chaque famille a son rôle.",
             "operations")
    data = [
        ("Hostile Miner", "production", "hostile_miner",
         "Détourne <b>15 %</b> de la production brute de la baie ciblée vers ta RAM.<br/><br/>"
         "<b>Persiste jusqu'à l'installation du patch adapté.</b>"),
        ("Ransomware", "alerte", "ransomware",
         "Bloque les commandes économiques : achats, upgrades, compilation, échanges…<br/><br/>"
         "<b>Rançon en RTM ou patch.</b> Durée maximale : <b>72 h</b>."),
        ("Vol de devises", "recolter", "currency_theft",
         "Dérobe <b>25 %</b> du solde USD en préservant un plancher de <b>50 $</b>. "
         "Frais : <b>5 %</b>.<br/><br/>Effet immédiat <b>à la livraison</b>."),
        ("Saturation RAM", "memoire", "saturation",
         "Ralentit de <b>30 %</b> la recherche du canal offensif adverse pendant <b>6 h</b>."
         "<br/><br/>En cas de cumul, la réduction est plafonnée à <b>60 %</b>."),
        ("Espionnage", "scan", "espionage",
         "Révèle les logiciels, dossiers et patchs de la cible.<br/><br/>"
         "La cartographie est remise <b>en message privé</b>, à la livraison."),
        ("Vol de logiciel", "logiciels", "software_theft",
         "Copie un logiciel compilé de la cible dans ton inventaire.<br/><br/>"
         "Effet immédiat à la livraison. La copie obtenue est <b>non revendable</b>."),
    ]
    gap = 14
    width = (INNER-gap)/2
    for i, (title, icon, key, body) in enumerate(data):
        x, y = M+(i%2)*(width+gap), 196+(i//2)*183
        d.panel(y, title, icon, body, accent="amber" if i in (1, 3) else "accent",
                x=x, width=width, tag=key, min_height=170)
    d.text("À la livraison = après le temps d'installation, pas au lancement de /hack.",
           M, 755, INNER, 9.5, "muted")
    d.footer(4)


def defense(d):
    d.header(5, "Défense & représailles", "Anomalie détectée",
             "Identifie la signature, prépare le correctif, puis installe-le sur ton réseau.",
             "alerte", alert=True)
    y = d.panel(192, "1. Identifier l'infection", "scan",
        "<b>/diag</b> ou <b>/hack diag</b> · <b>0,001 RTM</b><br/>"
        "Le diagnostic liste les signatures hostiles actives et leurs empreintes. "
        "Note la famille et l'identifiant, par exemple <b>hostile_miner / K7M2</b>.",
        accent="amber")
    y = d.text("2. Développer le patch correspondant", M, y+20, INNER, 13,
               font="RootBold")
    y = d.code(y+10, [
        "/dev start job_type:patch_research channel:defense",
        "  family:hostile_miner fingerprint:K7M2",
        "!dev start patch_research hostile_miner K7M2",
    ], size=9.3)
    y = d.text(
        "La commande /dev est répartie sur deux lignes pour la lecture : ses paramètres "
        "appartiennent à une seule commande. Remplace K7M2 par l'empreinte détectée.",
        M, y+8, INNER, 9.5, "muted", leading=13,
    )
    y = d.panel(y+15, "3. Installer depuis /library", "firewall",
        "Une fois prêt, <b>installe le patch</b> dans ta bibliothèque. Il supprime l'infection "
        "et immunise ton réseau contre <b>cette empreinte précise</b>.")
    y = d.panel(y+14, "4. Remonter la trace", "connexions",
        "<b>/trace</b> ou <b>/hack trace</b> · <b>0,002 RTM</b><br/>"
        "Si l'attaquant n'a pas patché son propre réseau, son identité est révélée. "
        "Tu obtiens alors <b>72 h de représailles</b> contre lui, sans restriction de niveau.")
    y = d.note(y+17, "RÉSEAU BLOQUÉ PAR UN RANSOMWARE ?",
        "<b>/pay</b> ou <b>/hack pay</b> règle la rançon demandée en RTM et débloque "
        "immédiatement tes commandes. Le patch reste l'autre voie de résolution.")
    d.text("Un diagnostic ne répare rien. Un patch prêt ne protège pas tant qu'il n'est pas installé.",
           M, y+16, INNER, 9.5, "amber", leading=13)
    d.footer(5)


def market(d):
    d.header(6, "Marché & commandes", "Équiper ton prochain coup",
             "Revends tes recherches ou achète l'outil qui manque à ton réseau.", "recolter")
    y = d.panel(193, "Ce qui peut circuler sur le marché", "logiciels",
        "<b>Logiciels compilés</b> · Copies légitimes, non volées.<br/>"
        "<b>Patchs</b> · Correctifs qui ne sont pas encore installés.<br/>"
        "<b>Dossiers</b> · Recherches offensives.", tag="5 % DE FRAIS / 5 ANNONCES MAXIMUM")
    y = d.text(
        "Un objet mis en vente est <b>réservé</b>. Les frais sont prélevés à la vente ; "
        "la limite de cinq annonces s'applique à chaque vendeur.", M, y+13,
    )
    y = d.label("COMMANDES DU MARCHÉ", M, y+18)
    rows = [
        ("!market list [type]", "Consulter les offres ; filtre facultatif."),
        ("!market mine", "Retrouver tes annonces."),
        ("!market sell software 12 500", "Vendre le logiciel n° 12 au prix de 500."),
        ("!market buy 4", "Acheter l'annonce n° 4."),
        ("!market cancel 4", "Retirer ton annonce n° 4."),
    ]
    y += 12
    for command, desc in rows:
        d.text(escape(command), M, y, 248, 9.2, "accent", "Mono", 13)
        d.text(desc, M+260, y, INNER-260, 9.5, leading=13)
        y += 26
    y = d.text(
        "En slash : <b>/market list [type]</b>, <b>/market mine</b>, "
        "<b>/market sell &lt;type&gt; &lt;id&gt; &lt;prix&gt;</b>, "
        "<b>/market buy &lt;listing_id&gt;</b>, <b>/market cancel &lt;listing_id&gt;</b>.",
        M, y+1, INNER, 9.7, "muted", leading=14,
    )
    d.line(M, y+15, INNER)
    y = d.label("RÉPERTOIRE EXPRESS", M, y+29)
    pairs = [
        ("/scan  ·  !scan", "/dev start  ·  !dev start"),
        ("/library  ·  !library", "/hack  ·  !hack  ·  !hk"),
        ("/diag  ·  !diag  ·  !hack diag", "/trace  ·  !trace  ·  !hack trace"),
        ("/pay  ·  !pay  ·  !hack pay", "/market  ·  !market  ·  !mkt"),
    ]
    for left, right in pairs:
        y += 23
        d.text(left, M, y, 250, 8.9, "ink", "Mono", 13)
        d.text(right, M+267, y, 252, 8.9, "ink", "Mono", 13)
    d.note(y+18, "AVANT DE QUITTER LE POSTE",
        "Cible analysée. Copie disponible. Empreinte choisie. Réseau surveillé.<br/>"
        "L'avantage se prépare autant qu'il se déploie.", "accent")
    d.footer(6)


def main():
    setup_fonts()
    document = Manual()
    for draw in (briefing, reconnaissance, preparation, families, defense, market):
        draw(document)
    document.pdf.save()
    print(OUTPUT)
    for page in range(1, 7):
        bottom = max(end for number, _, end, _ in document.bounds if number == page)
        print(f"Page {page}: content ends at {bottom:.1f} pt; footer at 791 pt")


if __name__ == "__main__":
    main()
