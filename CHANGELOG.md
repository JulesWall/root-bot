# :rocket: Beta Update N°2

### :briefcase: Nouveau Système de Contrats (`/contract`)
Travaillez pour l'agence **Root CyberSec** et encaissez des récompenses garanties en USD :
* **3 durées de mission** : Courte (30 min), Moyenne (2 h) et Longue (6 h).
* **Système de fidélité** : Enchaînez les missions pour débloquer des contrats spéciaux avec **+50 % de prime USD** !
* **Zéro stress** : Aucune pénalité de retard, encaissez votre salaire quand vous le souhaitez (`/contract collect`).

---

### :trophy: Nouveau Classement : Top Hashrate (`/top`)
Mesurez votre infrastructure minière face aux meilleurs mineurs du réseau :
* **Classement de puissance brute** : Suivi en direct du hashrate total cumulé en **H/s** (avec conversion dynamique kH/s, MH/s, GH/s, TH/s).
* **Navigation interactive** : Accessible via `/top category:hashrate` (alias `/top hs`, `/top h/s`) et par le nouveau bouton d'onglet **:pick: H/s**.

---

### :bell: Nouveau Système de Rappels & Minuteurs (`/rmd`)
Ne manquez plus jamais un claim ou la saturation de votre matériel :

* **:zap: Rappels Intelligents de Jeu** :
> • `/rmd auto` ou `/rmd auto target:all` — Active tous les rappels possibles en un clic (hourly, claim, et l'ensemble des mini-jeux réseau en attente).
> • `/rmd auto target:hourly` — Alerte dès que la prime horaire est disponible.
> • `/rmd auto target:claim` — Alerte dès que votre mémoire vive (RAM) est saturée à 100 %.
> • `/rmd auto target:events` *(ou par jeu : `hash`, `pin`, `signal`...)* — Alerte au lancement du prochain mini-jeu réseau.

* **:stopwatch: Minuteurs Libres & Personnalisés** :
> • `/rmd timer duration:<durée> [message:<sujet>]` — Minuteur libre de 10s à 30 jours.
> *(Exemples : `/rmd timer duration:30m message:Pause café`, `/rmd timer duration:2h`, `/rmd timer duration:45s`)*

* **:clipboard: Gestion Simple & Directe** :
> • `/rmd list` — Affiche la liste de vos rappels programmés avec compte à rebours dynamique.
> • `/rmd cancel [reminder_id]` — Annule un rappel par son ID ou supprime tout d'un coup.
> • `/rmd help` — Affiche l'aide et la documentation complète.

---

### :jigsaw: Refonte du Hash Challenge (`/hash`)
Fini le spam et place à la stratégie communautaire équitable pour tous (PC et mobile) :
* **Anti-Spam & Cadence Équitable** : Chaque joueur dispose désormais d'un délai de **8 minutes** entre deux propositions d'un même hash.
* **Plage de Recherche Resserrée** : Zone réduite à **1 000** d'écart seulement pour un affinement collectif rapide et efficace.
* **Réapparition Accélérée** : L'événement revient beaucoup plus vite après chaque victoire (3 à 8 min en journée, 5 à 15 min la nuit).
* **Récompenses Boostées** : Gains en dollars augmentés 
* **Consultation Gratuite** : Vérifier les bornes actuelles et l'avancement (`/hash` ou `{prefix}hash` sans argument) reste toujours gratuit et sans délai d'attente.

---

### :incoming_envelope: Support des Messages Privés (MP)
Jouez et gérez votre infrastructure en toute discrétion directement en message privé avec le bot :
* **Slash Commands en MP** : Accédez à l'ensemble de votre réseau (`/network`, `/buy`, `/upgrade`, `/claim`, `/contract`, `/hourly`, `/rmd`...) ainsi qu'aux commandes PvP (`/scan`, `/hack`) et utilitaires directement en MP.
* **Confidentialité Totale** : Vos stratégies de hack, vos scans et votre progression financière restent privés sans encombrer les salons de discussion des serveurs.
* **Exclusions Serveur** : Les commandes textuelles à préfixe sont désactivées en MP. Les commandes spécifiques aux serveurs (`/prefix`) ainsi que les échanges (`/trade`) restent réservées aux serveurs Discord.

---

### :tools: Correctifs & Améliorations (QoL)
* **Intégration dans l'aide (`/help`)** : Ajout des fiches détaillées, exemples et options pour `/hourly`, `/contract` et `/rmd` dans leurs rubriques respectives (*Développer mon réseau* et *Langue et informations*) ainsi que dans l'index complet de toutes les commandes (27 commandes répertoriées).
* **Optimisation des défis réseau** : Plafonnement et déduplication des messages de mini-jeux actifs avec actualisation simultanée lors des victoires pour prévenir tout risque de saturation et de ralentissement Discord.
* **Horodatages Discord** : Correction du décalage de fuseau horaire et affichage dynamique des comptes à rebours (`dans X min`).
* **Format des durées** : Correction d'erreurs d'affichage et support enrichi des formats de durée multilingues (`30s`, `15min`, `2h`, `1 jour`).
* **Parité bilingue** : Traduction et synchronisation FR/EN intégrale de toutes les commandes, options slash et messages.