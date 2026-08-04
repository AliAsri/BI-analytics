# 📊 Point d'Avancement : Projet Plateforme Décisionnelle MJCC

**Date** : 16 Juillet 2026
**Sujet** : Création d'une infrastructure de Business Intelligence (BI) pour le Ministère de la Jeunesse

---

## 🎯 1. Contexte & Objectif du Projet

Actuellement, le ministère gère ses données métier à travers deux systèmes transactionnels hétérogènes :
1.  **Application PassJeunes** (sur SQL Server) : Gère les profils des jeunes, les partenaires et les opérations de réduction.
2.  **Plateforme Jam3iya.ma** (sur MySQL) : Gère les maisons de jeunes, les associations et leurs activités.

**L'objectif du projet** est de construire une architecture décisionnelle centralisée. Au lieu d'interroger directement les bases de production (OLTP) au risque de les saturer, nous extrayons ces données pour les consolider dans un **Data Warehouse** (Entrepôt de données). Cela permettra au ministère d'avoir une vision 360° et de croiser les indicateurs clés (ex: quel impact a le PassJeunes sur l'engagement associatif local ?).

---

## 🏗️ 2. Avancement et Architecture Data (Phases 1 à 5 terminées)

Le socle technique et la "plomberie" des données (Data Engineering) sont désormais pleinement opérationnels.

### ✅ Phase 1 : Bases Sources et Simulation de Production
*   **Réalisation :** Modélisation et implémentation des deux bases transactionnelles.
*   **Données :** Pour travailler en conditions réelles, j'ai développé des scripts Python générant une volumétrie massive (ex: 10 000 jeunes simulés, +400 000 opérations, 500 associations).

### ✅ Phase 2 : Flux d'Extraction et Zone de Staging
*   **Réalisation :** Développement des premiers flux ETL (Extract, Transform, Load) avec Microsoft SSIS.
*   **Architecture :** Les données des deux systèmes (SQL Server et MySQL) sont extraites en parallèle vers une zone tampon : la base **Staging**. Cela permet d'isoler la charge d'extraction des bases de production.

### ✅ Phase 3 : Le Data Warehouse (DWH)
*   **Modélisation :** Création du DWH selon les standards BI avec une architecture en **Modèle en Étoile (Star Schema)**.
*   Le DWH sépare l'information pour optimiser les requêtes analytiques :
    *   **Dimensions (Les axes d'analyse) :** Le Temps, la Géographie (Régions), les Bénéficiaires, les Associations, etc.
    *   **Tables de Faits (Les métriques) :** Les Opérations, les Soldes, les Activités, le Volontariat.

### ✅ Phase 4 : Transformation et Automatisation SSIS
*   **Réalisation :** Les flux de données complexes entre le Staging et le DWH ont été validés.
*   **Transformation :** Résolution des clés substituts (Surrogate Keys) et gestion de la qualité de la donnée via des jointures inter-systèmes.
*   **Automatisation :** Un **Master Package** orchestre désormais l'intégralité du cycle. En une seule commande, le système purge les anciennes données, met à jour le Staging, remplit les Dimensions, puis peuple les tables de Faits avec un grand volume de données de manière très performante.

### ✅ Phase 5 : Modèle Sémantique (SSAS Tabular)
*   **Réalisation :** Déploiement réussi d'un modèle Tabulaire en mémoire (In-Memory) sur l'instance locale SSAS. Le modèle connecte et consolide l'ensemble des données (+400 000 opérations).
*   **Logique Métier :** Développement d'indicateurs de performance (KPIs) de haut niveau en langage **DAX** (Budget consommé, taux de satisfaction, montants de réduction, etc.).
*   **Analyse :** Implémentation de hiérarchies décisionnelles (Calendrier et Géographie) pour permettre l'exploration dynamique (Drill-down).

---

## 🚀 3. Prochaine et Dernière Étape : La Datavisualisation

Toute l'infrastructure Data (ETL + Data Warehouse + Modèle SSAS) étant solidement en place, le projet entre dans sa phase finale :

1.  **Data Visualization (Power BI) - Semaine 5**
    *   Connexion en direct (Live Connection) au modèle SSAS pour garantir des performances optimales sans duplication de données.
    *   Conception des tableaux de bord interactifs finaux destinés aux directeurs du Ministère.
    *   **Objectif :** Rendre la donnée facilement explorable et actionnable visuellement.
