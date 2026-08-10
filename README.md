# 🏛️ Data Intelligence & Machine Learning — Ministère de la Jeunesse (MJCC)

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Power BI](https://img.shields.io/badge/Power_BI-Dashboard-yellow.svg)
![SQL Server](https://img.shields.io/badge/SQL_Server-Data_Warehouse-red.svg)
![SSIS](https://img.shields.io/badge/SSIS-ETL_Pipeline-lightgrey.svg)
![SSAS](https://img.shields.io/badge/SSAS-Tabular_Model-orange.svg)
![Machine Learning](https://img.shields.io/badge/Machine_Learning-Scikit_Learn-green.svg)


---

## 📑 Table des Matières
1. [Contexte et Enjeux](#-contexte-et-enjeux)
2. [Architecture Technique](#-architecture-technique)
3. [Sources de Données](#-sources-de-données)
4. [Data Warehouse & BI](#-data-warehouse--bi)
5. [Modèles de Machine Learning](#-modèles-de-machine-learning)
6. [Structure du Dépôt](#-structure-du-dépôt)
7. [Installation et Déploiement](#-installation-et-déploiement)

---

## 🎯 Contexte et Enjeux

Le MJCC gère plusieurs plateformes numériques destinées à la jeunesse marocaine. L'objectif de ce projet est de **centraliser, croiser et valoriser** ces données éparses afin de fournir aux décideurs des tableaux de bord interactifs et des analyses prédictives. 

Les trois grands objectifs sont :
- **Analyser l'engagement** des jeunes sur les différentes plateformes.
- **Prédire et prévenir l'attrition (Churn)** sur l'application Pass Jeunes.
- **Personnaliser l'expérience** grâce à des recommandations d'offres ciblées basées sur l'IA.

---

## 🏗️ Architecture Technique

Le projet couvre l'intégralité du cycle de vie de la donnée (Data Engineering -> Data Science -> Data Viz) :

1. **Extraction & Transformation (ETL)** : Microsoft SSIS.
2. **Stockage Centralisé (DWH)** : SQL Server (Modélisation en Étoile).
3. **Couche Sémantique (OLAP)** : SQL Server Analysis Services (SSAS) Tabular.
4. **Data Visualisation (BI)** : Power BI.
5. **Intelligence Artificielle (ML)** : Python (Scikit-Learn, XGBoost, Pandas). Les résultats des prédictions sont réinjectés dans le DWH via un pipeline automatisé (PowerShell + AMO/TOM) pour être visualisés sans rupture de cohérence.

---

## 🗄️ Sources de Données

> ⚠️ **Note Importante sur la Confidentialité** : À l'exception du catalogue des offres *Pass Jeunes* (qui s'appuie sur des données réelles), **l'intégralité des données utilisées dans ce dépôt (profils utilisateurs, transactions, historique associatif, etc.) a été générée de manière synthétique et simulée** via des scripts Python. Aucune donnée réelle de citoyen n'est exposée dans ce projet.

Le Data Warehouse consolide les données issues de **2 systèmes sources hétérogènes**, tous deux relationnels :

- **📱 PassJeunesDB (SQL Server)** : base de l'application Pass Jeunes, offrant des réductions (Transports, Culture, Sport). Contient les profils démographiques, l'historique des transactions (`Operation`, `Solde`), le catalogue d'offres (`Offre`), et le programme de volontariat **Motatawi3** — une table de cette même base, et non un système CSV séparé.
- **🏢 jam3iya_db (MySQL)** : système de gestion de la vie associative et des Maisons de Jeunes (associations, activités, budgets, colonies de vacances).

*(Une clé de réconciliation basée sur la CIN permet de suivre un jeune à travers ces deux systèmes.)*

---

## 📊 Data Warehouse & BI

### Modélisation en Étoile (Star Schema)
Le DWH (`DWH_MJCC`) est construit autour d'une architecture optimisée pour l'analyse :
- **Dimensions (`dim_`)** : `dim_beneficiaire`, `dim_offre`, `dim_association`, `dim_maison_jeunes`, `dim_region`, `dim_temps`.
- **Faits (`fait_`)** : `fait_operations` (transactions Pass Jeunes), `fait_solde` (crédits annuels alloués/consommés), `fait_motatawi3` (missions de volontariat), `fait_activites` (activités Jam3iya).

> Note de conception : une entité `Partenaire` distincte avait été envisagée dans une première maquette, mais n'a pas été retenue dans le schéma final — le nom du partenaire est porté directement par `dim_offre`.

### Power BI Dashboard
Le tableau de bord décisionnel est composé de 6 pages interactives :
1. **Synthèse Exécutive** : KPIs macro-économiques.
2. **Opérations & Offres** : Analyse de la consommation Pass Jeunes.
3. **Volontariat Motatawi3** : Cartographie des missions de bénévolat.
4. **Vie Associative & Maisons** : Analyse budgétaire et infrastructurelle.
5. **Démographie & Inclusion** : Analyse du genre, de l'âge et de l'inclusion spatiale.
6. **Intelligence Artificielle & ML** : Visualisation des prédictions et segments.

---

## 🧠 Modèles de Machine Learning

Les algorithmes Python interagissent directement avec SQL Server via `pyodbc` pour extraire les données, les entraîner, et écrire les prédictions finales dans les tables de dimensions.

### 1. Prédiction de l'Attrition (Churn)
- **Objectif** : Identifier les jeunes qui risquent d'abandonner le Pass Jeunes.
- **Algorithme** : Stacking Classifier (combinaison de Random Forest, XGBoost, et Logistic Regression).
- **Features** : RFM (Récence, Fréquence, Montant), âge, historique transactionnel (38 variables).
- **Performance** : F1-score 0,62, AUC-ROC 0,77 (validation croisée 5 plis).
- **Intégration** : scores de risque réintégrés dans le DWH puis le cube SSAS.

### 2. Segmentation Comportementale (Clustering)
- **Objectif** : Créer des profils types d'utilisateurs.
- **Algorithme** : K-Means (Optimisé via la méthode du Coude et le score de Silhouette, K=3).
- **Segments Identifiés** : *Super-Actifs*, *Réguliers*, *Occasionnels*.

### 3. Moteur de Recommandation Personnalisée
- **Objectif** : Suggérer à chaque jeune les offres les plus pertinentes.
- **Algorithme** : Filtrage Collaboratif (User-Based, Similarité Cosinus) + repli Content-Based.
- **Intégration** : Top offres et catégorie recommandée ajoutés pour chaque utilisateur.

### 4. Propension à l'Engagement Associatif
- **Objectif** : Identifier, parmi les bénéficiaires Pass Jeunes non encore membres d'une association, ceux les plus susceptibles de le devenir.
- **Intégration** : scores réintégrés dans `dim_beneficiaire` (`propension_associative`).

---

## 📁 Structure du Dépôt

```text
📂 Projet_MJCC/
├── 📁 bi_dashboard/        # Rapports Power BI (.pbix) et thèmes JSON
├── 📁 etl_dwh/             # Scripts SQL de création du DWH et packages SSIS/SSAS
├── 📁 ml_models/           # Scripts Python d'Intelligence Artificielle
│   ├── ML_Churn/           # Prédiction de désabonnement
│   ├── ML_Recommandation/  # Moteur de recommandation d'offres
│   ├── ML_Segmentation/    # Clustering K-Means
│   └── ML_Engagement.../   # Prédiction d'engagement associatif
├── 📁 reference/           # Référentiel réel des offres partenaires (non confidentiel)
└── 📁 scripts/             # Utilitaires PowerShell et Python (automatisation)
```

> Les données synthétiques de test (CSV, Excel, JSON) ne sont pas versionnées (voir `.gitignore`) pour des raisons de confidentialité institutionnelle. Seul le référentiel des offres partenaires, non confidentiel, est conservé dans `reference/`.

---

## ⚙️ Installation et Déploiement

### Prérequis
- SQL Server 2019+ et SQL Server Management Studio (SSMS)
- SQL Server Analysis Services (SSAS) en mode Tabular
- MySQL (pour jam3iya_db)
- Python 3.9+ — dépendances listées dans `requirements.txt`
- Power BI Desktop

### Étapes de lancement
1. **Base de données** : exécutez les scripts SQL dans `etl_dwh/db/` pour créer les bases sources, `STAGING_MJCC` et `DWH_MJCC`.
2. **ETL** : lancez le script d'orchestration `python etl_dwh/execute_full_dwh_etl.py` (ou déployez le projet SSIS `etl_dwh/SSIS/ETL_MJCC`) pour charger les données.
3. **Modèle sémantique** : déployez le projet SSAS `etl_dwh/SSIS/SSAS_MJCC` (`Model.bim`) sur votre instance SSAS Tabular.
4. **Machine Learning** :
   - `pip install -r requirements.txt`
   - Naviguez vers `ml_models/` et exécutez séquentiellement les modèles (ex : `python ML_Churn/churn_prediction_v2.py`) pour générer les prédictions en base et réintégrer les scores au cube.
5. **Power BI** : ouvrez `bi_dashboard/MJCC_Dashboard.pbix` et actualisez les données pour visualiser les analyses et les KPIs ML.

---

## 📄 Documentation complémentaire

Le rapport de stage complet, incluant l'analyse détaillée de l'architecture, les résultats des modèles et les limites identifiées, est disponible séparément (`Rapport_Stage_MJCC.docx`).
