-- ============================================================
--  SOLUTION : Validation FK cross-SGBD (MySQL -> SQL Server)
--  Contexte : personne_association.jeune_cin doit reference
--  Beneficiaire.cin, mais les deux tables sont sur des moteurs
--  differents (MySQL vs SQL Server) : impossible de creer une
--  vraie FOREIGN KEY ANSI entre les deux.
--
--  Solution retenue : table miroir + trigger de validation.
--  1. Une table cin_beneficiaires_valides est maintenue dans
--     jam3iya_db (MySQL), alimentee par SSIS a chaque cycle ETL
--     (copie legere : uniquement le CIN, pas les donnees perso).
--  2. Un trigger BEFORE INSERT/UPDATE sur personne_association
--     verifie que jeune_cin existe dans cette table miroir.
--  3. Si jeune_cin est NULL, aucune verification (lien optionnel
--     conserve, cas normal pour un Animateur ou Membre_Bureau
--     sans compte PassJeunes).
-- ============================================================

USE jam3iya_db;

-- ── Etape 1 : table miroir des CIN valides ────────────────
DROP TABLE IF EXISTS cin_beneficiaires_valides;

CREATE TABLE cin_beneficiaires_valides (
    cin             VARCHAR(20) PRIMARY KEY,
    date_sync       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Cette table est repeuplee par un package SSIS dedie
-- (ex : 04_Sync_CIN_Miroir.dtsx), execute juste avant tout
-- chargement touchant personne_association :
--
--   Source OLE DB (PassJeunesDB) :
--     SELECT cin FROM dbo.Beneficiaire
--   Destination ODBC (jam3iya_db) :
--     TRUNCATE puis INSERT INTO cin_beneficiaires_valides (cin)
--
-- Frequence recommandee : a chaque execution du pipeline
-- (avant le chargement de personne_association), pour rester
-- synchronisee avec les nouveaux beneficiaires inscrits.

-- ── Etape 2 : trigger de validation a l'insertion ─────────
DROP TRIGGER IF EXISTS trg_check_cin_before_insert;

DELIMITER $$

CREATE TRIGGER trg_check_cin_before_insert
BEFORE INSERT ON personne_association
FOR EACH ROW
BEGIN
    DECLARE cin_exists INT DEFAULT 0;

    -- Si jeune_cin est renseigne, il doit exister dans la table miroir
    IF NEW.jeune_cin IS NOT NULL THEN
        SELECT COUNT(*) INTO cin_exists
        FROM cin_beneficiaires_valides
        WHERE cin = NEW.jeune_cin;

        IF cin_exists = 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'jeune_cin invalide : CIN non trouve dans cin_beneficiaires_valides';
        END IF;
    END IF;
END$$

DELIMITER ;

-- ── Etape 3 : meme validation a la mise a jour ────────────
DROP TRIGGER IF EXISTS trg_check_cin_before_update;

DELIMITER $$

CREATE TRIGGER trg_check_cin_before_update
BEFORE UPDATE ON personne_association
FOR EACH ROW
BEGIN
    DECLARE cin_exists INT DEFAULT 0;

    IF NEW.jeune_cin IS NOT NULL AND
       (OLD.jeune_cin IS NULL OR NEW.jeune_cin <> OLD.jeune_cin) THEN
        SELECT COUNT(*) INTO cin_exists
        FROM cin_beneficiaires_valides
        WHERE cin = NEW.jeune_cin;

        IF cin_exists = 0 THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'jeune_cin invalide : CIN non trouve dans cin_beneficiaires_valides';
        END IF;
    END IF;
END$$

DELIMITER ;

-- ============================================================
-- Verification rapide
-- ============================================================
-- Doit echouer (CIN inexistant) :
--   INSERT INTO personne_association
--     (association_id, jeune_cin, nom, prenom, genre, type_personne, role, date_debut, statut)
--   VALUES (1, 'ZZ999999', 'Test', 'Test', 'Homme', 'Membre_Bureau', 'Membre', CURDATE(), 'Actif');
--
-- Doit reussir (jeune_cin NULL, lien optionnel non renseigne) :
--   INSERT INTO personne_association
--     (association_id, jeune_cin, nom, prenom, genre, type_personne, role, date_debut, statut)
--   VALUES (1, NULL, 'Test', 'Test', 'Homme', 'Membre_Bureau', 'Membre', CURDATE(), 'Actif');

SELECT 'Trigger de validation cross-SGBD installe avec succes sur personne_association.' AS message;
