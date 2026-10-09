"""
Données textuelles et fiches de commandes pour le système d'aide en Français (/help).
Conforme aux spécifications de CONCEPTION_HELP.md.
"""

UI = {
    "select_category_placeholder": "Choisir une rubrique...",
    "select_command_placeholder": "Voir une commande en détail...",
    "btn_home": "Accueil",
    "btn_back_category": "Retour à la rubrique",
    "btn_view_text": "Voir en texte",
    "btn_view_slash": "Voir en slash",
    "btn_server": "Serveur officiel",
    "mode_slash": "Mode Slash",
    "mode_text": "Mode Texte",
    "footer_slash": "Root OS • Aide • Mode Slash",
    "footer_text": "Root OS • Aide • Mode Texte • Préfixe : {prefix}",
    "navigation_expired": "Navigation expirée. Relance `/help` pour continuer.",
    "not_author_error": "Ouvre `/help` pour consulter ton propre guide.",
    "unknown_command_title": "Commande non trouvée",
    "unknown_command_body": (
        "Cette commande n’est pas disponible dans l’aide des joueurs.\n"
        "Choisis une rubrique pour retrouver les commandes proposées."
    ),
    "beta_note": (
        "\n\n*Le jeu est actuellement en bêta : certaines commandes nécessitent un accès. "
        "Tu peux consulter cette aide et créer ton réseau avec `/network`.*"
    ),
    "sec_syntax": "Syntaxe",
    "sec_parameters": "Paramètres",
    "sec_example": "Exemple",
    "sec_prerequisites": "Avant d'utiliser",
    "sec_advice": "Conseil",
    "sec_aliases": "Alias texte",
    "sec_linked": "Commandes liées",
    "select_cmd_part1_placeholder": "Commandes (Réseau, Combat, Événements)...",
    "select_cmd_part2_placeholder": "Commandes (Échange, Utilitaires, Infos)...",
}

CATEGORIES = [
    {
        "id": "home",
        "emoji": "🏠",
        "label": "Accueil",
        "description": "Présentation générale et premiers pas",
    },
    {
        "id": "all",
        "emoji": "📜",
        "label": "Toutes les commandes",
        "description": "Index complet des 27 commandes du jeu",
    },
    {
        "id": "network",
        "emoji": "⛏️",
        "label": "Développer mon réseau",
        "description": "Gestion du matériel, minage et infrastructure",
    },
    {
        "id": "combat",
        "emoji": "⚔️",
        "label": "Attaquer et me défendre",
        "description": "Points d'attaque, scans et hacks PvP",
    },
    {
        "id": "events",
        "emoji": "🎮",
        "label": "Participer aux événements",
        "description": "Mini-jeux de cryptographie et défis réseau",
    },
    {
        "id": "trade",
        "emoji": "🤝",
        "label": "Échanger et me classer",
        "description": "Échanges, réputation, attestations et tops",
    },
    {
        "id": "info",
        "emoji": "⚙️",
        "label": "Langue et informations",
        "description": "Préférences et informations système",
    },
    {
        "id": "syntax",
        "emoji": "📖",
        "label": "Lire une syntaxe",
        "description": "Règles des paramètres, alias et préfixe",
    },
]

PAGES = {
    "home": {
        "title": "📡 ROOT — Centre d'aide",
        "body_slash": (
            "Développe ton réseau, produis du Rootium et affronte les autres joueurs.\n\n"
            "**🚀 Tes premiers pas sur Root :**\n"
            "**1. Crée ton réseau — `/network`**\n"
            "Tu y retrouveras tes ressources, ton matériel et ta production.\n\n"
            "**2. Installe un mineur — `/buy`**\n"
            "Ouvre la boutique et choisis un module de minage accessible.\n\n"
            "**3. Récupère ta production — `/claim`**\n"
            "Tes mineurs accumulent du Rootium. Quand la RAM est pleine, le minage s'arrête.\n\n"
            "**4. Finance la suite — `/market` et `/event`**\n"
            "Vends ou achète des RTM au cours dynamique et participe aux événements.\n\n"
            "**5. Développe ton réseau — `/upgrade`**\n"
            "Améliore ton infrastructure pour débloquer du matériel avancé (attention : le niveau 1 active le PvP !).\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "**Les ressources :**\n"
            "• **USD ($)** : Monnaie pour le minage, la défense et l'infrastructure.\n"
            "• **RTM** : Rootium miné, requis pour l'attaque, la compilation et les scans.\n"
            "• **ATK** : Points d'attaque fabriqués avec `/compile`.\n\n"
            "💬 **Communauté & Support :** [Rejoins le serveur officiel](https://discord.gg/FtfGuyb6mv)\n\n"
            "👉 *Utilise le menu ci-dessous pour parcourir les rubriques ou ouvrir directement une fiche avec `/help command:buy`.*"
        ),
        "body_text": (
            "Développe ton réseau, produis du Rootium et affronte les autres joueurs.\n\n"
            "**🚀 Tes premiers pas sur Root :**\n"
            "**1. Crée ton réseau — `{prefix}network`**\n"
            "Tu y retrouveras tes ressources, ton matériel et ta production.\n\n"
            "**2. Installe un mineur — `{prefix}buy`**\n"
            "Ouvre la boutique et choisis un module de minage accessible.\n\n"
            "**3. Récupère ta production — `{prefix}claim`**\n"
            "Tes mineurs accumulent du Rootium. Quand la RAM est pleine, le minage s'arrête.\n\n"
            "**4. Finance la suite — `{prefix}market` et `{prefix}event`**\n"
            "Vends ou achète des RTM au cours dynamique et participe aux événements.\n\n"
            "**5. Développe ton réseau — `{prefix}upgrade`**\n"
            "Améliore ton infrastructure pour débloquer du matériel avancé (attention : le niveau 1 active le PvP !).\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "**Les ressources :**\n"
            "• **USD ($)** : Monnaie pour le minage, la défense et l'infrastructure.\n"
            "• **RTM** : Rootium miné, requis pour l'attaque, la compilation et les scans.\n"
            "• **ATK** : Points d'attaque fabriqués avec `{prefix}compile`.\n\n"
            "💬 **Communauté & Support :** [Rejoins le serveur officiel](https://discord.gg/FtfGuyb6mv)\n\n"
            "👉 *Utilise le menu ci-dessous pour parcourir les rubriques ou ouvrir directement une fiche avec `{prefix}help buy`.*"
        ),
    },
    "all": {
        "title": "📜 ROOT — Toutes les commandes",
        "body_slash": (
            "Index complet des 28 commandes publiques de Root.\n\n"
            "**⛏️ Développer mon réseau**\n"
            "• **/network** — Créer ou consulter mon réseau et mes soldes\n"
            "• **/buy** — Acheter un module (minage, attaque, défense)\n"
            "• **/claim** — Récupérer le Rootium miné et libérer la RAM\n"
            "• **/hourly** — Réclamer ma prime horaire en dollars et faire monter le combo\n"
            "• **/contract** — Consulter et accepter des missions rémunérées avec Root CyberSec\n"
            "• **/market** — Consulter le cours dynamique, graphiques, achat et vente de Rootium\n"
            "• **/upgrade** — Améliorer le niveau d'infrastructure\n"
            "• **/macro** — Automatiser des routines de commandes séquentielles\n\n"
            "**⚔️ Attaquer et me défendre**\n"
            "• **/compile** — Fabriquer des points d'attaque (ATK)\n"
            "• **/scan** — Scanner un joueur pour trouver son Secret ID\n"
            "• **/hack** — Lancer une cyberattaque ciblée\n\n"
            "**🎮 Participer aux événements**\n"
            "• **/event** — Voir le tableau des événements actifs\n"
            "• **/hash** — Trouver le nombre secret du bloc\n"
            "• **/pin** — Deviner le code PIN à 4 chiffres\n"
            "• **/decode** — Décoder la matrice de lettres\n"
            "• **/anomaly** — Repérer la ligne de code anormale\n"
            "• **/buffer** — Reconstituer les fragments du buffer\n"
            "• **/signal** — Détecter la lettre dominante\n"
            "• **/packet** — Trouver le numéro du paquet manquant\n\n"
            "**🤝 Échanger et me classer**\n"
            "• **/rep** — Donner un point de réputation quotidien\n"
            "• **/trade** — Proposer un échange sécurisé de devises\n"
            "• **/attest** — Attester un solde minimum en public\n"
            "• **/top** — Consulter les classements des meilleurs joueurs\n\n"
            "**⚙️ Langue et informations**\n"
            "• **/lang** — Configurer sa langue d'affichage (fr/en)\n"
            "• **/rmd** — Programmer des rappels personnalisés ou automatiques\n"
            "• **/ping** — Tester la latence de la passerelle Discord\n"
            "• **/maths** — Évaluer une expression mathématique\n"
            "• **/botinfo** — Statistiques système et informations\n"
            "• **/invite** — Obtenir le lien d'invitation officiel\n\n"
            "👉 *Sélectionne n'importe quelle commande ci-dessous pour ouvrir sa fiche détaillée.*"
        ),
        "body_text": (
            "Index complet des 29 commandes publiques de Root.\n\n"
            "**⛏️ Développer mon réseau**\n"
            "• **{prefix}network** (alias `{prefix}n`) — Créer ou consulter mon réseau\n"
            "• **{prefix}buy** — Acheter un module (minage, attaque, défense)\n"
            "• **{prefix}claim** (alias `{prefix}cl`) — Récupérer le Rootium miné\n"
            "• **{prefix}hourly** (alias `{prefix}hr`) — Réclamer ma prime horaire en dollars\n"
            "• **{prefix}contract** — Accepter des missions rémunérées garanties\n"
            "• **{prefix}market** (alias `{prefix}mk`) — Consulter le cours, graphiques, acheter et vendre des RTM\n"
            "• **{prefix}upgrade** — Améliorer le niveau d'infrastructure\n"
            "• **{prefix}macro** (alias `{prefix}mac`) — Automatiser des routines de commandes\n\n"
            "**⚔️ Attaquer et me défendre**\n"
            "• **{prefix}compile** (alias `{prefix}cp`) — Fabriquer des points ATK\n"
            "• **{prefix}scan** — Scanner un joueur pour trouver son Secret ID\n"
            "• **{prefix}hack** (alias `{prefix}hk`) — Lancer une cyberattaque ciblée\n\n"
            "**🎮 Participer aux événements**\n"
            "• **{prefix}event** (alias `{prefix}events`, `{prefix}e`) — Tableau des événements\n"
            "• **{prefix}hash** (alias `{prefix}h`) — Trouver le nombre secret du bloc\n"
            "• **{prefix}pin** (alias `{prefix}p`) — Deviner le code PIN\n"
            "• **{prefix}decode** (alias `{prefix}d`) — Décoder la matrice\n"
            "• **{prefix}anomaly** (alias `{prefix}a`) — Repérer la ligne corrompue\n"
            "• **{prefix}buffer** (alias `{prefix}b`) — Reconstituer le buffer\n"
            "• **{prefix}signal** (alias `{prefix}s`) — Détecter la lettre dominante\n"
            "• **{prefix}packet** (alias `{prefix}pa`) — Trouver le paquet manquant\n\n"
            "**🤝 Échanger et me classer**\n"
            "• **{prefix}rep** (alias `{prefix}reputation`) — Donner de la réputation\n"
            "• **{prefix}trade** — Proposer un échange de ressources\n"
            "• **{prefix}attest** (alias `{prefix}certify`) — Attester un solde minimum\n"
            "• **{prefix}top** (alias `{prefix}leaderboard`) — Consulter les classements\n\n"
            "**⚙️ Langue et informations**\n"
            "• **{prefix}lang** (alias `{prefix}language`) — Configurer sa langue\n"
            "• **{prefix}rmd** (alias `{prefix}remind`, `{prefix}reminder`) — Programmer des rappels\n"
            "• **{prefix}ping** — Tester la latence du bot\n"
            "• **{prefix}maths** (alias `{prefix}math`, `{prefix}calc`) — Calculer une expression mathématique\n"
            "• **{prefix}botinfo** — Statistiques système et informations\n"
            "• **{prefix}invite** — Obtenir le lien d'invitation officiel\n\n"
            "👉 *Sélectionne n'importe quelle commande ci-dessous pour ouvrir sa fiche détaillée.*"
        ),
    },
    "network": {
        "title": "⛏️ Développer mon réseau",
        "body_slash": (
            "Consulte ton réseau, installe du matériel et récupère ta production pour financer ta progression.\n\n"
            "• **/network** : Crée ton profil ou consulte l'état de ton réseau et de ta mémoire.\n"
            "• **/buy** : Ouvre le catalogue ou achète directement un module de minage, d'attaque ou de défense.\n"
            "• **/claim** : Récupère le Rootium miné dans ton solde et libère la mémoire RAM.\n"
            "• **/hourly** : Réclame ta prime horaire et fais monter ton combo pour décupler tes récompenses en USD.\n"
            "• **/contract** : Travaille pour Root CyberSec et accomplis des missions garanties pour un revenu régulier.\n"
            "• **/market** : Consulte le cours dynamique, graphiques, et négocie (achète/vends) du RTM.\n"
            "• **/upgrade** : Lance l'amélioration de ton niveau d'infrastructure.\n"
            "• **/macro** : Automatise tes routines en programmant jusqu'à 5 actions séquentielles.\n\n"
            "👉 *Sélectionne une commande dans le menu déroulant ci-dessous pour voir sa fiche détaillée.*"
        ),
        "body_text": (
            "Consulte ton réseau, installe du matériel et récupère ta production pour financer ta progression.\n\n"
            "• **{prefix}network** (alias `{prefix}n`) : Crée ton profil ou consulte l'état de ton réseau.\n"
            "• **{prefix}buy** : Ouvre le catalogue ou achète un module directement.\n"
            "• **{prefix}claim** (alias `{prefix}cl`) : Récupère le Rootium miné et libère la RAM.\n"
            "• **{prefix}hourly** (alias `{prefix}hr`) : Réclame ta prime horaire et entretiens ton combo.\n"
            "• **{prefix}contract** : Accepte des contrats de sécurité informatique rémunérés en USD.\n"
            "• **{prefix}market** (alias `{prefix}mk`) : Consulte le cours, graphiques, ou échange des RTM (`buy`/`sell`).\n"
            "• **{prefix}upgrade** : Lance l'amélioration de ton infrastructure.\n"
            "• **{prefix}macro** (alias `{prefix}mac`) : Automatise tes routines en programmant jusqu'à 5 actions séquentielles.\n\n"
            "👉 *Sélectionne une commande dans le menu déroulant ci-dessous pour voir sa fiche détaillée.*"
        ),
    },
    "combat": {
        "title": "⚔️ Attaquer et me défendre",
        "body_slash": (
            "Un module d'attaque fournit un débit de production. Utilise `/compile` pour fabriquer des ATK, "
            "puis `/scan` pour tenter de découvrir une cible et `/hack` pour l'attaquer.\n\n"
            "• **/compile** : Produis des points d'attaque (ATK) selon la méthode et le débit choisis.\n"
            "• **/scan** : Lance un scan sur un joueur pour tenter d'obtenir son Secret ID.\n"
            "• **/hack** : Engage tes ATK contre le réseau d'un adversaire via son Secret ID.\n\n"
            "🛡️ *Pour te protéger, achète des modules avec `/buy kind:defense` et améliore ton infrastructure avec `/upgrade`.*"
        ),
        "body_text": (
            "Un module d'attaque fournit un débit de production. Utilise `{prefix}compile` pour fabriquer des ATK, "
            "puis `{prefix}scan` pour tenter de découvrir une cible et `{prefix}hack` pour l'attaquer.\n\n"
            "• **{prefix}compile** (alias `{prefix}cp`) : Fabrique des points ATK avec tes RTM.\n"
            "• **{prefix}scan** : Tente d'extraire le Secret ID d'une cible.\n"
            "• **{prefix}hack** (alias `{prefix}hk`) : Lance une cyberattaque ciblée.\n\n"
            "🛡️ *Pour te protéger, achète des modules avec `{prefix}buy defense` et améliore ton infrastructure avec `{prefix}upgrade`.*"
        ),
    },
    "events": {
        "title": "🎮 Participer aux événements",
        "body_slash": (
            "Consulte `/event` pour suivre les événements. Lance un mini-jeu sans réponse pour voir son état, "
            "puis ajoute ta proposition pour participer.\n\n"
            "• **/event** : Tableau récapitulatif des événements et de leur statut.\n"
            "• **/hash** : Trouve le nombre secret du bloc cryptographique.\n"
            "• **/pin** : Découvre le code PIN à 4 chiffres.\n"
            "• **/decode** : Retrouve le code caché dans la matrice de lettres.\n"
            "• **/anomaly** : Identifie la ligne contenant un caractère parasite.\n"
            "• **/buffer** : Reconstitue la séquence de données fragmentée.\n"
            "• **/signal** : Détecte la fréquence dominante dans le flux radio.\n"
            "• **/packet** : Retrouve le numéro du paquet réseau manquant.\n\n"
            "👉 *Sélectionne un mini-jeu dans le menu ci-dessous pour afficher son guide de résolution.*"
        ),
        "body_text": (
            "Consulte `{prefix}event` pour suivre les événements. Lance un mini-jeu sans réponse pour voir son état, "
            "puis ajoute ta proposition pour participer.\n\n"
            "• **{prefix}event** (alias `{prefix}events`, `{prefix}e`) : Tableau des événements actifs.\n"
            "• **{prefix}hash** (alias `{prefix}h`) : Trouve le nombre secret du bloc.\n"
            "• **{prefix}pin** (alias `{prefix}p`) : Découvre le code PIN à 4 chiffres.\n"
            "• **{prefix}decode** (alias `{prefix}d`) : Retrouve le code dans la matrice.\n"
            "• **{prefix}anomaly** (alias `{prefix}a`) : Identifie la ligne corrompue.\n"
            "• **{prefix}buffer** (alias `{prefix}b`) : Reconstitue les fragments ordonnés.\n"
            "• **{prefix}signal** (alias `{prefix}s`) : Détecte la lettre dominante.\n"
            "• **{prefix}packet** (alias `{prefix}pa`) : Trouve le paquet manquant.\n\n"
            "👉 *Sélectionne un mini-jeu dans le menu ci-dessous pour afficher son guide de résolution.*"
        ),
    },
    "trade": {
        "title": "🤝 Échanger et me classer",
        "body_slash": (
            "Échange des ressources, donne de la réputation et retrouve les classements.\n\n"
            "• **/rep** : Attribue un point de réputation quotidien à un autre joueur.\n"
            "• **/trade** : Propose un échange sécurisé de dollars et Rootium à un joueur.\n"
            "• **/attest** : Prouve publiquement que ton solde atteint un montant sans le dévoiler.\n"
            "• **/top** : Affiche les classements généraux (réputation, dollars, victoires d'événements, puissance H/s).\n\n"
            "👉 *Sélectionne une commande ci-dessous pour consulter ses options et sa syntaxe.*"
        ),
        "body_text": (
            "Échange des ressources, donne de la réputation et retrouve les classements.\n\n"
            "• **{prefix}rep** (alias `{prefix}reputation`) : Donne un point de réputation.\n"
            "• **{prefix}trade** : Propose un échange bilatéral de ressources.\n"
            "• **{prefix}attest** (alias `{prefix}certify`, `{prefix}proof`) : Atteste un solde minimum.\n"
            "• **{prefix}top** (alias `{prefix}leaderboard`) : Consulte les classements (réputation, dollars, victoires, H/s).\n\n"
            "👉 *Sélectionne une commande ci-dessous pour consulter ses options et sa syntaxe.*"
        ),
    },
    "info": {
        "title": "⚙️ Langue et informations",
        "body_slash": (
            "Choisis ta langue et consulte les informations utiles sur Root.\n\n"
            "• **/lang** : Définis ou consulte ta langue d'affichage préférée (français ou anglais).\n"
            "• **/rmd** : Définis un rappel sur mesure ou synchronisé avec le jeu (hourly, claim, mini-jeux ou all).\n"
            "• **/ping** : Mesure le temps de réponse et la latence du bot.\n"
            "• **/maths** : Évalue une expression ou formule mathématique.\n"
            "• **/botinfo** : Affiche les informations système et statistiques globales.\n"
            "• **/invite** : Obtiens le lien officiel pour inviter Root sur ton serveur Discord.\n\n"
            "💬 **Serveur officiel :** [discord.gg/FtfGuyb6mv](https://discord.gg/FtfGuyb6mv)"
        ),
        "body_text": (
            "Choisis ta langue et consulte les informations utiles sur Root.\n\n"
            "• **{prefix}lang** (alias `{prefix}language`) : Configure ta langue (fr/en).\n"
            "• **{prefix}rmd** (alias `{prefix}remind`, `{prefix}reminder`) : Programme un rappel automatique ou un minuteur.\n"
            "• **{prefix}ping** : Mesure la latence du bot.\n"
            "• **{prefix}maths** (alias `{prefix}math`, `{prefix}calc`) : Calcule une expression mathématique.\n"
            "• **{prefix}botinfo** : Statistiques et informations système.\n"
            "• **{prefix}invite** : Lien d'invitation officiel de Root.\n\n"
            "💬 **Serveur officiel :** [discord.gg/FtfGuyb6mv](https://discord.gg/FtfGuyb6mv)"
        ),
    },
    "syntax": {
        "title": "📖 Comment lire les commandes",
        "body_slash": (
            "**En mode Slash :**\n"
            "Tape le nom de la commande, puis renseigne les champs suggérés par Discord.\n"
            "Exemple : `/buy kind:mining tier:1`\n\n"
            "**En mode Texte :**\n"
            "Saisis le préfixe du serveur, le nom de la commande, puis ses arguments dans l'ordre.\n"
            "Exemple : `{prefix}buy mining 1`\n\n"
            "**Notation employée dans le guide :**\n"
            "• `<valeur>` : paramètre obligatoire.\n"
            "• `[valeur]` : paramètre facultatif.\n"
            "• `mining|attack|defense` : choisir une seule de ces options.\n"
            "*(Ne saisis jamais les chevrons `< >` ou crochets `[ ]` dans tes commandes.)*\n\n"
            "**Les alias :**\n"
            "Les alias sont des raccourcis **en mode Texte** uniquement. Par exemple, `{prefix}n` équivaut à `{prefix}network`.\n\n"
            "**La confirmation :**\n"
            "Sur les commandes d'achat ou de conversion, ajouter `confirm` exécute immédiatement l'ordre sans afficher le devis préalable."
        ),
        "body_text": (
            "**En mode Texte :**\n"
            "Saisis le préfixe du serveur, le nom de la commande, puis ses arguments séparés par des espaces.\n"
            "Exemple : `{prefix}buy mining 1`\n\n"
            "**En mode Slash :**\n"
            "Tape `/` suivi du nom de la commande pour remplir les options Discord.\n"
            "Exemple : `/buy kind:mining tier:1`\n\n"
            "**Notation employée dans le guide :**\n"
            "• `<valeur>` : paramètre obligatoire.\n"
            "• `[valeur]` : paramètre facultatif.\n"
            "• `mining|attack|defense` : choisir une seule de ces options.\n"
            "*(Ne saisis jamais les chevrons `< >` ou crochets `[ ]` dans tes commandes.)*\n\n"
            "**Les raccourcis :**\n"
            "Les alias raccourcissent la saisie texte : `{prefix}cp` remplace `{prefix}compile`.\n\n"
            "**La confirmation :**\n"
            "L'argument `confirm` en fin de commande valide directement l'action sans demander confirmation."
        ),
    },
}

COMMANDS = {
    # ── Page 2 : Développer mon réseau ──────────────────────────
    "network": {
        "name": "network",
        "category": "network",
        "title": "📡 `/network` — Créer ou consulter mon réseau",
        "description": "Crée ton profil lors de la première utilisation, puis consulte ton réseau, tes modules et tes ressources.",
        "slash_syntax": "/network",
        "text_syntax": "{prefix}network",
        "parameters": "Aucun paramètre.",
        "slash_example": "/network",
        "text_example": "{prefix}network",
        "prerequisites": "Aucun prérequis. Cette commande permet d'initialiser ton compte même si tu n'es pas inscrit.",
        "advice": "Commence ici ! Reviens ensuite régulièrement vérifier ta production et l'état de remplissage de ta mémoire.",
        "aliases": ["{prefix}n"],
        "linked_commands": ["buy", "claim"],
    },
    "buy": {
        "name": "buy",
        "category": "network",
        "title": "🛒 `/buy` — Acheter un module",
        "description": "Achète des modules de minage (RTM), offensifs (ATK) ou défensifs pour renforcer et équiper ton réseau.",
        "slash_syntax": "/buy [kind:<mining|attack|defense>] [tier:<1–5>] [count:<quantité>] [confirm:confirm]",
        "text_syntax": "{prefix}buy [mining|attack|defense] [tier] [quantité] [confirm]",
        "parameters": (
            "• `kind` : Type de module (`mining`, `attack`, `defense`). Ouvre le catalogue interactif si omis.\n"
            "• `tier` : Niveau du module de 1 à 5 (par défaut 1 si `kind` est précisé).\n"
            "• `count` : Nombre d'exemplaires à acheter (par défaut 1).\n"
            "• `confirm` : Valide l'achat directement sans afficher le devis interactif."
        ),
        "slash_example": "/buy kind:defense tier:3 count:20",
        "text_example": "{prefix}buy defense 3 20 confirm",
        "prerequisites": "Un réseau créé, les fonds nécessaires (USD ou RTM selon le module) et le niveau d'infrastructure requis.",
        "advice": "Ouvre `/buy` sans argument pour parcourir les modules disponibles, leurs statistiques et leurs tarifs.",
        "aliases": ["Synonyme texte : `{prefix}buy bay_defense` pour la défense"],
        "linked_commands": ["claim", "compile", "upgrade"],
    },
    "claim": {
        "name": "claim",
        "category": "network",
        "title": "⚡ `/claim` — Récupérer ma production",
        "description": "Transfère le Rootium miné et stocké dans tes modules vers ton solde principal et libère la mémoire RAM. Permet également d'automatiser les récoltes avec des crédits d'autoclaim.",
        "slash_syntax": "/claim [auto:<nb|all|cancel>]",
        "text_syntax": "{prefix}claim [auto <nb|all> | cancel]",
        "parameters": (
            "  `auto <nb|all>` : Lance l'autoclaim. Exécute une récolte immédiate puis programme chaque claim suivant dès que la RAM atteint 99,9 % (consomme des crédits d'autoclaim).\n"
            "  `cancel` : Annule les autoclaims programmés en cours et restitue les crédits non consommés.\n"
            "  *Sans argument* : Récolte manuelle immédiate standard."
        ),
        "slash_example": "/claim auto:all",
        "text_example": "{prefix}claim auto 3",
        "prerequisites": "Un réseau actif avec au moins un mineur ayant généré des fractions de Rootium. Des crédits d'autoclaim sont requis pour le mode auto.",
        "advice": "Une mémoire RAM saturée interrompt le minage ! Consulte `/network` pour surveiller ta jauge. Les résultats d'autoclaim sont envoyés en MP.",
        "aliases": ["{prefix}c", "{prefix}cl"],
        "linked_commands": ["convert", "network"],
    },
    "hourly": {
        "name": "hourly",
        "category": "network",
        "title": "⏱️ `/hourly` — Récompense horaire & combo",
        "description": "Réclame une prime en dollars USD toutes les 60 minutes. Si tu réclames dans la fenêtre de combo (entre 1h00 et 1h20 après ta dernière récolte), tu obtiens un bonus en pourcentage qui s'accumule sans limite !",
        "slash_syntax": "/hourly",
        "text_syntax": "{prefix}hourly",
        "parameters": "Aucun paramètre.",
        "slash_example": "/hourly",
        "text_example": "{prefix}hourly",
        "prerequisites": "Avoir créé son réseau avec `/network`.",
        "advice": "Active un rappel avec `/rmd timer:hourly` pour ne pas manquer la fenêtre de 20 minutes et préserver ton combo.",
        "aliases": ["{prefix}hr"],
        "linked_commands": ["network", "rmd", "contract"],
    },
    "contract": {
        "name": "contract",
        "category": "network",
        "title": "📋 `/contract` — Missions Root CyberSec",
        "description": "Accepte des contrats de sécurité informatique garantis (sans risque d'échec) pour Root CyberSec. Choisis parmi 3 durées (court 30 min, moyen 2h, long 6h) et cumule de la fidélité pour débloquer des missions spéciales (+40%).",
        "slash_syntax": "/contract [action] [duration]",
        "text_syntax": "{prefix}contract [action] [duration]",
        "parameters": (
            "• `action` (facultatif) : `view` (consulter l'état), `start` (démarrer un contrat) ou `collect` (récupérer la prime).\n"
            "• `duration` (facultatif) : `short` (30 min), `medium` (2h) ou `long` (6h)."
        ),
        "slash_example": "/contract action:start duration:short",
        "text_example": "{prefix}contract start short",
        "prerequisites": "Avoir créé son réseau avec `/network`.",
        "advice": "Tu peux aussi utiliser les boutons interactifs sous l'interface pour accepter un contrat ou récupérer ta paye en un clic.",
        "aliases": ["{prefix}co"],
        "linked_commands": ["network", "hourly", "buy"],
    },
    "upgrade": {
        "name": "upgrade",
        "category": "network",
        "title": "🛡️ `/upgrade` — Améliorer mon infrastructure",
        "description": "Augmente le niveau de ton infrastructure pour accroître ta défense globale, débloquer du matériel avancé et multiplier tes gains (horaire, contrats et événements x(niveau + 1)).",
        "slash_syntax": "/upgrade [confirm:confirm]",
        "text_syntax": "{prefix}upgrade [confirm]",
        "parameters": "• `confirm` : Lance directement le chantier d'amélioration sans étape de confirmation.",
        "slash_example": "/upgrade",
        "text_example": "{prefix}upgrade",
        "prerequisites": "Un réseau, les dollars requis et aucun chantier d'amélioration d'infrastructure déjà en cours.",
        "advice": "Chaque niveau d'infrastructure multiplie tes gains (/hourly, /contract et événements) par (Niveau + 1) ! Attention : au niveau 0, tu bénéficies d'une protection spéciale contre le PvP. Passer au niveau 1 t'expose aux attaques des autres joueurs !",
        "aliases": [],
        "linked_commands": ["buy", "network"],
    },

    # ── Page 3 : Attaquer et me défendre ────────────────────────
    "compile": {
        "name": "compile",
        "category": "combat",
        "title": "⚙️ `/compile` — Produire des points ATK",
        "description": "Lance un lot de compilation pour fabriquer des points d'attaque (ATK) à partir de tes réserves de Rootium.",
        "slash_syntax": "/compile method:<unskilled|skilled|ai> [atk:<entier|all>] [confirm:confirm]",
        "text_syntax": "{prefix}compile <unskilled|skilled|ai> [entier|all] [confirm]",
        "parameters": (
            "• `method` : Méthode employée (`unskilled` = non qualifié, `skilled` = qualifié, `ai` = intelligence artificielle).\n"
            "• `atk` : Quantité d'ATK à fabriquer (par défaut `all` pour produire le lot maximum permis par ton débit matériel).\n"
            "• `confirm` : Démarre directement la compilation sans afficher le devis."
        ),
        "slash_example": "/compile method:ai atk:1",
        "text_example": "{prefix}compile ai 1",
        "example_note": "Production au maximum : `/compile method:unskilled atk:all`",
        "prerequisites": "Posséder au moins un module d'attaque installé, les RTM nécessaires et aucun lot déjà en cours de compilation.",
        "advice": "Vérifie attentivement le coût en RTM et la durée de fabrication dans le devis avant de confirmer.",
        "aliases": ["{prefix}cp", "Alias des méthodes en texte : `uns`/`nq`, `sk`/`q`, `ia`"],
        "linked_commands": ["scan", "hack"],
    },
    "scan": {
        "name": "scan",
        "category": "combat",
        "title": "🔍 `/scan` — Scanner un joueur",
        "description": "Analyse le réseau d'un adversaire pour tenter de percer son infrastructure et révéler son Secret ID.",
        "slash_syntax": "/scan target:<@joueur>",
        "text_syntax": "{prefix}scan <@joueur>",
        "parameters": "• `target` : Mention ou sélection du joueur cible.",
        "slash_example": "/scan target:@Alex",
        "text_example": "{prefix}scan @Alex",
        "prerequisites": "Un réseau créé, les réserves de RTM requises et une cible valide (infrastructure ≥ 1, pas en protection novice).",
        "advice": "Le succès d'un scan dépend de vos statistiques respectives. Si le scan réussit, note bien le Secret ID : il est temporaire !",
        "aliases": [],
        "linked_commands": ["hack", "compile"],
    },
    "hack": {
        "name": "hack",
        "category": "combat",
        "title": "💥 `/hack` — Attaquer un réseau",
        "description": "Engage tes points ATK contre un réseau adverse pour piller un module de minage ou détruire ses équipements offensifs.",
        "slash_syntax": "/hack secret_id:<code> attack_points:<entier> zone:<mining|attack> [confirm:confirm]",
        "text_syntax": "{prefix}hack <secret_id> <attack_points> <mining|attack> [confirm]",
        "parameters": (
            "• `secret_id` : L'identifiant secret valide de la cible obtenu via un scan préalable.\n"
            "• `attack_points` : Nombre de points ATK à engager dans l'assaut.\n"
            "• `zone` : Cible de l'intrusion (`mining` pour voler un mineur, `attack` pour détruire un module offensif).\n"
            "• `confirm` : Lance l'attaque sans devis de risque."
        ),
        "slash_example": "/hack secret_id:123456 attack_points:10 zone:mining",
        "text_example": "{prefix}hack 123456 10 mining",
        "example_note": "`123456` et 10 ATK sont des valeurs d'illustration.",
        "prerequisites": "Un Secret ID valide, un stock d'ATK disponible et une cible non protégée.",
        "advice": "Pour que l'intrusion réussisse, tes points ATK doivent dépasser STRICTEMENT la défense totale adverse. En cas d'égalité, l'intrusion échoue !",
        "aliases": ["{prefix}hk"],
        "linked_commands": ["scan", "compile"],
    },

    # ── Page 4 : Participer aux événements ──────────────────────
    "event": {
        "name": "event",
        "category": "events",
        "title": "🎯 `/event` — Voir les événements",
        "description": "Consulte le tableau de bord des événements communautaires, les récompenses (multipliées par ton niveau d'infrastructure + 1) et les mini-jeux actuellement ouverts.",
        "slash_syntax": "/event",
        "text_syntax": "{prefix}event",
        "parameters": "Aucun paramètre.",
        "slash_example": "/event",
        "text_example": "{prefix}event",
        "prerequisites": "Aucun prérequis spécifique pour consulter le tableau.",
        "advice": "Repère un événement actif, puis lance la commande du mini-jeu sans argument pour lire son défi en cours. Tes gains d'événements sont multipliés par (Niveau d'infrastructure + 1) !",
        "aliases": ["{prefix}events", "{prefix}e"],
        "linked_commands": ["hash", "pin", "decode"],
    },
    "hash": {
        "name": "hash",
        "category": "events",
        "title": "🔢 `/hash` — Trouver le nombre du bloc",
        "description": "Découvre le nombre secret validant le bloc en réduisant l'intervalle selon les indices 'plus grand' ou 'plus petit'.",
        "slash_syntax": "/hash [guess:<entier>]",
        "text_syntax": "{prefix}hash [entier]",
        "parameters": "• `guess` : Le nombre proposé. Omettre pour afficher le défi et l'intervalle en cours.",
        "slash_example": "/hash guess:500",
        "text_example": "{prefix}hash 500",
        "prerequisites": "Un événement de minage de hash actif.",
        "advice": "Cadence d'un essai toutes les 8 minutes par joueur. Appuie-toi sur la fourchette affichée par le bot pour affiner efficacement.",
        "aliases": ["{prefix}h"],
        "linked_commands": ["event"],
    },
    "pin": {
        "name": "pin",
        "category": "events",
        "title": "🔐 `/pin` — Trouver le code PIN",
        "description": "Devine la combinaison numérique secrète en analysant les retours sur ta zone de recherche personnelle.",
        "slash_syntax": "/pin [guess:<entier>]",
        "text_syntax": "{prefix}pin [entier]",
        "parameters": "• `guess` : Le code PIN proposé. Omettre pour consulter le statut du défi.",
        "slash_example": "/pin guess:60",
        "text_example": "{prefix}pin 60",
        "prerequisites": "Un défi PIN actif.",
        "advice": "Ta zone de recherche t'est propre : ne suppose pas qu'elle est identique à celle des autres joueurs.",
        "aliases": ["{prefix}p"],
        "linked_commands": ["event"],
    },
    "decode": {
        "name": "decode",
        "category": "events",
        "title": "🧩 `/decode` — Décoder la matrice",
        "description": "Reconstitue le mot de passe de 4 lettres en lisant les coordonnées fournies dans la grille alphanumérique.",
        "slash_syntax": "/decode [code:<4 lettres>]",
        "text_syntax": "{prefix}decode [code]",
        "parameters": "• `code` : La suite de 4 lettres obtenue. Omettre pour afficher la grille.",
        "slash_example": "/decode code:ABCD",
        "text_example": "{prefix}decode ABCD",
        "prerequisites": "Un défi de décodage actif.",
        "advice": "Envoie les lettres trouvées aux intersections, et non pas les numéros de lignes et colonnes !",
        "aliases": ["{prefix}d"],
        "linked_commands": ["event"],
    },
    "anomaly": {
        "name": "anomaly",
        "category": "events",
        "title": "🚨 `/anomaly` — Repérer l'anomalie",
        "description": "Scanne les lignes de code affichées et identifie le numéro de la ligne qui contient un chiffre parasite.",
        "slash_syntax": "/anomaly [line:<1–10>]",
        "text_syntax": "{prefix}anomaly [ligne]",
        "parameters": "• `line` : Le numéro de la ligne suspecte (de 1 à 10). Omettre pour voir le flux.",
        "slash_example": "/anomaly line:4",
        "text_example": "{prefix}anomaly 4",
        "prerequisites": "Un événement d'anomalie réseau actif.",
        "advice": "Compte les lignes de haut en bas à partir de 1. Réponds avec le numéro de ligne, pas le chiffre découvert.",
        "aliases": ["{prefix}a"],
        "linked_commands": ["event"],
    },
    "buffer": {
        "name": "buffer",
        "category": "events",
        "title": "💾 `/buffer` — Reconstituer le buffer",
        "description": "Remets dans l'ordre chronologique (1 à 6) les fragments de mémoire mélangés pour former le mot de passe.",
        "slash_syntax": "/buffer [code:<6 lettres>]",
        "text_syntax": "{prefix}buffer [code]",
        "parameters": "• `code` : Les 6 lettres assemblées dans l'ordre 1 à 6. Omettre pour voir les fragments.",
        "slash_example": "/buffer code:ABCDEF",
        "text_example": "{prefix}buffer ABCDEF",
        "prerequisites": "Un défi buffer actif.",
        "advice": "Lis attentivement les numéros assignés à chaque lettre, et non pas l'ordre d'apparition à l'écran.",
        "aliases": ["{prefix}b"],
        "linked_commands": ["event"],
    },
    "signal": {
        "name": "signal",
        "category": "events",
        "title": "📡 `/signal` — Détecter le signal",
        "description": "Analyse le flux d'ondes brouillé et isole la lettre qui apparaît le plus grand nombre de fois.",
        "slash_syntax": "/signal [letter:<lettre>]",
        "text_syntax": "{prefix}signal [lettre]",
        "parameters": "• `letter` : La lettre dominante détectée. Omettre pour afficher le signal.",
        "slash_example": "/signal letter:A",
        "text_example": "{prefix}signal A",
        "prerequisites": "Un défi signal actif.",
        "advice": "Tu peux répondre directement en cliquant sur les boutons interactifs sous le message du défi.",
        "aliases": ["{prefix}s"],
        "linked_commands": ["event"],
    },
    "packet": {
        "name": "packet",
        "category": "events",
        "title": "📦 `/packet` — Trouver le paquet perdu",
        "description": "Identifie quel paquet de données manque à l'appel dans la séquence transmise (de 1 à 10).",
        "slash_syntax": "/packet [guess:<1–10>]",
        "text_syntax": "{prefix}packet [numéro]",
        "parameters": "• `guess` : Le numéro du paquet manquant. Omettre pour voir la liste reçue.",
        "slash_example": "/packet guess:7",
        "text_example": "{prefix}packet 7",
        "prerequisites": "Un événement de perte de paquets actif.",
        "advice": "Repère rapidement le trou dans la série comprise entre 1 et 10.",
        "aliases": ["{prefix}pa"],
        "linked_commands": ["event"],
    },

    # ── Page 5 : Échanger et me classer ─────────────────────────
    "rep": {
        "name": "rep",
        "category": "trade",
        "title": "⭐ `/rep` — Donner de la réputation",
        "description": "Donne un point de réputation à un joueur pour saluer son aide ou son fair-play et booster sa production.",
        "slash_syntax": "/rep target:<@joueur>",
        "text_syntax": "{prefix}rep <@joueur>",
        "parameters": "• `target` : Le joueur destinataire.",
        "slash_example": "/rep target:@Alex",
        "text_example": "{prefix}rep @Alex",
        "prerequisites": "Avoir un réseau créé, respecter le cooldown quotidien et ne pas se cibler soi-même.",
        "advice": "Recevoir de la réputation confère un bonus d'efficacité permanent sur le rendement de tes mineurs !",
        "aliases": ["{prefix}reputation"],
        "linked_commands": ["top"],
    },
    "trade": {
        "name": "trade",
        "category": "trade",
        "title": "🤝 `/trade` — Proposer un échange",
        "description": "Ouvre une négociation sécurisée pour échanger des dollars et/ou du Rootium avec un autre joueur.",
        "slash_syntax": "/trade target:<@joueur> [offer:<ressources>] [request:<ressources>]",
        "text_syntax": "{prefix}trade <@joueur> <ressources signées>",
        "parameters": (
            "• En Slash :\n"
            "  - `target` : Le joueur partenaire.\n"
            "  - `offer` : Ce que tu donnes (ex: `50usd`, `0.001rtm` ou `50usd 0.001rtm`).\n"
            "  - `request` : Ce que tu demandes en retour (ex: `0.001rtm`).\n"
            "• En Texte :\n"
            "  - Utilise les signes : `-` pour ce que tu donnes et `+` pour ce que tu reçois !"
        ),
        "slash_example": "/trade target:@Alex offer:50usd request:0.001rtm",
        "text_example": "{prefix}trade @Alex -50usd +0.001rtm",
        "example_note": "Les montants s'écrivent sans signe dans les champs slash dédiés, mais AVEC `-` et `+` en texte.",
        "prerequisites": "Les deux joueurs doivent posséder un réseau et les ressources engagées dans leur solde.",
        "advice": "Vérifie soigneusement l'offre et la demande sur le récapitulatif interactif avant de cliquer sur 'Confirmer'.",
        "aliases": [],
        "linked_commands": ["attest"],
    },
    "attest": {
        "name": "attest",
        "category": "trade",
        "title": "📜 `/attest` — Attester un solde minimum",
        "description": "Génère une preuve cryptographique prouvant que ton solde atteint au moins une valeur donnée sans révéler ton montant réel.",
        "slash_syntax": "/attest currency:<USD|RTM> amount:<montant>",
        "text_syntax": "{prefix}attest <usd|rtm> <montant>",
        "parameters": (
            "• `currency` : La monnaie certifiée (`USD` ou `RTM`).\n"
            "• `amount` : Le seuil de solde que tu souhaites attester."
        ),
        "slash_example": "/attest currency:USD amount:100",
        "text_example": "{prefix}attest usd 100",
        "example_note": "Variante texte compacte acceptée : `{prefix}attest 100usd`.",
        "prerequisites": "Un réseau créé et un solde réel au moins égal au montant renseigné.",
        "advice": "Idéal pour rassurer un partenaire commercial sur ta solvabilité sans dévoiler ta fortune exacte.",
        "aliases": ["{prefix}certify", "{prefix}proof"],
        "linked_commands": ["trade"],
    },
    "top": {
        "name": "top",
        "category": "trade",
        "title": "🏆 `/top` — Consulter les classements",
        "description": "Affiche le tableau d'honneur des meilleurs hackers du réseau selon différentes catégories.",
        "slash_syntax": "/top [category:<reputation|usd|events|hashrate>]",
        "text_syntax": "{prefix}top [reputation|usd|events|hashrate|hs]",
        "parameters": (
            "• `category` : Critère de classement (`reputation` par défaut, `usd` pour la fortune, `events` pour les victoires, `hashrate` pour la puissance H/s)."
        ),
        "slash_example": "/top category:hashrate",
        "text_example": "{prefix}top hs",
        "prerequisites": "Aucun prérequis pour consulter.",
        "advice": "Tu peux facilement passer d'une catégorie à une autre grâce aux boutons situés sous le classement.",
        "aliases": ["{prefix}leaderboard"],
        "linked_commands": ["rep"],
    },

    # ── Page 6 : Langue et informations ─────────────────────────
    "lang": {
        "name": "lang",
        "category": "info",
        "title": "🌐 `/lang` — Choisir ma langue",
        "description": "Configure ta langue préférée pour toutes les réponses et notifications envoyées par Root.",
        "slash_syntax": "/lang [choice:<fr|en|reset>]",
        "text_syntax": "{prefix}lang [fr|en|reset]",
        "parameters": (
            "• `choice` : `fr` pour le français, `en` pour l'anglais, `reset` pour suivre la langue de ton client Discord. "
            "Sans argument, affiche ton réglage actuel."
        ),
        "slash_example": "/lang choice:fr",
        "text_example": "{prefix}lang fr",
        "prerequisites": "Aucun prérequis.",
        "advice": "Ta préférence est enregistrée sur ton compte : elle persiste même si tu changes de serveur Discord.",
        "aliases": ["{prefix}language"],
        "linked_commands": ["botinfo"],
    },
    "rmd": {
        "name": "rmd",
        "category": "info",
        "title": "⏰ `/rmd` — Minuteurs et rappels Root OS",
        "description": "Programme des rappels automatiques intelligents liés à tes activités en jeu (hourly, claim RAM, événements) ou configure des minuteurs libres avec un message personnalisé.",
        "slash_syntax": "/rmd <auto|timer|list|cancel|help>",
        "text_syntax": "{prefix}rmd [durée|cible|action] [options...]",
        "parameters": (
            "• `/rmd auto [target]` : activer un rappel de jeu (`all`, `hourly`, `claim`, `events`...).\n"
            "• `/rmd timer <duration> [message]` : minuteur libre de 10s à 30j (ex: `30m`, `2h`, `45s`).\n"
            "• `/rmd list` : afficher la liste de tous tes rappels actifs.\n"
            "• `/rmd cancel [reminder_id]` : annuler un rappel par ID ou tout supprimer (`all`).\n"
            "• `/rmd help` : afficher la documentation et les raccourcis."
        ),
        "slash_example": "/rmd auto target:all",
        "text_example": "{prefix}rmd 30m Récolter le contrat",
        "prerequisites": "Autoriser les messages privés du bot si tu souhaites être notifié par MP.",
        "advice": "Tape `/rmd auto` pour planifier instantanément tous tes rappels de jeu en un clic !",
        "aliases": ["{prefix}remind", "{prefix}reminder"],
        "linked_commands": ["hourly", "claim", "event"],
    },
    "ping": {
        "name": "ping",
        "category": "info",
        "title": "🏓 `/ping` — Tester la latence",
        "description": "Mesure le temps de latence de la passerelle Discord (Gateway) et la réactivité du bot.",
        "slash_syntax": "/ping",
        "text_syntax": "{prefix}ping",
        "parameters": "Aucun paramètre.",
        "slash_example": "/ping",
        "text_example": "{prefix}ping",
        "prerequisites": "Aucun prérequis.",
        "advice": "Utile pour vérifier si le réseau ou Discord subit des ralentissements.",
        "aliases": [],
        "linked_commands": ["botinfo"],
    },
    "botinfo": {
        "name": "botinfo",
        "category": "info",
        "title": "ℹ️ `/botinfo` — Informations sur Root",
        "description": "Affiche les statistiques générales de Root : temps de fonctionnement (uptime), nombre de serveurs, latence et liens officiels (invitation et serveur Discord).",
        "slash_syntax": "/botinfo",
        "text_syntax": "{prefix}botinfo",
        "parameters": "Aucun paramètre.",
        "slash_example": "/botinfo",
        "text_example": "{prefix}botinfo",
        "prerequisites": "Aucun prérequis.",
        "advice": "Permet d'avoir une vue d'ensemble sur la santé et la charge du système.",
        "aliases": [],
        "linked_commands": ["invite", "ping"],
    },
    "invite": {
        "name": "invite",
        "category": "info",
        "title": "🔗 `/invite` — Lien d'invitation",
        "description": "Génère le lien officiel pour inviter le bot Root avec les permissions recommandées sur ton serveur Discord.",
        "slash_syntax": "/invite",
        "text_syntax": "{prefix}invite",
        "parameters": "Aucun paramètre.",
        "slash_example": "/invite",
        "text_example": "{prefix}invite",
        "prerequisites": "Aucun prérequis.",
        "advice": "Partage ce lien avec tes amis ou administrateurs pour installer Root sur une nouvelle communauté.",
        "aliases": [],
        "linked_commands": ["botinfo"],
    },
    "maths": {
        "name": "maths",
        "category": "info",
        "title": "🧮 `/maths` — Calculatrice",
        "description": "Évalue de manière sécurisée une expression mathématique (opérations arithmétiques, fonctions, constantes).",
        "slash_syntax": "/maths expression:<calcul>",
        "text_syntax": "{prefix}maths <calcul>",
        "parameters": "• `expression` : Calcul à effectuer (ex: `2 + 2`, `sqrt(144)`, `2^8`).",
        "slash_example": "/maths expression:2 + 2 * 5",
        "text_example": "{prefix}maths sqrt(144)",
        "prerequisites": "Aucun prérequis.",
        "advice": "Supporte les opérateurs usuels (+, -, *, /, //, %, ^, **), constantes (pi, e, tau) et fonctions (sqrt, abs, round, sin, cos, log, factorial).",
        "aliases": ["{prefix}math", "{prefix}calc", "{prefix}calcul"],
        "linked_commands": [],
    },
    "macro": {
        "name": "macro",
        "category": "network",
        "title": "🤖 `/macro` — Automatisation de Macros",
        "description": "Enregistre et exécute des séquences automatisées de 1 à 5 commandes pour piloter ton réseau en un éclair.",
        "slash_syntax": "/macro [nom:<nom>] [display:<True|False>]\n/macro-create [nom:<nom>]\n/macro-delete nom:<nom>",
        "text_syntax": "{prefix}macro [nom] [d]\n{prefix}macro create [nom]\n{prefix}macro delete <nom>\n{prefix}macro list",
        "parameters": (
            "• `nom` : Nom de la macro à exécuter (1 à 32 caractères minuscules). Laisse vide pour ouvrir le guide d'aide.\n"
            "• `display` / `d` : **Option d'affichage détaillé** — Affiche les réponses individuelles de chaque commande comme si tu les avais tapées toi-même (par défaut : rapport de synthèse compact).\n"
            "• `create` : Lance l'assistant pas-à-pas interactif pour concevoir ta macro.\n"
            "• `delete` : Supprime définitivement la macro spécifiée.\n"
            "• `list` : Affiche tes macros enregistrées et le nombre d'étapes."
        ),
        "slash_example": "/macro nom:farm display:True",
        "text_example": "{prefix}macro farm d",
        "example_note": "Ajouter `d` à la fin de `{prefix}macro <nom>` affiche chaque commande en détail dans le salon.",
        "prerequisites": "Un réseau créé. Maximum 3 macros par joueur, 1 à 5 étapes par macro. Cooldown global de 15s et quota de 60 lancements par heure.",
        "advice": "Idéal pour combiner `/claim`, `/hourly` et `/buy ... all` en une routine. Les commandes en attente de délai (cooldowns) sont automatiquement ignorées sans bloquer la suite.",
        "aliases": ["{prefix}mac", "{prefix}macros"],
        "linked_commands": ["claim", "hourly", "buy", "upgrade", "network"],
    },
    "market": {
        "name": "market",
        "category": "network",
        "title": "📈 `/market` — Terminal de marché, achat & vente de RTM",
        "description": "Consulte le cours dynamique du Rootium, les graphiques en temps réel, et négocie tes devises (achat USD➔RTM, vente RTM➔USD avec 1% de frais).",
        "slash_syntax": "/market [period:24h|7d|30d]",
        "text_syntax": "{prefix}market [24h|7d|30d|buy|sell|chart|alerts|autosell]",
        "parameters": (
            "• `period` : Période temporelle affichée (24h, 7d ou 30d). Par défaut : 24h.\n"
            "• `buy <montant|all>` : Acheter du Rootium avec des dollars USD (frais 1%).\n"
            "• `sell <montant|all>` : Vendre du Rootium contre des dollars USD (frais 1%).\n"
            "• `chart` : Génère l'image PNG haute résolution du cours."
        ),
        "slash_example": "/market period:7d",
        "text_example": "{prefix}market buy 0.0005",
        "example_note": "Pour vendre tout ton RTM : `{prefix}market sell all`.",
        "prerequisites": "Aucun prérequis pour consulter. Réseau et fonds requis pour acheter/vendre.",
        "advice": "Le cours évolue toutes les 15 minutes. Négocie au meilleur moment et surveille les alertes automatiques.",
        "aliases": ["{prefix}mk", "{prefix}sell", "{prefix}cv"],
        "linked_commands": ["network", "buy", "upgrade"],
    },
}

COMMAND_ALIASES = {
    "mac": "macro",
    "macros": "macro",
    "n": "network",
    "c": "claim",
    "cl": "claim",
    "co": "contract",
    "hr": "hourly",
    "cv": "market",
    "sell": "market",
    "mk": "market",
    "cp": "compile",
    "hk": "hack",
    "events": "event",
    "e": "event",
    "h": "hash",
    "p": "pin",
    "d": "decode",
    "a": "anomaly",
    "b": "buffer",
    "s": "signal",
    "pa": "packet",
    "reputation": "rep",
    "certify": "attest",
    "proof": "attest",
    "leaderboard": "top",
    "language": "lang",
    "remind": "rmd",
    "reminder": "rmd",
    "math": "maths",
    "calc": "maths",
    "calculate": "maths",
    "calcul": "maths",
}

