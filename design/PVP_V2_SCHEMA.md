# ROOT OS — Schéma relationnel PvP V2 (à approuver avant SQL)

**Étape 2 — Modèle pour validation humaine**
Statut : **EN ATTENTE DE VALIDATION**

Ce document décrit les nouvelles tables sans écrire de SQL.
Valider chaque table (`[OK]` ou commentaire) avant le début des travaux SQL.

---

## Périmètre couvert

| Table | Responsabilité |
|-------|---------------|
| `pvp_v2_research_folders` | Dossiers de recherche détenus par joueur |
| `pvp_v2_software_copies` | Logiciels compilés (copies avec origine et droits) |
| `pvp_v2_patches` | Correctifs compilés et correctifs installés |
| `pvp_v2_dev_jobs` | Jobs de développement (2 canaux : offense / defense) |
| `pvp_v2_operations` | Opérations PvP (cycle de vie complet) |
| `pvp_v2_active_effects` | Infections et effets persistants (siphon, rançon, saturation…) |
| `pvp_v2_scan_reports` | Rapports de scan horodatés figés |
| `pvp_v2_espionage_reports` | Rapports d'espionnage horodatés figés |
| `pvp_v2_market_listings` | Annonces de marché |

---

## 1. `pvp_v2_research_folders` — Dossiers de recherche

Un dossier est créé quand une recherche offensive ou défensive réussit.
Il permet de compiler des copies (offensif) ou des patches (défensif).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | BIGINT UNSIGNED AUTO_INCREMENT | PK | |
| `owner_id` | BIGINT UNSIGNED | FK players, ON DELETE CASCADE | Propriétaire |
| `channel` | ENUM('offense','defense') | NOT NULL | Canal de développement |
| `family` | VARCHAR(32) | NOT NULL | Famille (ex: `hostile_miner`) |
| `tier` | TINYINT UNSIGNED | NOT NULL | Tier matériel ciblé (1-6) |
| `fingerprint` | CHAR(4) | NOT NULL | Empreinte courte |
| `created_at` | DATETIME(6) | NOT NULL | Horodatage de création |

**Contraintes :**
- `UNIQUE (family, fingerprint)` — une empreinte est unique par famille
- `INDEX (owner_id)`

**Règle :** un joueur ne peut avoir qu'un seul dossier par `(family, tier)` actif. Contrainte applicative, pas SQL (un joueur peut avoir des dossiers pour différentes familles et tiers).

---

## 2. `pvp_v2_software_copies` — Copies de logiciels compilés

Chaque copie compilée ou achetée ou volée est une ligne distincte.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | BIGINT UNSIGNED AUTO_INCREMENT | PK | |
| `owner_id` | BIGINT UNSIGNED | FK players, ON DELETE CASCADE | Propriétaire actuel |
| `family` | VARCHAR(32) | NOT NULL | |
| `tier` | TINYINT UNSIGNED | NOT NULL | |
| `fingerprint` | CHAR(4) | NOT NULL | |
| `origin` | ENUM('compiled','purchased','stolen') | NOT NULL | Origine de la copie |
| `resellable` | TINYINT(1) | NOT NULL DEFAULT 1 | 0 si copie volée |
| `reserved` | TINYINT(1) | NOT NULL DEFAULT 0 | 1 si en vente sur le marché |
| `created_at` | DATETIME(6) | NOT NULL | |

**Contraintes :**
- `INDEX (owner_id)`
- `INDEX (fingerprint)` — pour vérifier les patches

**Règle :** `resellable = 0` quand `origin = 'stolen'` (contrainte applicative vérifiée à la création).

---

## 3. `pvp_v2_patches` — Correctifs

Un patch peut être compilé puis installé. Une fois installé, il protège tous les modules du tier ciblé (présents et futurs).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | BIGINT UNSIGNED AUTO_INCREMENT | PK | |
| `owner_id` | BIGINT UNSIGNED | FK players, ON DELETE CASCADE | Propriétaire |
| `family` | VARCHAR(32) | NOT NULL | Famille ciblée |
| `fingerprint` | CHAR(4) | NOT NULL | Empreinte bloquée par ce patch |
| `installed` | TINYINT(1) | NOT NULL DEFAULT 0 | 1 = installé sur le réseau |
| `installed_at` | DATETIME(6) | NULL | Horodatage d'installation |
| `reserved` | TINYINT(1) | NOT NULL DEFAULT 0 | 1 si en vente sur le marché |
| `created_at` | DATETIME(6) | NOT NULL | |

**Contraintes :**
- `UNIQUE (owner_id, fingerprint, installed)` partiellement : un joueur ne peut pas installer deux fois le même patch
- `INDEX (owner_id, fingerprint)` — lookup rapide pour vérifier si un réseau est protégé
- `INDEX (owner_id, installed)` — liste des patches installés d'un joueur

---

## 4. `pvp_v2_dev_jobs` — Jobs de développement

Un seul job actif par canal (`offense` ou `defense`) par joueur.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | BIGINT UNSIGNED AUTO_INCREMENT | PK | |
| `player_id` | BIGINT UNSIGNED | FK players, ON DELETE CASCADE | |
| `channel` | ENUM('offense','defense') | NOT NULL | Canal de calcul utilisé |
| `job_type` | ENUM('research','compile','patch_research','patch_compile') | NOT NULL | |
| `family` | VARCHAR(32) | NOT NULL | |
| `tier` | TINYINT UNSIGNED | NOT NULL | |
| `fingerprint` | CHAR(4) | NULL | NULL jusqu'à résolution (recherche) |
| `rtm_paid` | DECIMAL(30,5) | NOT NULL | Coût RTM réglé au lancement |
| `bits_per_s` | BIGINT UNSIGNED | NOT NULL DEFAULT 0 | Puissance au moment du lancement |
| `started_at` | DATETIME(6) | NOT NULL | |
| `resolves_at` | DATETIME(6) | NOT NULL | |

**Contraintes :**
- `UNIQUE (player_id, channel)` — un seul job actif par canal
- `INDEX (resolves_at)` — worker de livraison
- `INDEX (player_id)`

---

## 5. `pvp_v2_operations` — Opérations PvP

Cycle de vie complet d'une opération, de la préparation à la fin.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | BIGINT UNSIGNED AUTO_INCREMENT | PK | |
| `attacker_id` | BIGINT UNSIGNED | FK players, ON DELETE CASCADE | |
| `victim_id` | BIGINT UNSIGNED | FK players, ON DELETE CASCADE | |
| `family` | VARCHAR(32) | NOT NULL | |
| `tier` | TINYINT UNSIGNED | NOT NULL | |
| `fingerprint` | CHAR(4) | NOT NULL | |
| `software_copy_id` | BIGINT UNSIGNED | FK pvp_v2_software_copies, ON DELETE RESTRICT | Copie utilisée |
| `status` | ENUM('installing','active','completed','failed','cancelled') | NOT NULL DEFAULT 'installing' | |
| `rtm_cost` | DECIMAL(30,5) | NOT NULL | Coût RTM de l'opération |
| `started_at` | DATETIME(6) | NOT NULL | Lancement du job d'installation |
| `installed_at` | DATETIME(6) | NULL | Fin de l'installation (début de l'effet) |
| `ended_at` | DATETIME(6) | NULL | Fin de l'effet |
| `end_reason` | VARCHAR(32) | NULL | `'patch'`, `'expiry'`, `'cancelled'`… |

**Contraintes :**
- `INDEX (attacker_id, status)` — opérations actives d'un joueur
- `INDEX (victim_id, status)` — opérations subies par un joueur
- `INDEX (started_at)` — worker d'installation
- `CHECK (status IN ('installing','active','completed','failed','cancelled'))`

**Règle :** max 3 opérations `status IN ('installing','active')` par attaquant, max 1 par famille (contrainte applicative dans la transaction).

---

## 6. `pvp_v2_active_effects` — Effets persistants actifs

Un effet est créé quand une opération passe en `active`. Il reste jusqu'au patch ou à l'expiration.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | BIGINT UNSIGNED AUTO_INCREMENT | PK | |
| `operation_id` | BIGINT UNSIGNED | FK pvp_v2_operations, ON DELETE CASCADE | |
| `attacker_id` | BIGINT UNSIGNED | FK players, ON DELETE CASCADE | |
| `victim_id` | BIGINT UNSIGNED | FK players, ON DELETE CASCADE | |
| `family` | VARCHAR(32) | NOT NULL | |
| `tier` | TINYINT UNSIGNED | NOT NULL | |
| `fingerprint` | CHAR(4) | NOT NULL | |
| `started_at` | DATETIME(6) | NOT NULL | |
| `ended_at` | DATETIME(6) | NULL | NULL = toujours actif |
| `end_reason` | VARCHAR(32) | NULL | `'patch'`, `'victim_deleted'`… |

**Contraintes :**
- `INDEX (victim_id, ended_at)` — effets actifs sur un joueur (lookup rapide)
- `INDEX (attacker_id, ended_at)` — effets actifs d'un attaquant
- `INDEX (fingerprint, victim_id)` — vérifie si un réseau est déjà infecté par cette empreinte

---

## 7. `pvp_v2_scan_reports` — Rapports de scan figés

Photographie horodatée. Le contenu ne se met jamais à jour.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | BIGINT UNSIGNED AUTO_INCREMENT | PK | |
| `attacker_id` | BIGINT UNSIGNED | FK players, ON DELETE CASCADE | |
| `victim_id` | BIGINT UNSIGNED | FK players, ON DELETE CASCADE | |
| `scanned_at` | DATETIME(6) | NOT NULL | Moment de la capture |
| `expires_at` | DATETIME(6) | NOT NULL | Après cette date : périmé |
| `report_data` | JSON | NOT NULL | Snapshot figé (champs approuvés en décision 11) |

**Contraintes :**
- `INDEX (attacker_id, scanned_at)`
- `INDEX (expires_at)` — nettoyage périodique
- `INDEX (victim_id, scanned_at)` — vérification validité pour vol de logiciel

> **Justification du JSON :** la photographie est un snapshot variable selon l'état du réseau au moment du scan. Les valeurs critiques (attacker_id, victim_id, dates) sont des colonnes SQL normales.

---

## 8. `pvp_v2_espionage_reports` — Rapports d'espionnage figés

Même logique que le scan, contenu différent (jobs de développement de la cible).

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | BIGINT UNSIGNED AUTO_INCREMENT | PK | |
| `attacker_id` | BIGINT UNSIGNED | FK players, ON DELETE CASCADE | |
| `victim_id` | BIGINT UNSIGNED | FK players, ON DELETE CASCADE | |
| `scanned_at` | DATETIME(6) | NOT NULL | |
| `expires_at` | DATETIME(6) | NOT NULL | |
| `report_data` | JSON | NOT NULL | Jobs en cours capturés |

**Contraintes :**
- `INDEX (attacker_id, scanned_at)`
- `INDEX (expires_at)`

---

## 9. `pvp_v2_market_listings` — Annonces de marché

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | BIGINT UNSIGNED AUTO_INCREMENT | PK | |
| `seller_id` | BIGINT UNSIGNED | FK players, ON DELETE CASCADE | |
| `item_type` | ENUM('research_folder','compiled_software','patch') | NOT NULL | |
| `item_id` | BIGINT UNSIGNED | NOT NULL | ID dans la table source |
| `price_usd` | DECIMAL(30,2) | NOT NULL | Prix affiché |
| `status` | ENUM('active','sold','cancelled','expired') | NOT NULL DEFAULT 'active' | |
| `listed_at` | DATETIME(6) | NOT NULL | |
| `expires_at` | DATETIME(6) | NULL | NULL = pas d'expiration |
| `sold_to` | BIGINT UNSIGNED | NULL | Acheteur final |
| `sold_at` | DATETIME(6) | NULL | |

**Contraintes :**
- `UNIQUE (item_type, item_id, status)` partiel : empêche deux annonces actives pour le même item
- `INDEX (seller_id, status)`
- `INDEX (status, item_type)` — parcours du marché
- `INDEX (expires_at)` — nettoyage
- `CHECK (price_usd >= 0)`

---

## Décisions de modélisation

| Sujet | Choix retenu | Raison |
|-------|-------------|--------|
| Ransomware lock | Ligne dans `pvp_v2_active_effects` avec `family='ransomware'` + données en JSON (montant rançon) | Pas de table séparée, l'effet est géré comme les autres |
| Saturation | Ligne dans `pvp_v2_active_effects` | Même logique |
| Vol de logiciel | Crée une ligne `pvp_v2_software_copies` avec `origin='stolen'`, `resellable=0` | Copie, pas transfert |
| Patch installé | Même ligne `pvp_v2_patches` avec `installed=1`, pas de table séparée | Unicité par `(owner_id, fingerprint)` quand installé |
| Rapports JSON | Uniquement pour snapshots variables (scan, espionnage) | Soldes, propriétaires et états restent en colonnes SQL |
| Journal d'opération | **Supprimé** — pas de logging |  |

---

## Validation attendue

Pour chaque table, réponds `[OK]` ou donne une correction.

- [ ] `pvp_v2_research_folders`
- [ ] `pvp_v2_software_copies`
- [ ] `pvp_v2_patches`
- [ ] `pvp_v2_dev_jobs`
- [ ] `pvp_v2_operations`
- [ ] `pvp_v2_active_effects`
- [ ] `pvp_v2_scan_reports`
- [ ] `pvp_v2_espionage_reports`
- [ ] `pvp_v2_market_listings`

**Validation globale : `SCHEMA V2 APPROUVE` à apposer une fois toutes les tables validées.**
Ensuite seulement : écriture du SQL dans `root.sql` et `migration.sql`, création des dépôts `game/db/`.

