-- ============================================================
--  BASE SOURCE — JAM3IYA.MA  (Modele v3 - categories d'age mises a jour)
--  MySQL
--
--  Tables : maison_jeunes, association, personne_association,
--           colonie_vacances, activite, rapport_activite
-- ============================================================

CREATE DATABASE IF NOT EXISTS jam3iya_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE jam3iya_db;

-- Supprimer les tables si elles existent deja (ordre inverse des FK)
DROP TABLE IF EXISTS rapport_activite;
DROP TABLE IF EXISTS activite;
DROP TABLE IF EXISTS colonie_vacances;
DROP TABLE IF EXISTS personne_association;
DROP TABLE IF EXISTS association;
DROP TABLE IF EXISTS maison_jeunes;

-- ============================================================
-- TABLE : maison_jeunes
-- Centres physiques du ministere accueillant les associations
-- et leurs activites.
-- ============================================================
CREATE TABLE maison_jeunes (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    nom                 VARCHAR(200) NOT NULL,
    ville               VARCHAR(100) NOT NULL,
    region              VARCHAR(100) NOT NULL,
    adresse             VARCHAR(255),
    date_ouverture      DATE,
    capacite_accueil    INT,
    statut              VARCHAR(20)  NOT NULL DEFAULT 'Active'
                          CHECK (statut IN ('Active', 'Fermee', 'Renovation'))
) ENGINE=InnoDB;

-- ============================================================
-- TABLE : association
-- Rattachee a une maison de jeunes via une convention signee.
-- Finances (recettes, depenses, subvention) integrees directement
-- (pas de table Budget separee).
-- ============================================================
CREATE TABLE association (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    nom                  VARCHAR(200) NOT NULL,
    type                 VARCHAR(100),
    domaine_activite     VARCHAR(100) NOT NULL,
    maison_jeunes_id     INT NOT NULL,
    date_creation        DATE NOT NULL,
    date_convention      DATE,
    statut               VARCHAR(20)  NOT NULL DEFAULT 'Active'
                          CHECK (statut IN ('Active', 'Inactive', 'Suspendue')),
    nb_membres           INT DEFAULT 0,
    formulaire_adhesion  VARCHAR(255),          -- reference/lien du formulaire
    recettes_annuelles   DECIMAL(12,2) DEFAULT 0.00,
    depenses_annuelles   DECIMAL(12,2) DEFAULT 0.00,
    subvention_etat      DECIMAL(12,2) DEFAULT 0.00,
    annee_exercice       SMALLINT,

    FOREIGN KEY (maison_jeunes_id) REFERENCES maison_jeunes(id)
) ENGINE=InnoDB;

CREATE INDEX idx_assoc_maison ON association(maison_jeunes_id);

-- ============================================================
-- TABLE : personne_association
-- Fusion de Membre_Bureau + Animateur : une seule table avec
-- type_personne pour distinguer les deux roles.
-- Le lien vers PassJeunes se fait via jeune_cin (optionnel).
-- ============================================================
CREATE TABLE personne_association (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    association_id       INT NOT NULL,
    maison_jeunes_id     INT,                   -- rempli si type_personne = Animateur
    jeune_cin            VARCHAR(20),           -- lien optionnel vers Beneficiaire.cin
    nom                  VARCHAR(100) NOT NULL,
    prenom               VARCHAR(100) NOT NULL,
    genre                VARCHAR(10)  NOT NULL,
    type_personne        VARCHAR(20)  NOT NULL DEFAULT 'Membre_Bureau'
                          CHECK (type_personne IN ('Membre_Bureau', 'Animateur')),
    role                 VARCHAR(50)  NOT NULL DEFAULT 'Membre_Bureau'
                          CHECK (role IN ('President', 'Vice_President', 'Tresorier',
                                          'Secretaire', 'Animateur')),
    specialite           VARCHAR(100),          -- rempli si type_personne = Animateur
    date_debut           DATE NOT NULL,
    statut               VARCHAR(20)  NOT NULL DEFAULT 'Actif'
                          CHECK (statut IN ('Actif', 'Inactif')),

    FOREIGN KEY (association_id)   REFERENCES association(id),
    FOREIGN KEY (maison_jeunes_id) REFERENCES maison_jeunes(id)
) ENGINE=InnoDB;

CREATE INDEX idx_personne_assoc  ON personne_association(association_id);
CREATE INDEX idx_personne_maison ON personne_association(maison_jeunes_id);
CREATE INDEX idx_personne_cin    ON personne_association(jeune_cin);
CREATE INDEX idx_personne_type   ON personne_association(type_personne);

-- ============================================================
-- TABLE : colonie_vacances
-- Campus saisonniers (colonies) organises pendant les vacances.
-- ============================================================
CREATE TABLE colonie_vacances (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    nom                  VARCHAR(200) NOT NULL,
    ville                VARCHAR(100) NOT NULL,
    region               VARCHAR(100) NOT NULL,
    saison               VARCHAR(20)  NOT NULL
                          CHECK (saison IN ('Ete', 'Hiver', 'Printemps')),
    annee                SMALLINT     NOT NULL,
    categorie_cible      VARCHAR(100) NOT NULL DEFAULT 'Enfants 7-15 ans'
                          CHECK (categorie_cible IN ('Enfants 7-15 ans', 'Adolescents 15-18 ans', 'Enfants en situation de handicap')),
    duree_jours          INT
) ENGINE=InnoDB;

CREATE INDEX idx_colonie_annee ON colonie_vacances(annee);

-- ============================================================
-- TABLE : activite  (ex-projet)
-- Activites menees par les associations dans leur maison de
-- jeunes. Peut etre reguliere ou saisonniere (rattachee a une
-- colonie de vacances / campus).
-- ============================================================
CREATE TABLE activite (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    association_id       INT NOT NULL,
    maison_jeunes_id     INT NOT NULL,
    titre                VARCHAR(200) NOT NULL,
    description          TEXT,
    type_activite        VARCHAR(30)  NOT NULL DEFAULT 'Reguliere'
                          CHECK (type_activite IN ('Reguliere', 'Saisonniere_Campus')),
    colonie_vacances_id  INT,                   -- rempli si type_activite = Saisonniere_Campus
    budget               DECIMAL(12,2) DEFAULT 0.00,
    date_debut           DATE NOT NULL,
    date_fin             DATE,
    statut               VARCHAR(20)  NOT NULL DEFAULT 'Planifiee'
                          CHECK (statut IN ('Planifiee', 'En cours', 'Terminee', 'Annulee')),

    FOREIGN KEY (association_id)      REFERENCES association(id),
    FOREIGN KEY (maison_jeunes_id)    REFERENCES maison_jeunes(id),
    FOREIGN KEY (colonie_vacances_id) REFERENCES colonie_vacances(id)
) ENGINE=InnoDB;

CREATE INDEX idx_activite_assoc   ON activite(association_id);
CREATE INDEX idx_activite_maison  ON activite(maison_jeunes_id);
CREATE INDEX idx_activite_colonie ON activite(colonie_vacances_id);

-- ============================================================
-- TABLE : rapport_activite
-- Rapport texte + statistiques simples envoyes par les
-- associations apres chaque activite.
-- ============================================================
CREATE TABLE rapport_activite (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    activite_id          INT NOT NULL,
    date_envoi           DATE NOT NULL,
    contenu_texte        TEXT,
    nb_participants      INT,
    taux_satisfaction    DECIMAL(5,2),          -- note sur 5
    budget_consomme      DECIMAL(12,2),

    FOREIGN KEY (activite_id) REFERENCES activite(id)
) ENGINE=InnoDB;

CREATE INDEX idx_rapport_activite ON rapport_activite(activite_id);

SELECT 'Base jam3iya_db (v2) creee avec succes : maison_jeunes, association, personne_association, colonie_vacances, activite, rapport_activite.' AS message;
