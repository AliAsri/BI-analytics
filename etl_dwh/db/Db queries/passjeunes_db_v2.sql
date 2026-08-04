-- ============================================================
--  BASE SOURCE — PASSJEUNES  (Modele v2)
--  SQL Server (T-SQL)
--
--  Tables : Beneficiaire, Offre, Solde, Operation, Motatawi3
-- ============================================================

USE master;
GO

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'PassJeunesDB')
BEGIN
    CREATE DATABASE PassJeunesDB;
END
GO

USE PassJeunesDB;
GO

-- Supprimer les tables si elles existent deja (ordre inverse des FK)
IF OBJECT_ID('dbo.Motatawi3', 'U')   IS NOT NULL DROP TABLE dbo.Motatawi3;
IF OBJECT_ID('dbo.Operation', 'U')   IS NOT NULL DROP TABLE dbo.Operation;
IF OBJECT_ID('dbo.Solde', 'U')       IS NOT NULL DROP TABLE dbo.Solde;
IF OBJECT_ID('dbo.Offre', 'U')       IS NOT NULL DROP TABLE dbo.Offre;
IF OBJECT_ID('dbo.Beneficiaire', 'U') IS NOT NULL DROP TABLE dbo.Beneficiaire;
GO

-- ============================================================
-- TABLE : Beneficiaire
-- Profil des jeunes inscrits sur l'application (16-30 ans).
-- Le Pass se desactive automatiquement a 30 ans (statut_pass).
-- Inclut les profils speciaux : immigrants, subsahariens
-- naturalises, situation de handicap.
-- ============================================================
CREATE TABLE dbo.Beneficiaire (
    id                    INT IDENTITY(1,1) PRIMARY KEY,
    cin                   NVARCHAR(20)  NOT NULL UNIQUE,
    nom                   NVARCHAR(100) NOT NULL,
    prenom                NVARCHAR(100) NOT NULL,
    genre                 NVARCHAR(10)  NOT NULL,
    date_naissance        DATE          NOT NULL,
    ville                 NVARCHAR(100),
    region                NVARCHAR(100),
    email                 NVARCHAR(150),
    telephone             NVARCHAR(20),
    nationalite           NVARCHAR(50)  NOT NULL DEFAULT 'Marocaine',
    type_statut           NVARCHAR(30)  NOT NULL DEFAULT 'Marocain'
                            CHECK (type_statut IN ('Marocain', 'Immigrant_Etranger',
                                                    'Subsaharien_Naturalise', 'Marocain_Expatrie')),
    en_situation_handicap BIT           NOT NULL DEFAULT 0,
    date_inscription      DATE          NOT NULL DEFAULT GETDATE(),
    date_desactivation    DATE          NOT NULL,   -- = date_naissance + 30 ans
    statut_pass           NVARCHAR(20)  NOT NULL DEFAULT 'Actif'
                            CHECK (statut_pass IN ('Actif', 'Desactive')),

    CONSTRAINT chk_age_inscription
        CHECK (DATEDIFF(YEAR, date_naissance, date_inscription) BETWEEN 16 AND 30)
);
GO

CREATE INDEX idx_beneficiaire_region ON dbo.Beneficiaire(region);
CREATE INDEX idx_beneficiaire_statut ON dbo.Beneficiaire(statut_pass);
GO

-- ============================================================
-- TABLE : Offre
-- Catalogue reel des offres PassJeunes par partenaire.
-- Les beneficiaires/usages peuvent rester simules pour la BI,
-- mais cette table porte les offres et tarifs reels.
-- ============================================================
CREATE TABLE dbo.Offre (
    id                    INT IDENTITY(1,1) PRIMARY KEY,
    nom_partenaire        NVARCHAR(200) NOT NULL,
    categorie             NVARCHAR(100) NOT NULL,
    nom_offre             NVARCHAR(255) NOT NULL,
    description           NVARCHAR(MAX),
    conditions            NVARCHAR(MAX),
    type_avantage         NVARCHAR(50)  NOT NULL,
    valeur_avantage       DECIMAL(10,2),
    unite_avantage        NVARCHAR(20),
    tarif_pass_jeunes     NVARCHAR(100),
    tarif_public          DECIMAL(10,2),
    montant_a_debiter     DECIMAL(10,2),
    montant_a_payer       DECIMAL(10,2),
    solde_initial         DECIMAL(10,2),
    solde_mensuel         DECIMAL(10,2),
    ville                 NVARCHAR(100),
    region                NVARCHAR(100),
    actif                 BIT NOT NULL DEFAULT 1
);
GO

CREATE INDEX idx_offre_nom_partenaire ON dbo.Offre(nom_partenaire);
CREATE INDEX idx_offre_categorie      ON dbo.Offre(categorie);
GO

-- ============================================================
-- TABLE : Solde
-- Credit annuel par couple (Beneficiaire, Offre).
-- ============================================================
CREATE TABLE dbo.Solde (
    id                    INT IDENTITY(1,1) PRIMARY KEY,
    beneficiaire_id       INT NOT NULL FOREIGN KEY REFERENCES dbo.Beneficiaire(id),
    offre_id              INT NOT NULL FOREIGN KEY REFERENCES dbo.Offre(id),
    annee                 SMALLINT      NOT NULL,
    credit_initial        DECIMAL(10,2) NOT NULL,
    credit_restant        DECIMAL(10,2) NOT NULL,
    date_renouvellement   DATE          NOT NULL,

    CONSTRAINT uq_solde UNIQUE (beneficiaire_id, offre_id, annee)
);
GO

CREATE INDEX idx_solde_beneficiaire ON dbo.Solde(beneficiaire_id);
CREATE INDEX idx_solde_offre        ON dbo.Solde(offre_id);
GO

-- ============================================================
-- TABLE : Operation  (ex-Utilisation)
-- Chaque usage d'une offre. Decremente le Solde.
-- ============================================================
CREATE TABLE dbo.Operation (
    id                    INT IDENTITY(1,1) PRIMARY KEY,
    beneficiaire_id       INT NOT NULL FOREIGN KEY REFERENCES dbo.Beneficiaire(id),
    offre_id              INT NOT NULL FOREIGN KEY REFERENCES dbo.Offre(id),
    solde_id              INT          FOREIGN KEY REFERENCES dbo.Solde(id),
    categorie             NVARCHAR(100) NOT NULL,
    date_operation        DATE          NOT NULL,
    montant_reduction     DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    ville                 NVARCHAR(100)
);
GO

CREATE INDEX idx_operation_beneficiaire ON dbo.Operation(beneficiaire_id);
CREATE INDEX idx_operation_offre        ON dbo.Operation(offre_id);
CREATE INDEX idx_operation_date         ON dbo.Operation(date_operation);
GO

-- ============================================================
-- TABLE : Motatawi3
-- Programme national de volontariat, reserve aux 18-22 ans.
-- Inscription via l'app Pass Jeunes (lien direct beneficiaire_id).
-- Processus : formulaire -> charte -> depot dossier -> validation.
-- ============================================================
CREATE TABLE dbo.Motatawi3 (
    id                      INT IDENTITY(1,1) PRIMARY KEY,
    beneficiaire_id         INT NOT NULL FOREIGN KEY REFERENCES dbo.Beneficiaire(id),
    edition                 NVARCHAR(50)  NOT NULL,
    region                  NVARCHAR(100) NOT NULL,
    domaine_volontariat     NVARCHAR(100) NOT NULL,
    niveau_etudes           NVARCHAR(50)  NOT NULL DEFAULT 'Non_Scolarise' CHECK (niveau_etudes IN ('Lycee', 'Bac', 'Licence', 'Master', 'Doctorat', 'Non_Scolarise')),
    code_suivi              VARCHAR(20)   NOT NULL UNIQUE,
    date_inscription        DATE          NOT NULL,
    date_depot_dossier      DATE,
    statut_dossier          NVARCHAR(20)  NOT NULL DEFAULT 'Soumis'
                              CHECK (statut_dossier IN ('Soumis', 'En_Cours', 'Valide', 'Rejete')),
    statut                  NVARCHAR(20)  NOT NULL DEFAULT 'Actif'
                              CHECK (statut IN ('Actif', 'Termine'))
);
GO

CREATE INDEX idx_motatawi3_beneficiaire ON dbo.Motatawi3(beneficiaire_id);
CREATE INDEX idx_motatawi3_statut       ON dbo.Motatawi3(statut_dossier);
GO

PRINT 'Base PassJeunesDB (v2) creee avec succes : Beneficiaire, Offre, Solde, Operation, Motatawi3.';
GO
