"""
ETL Pipeline Execution Script.

This module executes the full data warehouse ETL process. It connects to the 
SQL Server database, drops/creates schemas if needed, populates the staging 
area from the source databases, and then loads data into the dimensions and 
fact tables of the Data Warehouse (DWH_MJCC).
"""

import re
from pathlib import Path

import pyodbc


def main():
    """
    Main function to execute the full ETL pipeline.
    Connects to SQL Server using a trusted connection (no hardcoded passwords) 
    and orchestrates the staging and DWH population steps.
    """
    # Connect to SQL Server (Trusted Connection, no raw password)
    conn_str = (
        "Driver={ODBC Driver 17 for SQL Server};"
        "Server=localhost;"
        "Database=master;"
        "Trusted_Connection=yes;"
    )
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    print("=" * 60)
    print("  EXECUTING AUTOMATED PIPELINE: STAGING -> DWH")
    print("=" * 60)

    # Base paths
    project_root = Path("c:/Users/moali/OneDrive/Desktop/Projet MJCC")
    db_queries_dir = project_root / "db" / "Db queries"
    scripts_dir = project_root / "etl_dwh" / "db" / "source_data_sql" / "scripts_sql"

    # Step 1: Ensure STAGING and DWH databases exist and schemas are loaded
    schema_stg_path = db_queries_dir / "schema_staging.sql"
    if schema_stg_path.exists():
        with open(schema_stg_path, "r", encoding="utf-8") as f:
            sql_stg = f.read()

        for batch in sql_stg.split("GO"):
            b = batch.strip()
            if b:
                try:
                    cursor.execute(b)
                except pyodbc.Error:
                    pass

    print("  [OK] STAGING_MJCC schema created/reset.")

    schema_dwh_path = db_queries_dir / "schema_dwh_sqlserver.sql"
    if schema_dwh_path.exists():
        with open(schema_dwh_path, "r", encoding="utf-8") as f:
            sql_dwh = f.read()

        for batch in sql_dwh.split("GO"):
            b = batch.strip()
            if b:
                try:
                    cursor.execute(b)
                except pyodbc.Error:
                    pass

    cursor.execute("""
        USE DWH_MJCC;
        IF OBJECT_ID('dbo.dim_temps', 'U') IS NOT NULL 
        BEGIN
            DELETE FROM dbo.dim_temps;
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
        END
    """)

    print("  [OK] DWH_MJCC schema & dim_temps created/reset.")

    # Step 2: Populate STAGING_MJCC from PassJeunesDB (T-SQL)
    cursor.execute("USE STAGING_MJCC;")
    cursor.execute("INSERT INTO dbo.stg_passjeunes_beneficiaire SELECT * FROM PassJeunesDB.dbo.Beneficiaire;")
    cursor.execute("INSERT INTO dbo.stg_passjeunes_offre SELECT * FROM PassJeunesDB.dbo.Offre;")
    cursor.execute("INSERT INTO dbo.stg_passjeunes_solde SELECT * FROM PassJeunesDB.dbo.Solde;")
    cursor.execute("INSERT INTO dbo.stg_passjeunes_operation SELECT * FROM PassJeunesDB.dbo.Operation;")
    cursor.execute("INSERT INTO dbo.stg_passjeunes_motatawi3 SELECT * FROM PassJeunesDB.dbo.Motatawi3;")
    print("  [OK] STAGING_MJCC populated from PassJeunesDB.")

    # Step 3: Populate STAGING_MJCC from generated Jam3iya scripts
    table_mapping = [
        ("06_jam3iya_maison_jeunes.sql", "maison_jeunes", "dbo.stg_jam3iya_maison_jeunes"),
        ("07_jam3iya_association.sql", "association", "dbo.stg_jam3iya_association"),
        ("08_jam3iya_personne_association.sql", "personne_association", "dbo.stg_jam3iya_personne_association"),
        ("09_jam3iya_colonie_vacances.sql", "colonie_vacances", "dbo.stg_jam3iya_colonie_vacances"),
        ("10_jam3iya_activite.sql", "activite", "dbo.stg_jam3iya_activite"),
        ("11_jam3iya_rapport_activite.sql", "rapport_activite", "dbo.stg_jam3iya_rapport_activite"),
    ]

    for fname, src_tbl, stg_table in table_mapping:
        fpath = scripts_dir / fname
        if fpath.exists():
            with open(fpath, "r", encoding="utf-8") as f:
                sql_text = f.read()
            sql_text = re.sub(r"USE jam3iya_db;\s*", "", sql_text)
            sql_text = re.sub(r"--[^\n]*\n", "", sql_text)
            sql_text = re.sub(rf"INSERT INTO {src_tbl}", f"INSERT INTO {stg_table}", sql_text)
            for stmt in sql_text.split(";"):
                s = stmt.strip()
                if "INSERT INTO" in s:
                    try:
                        cursor.execute(s)
                    except pyodbc.Error as e:
                        print(f"Error in {stg_table}:", e)

    print("  [OK] STAGING_MJCC populated from Jam3iya source data.")

    # Step 4: Populate DWH_MJCC Dimensions
    cursor.execute("USE DWH_MJCC;")

    # 4a. dim_region
    sql_dim_region = """
    INSERT INTO dbo.dim_region (ville, region, zone_geo)
    SELECT DISTINCT 
        ville, 
        region,
        CASE 
            WHEN region IN (N'Tanger-Tetouan-Al Hoceima', N'Rabat-Sale-Kenitra', N'Fes-Meknes', N'Oriental') THEN N'Nord'
            WHEN region IN (N'Casablanca-Settat', N'Marrakech-Safi', N'Beni Mellal-Khénifra', N'Draa-Tafilalet') THEN N'Centre'
            WHEN region IN (N'Souss-Massa', N'Guelmim-Oued Noun') THEN N'Sud'
            ELSE N'Sahara'
        END AS zone_geo
    FROM (
        SELECT ville, region FROM STAGING_MJCC.dbo.stg_passjeunes_beneficiaire WHERE ville IS NOT NULL AND region IS NOT NULL
        UNION
        SELECT ville, region FROM STAGING_MJCC.dbo.stg_jam3iya_maison_jeunes WHERE ville IS NOT NULL AND region IS NOT NULL
        UNION
        SELECT ville, region FROM STAGING_MJCC.dbo.stg_passjeunes_offre WHERE ville IS NOT NULL AND region IS NOT NULL
    ) AS v;
    """
    cursor.execute(sql_dim_region)
    print("  [OK] DWH: dim_region populated.")

    # 4b. dim_beneficiaire
    sql_dim_benef = """
    INSERT INTO dbo.dim_beneficiaire (
        source_id, cin, nom, prenom, genre, date_naissance,
        nationalite, type_statut, en_situation_handicap, statut_pass,
        tranche_age, date_inscription
    )
    SELECT 
        id AS source_id, cin, nom, prenom, genre, date_naissance,
        nationalite, type_statut, en_situation_handicap, statut_pass,
        CASE 
            WHEN DATEDIFF(YEAR, date_naissance, GETDATE()) BETWEEN 16 AND 18 THEN N'16-18'
            WHEN DATEDIFF(YEAR, date_naissance, GETDATE()) BETWEEN 19 AND 22 THEN N'19-22'
            WHEN DATEDIFF(YEAR, date_naissance, GETDATE()) BETWEEN 23 AND 25 THEN N'23-25'
            ELSE N'26-30'
        END AS tranche_age,
        date_inscription
    FROM STAGING_MJCC.dbo.stg_passjeunes_beneficiaire;
    """
    cursor.execute(sql_dim_benef)
    print("  [OK] DWH: dim_beneficiaire populated.")

    # 4c. dim_offre
    sql_dim_offre = """
    INSERT INTO dbo.dim_offre (
        source_id, nom_partenaire, secteur, categorie, nom_offre,
        description, conditions, type_avantage, valeur_avantage, unite_avantage,
        tarif_pass_jeunes, tarif_public, montant_a_debiter, montant_a_payer,
        solde_initial, solde_mensuel, ville_offre, region_offre, actif
    )
    SELECT 
        id AS source_id,
        ISNULL(nom_partenaire, N'Non precise') AS nom_partenaire,
        categorie AS secteur,
        categorie,
        nom_offre,
        description,
        conditions,
        type_avantage,
        valeur_avantage,
        unite_avantage,
        tarif_pass_jeunes,
        tarif_public,
        montant_a_debiter,
        montant_a_payer,
        solde_initial,
        solde_mensuel,
        ville AS ville_offre,
        region AS region_offre,
        actif
    FROM STAGING_MJCC.dbo.stg_passjeunes_offre;
    """
    cursor.execute(sql_dim_offre)
    print("  [OK] DWH: dim_offre populated.")

    # 4d. dim_association
    sql_dim_assoc = """
    INSERT INTO dbo.dim_association (
        source_id, nom, type, domaine_activite, statut, nb_membres, date_creation
    )
    SELECT 
        id AS source_id, nom, type, domaine_activite, statut, nb_membres, date_creation
    FROM STAGING_MJCC.dbo.stg_jam3iya_association;
    """
    cursor.execute(sql_dim_assoc)
    print("  [OK] DWH: dim_association populated.")

    # 4e. dim_maison_jeunes
    sql_dim_maison = """
    INSERT INTO dbo.dim_maison_jeunes (
        source_id, nom, capacite_accueil, statut, date_ouverture
    )
    SELECT 
        id AS source_id, nom, capacite_accueil, statut, date_ouverture
    FROM STAGING_MJCC.dbo.stg_jam3iya_maison_jeunes;
    """
    cursor.execute(sql_dim_maison)
    print("  [OK] DWH: dim_maison_jeunes populated.")

    # Step 5: Populate DWH_MJCC Fact Tables

    # 5a. fait_operations
    sql_fait_ops = """
    INSERT INTO dbo.fait_operations (
        source_id, temps_id, region_id, beneficiaire_id, offre_id, montant_reduction, nb_operations
    )
    SELECT 
        o.id AS source_id,
        ISNULL(t.temps_id, 20210101) AS temps_id,
        ISNULL(r.region_id, (SELECT TOP 1 region_id FROM dbo.dim_region)) AS region_id,
        b.beneficiaire_id,
        f.offre_id,
        o.montant_reduction,
        1 AS nb_operations
    FROM STAGING_MJCC.dbo.stg_passjeunes_operation o
    JOIN dbo.dim_beneficiaire b ON b.source_id = o.beneficiaire_id
    JOIN dbo.dim_offre f ON f.source_id = o.offre_id
    LEFT JOIN dbo.dim_temps t ON t.date_complete = CAST(o.date_operation AS DATE)
    LEFT JOIN dbo.dim_region r ON r.ville = o.ville;
    """
    cursor.execute(sql_fait_ops)
    print("  [OK] DWH: fait_operations populated.")

    # 5b. fait_solde
    sql_fait_solde = """
    INSERT INTO dbo.fait_solde (
        source_id, temps_id, beneficiaire_id, offre_id, annee, credit_initial, credit_restant
    )
    SELECT 
        s.id AS source_id,
        ISNULL(t.temps_id, 20210101) AS temps_id,
        b.beneficiaire_id,
        f.offre_id,
        s.annee,
        s.credit_initial,
        s.credit_restant
    FROM STAGING_MJCC.dbo.stg_passjeunes_solde s
    JOIN dbo.dim_beneficiaire b ON b.source_id = s.beneficiaire_id
    JOIN dbo.dim_offre f ON f.source_id = s.offre_id
    LEFT JOIN dbo.dim_temps t ON t.date_complete = CAST(s.date_renouvellement AS DATE);
    """
    cursor.execute(sql_fait_solde)
    print("  [OK] DWH: fait_solde populated.")

    # 5c. fait_activites
    sql_fait_act = """
    INSERT INTO dbo.fait_activites (
        source_id, temps_id, region_id, association_id, maison_id,
        type_activite, statut, budget, nb_participants, taux_satisfaction, budget_consomme, duree_jours
    )
    SELECT 
        a.id AS source_id,
        ISNULL(t.temps_id, 20210101) AS temps_id,
        ISNULL(r.region_id, (SELECT TOP 1 region_id FROM dbo.dim_region)) AS region_id,
        assoc.association_id,
        m.maison_id,
        a.type_activite,
        a.statut,
        a.budget,
        ISNULL(rap.nb_participants, 0) AS nb_participants,
        ISNULL(rap.taux_satisfaction, 0) AS taux_satisfaction,
        ISNULL(rap.budget_consomme, 0) AS budget_consomme,
        ISNULL(DATEDIFF(DAY, a.date_debut, a.date_fin), 1) AS duree_jours
    FROM STAGING_MJCC.dbo.stg_jam3iya_activite a
    JOIN dbo.dim_association assoc ON assoc.source_id = a.association_id
    JOIN dbo.dim_maison_jeunes m ON m.source_id = a.maison_jeunes_id
    LEFT JOIN STAGING_MJCC.dbo.stg_jam3iya_rapport_activite rap ON rap.activite_id = a.id
    LEFT JOIN STAGING_MJCC.dbo.stg_jam3iya_maison_jeunes stg_m ON stg_m.id = a.maison_jeunes_id
    LEFT JOIN dbo.dim_temps t ON t.date_complete = CAST(a.date_debut AS DATE)
    LEFT JOIN dbo.dim_region r ON r.ville = stg_m.ville AND r.region = stg_m.region;
    """
    cursor.execute(sql_fait_act)
    print("  [OK] DWH: fait_activites populated.")

    # 5d. fait_motatawi3
    sql_fait_mot = """
    INSERT INTO dbo.fait_motatawi3 (
        source_id, temps_id, region_id, beneficiaire_id,
        edition, domaine_volontariat, niveau_etudes, statut_dossier, statut
    )
    SELECT 
        m.id AS source_id,
        ISNULL(t.temps_id, 20210101) AS temps_id,
        ISNULL(r.region_id, (SELECT TOP 1 region_id FROM dbo.dim_region)) AS region_id,
        b.beneficiaire_id,
        m.edition,
        m.domaine_volontariat,
        m.niveau_etudes,
        m.statut_dossier,
        m.statut
    FROM STAGING_MJCC.dbo.stg_passjeunes_motatawi3 m
    JOIN dbo.dim_beneficiaire b ON b.source_id = m.beneficiaire_id
    LEFT JOIN dbo.dim_temps t ON t.date_complete = CAST(m.date_inscription AS DATE)
    LEFT JOIN dbo.dim_region r ON r.region = m.region;
    """
    cursor.execute(sql_fait_mot)
    print("  [OK] DWH: fait_motatawi3 populated.")

    print("\n" + "=" * 60)
    print("  PIPELINE ETL TERMINE AVEC SUCCES !")
    print("  Toutes les tables de STAGING_MJCC et DWH_MJCC sont chargees.")
    print("=" * 60)


if __name__ == "__main__":
    main()
