-- ============================================================
--  DATA WAREHOUSE — DWH_MJCC
--  SQL Server (T-SQL) — Schema en etoile
--
--  Dimensions : dim_temps, dim_region, dim_beneficiaire,
--               dim_offre, dim_association,
--               dim_maison_jeunes, dim_domaine_volontariat
--
--  Faits :     fait_operations, fait_solde,
--              fait_activites, fait_motatawi3
--
--  Sources :   PassJeunesDB (SQL Server) + jam3iya_db (MySQL)
--              via STAGING_MJCC
-- ============================================================

USE master;
GO

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'DWH_MJCC')
BEGIN
    CREATE DATABASE DWH_MJCC;
END
GO

USE DWH_MJCC;
GO

-- ============================================================
--  DROP des tables existantes (ordre inverse des FK)
-- ============================================================
IF OBJECT_ID('dbo.fait_motatawi3', 'U')   IS NOT NULL DROP TABLE dbo.fait_motatawi3;
IF OBJECT_ID('dbo.fait_activites', 'U')   IS NOT NULL DROP TABLE dbo.fait_activites;
IF OBJECT_ID('dbo.fait_solde', 'U')       IS NOT NULL DROP TABLE dbo.fait_solde;
IF OBJECT_ID('dbo.fait_operations', 'U')  IS NOT NULL DROP TABLE dbo.fait_operations;
IF OBJECT_ID('dbo.dim_offre', 'U')        IS NOT NULL DROP TABLE dbo.dim_offre;
IF OBJECT_ID('dbo.dim_beneficiaire', 'U') IS NOT NULL DROP TABLE dbo.dim_beneficiaire;
IF OBJECT_ID('dbo.dim_association', 'U')  IS NOT NULL DROP TABLE dbo.dim_association;
IF OBJECT_ID('dbo.dim_maison_jeunes', 'U') IS NOT NULL DROP TABLE dbo.dim_maison_jeunes;
IF OBJECT_ID('dbo.dim_region', 'U')       IS NOT NULL DROP TABLE dbo.dim_region;
IF OBJECT_ID('dbo.dim_temps', 'U')        IS NOT NULL DROP TABLE dbo.dim_temps;
GO

-- ############################################################
--  DIMENSIONS
-- ############################################################

-- ============================================================
--  dim_temps — Dimension temporelle
--  Hierarchie : Annee > Trimestre > Mois > Jour
--  Periode couverte : 2018-01-01 a 2026-12-31
-- ============================================================
CREATE TABLE dbo.dim_temps (
    temps_id        INT           PRIMARY KEY,   -- format YYYYMMDD
    date_complete   DATE          NOT NULL UNIQUE,
    jour            TINYINT       NOT NULL,
    mois            TINYINT       NOT NULL,
    annee           SMALLINT      NOT NULL,
    trimestre       TINYINT       NOT NULL,
    nom_jour        NVARCHAR(10)  NOT NULL,      -- Lundi, Mardi...
    nom_mois        NVARCHAR(10)  NOT NULL,      -- Janvier, Fevrier...
    jour_semaine    TINYINT       NOT NULL,       -- 1=Lundi ... 7=Dimanche
    semaine_annee   TINYINT       NOT NULL,
    est_weekend     BIT           NOT NULL DEFAULT 0
);
GO

-- Remplissage automatique de dim_temps (2018-2026)
WITH Dates AS (
    SELECT CAST('2018-01-01' AS DATE) AS d
    UNION ALL
    SELECT DATEADD(DAY, 1, d)
    FROM Dates
    WHERE d <= '2026-12-31'
)
INSERT INTO dbo.dim_temps (
    temps_id, date_complete, jour, mois, annee, trimestre,
    nom_jour, nom_mois, jour_semaine, semaine_annee, est_weekend
)
SELECT 
    CONVERT(INT, FORMAT(d, 'yyyyMMdd')),
    d,
    DAY(d),
    MONTH(d),
    YEAR(d),
    DATEPART(QUARTER, d),
    CASE DATEPART(WEEKDAY, d)
        WHEN 1 THEN 'Dimanche' WHEN 2 THEN 'Lundi' WHEN 3 THEN 'Mardi'
        WHEN 4 THEN 'Mercredi' WHEN 5 THEN 'Jeudi' WHEN 6 THEN 'Vendredi'
        WHEN 7 THEN 'Samedi'
    END,
    CASE MONTH(d)
        WHEN 1  THEN 'Janvier'   WHEN 2  THEN 'Fevrier'  WHEN 3  THEN 'Mars'
        WHEN 4  THEN 'Avril'     WHEN 5  THEN 'Mai'      WHEN 6  THEN 'Juin'
        WHEN 7  THEN 'Juillet'   WHEN 8  THEN 'Aout'     WHEN 9  THEN 'Septembre'
        WHEN 10 THEN 'Octobre'   WHEN 11 THEN 'Novembre' WHEN 12 THEN 'Decembre'
    END,
    CASE WHEN DATEPART(WEEKDAY, d) = 1 THEN 7 ELSE DATEPART(WEEKDAY, d) - 1 END,
    DATEPART(ISO_WEEK, d),
    CASE WHEN DATEPART(WEEKDAY, d) IN (1, 7) THEN 1 ELSE 0 END
FROM Dates
OPTION (MAXRECURSION 4000);
GO

-- ============================================================
--  dim_region — Dimension geographique
--  Hierarchie : Zone Geo > Region > Ville
--  Regroupe les 12 regions du Maroc + villes
-- ============================================================
CREATE TABLE dbo.dim_region (
    region_id       INT IDENTITY(1,1) PRIMARY KEY,
    ville           NVARCHAR(100) NOT NULL,
    region          NVARCHAR(100) NOT NULL,
    zone_geo        NVARCHAR(50)  NOT NULL,   -- Nord, Centre, Sud, Est, Sahara

    CONSTRAINT uq_dim_region UNIQUE (ville, region)
);
GO

-- Insertion des zones geographiques par region
-- (sera peuplee lors du chargement ETL a partir des villes reelles)

-- ============================================================
--  dim_beneficiaire — Dimension jeune/beneficiaire
--  Source : PassJeunesDB.dbo.Beneficiaire
-- ============================================================
CREATE TABLE dbo.dim_beneficiaire (
    beneficiaire_id     INT IDENTITY(1,1) PRIMARY KEY,
    source_id           INT           NOT NULL UNIQUE,  -- id original
    cin                 NVARCHAR(20)  NOT NULL,
    nom                 NVARCHAR(100) NOT NULL,
    prenom              NVARCHAR(100) NOT NULL,
    genre               NVARCHAR(10)  NOT NULL,
    date_naissance      DATE          NOT NULL,
    nationalite         NVARCHAR(50)  NOT NULL,
    type_statut         NVARCHAR(30)  NOT NULL,
    en_situation_handicap BIT         NOT NULL,
    statut_pass         NVARCHAR(20)  NOT NULL,
    tranche_age         NVARCHAR(20)  NOT NULL,       -- '16-18', '19-22', '23-25', '26-30'
    date_inscription    DATE          NOT NULL,
    est_membre_association BIT        NOT NULL DEFAULT 0,
    date_chargement     DATETIME      NOT NULL DEFAULT GETDATE()
);
GO

-- ============================================================
--  dim_offre — Dimension offres PassJeunes (inclut infos partenaire)
--  Source : PassJeunesDB.dbo.Offre_PassJeunes
-- ============================================================
CREATE TABLE dbo.dim_offre (
    offre_id            INT IDENTITY(1,1) PRIMARY KEY,
    source_id           INT           NOT NULL UNIQUE,
    -- Infos Partenaire (fusionnees dans offre)
    nom_partenaire      NVARCHAR(200) NOT NULL,
    secteur             NVARCHAR(100),
    -- Infos Offre
    categorie           NVARCHAR(100) NOT NULL,
    nom_offre           NVARCHAR(255) NOT NULL,
    description         NVARCHAR(MAX),
    conditions          NVARCHAR(MAX),
    type_avantage       NVARCHAR(50)  NOT NULL,
    valeur_avantage     DECIMAL(10,2),
    unite_avantage      NVARCHAR(20),
    tarif_pass_jeunes   DECIMAL(10,2),
    tarif_public        DECIMAL(10,2),
    montant_a_debiter   DECIMAL(10,2),
    montant_a_payer     DECIMAL(10,2),
    solde_initial       DECIMAL(10,2),
    solde_mensuel       DECIMAL(10,2),
    ville_offre         NVARCHAR(100),
    region_offre        NVARCHAR(100),
    actif               BIT           NOT NULL,
    date_chargement     DATETIME      NOT NULL DEFAULT GETDATE()
);
GO

-- ============================================================
--  dim_association — Dimension associations
--  Source : jam3iya_db.association
-- ============================================================
CREATE TABLE dbo.dim_association (
    association_id      INT IDENTITY(1,1) PRIMARY KEY,
    source_id           INT           NOT NULL UNIQUE,
    nom                 NVARCHAR(200) NOT NULL,
    type                NVARCHAR(100),
    domaine_activite    NVARCHAR(100) NOT NULL,
    statut              NVARCHAR(20)  NOT NULL,
    nb_membres          INT           DEFAULT 0,
    date_creation       DATE          NOT NULL,
    date_chargement     DATETIME      NOT NULL DEFAULT GETDATE()
);
GO

-- ============================================================
--  dim_maison_jeunes — Dimension maisons de jeunes
--  Source : jam3iya_db.maison_jeunes
-- ============================================================
CREATE TABLE dbo.dim_maison_jeunes (
    maison_id           INT IDENTITY(1,1) PRIMARY KEY,
    source_id           INT           NOT NULL UNIQUE,
    nom                 NVARCHAR(200) NOT NULL,
    capacite_accueil    INT,
    statut              NVARCHAR(20)  NOT NULL,
    date_ouverture      DATE,
    date_chargement     DATETIME      NOT NULL DEFAULT GETDATE()
);
GO


-- ############################################################
--  TABLES DE FAITS
-- ############################################################

-- ============================================================
--  fait_operations — Utilisations des offres PassJeunes
--  Grain : 1 ligne = 1 operation (usage d'une offre)
--  Mesures : montant_reduction, nb_operations (compteur)
--  Source : PassJeunesDB.dbo.Operation
-- ============================================================
CREATE TABLE dbo.fait_operations (
    operation_id        INT IDENTITY(1,1) PRIMARY KEY,
    source_id           INT           NOT NULL,
    -- Cles etrangeres (dimensions)
    temps_id            INT           NOT NULL FOREIGN KEY REFERENCES dbo.dim_temps(temps_id),
    region_id           INT           NOT NULL FOREIGN KEY REFERENCES dbo.dim_region(region_id),
    beneficiaire_id     INT           NOT NULL FOREIGN KEY REFERENCES dbo.dim_beneficiaire(beneficiaire_id),
    offre_id            INT           NOT NULL FOREIGN KEY REFERENCES dbo.dim_offre(offre_id),
    -- Mesures
    montant_reduction   DECIMAL(10,2) NOT NULL,
    nb_operations       INT           NOT NULL DEFAULT 1
);
GO

CREATE INDEX idx_fait_op_temps ON dbo.fait_operations(temps_id);
CREATE INDEX idx_fait_op_region ON dbo.fait_operations(region_id);
CREATE INDEX idx_fait_op_benef ON dbo.fait_operations(beneficiaire_id);
CREATE INDEX idx_fait_op_offre ON dbo.fait_operations(offre_id);
GO

-- ============================================================
--  fait_solde — Credits annuels par beneficiaire/partenaire
--  Grain : 1 ligne = 1 solde annuel (benef x offre x annee)
--  Mesures : credit_initial, credit_restant, credit_consomme
--  Source : PassJeunesDB.dbo.Solde
-- ============================================================
CREATE TABLE dbo.fait_solde (
    solde_id            INT IDENTITY(1,1) PRIMARY KEY,
    source_id           INT           NOT NULL,
    -- Cles etrangeres
    temps_id            INT           NOT NULL FOREIGN KEY REFERENCES dbo.dim_temps(temps_id),
    beneficiaire_id     INT           NOT NULL FOREIGN KEY REFERENCES dbo.dim_beneficiaire(beneficiaire_id),
    offre_id            INT           NOT NULL FOREIGN KEY REFERENCES dbo.dim_offre(offre_id),
    -- Mesures
    annee               SMALLINT      NOT NULL,
    credit_initial      DECIMAL(10,2) NOT NULL,
    credit_restant      DECIMAL(10,2) NOT NULL,
    credit_consomme     AS (credit_initial - credit_restant) PERSISTED   -- colonne calculee
);
GO

CREATE INDEX idx_fait_solde_temps ON dbo.fait_solde(temps_id);
CREATE INDEX idx_fait_solde_benef ON dbo.fait_solde(beneficiaire_id);
CREATE INDEX idx_fait_solde_offre ON dbo.fait_solde(offre_id);
GO

-- ============================================================
--  fait_activites — Activites des associations
--  Grain : 1 ligne = 1 activite avec son rapport
--  Mesures : budget, nb_participants, taux_satisfaction,
--            budget_consomme
--  Source : jam3iya_db.activite + rapport_activite
-- ============================================================
CREATE TABLE dbo.fait_activites (
    activite_id         INT IDENTITY(1,1) PRIMARY KEY,
    source_id           INT           NOT NULL,
    -- Cles etrangeres
    temps_id            INT           NOT NULL FOREIGN KEY REFERENCES dbo.dim_temps(temps_id),
    region_id           INT           NOT NULL FOREIGN KEY REFERENCES dbo.dim_region(region_id),
    association_id      INT           NOT NULL FOREIGN KEY REFERENCES dbo.dim_association(association_id),
    maison_id           INT           NOT NULL FOREIGN KEY REFERENCES dbo.dim_maison_jeunes(maison_id),
    -- Attributs descriptifs
    type_activite       NVARCHAR(30)  NOT NULL,
    statut              NVARCHAR(20)  NOT NULL,
    -- Mesures
    budget              DECIMAL(12,2) NOT NULL DEFAULT 0,
    nb_participants     INT           DEFAULT 0,
    taux_satisfaction   DECIMAL(5,2)  DEFAULT 0,
    budget_consomme     DECIMAL(12,2) DEFAULT 0,
    duree_jours         INT           DEFAULT 0
);
GO

CREATE INDEX idx_fait_act_temps ON dbo.fait_activites(temps_id);
CREATE INDEX idx_fait_act_region ON dbo.fait_activites(region_id);
CREATE INDEX idx_fait_act_assoc ON dbo.fait_activites(association_id);
CREATE INDEX idx_fait_act_maison ON dbo.fait_activites(maison_id);
GO

-- ============================================================
--  fait_motatawi3 — Programme de volontariat
--  Grain : 1 ligne = 1 inscription Motatawi3
--  Source : PassJeunesDB.dbo.Motatawi3
-- ============================================================
CREATE TABLE dbo.fait_motatawi3 (
    motatawi3_id        INT IDENTITY(1,1) PRIMARY KEY,
    source_id           INT           NOT NULL,
    -- Cles etrangeres
    temps_id            INT           NOT NULL FOREIGN KEY REFERENCES dbo.dim_temps(temps_id),
    region_id           INT           NOT NULL FOREIGN KEY REFERENCES dbo.dim_region(region_id),
    beneficiaire_id     INT           NOT NULL FOREIGN KEY REFERENCES dbo.dim_beneficiaire(beneficiaire_id),
    -- Attributs descriptifs
    edition             NVARCHAR(50)  NOT NULL,
    domaine_volontariat NVARCHAR(100) NOT NULL,
    niveau_etudes       NVARCHAR(50)  NOT NULL DEFAULT 'Non_Scolarise',
    statut_dossier      NVARCHAR(20)  NOT NULL,
    statut              NVARCHAR(20)  NOT NULL
);
GO

CREATE INDEX idx_fait_mot_temps ON dbo.fait_motatawi3(temps_id);
CREATE INDEX idx_fait_mot_region ON dbo.fait_motatawi3(region_id);
CREATE INDEX idx_fait_mot_benef ON dbo.fait_motatawi3(beneficiaire_id);
GO

-- ============================================================
--  MESSAGE DE CONFIRMATION
-- ============================================================
PRINT '========================================================';
PRINT '  DWH_MJCC cree avec succes !';
PRINT '  DIMENSIONS :';
PRINT '    - dim_temps          (remplie : 2018-2026)';
PRINT '    - dim_region         (a peupler via ETL)';
PRINT '    - dim_beneficiaire   (a peupler via ETL)';
PRINT '    - dim_offre          (a peupler via ETL)';
PRINT '    - dim_association    (a peupler via ETL)';
PRINT '    - dim_maison_jeunes  (a peupler via ETL)';
PRINT '  FAITS :';
PRINT '    - fait_operations    (a peupler via ETL)';
PRINT '    - fait_solde         (a peupler via ETL)';
PRINT '    - fait_activites     (a peupler via ETL)';
PRINT '    - fait_motatawi3     (a peupler via ETL)';
PRINT '========================================================';
GO
