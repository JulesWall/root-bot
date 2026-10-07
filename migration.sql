-- Migration SQL : Refonte Graphique Root OS (v3.0.0)
-- Aucune modification de schéma requise (les colonnes existantes supportent l'infrastructure 0 à 5).

-- Migration SQL : Contrats Dynamiques V2
ALTER TABLE contracts MODIFY COLUMN title VARCHAR(255) NOT NULL;
ALTER TABLE contracts MODIFY COLUMN duration_type VARCHAR(32) NOT NULL;
