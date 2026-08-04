-- ============================================================
--  BASE STAGING — STAGING_MJCC
--  SQL Server (T-SQL)
--
--  Tables staging (sans FK, sans CHECK) pour le pipeline ETL.
--  Sources : PassJeunesDB (SQL Server) + jam3iya_db (MySQL)
--
--  Usage : executer ce script dans SSMS avant de configurer
--          les Data Flow Tasks dans SSIS.
-- ============================================================

USE master;
GO

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'STAGING_MJCC')
BEGIN
    CREATE DATABASE STAGING_MJCC;
END
GO

USE STAGING_MJCC;
GO

-- ============================================================
--  TABLE DE LOG ETL
--  Trace chaque execution du pipeline (nb lignes, statut, erreurs)
-- ============================================================
IF OBJECT_ID('dbo.etl_log', 'U') IS NOT NULL DROP TABLE dbo.etl_log;
GO

CREATE TABLE dbo.etl_log (
    id                INT IDENTITY(1,1) PRIMARY KEY,
    nom_table         NVARCHAR(100)  NOT NULL,
    source            NVARCHAR(50)   NOT NULL,      -- 'PassJeunesDB' ou 'jam3iya_db'
    date_execution    DATETIME       NOT NULL DEFAULT GETDATE(),
    nb_lignes_source  INT            DEFAULT 0,
    nb_lignes_insert  INT            DEFAULT 0,
    statut            NVARCHAR(20)   NOT NULL DEFAULT 'En cours',  -- En cours, Succes, Erreur
    message_erreur    NVARCHAR(MAX),
    duree_secondes    INT
);
GO

-- ============================================================
--  STAGING — PASSJEUNES (5 tables)
-- ============================================================

-- ── stg_passjeunes_beneficiaire ──────────────────────────
IF OBJECT_ID('dbo.stg_passjeunes_beneficiaire', 'U') IS NOT NULL DROP TABLE dbo.stg_passjeunes_beneficiaire;
GO

CREATE TABLE dbo.stg_passjeunes_beneficiaire (
    id                    INT,
    cin                   NVARCHAR(20),
    nom                   NVARCHAR(100),
    prenom                NVARCHAR(100),
    genre                 NVARCHAR(10),
    date_naissance        DATE,
    ville                 NVARCHAR(100),
    region                NVARCHAR(100),
    email                 NVARCHAR(150),
    telephone             NVARCHAR(20),
    nationalite           NVARCHAR(50),
    type_statut           NVARCHAR(30),
    en_situation_handicap BIT,
    date_inscription      DATE,
    date_desactivation    DATE,
    statut_pass           NVARCHAR(20)
);
GO


-- ── stg_passjeunes_offre ─────────────────────────────────
IF OBJECT_ID('dbo.stg_passjeunes_offre', 'U') IS NOT NULL DROP TABLE dbo.stg_passjeunes_offre;
GO

CREATE TABLE dbo.stg_passjeunes_offre (
    id                    INT,
    nom_partenaire        NVARCHAR(200),
    categorie             NVARCHAR(100),
    nom_offre             NVARCHAR(255),
    description           NVARCHAR(MAX),
    conditions            NVARCHAR(MAX),
    type_avantage         NVARCHAR(50),
    valeur_avantage       DECIMAL(10,2),
    unite_avantage        NVARCHAR(20),
    tarif_pass_jeunes     DECIMAL(10,2),
    tarif_public          DECIMAL(10,2),
    montant_a_debiter     DECIMAL(10,2),
    montant_a_payer       DECIMAL(10,2),
    solde_initial         DECIMAL(10,2),
    solde_mensuel         DECIMAL(10,2),
    ville                 NVARCHAR(100),
    region                NVARCHAR(100),
    actif                 BIT
);
GO

-- ── stg_passjeunes_solde ─────────────────────────────────
IF OBJECT_ID('dbo.stg_passjeunes_solde', 'U') IS NOT NULL DROP TABLE dbo.stg_passjeunes_solde;
GO

CREATE TABLE dbo.stg_passjeunes_solde (
    id                    INT,
    beneficiaire_id       INT,
    offre_id              INT,
    annee                 SMALLINT,
    credit_initial        DECIMAL(10,2),
    credit_restant        DECIMAL(10,2),
    date_renouvellement   DATE
);
GO

-- ── stg_passjeunes_operation ─────────────────────────────
IF OBJECT_ID('dbo.stg_passjeunes_operation', 'U') IS NOT NULL DROP TABLE dbo.stg_passjeunes_operation;
GO

CREATE TABLE dbo.stg_passjeunes_operation (
    id                    INT,
    beneficiaire_id       INT,
    offre_id              INT,
    solde_id              INT,
    categorie             NVARCHAR(100),
    date_operation        DATE,
    montant_reduction     DECIMAL(10,2),
    ville                 NVARCHAR(100)
);
GO

-- ── stg_passjeunes_motatawi3 ─────────────────────────────
IF OBJECT_ID('dbo.stg_passjeunes_motatawi3', 'U') IS NOT NULL DROP TABLE dbo.stg_passjeunes_motatawi3;
GO

CREATE TABLE dbo.stg_passjeunes_motatawi3 (
    id                      INT,
    beneficiaire_id         INT,
    edition                 NVARCHAR(50),
    region                  NVARCHAR(100),
    domaine_volontariat     NVARCHAR(100),
    niveau_etudes           NVARCHAR(50),
    code_suivi              VARCHAR(20),
    date_inscription        DATE,
    date_depot_dossier      DATE,
    statut_dossier          NVARCHAR(20),
    statut                  NVARCHAR(20)
);
GO

-- ============================================================
--  STAGING — JAM3IYA (6 tables)
--  Types MySQL traduits en SQL Server equivalents
-- ============================================================

-- ── stg_jam3iya_maison_jeunes ────────────────────────────
IF OBJECT_ID('dbo.stg_jam3iya_maison_jeunes', 'U') IS NOT NULL DROP TABLE dbo.stg_jam3iya_maison_jeunes;
GO

CREATE TABLE dbo.stg_jam3iya_maison_jeunes (
    id                  INT PRIMARY KEY,
    nom                 NVARCHAR(200),
    ville               NVARCHAR(100),
    region              NVARCHAR(100),
    adresse             NVARCHAR(255),
    date_ouverture      DATE,
    capacite_accueil    INT,
    statut              NVARCHAR(20)
);
GO

-- ── stg_jam3iya_association ──────────────────────────────
IF OBJECT_ID('dbo.stg_jam3iya_association', 'U') IS NOT NULL DROP TABLE dbo.stg_jam3iya_association;
GO

CREATE TABLE dbo.stg_jam3iya_association (
    id                   INT PRIMARY KEY,
    nom                  NVARCHAR(200),
    type                 NVARCHAR(100),
    domaine_activite     NVARCHAR(100),
    maison_jeunes_id     INT,
    date_creation        DATE,
    date_convention      DATE,
    statut               NVARCHAR(20),
    nb_membres           INT,
    formulaire_adhesion  NVARCHAR(255),
    recettes_annuelles   DECIMAL(12,2),
    depenses_annuelles   DECIMAL(12,2),
    subvention_etat      DECIMAL(12,2),
    annee_exercice       SMALLINT
);
GO

-- ── stg_jam3iya_personne_association ─────────────────────
IF OBJECT_ID('dbo.stg_jam3iya_personne_association', 'U') IS NOT NULL DROP TABLE dbo.stg_jam3iya_personne_association;
GO

CREATE TABLE dbo.stg_jam3iya_personne_association (
    id                   INT PRIMARY KEY,
    association_id       INT,
    maison_jeunes_id     INT,
    jeune_cin            NVARCHAR(20),
    nom                  NVARCHAR(100),
    prenom               NVARCHAR(100),
    genre                NVARCHAR(10),
    type_personne        NVARCHAR(20),
    role                 NVARCHAR(50),
    specialite           NVARCHAR(100),
    date_debut           DATE,
    statut               NVARCHAR(20)
);
GO

-- ── stg_jam3iya_colonie_vacances ─────────────────────────
IF OBJECT_ID('dbo.stg_jam3iya_colonie_vacances', 'U') IS NOT NULL DROP TABLE dbo.stg_jam3iya_colonie_vacances;
GO

CREATE TABLE dbo.stg_jam3iya_colonie_vacances (
    id                   INT PRIMARY KEY,
    nom                  NVARCHAR(200),
    ville                NVARCHAR(100),
    region               NVARCHAR(100),
    saison               NVARCHAR(20),
    annee                SMALLINT,
    categorie_cible      NVARCHAR(100),
    duree_jours          INT
);
GO

-- ── stg_jam3iya_activite ─────────────────────────────────
IF OBJECT_ID('dbo.stg_jam3iya_activite', 'U') IS NOT NULL DROP TABLE dbo.stg_jam3iya_activite;
GO

CREATE TABLE dbo.stg_jam3iya_activite (
    id                   INT PRIMARY KEY,
    association_id       INT,
    maison_jeunes_id     INT,
    titre                NVARCHAR(200),
    description          NVARCHAR(MAX),
    type_activite        NVARCHAR(30),
    colonie_vacances_id  INT,
    budget               DECIMAL(12,2),
    date_debut           DATE,
    date_fin             DATE,
    statut               NVARCHAR(20)
);
GO

-- ── stg_jam3iya_rapport_activite ─────────────────────────
IF OBJECT_ID('dbo.stg_jam3iya_rapport_activite', 'U') IS NOT NULL DROP TABLE dbo.stg_jam3iya_rapport_activite;
GO

CREATE TABLE dbo.stg_jam3iya_rapport_activite (
    id                   INT,
    activite_id          INT,
    date_envoi           DATE,
    contenu_texte        NVARCHAR(MAX),
    nb_participants      INT,
    taux_satisfaction    DECIMAL(5,2),
    budget_consomme      DECIMAL(12,2)
);
GO

PRINT '========================================================';
PRINT '  STAGING_MJCC creee avec succes !';
PRINT '  - 5 tables stg_passjeunes_*';
PRINT '  - 6 tables stg_jam3iya_*';
PRINT '  - 1 table etl_log';
PRINT '  - Aucune contrainte FK/CHECK (staging)';
PRINT '========================================================';
GO
