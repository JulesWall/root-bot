# 🚀 Changelog — Root OS : Mise à Jour Majeure 3.0

## 🎨 Intégration des Emojis `root_verrou` & `root_usd` et Polissage Visuel

- **Nouvel emoji `root_verrou` (🔒)** :
  - Intégré dans le log public de dégâts critiques.
  - Affiché dans les alertes privées et les messages de refus en cas de tentative de `/hack` ou `/scan` sous verrouillage critique.
  - Affiché dans `/network` (Poste de commande et Opérations) pour indiquer en temps réel la durée de protection restante.
- **Nouvel emoji `root_usd` (💵)** :
  - Intégré dans les offres et gains de contrats (`/contract`).
  - Intégré pour le solde USD dans `/network` et les récapitulatifs financiers de manière sobre et épurée (sans répétition excessive sur chaque ligne).
- **Correction du double titre dans les rapports PvP (`/hack`)** :
  - Suppression des titres d'en-tête redondants dans le corps du texte.
  - Titres d'embeds précis et contextualisés : *Rapport d'opération — Accès obtenu/refusé* et *Alerte intrusion — Brèche confirmée / Intrusion repoussée*.
- **Protection des blocs de code et balises inline** :
  - Le convertisseur d'emojis préserve désormais strictement le texte entre accents graves (`` `...` `` et ``` ```) afin d'éviter l'affichage de codes d'emojis bruts non interprétés par Discord.

Bienvenue dans l'**Update 3 de Root OS** ! 🎉

Merci à toutes et à tous pour votre fidélité, votre énergie et vos retours précieux depuis le lancement. Cette mise à jour est un cap majeur pour toute la communauté : elle transforme en profondeur votre expérience de jeu, enrichit l'univers cyberpunk du bot et vous offre un poste de commande plus vivant, plus beau et plus intuitif que jamais. 

Installez-vous confortablement, préparez vos rigs, voici tout ce qui change pour vous !

## 🛡️ Procédure de Sauvegarde d'Urgence PvP (Dégâts Critiques)

Afin d'éviter qu'une intrusion brutale ne réduise à néant vos investissements matériels, Root OS introduit la **Procédure de Sauvegarde d'Urgence** lors des combats PvP !

### ⚡ Ce qui change pour vous :
- **Plafonnement strict des pertes de modules (60 %)** :
  - Si une cyberattaque ennemie réussie devait détruire ou transférer une part excessive de vos modules d'attaque ou de minage (perte strictement supérieure à 60 % de vos modules dans la catégorie visée), la procédure de sécurité se déclenche automatiquement.
  - La perte infligée est alors strictement limitée au plafond configuré (`floor(total × 60 / 100)`).
  - Si vous ne possédez qu'un seul module dans cette catégorie, l'arrondi protège l'intégralité de votre équipement : aucun module n'est perdu !
- **Verrouillage de sauvegarde temporaire (48h)** :
  - Lors du déclenchement, votre profil réseau entre sous protocole d'urgence pendant 48 heures.
  - Pendant cette période de reconstruction, votre profil est sanctuarisé : **impossible de subir ou de lancer des attaques (`/hack`)** et **impossible de lancer des scans (`/scan`)**.
  - Le verrouillage s'applique à votre profil de jeu global sur l'ensemble des serveurs Discord.
- **Activités économiques et défensives préservées** :
  - Même sous verrouillage, vous conservez le plein accès à toutes vos commandes régulières : récolter votre Rootium (`/claim`), récupérer vos primes (`/hourly`), compiler des points d'attaque (`/compile`), acheter du matériel (`/buy`), améliorer votre infrastructure (`/upgrade`) et accomplir des contrats (`/contract`).
- **Journal public & notifications dédiées** :
  - Un événement public dédié (teinté de violet électrique) annonce la mise sous sauvegarde de la victime et la durée du verrouillage, sans divulguer de détails sensibles (ni attaquant, ni puissance ATK, ni Secret ID).
  - Les rapports d'opération privés en DM détaillent avec précision les modules préservés et l'horodatage exact d'expiration de la protection.

---

## 🤖 Nouveauté : Système de Macros Joueur (`/macro` & `!macro`)

Vous rêviez d'enchaîner vos tâches de routine en une seule action ? Le système de **macros séquentielles** débarque dans Root OS !

### ⚡ Ce qui change pour vous :
- **Jusqu'à 3 macros personnalisées par joueur** : Programmez vos routines favorites (ex: `matin`, `farm`, `defense`).
- **1 à 5 étapes séquentielles par macro** : Enchaînez vos actions préférées (`claim`, `hourly`, `buy`, `upgrade`, `convert`, `compile`, `contract`, `scan`, `hack`, `reputation`, `network`, etc.).
- **Assistant Interactif & Création Rapide** :
  - **Assistant pas-à-pas fiabilisé (`/macro-create` ou `!macro create`)** : résolution complète des blocages lors de la saisie du nom ou des paramètres d'étape. Ajout d'un bouton pour annuler ou retirer la dernière étape programmée (`↩️`).
  - **Création rapide directe (`!macro create <nom> <cmd1> [cmd2]...`)** : créez instantanément une macro en une seule ligne sans passer par les menus déroulants (ex: `!macro create farm claim hourly upgrade`).
- **Commandes avec devis (`/buy`)** : confirmation directe simplifiée (`confirm: true/oui/confirm`) et prise en charge du mot-clé `all` pour acheter le maximum de modules abordables d'un coup.
- **Rappels intelligents (`/rmd` & `!rmd`) dans les macros** : intégration naturelle et simplifiée de `rmd` dans vos routines. Un seul paramètre intuitif (par défaut `all`, ou au choix `hourly`, `claim`, `events`, `list`, `cancel`). Plus besoin d'action technique complexe : tapez simplement `rmd:all`, `rmd:hourly` ou sélectionnez directement votre cible dans l'assistant !
- **Exécution Directe & Sécurisée** :
  - Lancez votre routine avec `/macro nom:<nom>` (avec autocomplétion intelligente de vos macros) ou via le préfixe `!macro <nom>`.
  - **Mode Verbeux / Display (`!macro <nom> d` ou `/macro display:True`)** : recevez les messages complets et interactifs de chaque commande comme si vous les aviez tapées vous-même dans le salon ! Une astuce claire vous le rappelle automatiquement à chaque lancement.
  - **Panneau d'aide intégré (`!macro`, `!macro help`, `/help macro`)** : taper `!macro` seul ou `!macro help` affiche immédiatement un guide complet illustré ainsi que la liste de vos macros en cours. La fiche `/help macro` rejoint officiellement le manuel public de Root OS.
  - **Rapport d'exécution compact** : par défaut, un rapport synthétique élégant avec jauge de progression unifiée (`■■■□□`) résume l'exécution en un seul message propre.
  - **Achat maximal (`buy ... all`)** : achetez en macro le maximum de modules abordables en une seule étape (`buy mining 1 all` ou `buy mining all`).
  - **Gestion intelligente des délais & cooldowns** : Si une commande est en attente de délai (ex: récompense `/hourly` ou récolte `/claim` pas encore disponible, contrat ou amélioration en cours), l'étape est automatiquement ignorée (`⏳ Étape ignorée`) sans interrompre votre routine.
  - **Exécution continue sans blocage** : même si une commande échoue (fonds insuffisants, cible invalide, etc.), elle ne bloque plus jamais les étapes suivantes. Le bot tente et mène à bien l'ensemble de votre routine programmée.
  - **Traçabilité complète (Logs & Blockchain)** : chaque commande exécutée par une macro (récoltes `/claim`, primes `/hourly`, ventes `/convert`, achats offensifs en RTM, etc.) est rigoureusement consignée dans le salon `#blockchain` et les journaux de modération comme une commande standard.
- **Cadence & Fair-Play** : Cooldown global de sécurité de 15 secondes et quota de 60 lancements par heure pour préserver la stabilité du réseau.

---

## 🏢 Adieu le « Firewall », place aux véritables Infrastructures !

Le terme générique de **« Firewall » tire sa révérence** pour laisser place à un système bien plus immersif et représentatif de votre ascension : les **Infrastructures de contrôle**.

Désormais, lorsque vous améliorez votre réseau avec `/upgrade`, vous ne faites plus simplement monter un niveau abstrait : vous bâtissez et faites grandir votre propre QG informatique physique, du matériel improvisé jusqu'à la forteresse technologique industrielle !

### 🛠️ Les 6 Paliers d'Infrastructure :
- **Niveau 0 — Smartphone bricolé** : Vos tout premiers pas dans l'ombre, avec les moyens du bord.
- **Niveau 1 — PC assemblé** : Votre première véritable tour dédiée au minage et au hacking.
- **Niveau 2 — Station de travail** : Un poste multitâche musclé pour gérer plusieurs baies de modules.
- **Niveau 3 — Serveur dédié** : Une machine professionnelle tournant 24h/24 avec une protection réseau renforcée.
- **Niveau 4 — Salle des serveurs** : Une installation industrielle climatisée capable d'encaisser les assauts lourds.
- **Niveau 5 — Datacenter** : Le sommet absolu du réseau Root OS, une puissance herculéenne et une forteresse imprenable.

### 🛡️ Ce que votre Infrastructure débloque et améliore :
- **Défense Réseau native** : Votre infrastructure vous confère une réserve de base de points de défense (`DEF`), complétée par vos baies défensives.
- **Accès aux Tiers de modules** : Plus votre infrastructure évolue, plus vous débloquez l'accès aux modules de rang supérieur dans la boutique (de T1 jusqu'à T5).
- **Multiplicateurs d'infrastructure renforcés** : Vos primes horaires (`/hourly`), vos contrats réseau et vos gains d'événements profitent de multiplicateurs massifs à chaque niveau : **Niveau 0 = ×1**, **Niveau 1 = ×1.75**, **Niveau 2 = ×3**, **Niveau 3 = ×5.25**, **Niveau 4 = ×9**, **Niveau 5 = ×15** !
- **Illustration panoramique exclusive** : Chaque palier possède sa propre scène en pixel art générée sur mesure, trônant au sommet de votre poste de commande !

---

## 🖥️ Le Nouveau Poste de Commande V2 (`/network`)

L'affichage central de votre réseau a été entièrement repensé autour des composants interactifs de Discord pour devenir votre véritable cockpit de jeu :

- **4 Onglets Dédiés et Complets** :
  - **Accueil** : Vue d'ensemble immédiate, affichage de votre **Secret ID** protégé directement sous l'en-tête du réseau, statistiques clés, état de l'infrastructure et progression vers le palier suivant.
  - **Ferme** : Débits de minage en temps réel, jauge visuelle de mémoire vive, répartition des mineurs par tier et état de l'automatisation.
  - **Matériel** : Inventaire complet et limpide de vos baies (Minage, Attaque, Défense) réparties par palier, avec raccourcis d'achat.
  - **Opérations** : Stock d'outils offensifs, état des compilations d'exploits, scans actifs, attaques en cours et droits de représailles.
- **Illustration Panoramique Intégrée** : La scène pixel-art de votre infrastructure s'affiche en grand au sommet de chaque écran.
- **Boutons d'Actions Rapides** : Basculez entre les onglets en un clic et déclenchez votre **Récolte** (`Claim`) directement depuis les boutons intégrés sans avoir à retaper de commande !

---

## 🎨 Graphismes, Identité Visuelle & Emojis Officiels Root OS

- **17 Emojis Animés et Statiques Exclusifs** : Remplacement complet des emojis standards de Discord par notre propre collection graphique (terminaux animés, jauges de mémoire, radars de scan, alertes système, icônes matérielles, etc.).
- **Éradication des Embeds Encombrants** : Les confirmations rapides, les erreurs de saisie et les récoltes s'affichent maintenant en messages directs, aérés et élégants. Moins de pollution visuelle, plus de lisibilité !
- **Signature Cyberpunk Unifiée** : Tous les panneaux et devis adoptent la charte graphique officielle de Root OS : Turquoise cyber (`#54E2D1`), Ambre d'alerte (`#FFC15A`) et Rouge d'intrusion (`#F06A6A`).

---

## ⏱️ Horodatage Dynamique & Minuteurs Universels

- **Double Affichage Infaillible** : Fini les comptes à rebours figés par les limites Discord ! Tous les minuteurs du jeu combinent désormais le timestamp dynamique et la durée textuelle explicite : `<t:{timestamp}:R> ({durée_restante})`.
- **Zéro Décalage Horaire** : Tous les calculs temporels (`/hourly`, `/claim`, mini-jeux, compilations et scans) sont calibrés sur l'UTC universel, éliminant les bugs de décalage horaire. Vos délais futurs indiquent toujours avec exactitude le temps qu'il vous reste à patienter.

---

## 🛡️ Modération, Sécurité & Équité de Jeu

- **Purge Glissante en 24h** : Les données d'audit et d'historique de modération sont désormais gérées sur une fenêtre glissante stricte de 24 heures, garantissant une surveillance en temps réel, nette et respectueuse des ressources.
- **Outils d'Audit OP Modernisés** : Les rapports et commandes de contrôle (`!claimaudit`, `!hourlyaudit`, `!eventaudit`) fournissent aux équipes de modération des analyses ultra-précises sur la cadence des 24 dernières heures.

## ⚙️ Équilibrage de la Compilation d'Exploits (`/compile`)

Les méthodes de génération de points d'attaque (`ATK`) ont été réajustées pour mieux valoriser vos choix stratégiques :

- **Méthode Non-Qualifiée (`unskilled`)** : Coût réduit à **`0.00009 RTM / ATK`** avec un multiplicateur de durée ajusté à **`90.0`** (idéal pour économiser votre Rootium sur des sessions de compilation modérées).
- **Méthode Qualifiée (`skilled`)** : Vitesse optimisée avec un multiplicateur de durée fixé à **`25.0`** pour un coût de **`0.0005 RTM / ATK`** (le choix rapide pour les attaques éclair).
- **Méthode IA (`ai`)** : Coût ultra-économique à seulement **`0.000007 RTM / ATK`** (`7e-06 RTM`) pour un multiplicateur de durée étendu à **`180.0`** (parfait pour lancer de très grosses productions de fond en arrière-plan à coût quasi nul en Rootium).

## 💼 Marché des Missions & Embed Cybernétique Épuré (`/contract`)

Le système de missions garanties en USD fait peau neuve avec une refonte graphique complète façon tableau d'affichage de cyber-agence :

- **Mise en Forme Épurée dans l'Embed** : Les offres sont désormais présentées sous forme de cartes d'agence aérées avec badge numéroté (`** 01 ** Audit de sécurité...`), entreprise commanditaire, durée et rémunération mise en valeur d'un coup d'œil.
- **Boutons Ultra-Compacts sur une Seule Rangée** : Remplacement des longs boutons encombrants par une rangée compacte de boutons numérotés épurés (`[ 01 ]`, `[ 02 ]`, `[ 03 ]`, `[ 04 ]`) et du bouton d'actualisation (`[ 🔄 Actualiser ]`), s'intégrant parfaitement sous l'embed sans occuper d'espace inutile.
- **Jauge de Progression Universelle** : Remplacement des glyphes carrés par une jauge de fidélité Unicode haute lisibilité (`■■■□□ 3/5`).
- **4 Contrats Dynamiques & Entreprises Variées** : Tirage de 4 missions sans doublon parmi les grandes corporations du jeu (*Novacore Systems, Asterion Bank, Helix Medical, etc.*) avec durées et rémunérations ajustées à vos multiplicateurs d'infrastructure.
- **Fiabilité & Fluidité Absolue** : Intégration standardisée dans les embeds Discord pour un affichage instantané et infaillible sur tous les supports (PC, Mac, mobile).

---

## 🤝 Échanges Réseau & Commerce (`/trade`)

- **Message de Confirmation Public dans le Salon** : La validation d'un échange ne fait plus disparaître le message d'origine dans le salon. Le message est désormais mis à jour avec un embed officiel de succès (`🤝 Échange validé avec succès`) attestant publiquement de la transaction entre les deux joueurs, tandis que le récapitulatif détaillé des montants transférés continue d'être envoyé en MP privé à chacun.
- **Identité Visuelle de Négociation** : L'embed de proposition initiale d'échange adopte la teinte Ambre (`#FFC15A`) de négociation en attente, avant de basculer sur le Turquoise de succès (`#54E2D1`) une fois conclu !

---

## 🎨 Harmonisation Visuelle & Finitions

- **Logs Publics Harmonisés par Rôle** :
  - **Événements & Mini-jeux résolus** : Tous les mini-jeux (Hash, PIN, Decode, Anomaly, Buffer, Signal, Packet) partagent désormais la même couleur officielle Turquoise cyber (`#54E2D1`) pour une lisibilité parfaite du flux.
  - **Alertes d'Attaques PvP** : Les alertes d'offensive s'affichent distinctement en Rouge d'intrusion (`#F06A6A`).
  - **Cyber-renseignement & Scans** : Les fuites de Secret ID et détections de scan s'affichent en Ambre de surveillance (`#FFC15A`).
- **Poste de Commande `/network`** : Ajout de l'icône billet `💵` sur la ligne du solde USD dans le portefeuille de l'Accueil pour une identification instantanée de vos devises.
- **Vocabulaire d'Infrastructure Uniformisé** : Remplacement des derniers intitulés résiduels de « Firewall Upgrade » par « Infrastructure Upgrade » dans toutes les langues du jeu.

---

Merci encore à toute la communauté pour vos retours et vos parties endiablées. Bonne exploration de la version 3.0 et que vos débits de Rootium soient maximaux ! ⚡
