# ROOT OS - Specification des nouveaux embeds

## 1. Portee et references

Document de reference pour un agent IA qui developpe les interfaces Discord du bot.
Objectif : donner la sensation de consulter son ordinateur et son reseau, tout en
restant comprehensible sans connaissance informatique. Priorite : immersion,
lisibilite, puis decoration.

- Reference executable : `demo_embeds.py` (`DemoView`, `select_emojis`, `send_demo`).
- Tests hors ligne : `tests/test_demo_embeds.py`.
- Banniere : `design/root-os-banner.png`.
- Emojis statiques : `design/root-os-emojis/png/`.
- Emojis animes : `design/root-os-emojis-animes/root_*.gif`.
- Dependances du projet : `requirements.txt` ; utiliser Pycord, pas discord.py.

Ce document definit une presentation, PAS de nouvelles regles economiques ou PVP.
Ne pas modifier le gameplay, les couts, les protections ou la base de donnees pour
appliquer ce style. Les fonctionnalites de la demo ne sont pas toutes des
fonctionnalites existantes du jeu. Ne pas les deployer implicitement.

## 2. Implementation obligatoire

Le mot "embed" designe ici un panneau en **Discord Components V2**, et non un
`discord.Embed` classique. Utiliser `discord.ui.DesignerView` avec `Container`,
`MediaGallery`, `TextDisplay`, `Separator`, `ActionRow` et `Button`.

- Envoyer le panneau via `view=...`. Ne pas joindre `content=` ou `embed(s)=`
  au meme message V2 ; placer les textes dans des `TextDisplay`.
- Construire un seul `Container` principal ; ne pas imbriquer des panneaux.
- Laisser Discord gerer la typographie, la largeur et le fond. Pas de HTML/CSS,
  fausses colonnes alignees avec des espaces ou promesse de rendu pixel-perfect.
- Ne pas rasteriser les statistiques dans une image : elles doivent rester du
  texte lisible, selectionnable et actualisable.
- Budget conservateur du projet : au plus 40 composants, 4 000 caracteres de
  texte cumules et 5 boutons par `ActionRow`. Verifier le payload serialise.

## 3. Structure visuelle

Respecter cet ordre sur les ecrans principaux et leurs sous-vues :

```text
DesignerView
  Container [couleur d'etat]
    MediaGallery [banniere du poste, si disponible]
    TextDisplay [## {terminal} ROOT OS / {pseudo}]
                [-# {machine} / Reseau personnel / {etat}]
    Separator
    TextDisplay [titre de la vue et contexte]
    TextDisplay [statistiques ou informations utiles]
    Separator [seulement si un second groupe existe]
    TextDisplay [activite, consequence ou dernier evenement]
    ActionRow [actions de la vue]
  ActionRow [Poste | Anomalie | Operation]
  TextDisplay [mention de simulation, uniquement dans la demo]
```

- Banniere en premier, pas en pied de panneau. Conserver le format panoramique.
- Joindre l'image locale et la referencer par `attachment://root-os-banner.png`.
  Une illustration fournie explicitement remplace la banniere par defaut.
- Garder l'image et sa piece jointe lors des changements de vue. Si elle manque,
  afficher un panneau textuel fonctionnel sans URL cassee.
- Titre de session en `##`, titre de sous-vue en `###`, contexte secondaire en
  `-#`. Pas de grands titres repetes pour chaque statistique.
- Format des donnees : `{emoji} **Libelle** · valeur unite`, une donnee par ligne.
- Utiliser des lignes vides entre groupes, pas entre toutes les statistiques.
- Un emoji semantique par ligne ou bouton suffit. Pas de decoration repetee.
- Les couleurs ne remplacent jamais un libelle d'etat.

Palette : turquoise `#54E2D1` pour l'accent normal, ambre `#FFC15A` pour une
anomalie non resolue, blanc `#EEF1F5` pour les pictogrammes neutres. Ne pas chercher
a forcer la couleur du texte Discord. Le vert natif des boutons est reserve a
la recolte ; les controles secondaires utilisent le style `secondary`.

## 4. Registre des emojis

Les noms ci-dessous sont les noms EXACTS des emojis importes dans le serveur.
Ne pas en inventer de nouveaux ni remplacer le pack par des symboles generiques
quand il est disponible.

- `root_terminal` : identite ROOT OS, poste, session. Anime : curseur clignotant.
- `root_firewall` : niveau de firewall, protection, isolation d'une connexion.
- `root_ferme` : mineurs, ferme de minage, nombre de machines.
- `root_puissance` : puissance de calcul, valeur en H/s.
- `root_production` : debit de production, comparaison attendu/recu.
- `root_memoire` : reserve locale et capacite avant recolte.
- `root_temps` : duree, estimation, compilation en cours.
- `root_recolter` : recolte, transfert, montant recupere. Anime : fleche descendante.
- `root_materiel` : acces a la vue materiel.
- `root_logiciels` : bibliotheque et etat des logiciels.
- `root_operations` : navigation et fiche d'operation.
- `root_journal` : evenements et historique horodate.
- `root_alerte` : anomalie ou intrusion non resolue. Anime : triangle pulsant.
- `root_scan` : diagnostic, recherche de la cause. Anime : balayage dans la loupe.
- `root_connexions` : reseau, liaisons actives, cible distante.
- `root_retour` : revenir a la vue parente. Anime : fleche vers la gauche.
- `root_bilan` : synthese des resultats d'une operation.

### Resolution et utilisation

1. Recuperer les emojis du serveur concerne, pas ceux d'un serveur arbitraire.
2. Utiliser le cache ; le rafraichir via `guild.fetch_emojis()` a l'ouverture si
   necessaire. La demo rafraichit a chaque commande. Ne pas refaire un appel HTTP
   a chaque bouton. En cas d'echec HTTP, revenir au cache.
3. Filtrer les emojis non utilisables par le bot avec `is_usable()`.
4. Pour un meme nom, privilegier la version animee utilisable, puis la statique.
   A type identique, la demo choisit l'ID le plus eleve pour rester deterministe.
5. Dans un `TextDisplay`, inserer `str(emoji)` : Discord obtient
   `<:nom:ID>` ou `<a:nom:ID>` pour un anime. Ne jamais inventer les IDs.
6. Dans un bouton, fournir l'objet emoji via `emoji=...`, pas dans `label`.
7. Si le nom manque, reprendre le repli Unicode de `FALLBACKS` dans la demo.
   Garder le libelle lisible et signaler le nom manquant dans les logs techniques.

Ne pas placer les emojis personnalises dans des blocs de code ou du texte entre
backticks : ils ne s'y affichent pas comme des emojis. Un fichier GIF local ne
remplace pas un emoji importe. L'animation est geree par Discord ; ne pas editer
periodiquement le message pour l'animer. Le sens doit rester clair si le client
du joueur desactive les animations.

## 5. Contenu des vues

### Poste

Afficher l'identite du poste, le firewall, puis le trajet simplifie du reseau
(`ATLAS → Ferme T3 → Memoire locale` dans la demo). Presentent ensuite, dans cet
ordre : ferme, puissance, production recue et memoire utilisee/capacite.
Terminer par le travail logiciel en cours et un evenement court.

Actions : `Recolter` (`root_recolter`, success), `Materiel` (`root_materiel`),
`Logiciels` (`root_logiciels`). Apres recolte reussie, afficher le montant
effectivement transfere, actualiser la memoire et desactiver l'action tant qu'il
n'y a rien a recolter. Ne pas confirmer avant la reussite de l'operation metier.

### Anomalie

Afficher le systeme concerne, la production attendue, la production recue et
l'ecart en pourcentage. La couleur ambre reste presente tant que le probleme
affiche n'est pas resolu. Ne pas reveler une cause avant qu'elle soit connue.

La demo illustre trois etats :

1. Rendement inhabituel : liaison non identifiee ; bouton `Diagnostiquer` / `root_scan`.
2. Intrusion identifiee : nature et consequence connues ; action d'isolation.
3. Connexion isolee : debit retabli ; action desactivee et trace conservee.

Un diagnostic n'est pas une reparation. Isoler une connexion n'installe pas un
patch : ne pas afficher "systeme securise" tant que la faille reste ouverte.
La vue `Connexions` utilise `root_connexions` et reprend exactement le meme etat.
Cette sequence illustre une presentation ; ne pas ajouter ces mecaniques au jeu
sans demande explicite.

### Operation

Afficher le nom du logiciel, la cible, l'etat de la liaison, la periode active,
la duree effective, le montant recupere et la cause de fin. Bouton `Journal` /
`root_journal` pour la chronologie. Distinguer une operation sur une cible
distante d'une intrusion subie par le joueur.

### Sous-vues

- Materiel : station, firewall, mineurs, puissance et capacite memoire.
- Logiciels : logiciels disponibles, etats et travail en cours.
- Connexions : liaisons locales, pool et liaisons distantes connues.
- Journal : heures courtes en backticks et evenements factuels, sans logs bruts.
- Chaque sous-vue propose `Retour` / `root_retour` vers sa vue parente.

Ne pas ajouter d'emplacements ou de plafond de mineurs pour faire tenir l'UI.
Regrouper les mineurs par tier, puis paginer le detail si necessaire.

## 6. Interactions et visibilite

- Les panneaux de ce parcours sont publics : `ephemeral=False`, y compris au
  `defer`. Dans la demo, les messages de validation sont egalement publics.
- Editer le message existant lors d'une navigation ou d'une action. Ne pas
  envoyer un nouveau panneau a chaque clic.
- Navigation : `Poste` / `root_terminal`, `Anomalie` / `root_alerte`,
  `Operation` / `root_operations`. Desactiver la page active ; depuis une
  sous-vue, son onglet parent redevient cliquable.
- Utiliser des `custom_id` stables et distincts par action. Lier le callback a
  l'action identifiee, pas a la page courante au moment de son execution.
- Accuser reception rapidement ; differer avant une requete potentiellement
  lente. Revalider les droits et l'etat metier au moment du clic.
- La demo autorise tout le monde a manipuler son etat fictif partage. Ce n'est
  PAS une autorisation de recolter ou d'agir sur le compte d'un autre joueur.
  En production, conserver les controles d'identite et de propriete existants.
- Proteger les actions contre les doubles clics et les courses concurrentes.
  Le verrou local de la demo ne remplace pas l'atomicite metier en production.
- Apres 600 secondes d'inactivite, la demo desactive ses boutons et laisse le
  panneau visible. Prevoir aussi la reouverture apres expiration ou redemarrage.
- Desactiver les mentions automatiques et echapper le Markdown des noms saisis
  par les joueurs. Ne jamais exposer de secret, de token ou d'erreur technique.

## 7. Texte et donnees

Texte affiche en francais naturel, avec accents. Phrases courtes et concretes :
"Connexion fermee", "Compilation en cours", "Memoire liberee". Pas de faux code,
de jargon reseau inutile, de texte marketing ou d'explication de l'interface.

- Afficher les unites : H/s, RTM/h, RTM, min. Respecter la precision metier ;
  utiliser la virgule decimale et un separateur de milliers lisible.
- Toutes les vues d'une session doivent refleter le meme etat. Apres une action,
  recalculer les valeurs concernees au lieu de conserver un texte contradictoire.
- Une valeur inconnue s'affiche comme indisponible, pas comme zero.
- Un etat vide indique ce qui manque ; un echec donne une raison utile sans
  trace technique. Ne jamais annoncer une reussite sur un simple clic.
- `Nox`, `ATLAS`, `Echo`, `K-4821`, les montants et les `18 min` sont des exemples
  de demo. Les remplacer par des donnees reelles uniquement lors de l'integration.
- Ne pas simuler un compte a rebours avec une duree fixe en production.
- Conserver "Simulation publique / Donnees fictives / Aucun effet sur le jeu"
  uniquement pour la demo ; ne pas l'afficher sur une vraie interface de jeu.

## 8. Verification avant livraison

- Tester tous les ecrans, sous-vues, retours, etats vides, erreurs et expirations.
- Verifier le payload V2, les limites de composants et l'unicite des boutons.
- Tester les emojis animes, statiques, absents et interdits au bot.
- Verifier que les messages ne sont pas ephemeres et que les images survivent
  aux editions du message.
- Tester doubles clics, callbacks anciens et controles de propriete.
- Pour la demo : `.venv\Scripts\python.exe -m unittest discover -s tests -p test_demo_embeds.py -v`.
- Verifier le rendu dans Discord sur ordinateur et mobile : aucune simulation
  locale ne prouve seule le rendu reel. Indiquer si cette verification manque.
- Ne pas lancer le bot ni publier un message pour une verification sans accord.
- Consigner la modification dans `changelog.md` ; ne pas recopier de secrets
  depuis la configuration de la demo.
