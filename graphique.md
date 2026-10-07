# Charte graphique ROOT OS

Référence courte pour toute interface du bot visible par les joueurs. Pour les règles détaillées de la refonte de `/network`, consulter `design/GRAPHIC_UPDATE_PLAN.md`. Pour les fichiers d’emojis déjà dessinés, consulter `design/root-os-emojis/` et `design/root-os-emojis-animes/`.

## Identité

ROOT OS est un poste de contrôle informatique tangible, sobre et chaleureux. Le style doit rester lisible dans Discord sur ordinateur comme sur mobile : titres courts, hiérarchie claire, chiffres accompagnés de leurs unités, peu de décorations et un emoji sémantique par bloc ou action. Employer des termes concrets du jeu — réseau, ferme, matériel, opérations, mémoire, compilation — sans laisser le jargon remplacer l’explication.

## Palette

| Couleur | Code | Usage |
| --- | --- | --- |
| Turquoise | `#54E2D1` | État normal, consultation, devis, progression et réussite. |
| Ambre | `#FFC15A` | Attention, délai, expiration, mémoire pleine ou action indisponible. |
| Rouge doux | `#F06A6A` | Échec bloquant et conséquence critique. |
| Blanc cassé | `#EEF1F5` | Icônes d’action, éléments neutres et pictogrammes. |
| Violet électrique | `#B66DFF` | Accent dédié au log public de dégâts critiques/protection, pour le distinguer nettement des logs d’événements, d’attaque et de scan. |

Les couleurs d’interface et leurs états sont centralisés dans `utils/root_theme.py`. Le violet est une extension dédiée définie dans le plan des dégâts critiques ; lors de l’implémentation, l’ajouter comme constante distincte et ne pas le disperser dans les commandes. La couleur complète le libellé d’état, elle ne le remplace jamais.

## Mise en page et rédaction

- Présenter d’abord le résultat ou l’état, puis les données nécessaires et l’action suivante.
- Garder les informations importantes dans des lignes courtes et verticales ; limiter les colonnes, particulièrement pour l’affichage mobile.
- Employer des unités et noms cohérents (`USD`, `RTM`, `H/s`, `bits/s`, `ATK`, `DEF`) et les heures Discord relatives/absolues pour les échéances.
- Utiliser le footer `ROOT OS · Rubrique`, sans fausse promesse de sécurité ni identifiant technique inutile.
- Réserver le rouge aux cas réellement bloquants. Une réussite reste explicitement écrite même si l’embed est turquoise.
- Les messages publics ne révèlent que les informations déjà destinées au public ; ne jamais y publier de secret ID ni de donnée privée.
- Les boutons emploient des verbes directs. Ne pas répéter le même emoji dans le texte et dans la propriété emoji du bouton.

Pour les messages en Components V2, composer l’interface avec conteneurs, sections, affichages de texte et séparateurs. Un message V2 ne mélange pas ces composants avec un embed classique ; appliquer une hiérarchie et une palette cohérentes dans les deux formats.

## Emojis existants

Utiliser d’abord le registre existant plutôt que de créer un doublon :

- `root_terminal` : identité ROOT OS (version animée disponible).
- `root_ferme`, `root_puissance`, `root_production`, `root_memoire`, `root_temps` : minage, ATK, production, mémoire/RTM, durée.
- `root_recolter`, `root_materiel`, `root_logiciels`, `root_operations`, `root_journal`, `root_alerte`, `root_scan`, `root_connexions`, `root_retour`, `root_bilan` : actions et rubriques du jeu (versions animées disponibles pour `root_recolter`, `root_alerte`, `root_scan` et `root_retour`).
- `root_firewall` est un asset historique : ne pas l’utiliser dans les nouveaux textes joueurs si la terminologie actuelle dit « infrastructure ».

Les pictogrammes du pack sont des icônes sobres, transparentes, prévues pour le fond sombre et principalement recolorées en turquoise, blanc cassé ou ambre. Résoudre les emojis Discord par le registre prévu ; ne pas inventer leurs IDs et prévoir un libellé lisible si l’emoji est indisponible.

## Règle de portée

Cette charte concerne toutes les réponses, interfaces, notifications et annonces du bot visibles par les joueurs, en salon, en message privé ou en interaction. Un changement visuel ne doit pas modifier les règles métier, les montants, les validations, les permissions ni les résultats du jeu.
