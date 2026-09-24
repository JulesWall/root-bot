# :tools: Hotfix Update 2

### :jigsaw: Améliorations & Visibilité du Hash Challenge (`/hash`)
* **Suivi en direct de son cooldown personnel** :
  > Lancer `/hash` ou `!hash` tout court (sans argument) affiche désormais l'état exact de votre délai d'attente individuel :
  > • En attente : `⏳ Ton cooldown : Disponible dans X min (Xmin Ys)`
  > • Disponible : `⏳ Ton cooldown : Disponible maintenant ✅`
  > Plus besoin de soumettre une valeur à l'aveugle pour savoir si votre délai de 8 minutes est écoulé !
* **Correction de la description `/event`** :
  > Rectification de la fiche du Hash Challenge dans le tableau de bord `/event` et `!event` : remplacement de l'ancienne mention (*Fourchette de 100k*) par la nouvelle fourchette resserrée de l'Update 2 (*Fourchette de 1 000*).

---

### :bell: Intégration Intelligente des Rappels (`/rmd`)
* **Prise en compte du cooldown Hash dans `/rmd all`** :
  > Lorsque le défi Hash est actif sur le réseau mais que vous êtes temporairement bloqué par votre cadence personnelle de 8 minutes, `/rmd all` (ou `/rmd auto target:all`) planifie désormais automatiquement un rappel pour la fin exacte de votre cooldown personnel.
* **Support dédié `/rmd auto target:hash`** :
  > Programmer un rappel spécifique avec `/rmd auto target:hash` ou `!rmd hash` prend également en compte votre cooldown individuel au lieu de simplement considérer l'événement comme déjà disponible.