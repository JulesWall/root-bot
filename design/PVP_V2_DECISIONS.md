# ROOT OS — Décisions de Game Design PvP V2

**Étape 0 — Document de validation**
Statut : **EN ATTENTE DE VALIDATION HUMAINE**

Ce document répond aux 20 points ouverts du `PVP_IMPLEMENTATION_PLAN.md`.
Pour chaque décision : choix proposé · raison · exemple chiffré · cas limite.

Chaque section doit recevoir un statut explicite avant le début de l'étape 1 :
- `[VALIDÉ]` — choix retenu tel quel.
- `[MODIFIÉ : ...]` — choix retenu avec correction précisée.
- `[REFUSÉ : ...]` — choix rejeté, nouvelle décision à écrire.

---

## Décision 1 — Périmètre d'une vulnérabilité

**Choix proposé :** Une vulnérabilité cible **un tier précis** d'un type de module (ex. : mineurs T3).

**Raison :** Cela donne de la valeur à la diversification du parc matériel. Un joueur avec plusieurs tiers ne peut pas être intégralement siphonné par un seul logiciel. Rend le patch chirurgical et compréhensible.

**Exemple :** Hostile Miner / K7M2 cible les mineurs T3. Seulement les mineurs T3 de la victime sont affectés. Ses mineurs T1 et T5 continuent à produire normalement.

**Cas limite :** Si la victime n'a aucun module du tier ciblé au moment de l'installation, l'opération échoue proprement au moment de la résolution (pas au moment du devis).

**Statut : [VALIDÉ ]**

---

## Décision 2 — Génération de l'empreinte courte

**Choix proposé :**
- Alphabet : majuscules + chiffres, sans caractères ambigus (`0`, `O`, `I`, `1` retirés) → 32 caractères.
- Longueur : 4 caractères → 32⁴ = 1 048 576 combinaisons par famille.
- Unicité : contrainte d'unicité **par famille** en base (`UNIQUE KEY (family, fingerprint)`). La même empreinte peut exister dans deux familles différentes (ex. K7M2 chez Hostile Miner et chez Ransomware).
- Gestion des collisions : jusqu'à 10 tentatives de génération aléatoire. Si toutes échouent (saturation très improbable), le job de recherche échoue avec message clair ; le coût de départ n'est pas remboursé (la recherche a eu lieu, la vulnérabilité n'était pas exploitable).
- Caractère public : l'empreinte est visible par l'attaquant et peut être révélée à la victime après diagnostic. Elle n'expose pas l'auteur de l'attaque directement.

**Exemple :** Recherche réussie → empreinte générée `K7M2`. Un autre joueur compile la même famille et obtient `P3RX`. Un troisième recompile depuis le même dossier → obtient exactement la même empreinte `K7M2`.

**Cas limite :** Deux joueurs compilent depuis deux dossiers différents ciblant le même tier → deux empreintes différentes, deux correctifs différents. Patcher l'un ne protège pas de l'autre.

**Statut : [ VALIDÉ]**

---

## Décision 3 — Recherche : probabilité vs garanti

**Choix proposé :** La recherche est un **résultat garanti**, pas probabiliste.

**Raison :** Une probabilité d'échec sur un job long (plusieurs minutes/heures) est frustrante. La variabilité vient déjà de la durée (qui dépend de la puissance disponible) et du coût. La recherche échoue uniquement pour des raisons explicites : solde insuffisant à la confirmation, ou collision d'empreinte non résolvable.

**Redécouverte d'une vulnérabilité connue :** Si le joueur lance une recherche sur une famille + tier pour lesquels il a déjà un dossier actif, le service refuse le job avec message explicite. Il ne consomme pas de ressources.

**Recherches simultanées :** 1 seule recherche ou compilation par canal (offensif ou défensif). Les deux canaux peuvent tourner en même temps. Un joueur peut donc mener une recherche offensive et fabriquer un patch défensif simultanément.

**Coût d'un "échec" :** Le RTM versé au départ du job est consommé dans tous les cas. Si le job échoue à la résolution (cible disparue, collision), le RTM n'est pas remboursé. Le message d'échec précise la raison.

**Exemple :** Joueur A lance recherche Hostile Miner T3 (durée calculée : 47 min, coût : 0,002 RTM). À t+47 min, résolution : empreinte `K7M2` assignée, dossier créé. Coût payé au lancement.

**Cas limite :** Bot redémarre pendant la recherche → le job reprend depuis la BDD, livraison unique à l'échéance originale.

**Statut : [ VALIDÉ]**

---

## Décision 4 — Définitions exactes des objets

**Choix proposé :**

| Objet | Définition | Contient |
|-------|-----------|----------|
| **Dossier de recherche** | Résultat d'une recherche réussie. Appartient au joueur. Permet de compiler des copies. | Famille, tier, empreinte, auteur |
| **Logiciel compilé** | Binaire utilisable produit depuis un dossier. Une même empreinte peut avoir plusieurs copies. | Famille, tier, empreinte, propriétaire actuel, origine (dossier ou vol/achat) |
| **Copie** | Logiciel compilé supplémentaire depuis le même dossier, ou copie transmise via achat/vol. | Mêmes champs, propriétaire différent. N'inclut pas le dossier source. |
| **Licence** | Non retenu. Remplacé par "copie avec droits de revente". | — |
| **Patch** | Correctif compilé depuis un dossier de recherche **défensif** de la même empreinte. | Famille, empreinte ciblée, propriétaire |
| **Patch installé** | Patch appliqué au réseau du joueur. Protège tous les modules du tier ciblé, présents et futurs. | Enregistrement en base, lié à l'empreinte bloquée |

**Exemple :** Joueur A a le dossier `Hostile Miner / K7M2 / T3`. Il compile une copie pour lui et une copie à vendre. L'acheteur B obtient une copie (peut attaquer) mais pas le dossier (ne peut pas en compiler d'autres).

**Cas limite :** Un joueur vole une copie → obtient la copie, pas le dossier. Recompiler depuis une copie volée est impossible.

**Statut : [VALIDÉ ]**

---

## Décision 5 — Droits de copie et de revente

**Choix proposé :**

| Possession | Peut attaquer | Peut copier | Peut vendre copie | Peut fabriquer patch |
|------------|:---:|:---:|:---:|:---:|
| Dossier de recherche offensif | ✅ (compile d'abord) | ✅ | ✅ | ❌ |
| Logiciel compilé (copie propre) | ✅ | ❌ | ✅ | ❌ |
| Copie achetée | ✅ | ❌ | ✅ | ❌ |
| Copie volée | ✅ | ❌ | ❌ (vol interdit à la revente) | ❌ |
| Dossier défensif | ❌ | ❌ | ❌ | ✅ |
| Patch (non installé) | ❌ | ❌ | ✅ | ❌ |
| Patch installé | ❌ | ❌ | ❌ (déjà consommé) | ❌ |

**Raison :** Le vol a un coût d'opportunité (revente impossible) pour limiter l'exploitation compulsive. Le dossier de recherche offensif est la ressource de production ; le logiciel compilé est l'outil de consommation.

**Exemple :** A vole une copie de B. A peut s'en servir pour attaquer C, mais ne peut pas la revendre au marché.

**Cas limite :** A achète une copie, puis se fait voler. Le voleur obtient une "copie achetée" → peut revendre.

**Statut : [ nul il faut simplifier ça je pense qu'on a qu'une version et voilà]**

---

## Décision 6 — Hostile Miner : paramètres

**Choix proposé :**

- **Taux de siphonnage :** 15 % de la production H/s des modules du tier ciblé.
- **Assiette :** puissance brute des modules du tier ciblé uniquement (pas les bonus de réputation).
- **Stockage du gain :** le RTM siphonné s'accumule dans le `mining_buffer` de l'attaquant exactement comme sa propre production. La mémoire de l'attaquant s'applique normalement.
- **Effet d'une mémoire pleine (attaquant) :** si le buffer de l'attaquant est plein, le RTM siphonné est perdu (ni crédité à l'attaquant, ni rendu à la victime). Le siphon continue.
- **Effet d'une mémoire pleine (victime) :** la victime ne produit plus non plus → le taux s'applique sur zéro → siphon nul jusqu'à la prochaine récolte.
- **Cumul de plusieurs attaquants :** plafond global de 40 % de siphonnage tous attaquants confondus sur le même tier. Si A et B attaquent simultanément (chacun 15 %), ils se partagent le plafond à proportion (20 % chacun). Un troisième attaquant en reçoit 0 % sur ce tier tant que le plafond est atteint.
- **Fin de l'infection :** uniquement par installation du bon patch (empreinte correspondante). Un redémarrage du bot, un `/claim`, ou une déconnexion Discord n'arrêtent pas l'infection.

**Exemple :** Victime avec 4 mineurs T3 à 625 H/s chacun = 2 500 H/s T3. Production = 2 500 × 1e-7 RTM/min = 0,00025 RTM/min = 0,015 RTM/h. Siphonnage 15 % = 0,00225 RTM/h pour l'attaquant, victime reçoit 0,01275 RTM/h.

**Cas limite :** Victime achète un nouveau mineur T3 pendant l'infection → il est immédiatement siphonné (le siphon porte sur tous les modules du tier ciblé, présents et futurs, jusqu'au patch).

**Statut : [ VALIDÉ]**

---

## Décision 7 — Espionnage préventif

**Choix proposé :**

- **Données révélées :** uniquement les jobs de développement en cours de la cible (famille, tier, canal offensif/défensif, progression estimée). Pas les soldes, pas les modules, pas les logiciels compilés.
- **Durée du renseignement :** le rapport d'espionnage est valide **jusqu'à la fin du job espionné** ou jusqu'à 24h, selon ce qui vient en premier. Passé ce délai, le rapport est archivé mais marqué périmé.
- **Discrétion :** l'espionnage lui-même n'est pas détectable par la cible. La cible n'est pas notifiée.
- **Moment où un correctif défensif peut commencer :** immédiatement après réception du rapport d'espionnage. Le coût et le temps sont normaux.
- **Possibilité de rester discret :** oui, l'espionnage est toujours discret (pas de trace vers la victime). La seule détection possible est via l'analyse de trace d'un Hostile Miner actif (autre famille).

**Exemple :** A espionne B. Rapport : « B compile actuellement Hostile Miner / T3 — progression ~60% — 18 min restantes. » A lance immédiatement la recherche défensive pour T3. Si A installe le patch avant la fin de la compilation de B, l'attaque future de B sera bloquée.

**Cas limite :** Le job espionné est annulé entre le lancement et la résolution de l'espionnage → le rapport indique « job terminé ou annulé » et est immédiatement périmé.

**Statut : [tous les logiciels en cours ou non c'est genre un dir ]**

---

## Décision 8 — Blocage contre rançon (Ransomware)

**Choix proposé :**

- **Commandes bloquées :** toutes les commandes de jeu économiques actives à l'exception explicite de la liste blanche ci-dessous. La liste des commandes bloquables est dans `math.json` (`pvp_v2.ransomware.blocked_commands`).
- **Commandes toujours accessibles :** `/network` (lecture), `/claim` (récolte — la victime ne doit pas perdre sa production), `/help`, `/scan` défensif, développement de patch (`game/pvp dev`), paiement de la rançon, diagnostic.
- **Calcul de la rançon :** montant fixe en dollars, tiré depuis `math.json` (valeur par tier du logiciel ransomware), indépendant du solde de la victime.
- **Durée maximale :** 72h. Passé ce délai, le blocage est levé automatiquement sans paiement. Aucune immunité accordée dans ce cas (l'attaquant peut recommencer après le cooldown standard).
- **Paiement :** le montant exact est transféré à l'attaquant atomiquement. Le blocage est levé simultanément. Paiement doublon impossible (idempotence).
- **Immunité temporaire après résolution :** 48h d'immunité contre le même logiciel (même empreinte) après paiement ou installation du patch.

**Exemple :** Ransomware T3 = rançon 500 $. Victime a 300 $ → ne peut pas payer → doit patcher ou attendre 72h. Victime a 800 $ → peut payer 500 $ directement. Reste : 300 $.

**Cas limite :** Solde passe sous 500 $ entre le devis et le paiement → paiement refusé, message `quote_changed`, la victime doit tenter à nouveau.

**Statut : [ la raçon est déterminée par l'attaquant, elle est payable en RTM ]**

---

## Décision 9 — Vol de monnaie

**Choix proposé :**

- **Devise ciblée :** dollars uniquement.
- **Réserve exposée :** 25 % du solde en dollars de la victime au moment de la résolution.
- **Montant maximal par opération :** plafonné à 1 000 $.
- **Protection du solde minimum :** la victime conserve toujours au minimum 50 $ (non volables). Si son solde est ≤ 50 $, l'opération échoue proprement.
- **Fréquence :** même victime re-ciblable au plus une fois par 48h (par attaquant différent : pas de cumul de cooldown). Le plafond de cumul tous attaquants confondus sur 24h = 30 % du solde de départ de la journée.

**Exemple :** Victime a 2 000 $. Réserve exposée = 500 $. Plafond 1 000 $. Vol = min(500, 1000) = 500 $. Attaquant reçoit 500 $ moins les frais de transaction (5 %, soit 25 $) → attaquant gagne 475 $, victime perd 500 $.

**Cas limite :** Solde de la victime passe de 2 000 $ à 60 $ entre le devis et la résolution → réserve exposée recalculée = 15 $, mais solde restant après vol = 45 $ < 50 $ → montant ajusté pour respecter le plancher : vol = 10 $. Frais = 0,50 $ (arrondi Decimal à 2 décimales).

**Statut : [ pas de plafond]**

---

## Décision 10 — Saturation du calcul

**Choix proposé :**

- **Ressource ralentie :** la puissance de développement du canal **offensif** uniquement. Le canal défensif n'est jamais saturable.
- **Taux de ralentissement :** 30 % de la puissance offensive effective réduite par saturation active.
- **Durée d'un effet de saturation :** 6h à partir de la résolution du job d'installation.
- **Cumul de plusieurs saturations :** non additif. Le plafond est 60 % de réduction, quel que soit le nombre d'attaquants actifs.
- **Plancher de capacité défensive :** le canal défensif reste toujours à 100 % de sa puissance. Un joueur entièrement saturé peut encore fabriquer des patchs à pleine vitesse.
- **Jobs déjà lancés :** les jobs offensifs déjà en cours au moment de l'installation de la saturation **conservent leur devis initial** (durée non modifiée). Seuls les nouveaux jobs lancés après sont ralentis.

**Exemple :** A sature B. B a 500 bits/s offensifs. Pendant 6h, B ne dispose que de 350 bits/s offensifs pour ses nouvelles recherches. Sa défense reste à 200 bits/s défensifs (inchangée).

**Cas limite :** B lance un job offensif 5 min avant la saturation → durée non modifiée. B lance un job 5 min après → durée calculée avec 350 bits/s.

**Statut : [ VALIDÉ]**

---

## Décision 11 — Scan complet du réseau

**Choix proposé :**

**Données visibles dans le rapport :**
- Niveau d'infrastructure (0-5)
- Quantité de modules par type et par tier (mining, attack, bay_defense)
- Puissance totale H/s et débit RTM/h estimé
- Réserve de mémoire utilisée / capacité totale
- Logiciels installés actifs (famille + empreinte, pas l'auteur)
- Patches installés (famille + empreinte)
- Nombre de jobs de développement en cours (pas leur contenu)

**Données non incluses :**
- Soldes en dollars ou RTM
- Secret ID ou identifiant Discord brut
- Contenu des jobs de développement (couvert par l'espionnage)
- Attaquants actifs non encore diagnostiqués (intrus inconnu = invisible au scan)

**Durée de validité du rapport :** 24h. Passé ce délai, le rapport reste lisible mais est marqué périmé (les données peuvent ne plus être exactes).

**Capture des données :** au moment de la **résolution du scan**, pas au moment du devis.

**Exemple :** A scanne B. Rapport figé à t=résolution : 4 mineurs T3, 2 bay_defense T2, 1 Hostile Miner K7M2 actif (car diagnostiqué par B), 0 patch. B achète ensuite 10 mineurs T4 → l'ancien rapport dit toujours 4 T3.

**Cas limite :** La cible est supprimée entre le devis et la résolution → le scan échoue, RTM non remboursé, message explicite.

**Statut : [VALIDÉ ]**

---

## Décision 12 — Vol de logiciel

**Choix proposé :**

- **Sélection de la cible :** uniquement un logiciel compilé que l'attaquant a préalablement identifié via un scan ou un rapport d'espionnage valide (non périmé).
- **Visibilité préalable :** obligatoire. Sans scan récent (< 24h) ou rapport d'espionnage valide, l'opération est impossible.
- **Conservation de l'original :** l'original reste chez la victime. C'est une copie qui est volée, pas un transfert.
- **Revente :** une copie volée ne peut pas être revendue (cf. Décision 5).
- **Accès au dossier source :** non. Le vol donne uniquement une copie utilisable.

**Exemple :** A scanne B (valide). B a `Ransomware / P3RX` compilé. A lance un vol. Si succès : A obtient une copie de `Ransomware / P3RX`. B conserve son exemplaire. A peut l'utiliser mais pas le vendre.

**Cas limite :** Le rapport de scan expire pendant le job de vol → la résolution vérifie que A avait bien un rapport valide au moment du devis. Si le rapport a expiré entre devis et confirmation → `quote_changed`, A doit rescanner.

**Statut : [ VALIDÉ]**

---

## Décision 13 — Modules de défense : formule et patch

**Choix proposé :**

- **Formule de ralentissement de l'installation :** la durée d'installation d'un logiciel hostile est multipliée par un facteur calculé depuis la puissance défensive de la victime. Formule : `durée_effective = durée_base × (1 + defense_power / defense_divisor)` où `defense_divisor` est défini dans `math.json`.
- **Plafond du ralentissement :** la durée d'installation ne peut pas dépasser 10× la durée de base (même avec une défense infinie).
- **Puissance de recherche défensive par tier :** identique aux `bay_defense_power` existants (T1=10, T2=50, T3=200, T4=800, T5=3000). Ces valeurs peuvent être recalibrées à l'étape 1.
- **Coût des correctifs :** un patch coûte le même RTM que la compilation offensive équivalente (même tier). La durée est calculée sur la puissance défensive (canal `bay_defense`).
- **Patch permanent pour les achats futurs :** un patch installé protège tous les modules du tier concerné, y compris ceux achetés après l'installation.

**Exemple :** Durée de base d'installation d'un Hostile Miner T3 = 45 min. Victime a 5 bay_defense T2 (puissance = 5×50 = 250). `defense_divisor = 500` (valeur indicative à valider). Facteur = 1 + 250/500 = 1,5. Durée effective = 67,5 min.

**Cas limite :** Victime a un défense de 10 000 points → facteur = 1 + 10000/500 = 21 → plafonné à 10 → durée = 450 min = 7,5h.

**Statut : [ VALIDÉ]**

---

## Décision 14 — Opérations simultanées

**Choix proposé :**

**Par attaquant :**
- 1 opération active à la fois **par famille** (impossible de lancer deux Hostile Miners simultanément).
- Maximum 3 opérations actives simultanées toutes familles confondues.

**Par victime :**
- Pas de limite sur le nombre d'attaquants différents.
- Plafonds d'effets cumulés définis par famille (cf. Décisions 6, 9, 10).

**Limites d'effets cumulés (rappel) :**
| Famille | Plafond cumulé |
|---------|---------------|
| Hostile Miner | 40 % du siphonnage sur un tier donné |
| Vol de monnaie | 30 % du solde/24h tous attaquants |
| Saturation | 60 % de réduction offensive |

**Exemple :** A a une opération Hostile Miner T3 et une Saturation active contre B. A peut encore lancer un Ransomware contre B (3e famille différente). A ne peut pas lancer un second Hostile Miner contre B (même famille).

**Cas limite :** A atteint 3 opérations actives. Il doit attendre qu'une se termine naturellement ou soit patchée avant d'en lancer une nouvelle.

**Statut : [ VALIDÉ]**

---

## Décision 15 — Détection, trace, identification et représailles

**Choix proposé :**

- **Détection d'une anomalie :** automatique (la vue `/network` signale un écart de production > 5 %) mais ne révèle pas la cause.
- **Diagnostic :** commande explicite (`/network` → Diagnostiquer). Durée : 10 min, coût en RTM défini dans `math.json`. Révèle la famille et l'empreinte de l'infection, pas l'auteur.
- **Analyse de trace :** commande séparée après diagnostic. Durée : 30 min, coût en RTM. Révèle l'identifiant du joueur attaquant (son pseudo + tag Discord).
- **Identification de l'auteur :** uniquement après analyse de trace complète.
- **Début des 72h de représailles :** à partir de la **fin de l'analyse de trace** (pas du diagnostic, pas du scan). Sans analyse de trace, pas de représailles possibles.
- **Discrétion de l'attaquant :** l'attaquant peut ajouter un module de discrétion (coût en RTM à l'opération) qui allonge la durée d'analyse de trace de 100 % (60 min au lieu de 30 min) mais ne rend pas l'identification impossible.

**Exemple :** B constate un écart à 14h. B lance le diagnostic → terminé à 14h10 : « Hostile Miner / K7M2 ». B lance l'analyse de trace → terminée à 14h40 : auteur = A. Les 72h de représailles commencent à 14h40. B peut attaquer A (même niveau inférieur) jusqu'à 14h40 le lendemain.

**Cas limite :** A patche son propre réseau avant que B finisse l'analyse de trace → l'analyse échoue, B ne peut pas identifier A, pas de représailles.

**Statut : [VALIDÉ ]**

---

## Décision 16 — Publication et installation d'un patch public

**Choix proposé :**

- **Coût de publication :** 0 $ supplémentaire. Le coût de compilation du patch a déjà été payé.
- **Publication :** le joueur marque son patch comme "public" dans le marché. Prix : libre (peut être gratuit ou payant).
- **Durée de disponibilité :** illimitée jusqu'à retrait volontaire ou suppression du compte.
- **Installation chez les autres :** chaque joueur doit **acheter ou récupérer le patch** puis **l'installer manuellement**. Une publication gratuite n'installe pas le patch automatiquement chez quiconque.
- **Comportement hors ligne :** l'installation est un job différé. Si le joueur se déconnecte après confirmation, le job continue et la livraison est envoyée en DM ou inscrite dans le Journal.

**Exemple :** A compile le patch de `Hostile Miner / K7M2` et le publie gratuitement. B voit le patch disponible, le récupère (0 $) et lance l'installation (job de 15 min). C ne fait rien → toujours vulnérable.

**Cas limite :** Le joueur publie un patch puis supprime son compte → le patch reste dans les inventaires des acheteurs mais disparaît du marché.

**Statut : [VALIDÉ ]**

---

## Décision 17 — Conversion du stock `attack_points`

**Choix proposé :**

- **Barème :** 1 attack_point = 1 $ (dollars en jeu). Conversion directe et immédiate.
- **Moment :** lors du déploiement (étape 13), une migration SQL convertit automatiquement le stock de chaque joueur en dollars. Aucune action manuelle requise.
- **Plafond de conversion :** aucun plafond. Même les grands stocks sont convertis intégralement pour ne pas pénaliser les joueurs qui ont investi dans `/compile`.
- **Communication :** un message dans le Journal de chaque joueur concerné indique le montant converti au démarrage post-migration.
- **Après la conversion :** la colonne `attack_points` est mise à 0 et n'est plus alimentée. Elle sera physiquement supprimée à l'étape 13 après vérification humaine.

**Exemple :** Joueur avec 15 000 attack_points → reçoit 15 000 $ en dollars le jour du déploiement.

**Cas limite :** Joueur avec 0 attack_points → aucun changement. Joueur avec un job `/compile` en cours au moment du déploiement → le job est annulé, le RTM payé est remboursé, l'attack_points non encore livré est perdu (le RTM de remboursement compense).

**Statut : [1 attack point = 20 usd ]**

---

## Décision 18 — Commandes finales

**Choix proposé :**

| Ancienne commande | Comportement V2 |
|------------------|----------------|
| `/compile` | Remplacé par `/dev start` (lancement d'une recherche ou compilation, offensif ou défensif) |
| `/scan` | Remplacé par `/scan` avec nouvelle mécanique (photographie horodatée V2) |
| `/hack` | Remplacé par `/op start` (lancement d'une opération PvP : famille + cible + logiciel) |

**Nouvelles commandes ajoutées :**
- `/dev` : sous-commandes `start`, `status`, `cancel` pour les jobs de développement
- `/op` : sous-commandes `start`, `status`, `cancel`, `log` pour les opérations
- `/library` : bibliothèque des logiciels et patches détenus
- `/market` : marché des logiciels et patches

**Compatibilité :** aucune compatibilité comportementale exigée avec l'ancien PvP. Les anciens noms de commandes (`/compile`, `/hack`) affichent un message localisé d'indisponibilité sur la branche de développement.

**Exemple :** `/dev start offensive hostile_miner t3` → lance la recherche. `/op start hostile_miner K7M2 @victime` → lance l'opération si le logiciel est compilé.

**Cas limite :** Un joueur tente `/hack @cible` → message : « Cette commande n'est pas disponible. Utilise `/op start` pour lancer une opération. »

**Statut : [VALIDÉ ]**

---

## Décision 19 — Visibilité publique ou privée

**Choix proposé :**

| Élément | Visibilité |
|---------|-----------|
| Panneau `/network` | **Public** (tout le monde peut voir le panneau d'un joueur, mais seul le propriétaire peut agir) |
| Rapports de scan | **Privé** (visible uniquement par l'attaquant ayant effectué le scan) |
| Bibliothèque (`/library`) | **Privé** (visible uniquement par le propriétaire) |
| Opérations en cours (`/op status`) | **Privé** (attaquant uniquement) |
| Journal de la victime | **Privé** (visible uniquement par la victime) |
| Listings du marché | **Public** (visible par tous, acheteurs potentiels) |
| Rapport d'espionnage | **Privé** (espion uniquement) |

**Raison :** Le panneau `/network` public permet la dimension sociale (spectateurs, streamers). Tout le reste reste privé pour préserver la tension stratégique.

**Exemple :** B peut voir le `/network` de A et constater ses mineurs T3, mais pas son stock RTM ni ses logiciels.

**Cas limite :** Un joueur fait un screenshot de son propre rapport de scan → c'est son droit. Le bot ne le prévient pas.

**Statut : [tout est visible c'est au joueur d'être vigilant sur le lieux où il fait ses commandes ]**

---

## Décision 20 — Règles initiales du marché

**Choix proposé :**

- **Prix :** libre, fixé par le vendeur. Bornes dans `math.json` : minimum 1 $, maximum 100 000 $.
- **Taxes :** 5 % prélevés sur le prix à la transaction, crédités à un compte "banque" fictif (retirés de la circulation). Défini dans `math.json`.
- **Annulation :** le vendeur peut annuler son annonce à tout moment si elle n'a pas encore été achetée. L'actif lui est restitué.
- **Offres simultanées :** un vendeur peut avoir au maximum 5 annonces actives simultanément.
- **Anti-auto-achat :** un joueur ne peut pas acheter ses propres annonces. Vérifié côté serveur.
- **Actifs vendables :** logiciels compilés (copie propre ou achetée), patches (non installés), dossiers de recherche offensifs (avec droits de compilation).
- **Actifs non vendables :** copies volées, patches déjà installés, dossiers défensifs.
- **Réservation à la création :** l'actif vendu est marqué "réservé" dès la création de l'annonce. Il ne peut pas être utilisé ni revendu ailleurs tant que l'annonce est active.

**Exemple :** A met en vente une copie de `Hostile Miner / K7M2` pour 2 000 $. B achète → B paie 2 000 $, A reçoit 1 900 $ (5 % de taxe = 100 $). La copie passe dans l'inventaire de B.

**Cas limite :** Deux joueurs cliquent "Acheter" en même temps → un seul réussit (verrou transactionnel), l'autre reçoit une erreur explicite. Aucun doublon possible.

**Statut : [modifié : pas de plafond pour la mise ne vente ]**

---

## Récapitulatif des validations

| # | Décision | Statut |
|---|----------|--------|
| 1 | Périmètre d'une vulnérabilité | [ ] |
| 2 | Génération de l'empreinte | [ ] |
| 3 | Recherche : garanti ou probabiliste | [ ] |
| 4 | Définitions exactes des objets | [ ] |
| 5 | Droits de copie et revente | [ ] |
| 6 | Hostile Miner | [ ] |
| 7 | Espionnage préventif | [ ] |
| 8 | Ransomware | [ ] |
| 9 | Vol de monnaie | [ ] |
| 10 | Saturation du calcul | [ ] |
| 11 | Scan complet | [ ] |
| 12 | Vol de logiciel | [ ] |
| 13 | Défense et patch | [ ] |
| 14 | Opérations simultanées | [ ] |
| 15 | Détection, trace, représailles | [ ] |
| 16 | Patch public | [ ] |
| 17 | Conversion attack_points | [ ] |
| 18 | Commandes finales | [ ] |
| 19 | Visibilité | [ ] |
| 20 | Marché | [ ] |

**Validation globale : `ETAPE 0 VALIDEE` à apposer ici une fois toutes les cases cochées.**

