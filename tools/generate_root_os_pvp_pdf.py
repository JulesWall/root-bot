from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "pdf"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "guide-root-os-pvp-v2.pdf"


PALETTE = {
    "ink": colors.HexColor("#101820"),
    "muted": colors.HexColor("#54616f"),
    "line": colors.HexColor("#d8dee7"),
    "paper": colors.HexColor("#f6f8fb"),
    "panel": colors.HexColor("#eaf0f6"),
    "cyan": colors.HexColor("#1f8ea9"),
    "green": colors.HexColor("#1f7a56"),
    "red": colors.HexColor("#b13f4a"),
    "gold": colors.HexColor("#b47a1d"),
    "night": colors.HexColor("#17212b"),
}


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="CoverTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=32,
        leading=37,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
)
styles.add(
    ParagraphStyle(
        name="CoverSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12.5,
        leading=17,
        textColor=colors.HexColor("#c7d5e4"),
        alignment=TA_CENTER,
    )
)
styles.add(
    ParagraphStyle(
        name="Section",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        textColor=PALETTE["ink"],
        spaceBefore=18,
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        name="SubSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=15,
        textColor=PALETTE["cyan"],
        spaceBefore=10,
        spaceAfter=5,
    )
)
styles.add(
    ParagraphStyle(
        name="BodyNice",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.6,
        leading=13.2,
        textColor=PALETTE["ink"],
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        name="Small",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.3,
        leading=11,
        textColor=PALETTE["muted"],
    )
)
styles.add(
    ParagraphStyle(
        name="Command",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=8.3,
        leading=10.5,
        textColor=colors.HexColor("#183449"),
        backColor=colors.HexColor("#eef3f8"),
        borderColor=colors.HexColor("#d2dce7"),
        borderWidth=0.4,
        borderPadding=5,
        spaceBefore=2,
        spaceAfter=6,
    )
)


def p(text, style="BodyNice"):
    return Paragraph(text, styles[style])


def bullet(text):
    return Paragraph(f"- {text}", styles["BodyNice"])


def command(text):
    return Paragraph(text.replace("\n", "<br/>"), styles["Command"])


def section(title):
    return Paragraph(title, styles["Section"])


def subsection(title):
    return Paragraph(title, styles["SubSection"])


def table(data, widths, header=True):
    converted = []
    for row_idx, row in enumerate(data):
        converted.append(
            [
                cell
                if hasattr(cell, "wrap")
                else Paragraph(str(cell), styles["Small"] if row_idx else styles["BodyNice"])
                for cell in row
            ]
        )
    style = [
        ("GRID", (0, 0), (-1, -1), 0.35, PALETTE["line"]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        style.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PALETTE["night"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    for idx in range(1, len(data), 2):
        style.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#fbfcfe")))
    t = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    t.setStyle(TableStyle(style))
    return t


def build_story():
    story = []

    story.append(Spacer(1, 3.8 * cm))
    story.append(p("ROOT OS", "CoverTitle"))
    story.append(p("Manuel PvP V2", "CoverTitle"))
    story.append(Spacer(1, 0.2 * cm))
    story.append(
        p(
            "Guide synthetique, complet et pret a partager pour comprendre le nouveau systeme PvP.",
            "CoverSub",
        )
    )
    story.append(Spacer(1, 1.1 * cm))
    story.append(
        table(
            [
                ["Cycle principal", "Scanner -> Developper -> Compiler -> Deployer -> Diagnostiquer -> Patch"],
                ["Ressource cle", "Chaque faille possede une empreinte unique, par exemple [K7M2]."],
                ["Objectif", "Gagner par information, tempo, preparation et gestion du risque."],
            ],
            [4.2 * cm, 10.8 * cm],
            header=False,
        )
    )
    story.append(PageBreak())

    story.append(section("Vue d'ensemble"))
    story.append(
        p(
            "Le PvP de Root OS V2 remplace les attaques abstraites par une boucle plus tactique. "
            "Vous observez une cible, vous preparez un outil, vous compilez une copie exploitable, "
            "puis vous choisissez le moment exact pour lancer l'operation."
        )
    )
    story.append(
        p(
            "Chaque faille decouverte recoit une empreinte unique de 4 caracteres. Cette empreinte "
            "sert a suivre la menace, a fabriquer des copies offensives et a creer le patch capable "
            "de la neutraliser definitivement."
        )
    )

    story.append(subsection("Les trois objets essentiels"))
    story.append(
        table(
            [
                ["Objet", "Role"],
                ["Dossier de recherche", "Decouverte originale. Permet de compiler des copies utilisables."],
                ["Logiciel compile", "Copie prete a etre deployee. Une attaque consomme une copie."],
                ["Patch", "Correctif lie a une empreinte precise. Il supprime l'infection et immunise contre cette empreinte."],
            ],
            [4.5 * cm, 11 * cm],
        )
    )

    story.append(subsection("Les deux canaux"))
    story.append(bullet("<b>Canal offensif</b> : recherche et compilation d'outils d'attaque."))
    story.append(bullet("<b>Canal defensif</b> : creation de patchs et protection du reseau."))

    story.append(section("1. Observer avant d'attaquer : /scan"))
    story.append(command("/scan @cible\n!scan @cible"))
    story.append(
        table(
            [
                ["Parametre", "Valeur"],
                ["Cout", "0.005 RTM"],
                ["Delai", "90 secondes"],
                ["Condition", "Infrastructure niveau 1 minimum."],
                ["Restriction", "Cible de niveau superieur ou egal au votre, sauf droit de represailles actif."],
            ],
            [4.2 * cm, 11.2 * cm],
        )
    )
    story.append(p("Le rapport de reconnaissance arrive en message prive et indique :"))
    for item in [
        "le niveau d'infrastructure adverse et ses points de defense passive ;",
        "son materiel minier, ses tiers et son hashrate total ;",
        "le taux de remplissage de sa RAM ;",
        "les signatures de logiciels et correctifs deja deployes.",
    ]:
        story.append(bullet(item))
    story.append(p("Le scan sert a savoir si la cible est rentable, protegee, fragile ou deja compromise."))

    story.append(section("2. Creer ses outils : /dev et /library"))
    story.append(subsection("Rechercher une faille"))
    story.append(command("/dev start job_type:research channel:offense family:hostile_miner tier:2\n!dev start research hostile_miner 2"))
    story.append(p("A la fin du travail, vous obtenez un dossier de recherche avec une empreinte unique."))
    story.append(subsection("Compiler une copie"))
    story.append(command("/dev start job_type:compile channel:offense family:hostile_miner tier:2\n!dev start compile hostile_miner 2"))
    story.append(p("Chaque copie compilee peut ensuite etre consommee dans une attaque."))
    story.append(subsection("Consulter la bibliotheque"))
    story.append(command("/library\n!library"))
    story.append(p("La bibliotheque centralise vos dossiers, copies logicielles et patchs."))

    story.append(section("3. Deployer une attaque : /hack"))
    story.append(command("/hack target:@cible family:<famille> tier:<tier> confirm:confirm\n!hack @cible <famille> <tier> confirm"))
    story.append(
        p(
            "L'installation se deroule en fond. Plus la cible possede de defense de baie, "
            "plus le deploiement est lent."
        )
    )
    story.append(command("Duree effective = Duree de base x (1 + DEF cible / 500)\nDuree plafonnee a x10"))
    story.append(bullet("1 seule operation active par famille."))
    story.append(bullet("3 operations offensives actives maximum en meme temps."))
    story.append(PageBreak())

    story.append(section("4. Les six familles de malwares"))
    malware_rows = [
        ["Famille", "Effet", "Resolution"],
        ["Hostile Miner", "Siphonne 15% de la production brute de la baie ciblee vers votre RAM.", "Persistant jusqu'au patch correspondant."],
        ["Ransomware", "Bloque les commandes economiques : buy, upgrade, compile, trade, etc.", "Paiement de rancon ou patch. Maximum 72h."],
        ["Currency Theft", "Vole instantanement 25% du solde USD de la cible. Plancher protege : 50$.", "Effet immediat. Frais de 5%."],
        ["Saturation", "Reduit de 30% la vitesse du canal de recherche offensif adverse.", "6h. Effet cumule plafonne a 60%."],
        ["Espionage", "Cartographie discrete des logiciels, dossiers et patchs adverses.", "Rapport instantane en MP."],
        ["Software Theft", "Copie un logiciel compile present chez la cible dans votre inventaire.", "Effet immediat. Non revendable."],
    ]
    story.append(table(malware_rows, [3.3 * cm, 8.2 * cm, 4.2 * cm]))

    story.append(section("5. Se defendre : /diag, patch et /trace"))
    story.append(subsection("Diagnostic"))
    story.append(command("/diag\n!diag\n!hack diag"))
    story.append(p("Cout : 0.001 RTM. Le diagnostic revele les signatures hostiles actives et leurs empreintes."))
    story.append(subsection("Creer un patch"))
    story.append(command("/dev start job_type:patch_research channel:defense family:hostile_miner fingerprint:K7M2\n!dev start patch_research hostile_miner K7M2"))
    story.append(p("Une fois le patch pret, installez-le depuis /library pour supprimer l'infection et bloquer cette empreinte."))
    story.append(subsection("Remonter une trace"))
    story.append(command("/trace\n!trace\n!hack trace"))
    story.append(
        p(
            "Cout : 0.002 RTM. Si l'attaquant n'a pas protege son propre reseau, son identite est revelee. "
            "Vous obtenez alors un droit de represailles de 72h."
        )
    )
    story.append(subsection("Payer une rancon"))
    story.append(command("/pay\n!pay\n!hack pay"))
    story.append(p("Permet de debloquer immediatement un reseau paralyse par ransomware."))

    story.append(section("6. Le marche souterrain : /market"))
    story.append(p("Le marche permet d'acheter ou de vendre des outils PvP."))
    story.append(bullet("Logiciels compiles non voles."))
    story.append(bullet("Patchs non installes."))
    story.append(bullet("Dossiers de recherche offensifs."))
    story.append(
        table(
            [
                ["Regle", "Detail"],
                ["Frais", "5% sur chaque vente."],
                ["Limite", "5 annonces simultanees maximum par vendeur."],
                ["Securite", "L'objet mis en vente est reserve pour eviter les fraudes."],
            ],
            [4.2 * cm, 11.2 * cm],
        )
    )
    story.append(
        table(
            [
                ["Commande", "Usage"],
                ["/market list ou !market list", "Voir les offres."],
                ["/market mine ou !market mine", "Voir vos annonces."],
                ["/market sell <type> <id> <prix>", "Mettre un objet en vente."],
                ["/market buy <listing_id>", "Acheter une annonce."],
                ["/market cancel <listing_id>", "Annuler une vente."],
            ],
            [6.5 * cm, 8.8 * cm],
        )
    )

    story.append(section("7. Commandes rapides"))
    story.append(
        table(
            [
                ["Commande", "Alias", "Usage"],
                ["/scan @cible", "!scan", "Analyse une cible avant attaque."],
                ["/dev start", "!dev start", "Recherche, compilation ou creation de patch."],
                ["/library", "!library", "Consulte vos logiciels, dossiers et patchs."],
                ["/hack", "!hack, !hk", "Deploie un logiciel offensif."],
                ["/diag", "!diag", "Detecte les infections actives."],
                ["/trace", "!trace", "Tente d'identifier l'attaquant."],
                ["/pay", "!pay", "Paie une rancon active."],
                ["/market", "!market, !mkt", "Accede au marche souterrain."],
            ],
            [4.2 * cm, 4.1 * cm, 7.1 * cm],
        )
    )

    story.append(section("Boucle de jeu conseillee"))
    for item in [
        "Scannez une cible.",
        "Developpez un outil adapte.",
        "Compilez une copie.",
        "Deployez l'attaque.",
        "Surveillez vos gains et vos risques.",
        "Diagnostiquez regulierement votre reseau.",
        "Patchez les empreintes dangereuses.",
        "Achetez ou vendez au marche pour accelerer votre strategie.",
    ]:
        story.append(bullet(item))
    story.append(
        p(
            "<b>Root OS V2 est un jeu d'information, de tempo et de preparation.</b> "
            "Le meilleur joueur n'est pas seulement celui qui attaque le plus fort, mais celui qui sait quand observer, "
            "quand frapper, quand vendre et quand disparaitre proprement."
        )
    )
    return story


def on_page(canvas, doc):
    canvas.saveState()
    page_width, page_height = A4
    if doc.page == 1:
        canvas.setFillColor(PALETTE["night"])
        canvas.rect(0, 0, page_width, page_height, stroke=0, fill=1)
        canvas.setStrokeColor(PALETTE["cyan"])
        canvas.setLineWidth(2)
        canvas.line(2.2 * cm, 5.1 * cm, page_width - 2.2 * cm, 5.1 * cm)
    else:
        canvas.setFillColor(PALETTE["paper"])
        canvas.rect(0, 0, page_width, page_height, stroke=0, fill=1)
        canvas.setStrokeColor(PALETTE["line"])
        canvas.setLineWidth(0.6)
        canvas.line(1.7 * cm, page_height - 1.35 * cm, page_width - 1.7 * cm, page_height - 1.35 * cm)
        canvas.setFillColor(PALETTE["muted"])
        canvas.setFont("Helvetica", 8)
        canvas.drawString(1.7 * cm, page_height - 1.1 * cm, "Root OS PvP V2")
        canvas.drawRightString(page_width - 1.7 * cm, 1.0 * cm, f"Page {doc.page}")
    canvas.restoreState()


def main():
    doc = SimpleDocTemplate(
        str(OUT_FILE),
        pagesize=A4,
        rightMargin=1.7 * cm,
        leftMargin=1.7 * cm,
        topMargin=1.65 * cm,
        bottomMargin=1.6 * cm,
        title="Manuel PvP Root OS V2",
        author="Root OS",
    )
    doc.build(build_story(), onFirstPage=on_page, onLaterPages=on_page)
    print(OUT_FILE)


if __name__ == "__main__":
    main()
