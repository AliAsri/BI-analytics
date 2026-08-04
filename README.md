# 🏛️ Data Intelligence & Machine Learning — Ministère de la Jeunesse (MJCC)

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Power BI](https://img.shields.io/badge/Power_BI-Dashboard-yellow.svg)
![SQL Server](https://img.shields.io/badge/SQL_Server-Data_Warehouse-red.svg)
![SSIS](https://img.shields.io/badge/SSIS-ETL_Pipeline-lightgrey.svg)
![SSAS](https://img.shields.io/badge/SSAS-Tabular_Model-orange.svg)
![Machine Learning](https://img.shields.io/badge/Machine_Learning-Scikit_Learn-green.svg)

Bienvenue dans le dépôt officiel du projet de **Business Intelligence (BI) et d'Intelligence Artificielle (IA)** développé pour le compte du **Ministère de la Jeunesse, de la Culture et de la Communication (MJCC)** du Maroc.

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
5. **Intelligence Artificielle (ML)** : Python (Scikit-Learn, Pandas). Les résultats des prédictions sont réinjectés dans le DWH pour être visualisés.

---

## 🗄️ Sources de Données

> ⚠️ **Note Importante sur la Confidentialité** : À l'exception du catalogue des offres *Pass Jeunes* (qui s'appuie sur des données réelles), **l'intégralité des données utilisées dans ce dépôt (profils utilisateurs, transactions, historique associatif, etc.) a été générée de manière synthétique et simulée** via des scripts Python. Aucune donnée réelle de citoyen n'est exposée dans ce projet.

Le Data Warehouse consolide les données issues de 3 systèmes hétérogènes :

- **📱 Pass Jeunes (API / JSON)** : Application mobile offrant des réductions (Transports, Culture, Sport). Contient les profils démographiques et l'historique des transactions.
- **🤝 Motatawi3 (Fichiers CSV)** : Plateforme nationale de volontariat. Contient les missions, les associations hôtes et les heures de bénévolat.
- **🏢 Jam3iya (Base de données SQL)** : Système de gestion de la vie associative et des Maisons de Jeunes (budgets, événements, infrastructures).

*(Une clé de réconciliation basée sur la CIN permet de suivre un jeune à travers ces trois systèmes).*

---

## 📊 Data Warehouse & BI

### Modélisation en Étoile (Star Schema)
Le DWH (`DWH_MJCC`) est construit autour d'une architecture optimisée pour l'analyse :
- **Dimensions (`dim_`)** : `dim_beneficiaire`, `dim_offre`, `dim_association`, `dim_maison_jeunes`, `dim_date`.
- **Faits (`fait_`)** : `fait_operations` (transactions Pass Jeunes), `fait_motatawi3` (missions), `fait_activites` (Jam3iya).

### Power BI Dashboard
Le tableau de bord décisionnel est composé de 6 pages interactives :
1. **Vue Globale** : KPIs macro-économiques.
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
- **Intégration** : Colonnes `churn_probability` et `churn_risk_segment` ajoutées au DWH.

### 2. Segmentation Comportementale (Clustering)
- **Objectif** : Créer des profils types d'utilisateurs.
- **Algorithme** : K-Means (Optimisé via la méthode du Coude et le score de Silhouette, K=3).
- **Segments Identifiés** : *Super-Actifs*, *Réguliers*, *Occasionnels*.
- **Intégration** : Colonne `segment_beneficiaire` ajoutée au DWH.

### 3. Moteur de Recommandation Personnalisée
- **Objectif** : Suggérer à chaque jeune les offres les plus pertinentes.
- **Algorithme** : Filtrage Collaboratif (User-Based) utilisant la Similarité Cosinus.
- **Intégration** : Top 3 des offres et secteur recommandé ajoutés pour chaque utilisateur.

---

## 📁 Structure du Dépôt

```text
📂 Projet_MJCC/
├── 📁 bi_dashboard/        # Rapports Power BI (.pbix) et thèmes JSON
├── 📁 data/                # Fichiers de données plats (CSV, Excel) utilisés pour l'ETL
├── 📁 docs/                # Architecture, diagrammes, notes de cadrage (PDF, PNG)
├── 📁 etl_dwh/             # Scripts SQL de création du DWH et packages SSIS
├── 📁 ml_models/           # Scripts Python d'Intelligence Artificielle
│   ├── ML_Churn/           # Prédiction de désabonnement
│   ├── ML_Recommandation/  # Moteur de recommandation d'offres
│   ├── ML_Segmentation/    # Clustering K-Means
│   └── ML_Engagement.../   # Prédiction d'engagement associatif
└── 📁 scripts/             # Utilitaires PowerShell et Python (Automatisation)
```

---

## ⚙️ Installation et Déploiement

### Prérequis
- SQL Server 2019+ et SQL Server Management Studio (SSMS)
- SQL Server Analysis Services (SSAS)
- Python 3.9+ avec `pandas`, `scikit-learn`, `pyodbc`
- Power BI Desktop

### Étapes de lancement
1. **Base de données** : Exécutez les scripts SQL dans `etl_dwh/` pour créer `DWH_MJCC`.
2. **ETL** : Lancez le script d'orchestration `python etl_dwh/execute_full_dwh_etl.py` (ou déployez le projet SSIS) pour charger les données.
3. **Machine Learning** : 
   - Naviguez vers `ml_models/`.
   - Exécutez séquentiellement les modèles (ex: `python ML_Churn/churn_prediction_v2.py`) pour générer les prédictions en base.
4. **Power BI** : Ouvrez `bi_dashboard/MJCC_Dashboard.pbix` et actualisez les données pour visualiser les analyses et les KPIs ML.

---
*Projet développé avec passion pour l'amélioration des services publics par la Donnée.*
