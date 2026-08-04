# 🏁 Checkpoint Projet MJCC — État d'avancement

> **Date** : 15 juillet 2026  
> **Dernière mise à jour** : 22h35

---

## Récapitulatif global

| Phase | Intitulé | Statut | Progression |
|-------|----------|--------|-------------|
| 1 | Bases sources + Diagrammes | ✅ Terminé | 100% |
| 2 | ETL — Base de Staging (SSIS) | ✅ Terminé | 100% |
| 3 | SSIS — Extraction, Transformation, Chargement (vers DWH) | 🔶 En cours | 90% |
| 4 | SSAS — Dimensions et Cube (Tabular) | ⏳ Non commencé | 0% |
| 5 | Power BI — Visualisation | ⏳ Non commencé | 0% |

---

## Phase 1 · Bases sources + Diagrammes ✅

### Travail accompli
- [x] **PassJeunesDB** créée dans SQL Server (SSMS) — 6 tables
  - `Beneficiaire`, `Partenaire`, `Offre_PassJeunes`, `Solde`, `Operation`, `Motatawi3`
- [x] **jam3iya_db** créée dans MySQL (Workbench) — 7 tables
  - `maison_jeunes`, `association`, `personne_association`, `colonie_vacances`, `activite`, `rapport_activite`, `cin_beneficiaires_valides`
- [x] Données générées et insérées (10 000 bénéficiaires, 24 partenaires, 500 associations, etc.)
- [x] Diagramme relationnel PassJeunes (SSMS)
- [x] Diagramme relationnel jam3iya_db (MySQL Workbench)

### Bugs résolus
- **`chk_age_inscription`** : La fonction Python `date_naissance_pour_age_a_date()` générait des dates de naissance dont l'année pouvait être décalée de -1 par rapport au calcul `DATEDIFF(YEAR)` de SQL Server. Corrigé dans `generate_source_data.py` (ligne 112).
- **FK Solde → Beneficiaire** : Le compteur IDENTITY de SQL Server avait avancé à cause des inserts échoués. Résolu en ré-exécutant `passjeunes_db_v2.sql` (DROP + CREATE) avant les insertions.

### Fichiers clés
- `db/Db queries/passjeunes_db_v2.sql` — Schéma SQL Server
- `db/Db queries/jam3iya_db_v2.sql` — Schéma MySQL
- `db/source_data_sql/generate_source_data.py` — Générateur Python
- `db/source_data_sql/scripts_sql/` — 12 scripts d'insertion générés

---

## Phase 2 · ETL — Base de Staging ✅

### Travail accompli
- [x] **STAGING_MJCC** créée dans SQL Server — 13 tables
  - 6 tables `stg_passjeunes_*` (sans FK/CHECK)
  - 6 tables `stg_jam3iya_*` (sans FK/CHECK)
  - 1 table `etl_log` (traçabilité)
- [x] Projet SSIS `ETL_MJCC` créé dans Visual Studio
- [x] 3 Connection Managers configurés et testés :
  - `LocalHost.PassJeunesDB` (OLE DB)
  - `LocalHost.STAGING_MJCC` (OLE DB)
  - `localhost.jam3iya_db.root` (ADO.NET / MySql.Data.MySqlClient)
- [x] **SEQ_PassJeunes_SQLServer** — 6 flux en parallèle (TRUNCATE + Data Flow) ✅ tout vert
- [x] **SEQ_Jam3iya_MySQL** — 6 flux en parallèle (TRUNCATE + Data Flow) ✅ tout vert
- [x] `SQL_Log_Beneficiaire` configuré (preuve de concept pour `etl_log`)

### Problèmes rencontrés et résolus
- **`DTSRuntimeWrap` Library not registered** → Résolu en lançant Visual Studio en administrateur
- **MySQL ADO.NET "No tables or views could be loaded"** → Contourné en utilisant `SQL command` au lieu de `Table or view`
- **Truncation warning sur colonne `nom`** → Avertissement ignoré (pas d'impact réel)

### Architecture SSIS actuelle
```
Control Flow
├── SEQ_PassJeunes_SQLServer
│   ├── SQL_TRUNC_Beneficiaire  → DFT_Load_Beneficiaire → SQL_Log_Beneficiaire
│   ├── SQL_TRUNC_Partenaire    → DFT_Load_Partenaire
│   ├── SQL_TRUNC_Offre         → DFT_Load_Offre
│   ├── SQL_TRUNC_Operation     → DFT_Load_Operation
│   ├── SQL_TRUNC_Motatawi3     → DFT_Load_Motatawi3
│   └── SQL_TRUNC_Solde         → DFT_Load_Solde
│
└── SEQ_Jam3iya_MySQL
    ├── SQL_TRUNC_MaisonJeunes        → DFT_Load_MaisonJeunes
    ├── SQL_TRUNC_Association          → DFT_Load_Association
    ├── SQL_TRUNC_PersonneAssociation  → DFT_Load_PersonneAssociation
    ├── SQL_TRUNC_ColonieVacance       → DFT_Load_ColonieVacance
    ├── SQL_TRUNC_Activite             → DFT_Load_Activite
    └── SQL_TRUNC_RapportActivite      → DFT_Load_RapportActivite
```

### Fichiers clés
- `db/Db queries/schema_staging.sql` — Schéma de la base Staging

---

## Phase 3 · SSIS — ETL vers DWH 🔶 En cours

### Ce qui est fait
- [x] Projet SSIS créé
- [x] Connection Managers : PassJeunesDB, STAGING_MJCC, jam3iya_db
- [x] Connection Manager vers DWH_MJCC
- [x] **Créer DWH_MJCC** (schéma en étoile) → `schema_dwh_sqlserver.sql`
- [x] Créer package `03_Load_DWH.dtsx` (Dimensions terminées, Faits en cours de finalisation)

### Ce qui reste à faire
- [ ] Finaliser l'exécution des 4 tables de faits
- [ ] Créer les 3 autres packages SSIS (Master, Extract PassJeunes, Extract Jam3iya) pour orchestrer l'ensemble.
- [ ] Derived Column transformations
- [ ] Chargement incrémental (exécuter 2x sans doublons)

---

## Phase 4 · SSAS Tabular ⏳ Non commencé

### À faire
- [ ] Créer projet SSAS Tabular `SSAS_MJCC` (compatibilité 1600+)
- [ ] Importer tables `dim_*` et `fait_*` depuis DWH_MJCC
- [ ] Vérifier relations dans la vue Diagramme
- [ ] Marquer `dim_temps` comme Date Table
- [ ] Créer hiérarchies :
  - Géographie : Zone Géo → Région → Ville
  - Calendrier : Année → Trimestre → Mois → Jour
- [ ] Créer mesures DAX (Nb Jeunes Inscrits, Montant Réductions, Budget Associations, etc.)
- [ ] Déployer sur l'instance SSAS locale

---

## Phase 5 · Power BI ⏳ Non commencé

### À faire
- [ ] Connecter Power BI Desktop à SSAS_MJCC (Connect Live)
- [ ] Dashboard 1 — Vue Jeunes (KPIs + graphiques)
- [ ] Dashboard 2 — Vue Associations
- [ ] Dashboard 3 — Vue Croisée

---

## 🎯 Prochaine étape immédiate

> **Créer le schéma en étoile du Data Warehouse (DWH_MJCC)**
> 
> C'est le prérequis pour tout le reste :
> - Phase 3 (Lookups vers les dimensions)
> - Phase 4 (Import dans SSAS Tabular)
> - Phase 5 (Dashboards Power BI)

### Fichiers de référence
- `GUIDE_SSIS.md` — Packages et Lookups en détail
- `GUIDE_SSAS_TABULAR.md` — Mesures DAX et hiérarchies
- `schema_dwh_sqlserver.sql` — Schéma DWH (à créer)
- `schema_staging.sql` — ✅ Déjà créé
- `passjeunes_db_v2.sql` — ✅ Déjà exécuté
- `jam3iya_db_v2.sql` — ✅ Déjà exécuté
