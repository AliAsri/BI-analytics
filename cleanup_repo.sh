#!/bin/bash
# ============================================================================
# Script de nettoyage du repo BI-analytics — à exécuter à la racine du repo,
# après avoir fait un `git pull` pour être à jour.
# Lis chaque section avant de lancer : certaines étapes sont irréversibles
# une fois poussées (git push). Fais un `git status` après chaque étape.
# ============================================================================
set -e

echo "== 1. Retrait des artefacts de build Visual Studio (SSIS/SSAS) =="
git rm -r --cached "etl_dwh/SSIS/ETL_MJCC/.vs" 2>/dev/null || true
git rm -r --cached "etl_dwh/SSIS/ETL_MJCC/ETL_MJCC/bin" 2>/dev/null || true
git rm -r --cached "etl_dwh/SSIS/ETL_MJCC/ETL_MJCC/obj" 2>/dev/null || true
git rm -r --cached "etl_dwh/SSIS/SSAS_MJCC/.vs" 2>/dev/null || true
git rm -r --cached "etl_dwh/SSIS/SSAS_MJCC/SSAS_MJCC/bin" 2>/dev/null || true
git rm -r --cached "etl_dwh/SSIS/SSAS_MJCC/SSAS_MJCC/obj" 2>/dev/null || true
# Les dossiers restent sur ton disque (utiles pour rouvrir le projet dans
# Visual Studio) mais ne seront plus versionnés grâce au .gitignore mis à jour.

echo "== 2. Fusion des dossiers DWH steps / DWH steps 2 =="
mkdir -p "etl_dwh/screenshots"

# Images valides et à jour, à conserver (issues des deux dossiers) :
git mv "etl_dwh/DWH steps 2/Extract to stagingDB.png" "etl_dwh/screenshots/" 2>/dev/null || true
git mv "etl_dwh/DWH steps 2/load to DWH.png" "etl_dwh/screenshots/" 2>/dev/null || true
git mv "etl_dwh/DWH steps 2/star schema DWH.png" "etl_dwh/screenshots/" 2>/dev/null || true
git mv "etl_dwh/DWH steps/Exécution réussie du flux de chargement Staging pour la base source Jam3iyaDB.png" "etl_dwh/screenshots/" 2>/dev/null || true
git mv "etl_dwh/DWH steps/Orchestration du pipeline de données via le package Maître.png" "etl_dwh/screenshots/" 2>/dev/null || true
git mv "etl_dwh/DWH steps/connection jam3iya db MYSQL.png" "etl_dwh/screenshots/" 2>/dev/null || true
git mv "etl_dwh/DWH steps/connection passjeunes DB.png" "etl_dwh/screenshots/" 2>/dev/null || true
git mv "etl_dwh/DWH steps/connection schema staging.png" "etl_dwh/screenshots/" 2>/dev/null || true
git mv "etl_dwh/DWH steps/jam3iya db mysql source.png" "etl_dwh/screenshots/" 2>/dev/null || true
git mv "etl_dwh/DWH steps/ole db source beneficiare.png" "etl_dwh/screenshots/" 2>/dev/null || true

# Images obsolètes (ancienne conception avec une dimension Partenaire
# distincte, abandonnée — voir Annexe D du rapport) : à supprimer.
git rm "etl_dwh/DWH steps/Architecture finale du Control Flow SSIS pour l'alimentation complète du DWH.png" 2>/dev/null || true
git rm "etl_dwh/DWH steps/Chargement parallèle des tables de dimensions dans le DWH.png" 2>/dev/null || true
git rm "etl_dwh/DWH steps/diagramme star schema.png" 2>/dev/null || true
git rm "etl_dwh/DWH steps/First task table beneficiare.png" 2>/dev/null || true

# Capture d'une exécution antérieure (6 flux, avec Partenaire) : gardée à
# titre d'archive documentée (voir Figure 7 du rapport), mais déplacée et
# clairement renommée pour ne pas laisser croire qu'elle est à jour.
mkdir -p "etl_dwh/screenshots/archive"
git mv "etl_dwh/DWH steps/Exécution réussie du flux de chargement Staging pour la base source PassJeunes.png" \
       "etl_dwh/screenshots/archive/Exécution Staging PassJeunes (ancienne version, avant simplification du schéma).png" 2>/dev/null || true
# -> Si tu préfères la supprimer purement et simplement, remplace les deux
#    lignes ci-dessus par :
#    git rm "etl_dwh/DWH steps/Exécution réussie du flux de chargement Staging pour la base source PassJeunes.png"

# Suppression des dossiers désormais vides
rmdir "etl_dwh/DWH steps" 2>/dev/null || true
rmdir "etl_dwh/DWH steps 2" 2>/dev/null || true

echo "== 3. Déplacement du référentiel des offres (données réelles, non confidentielles) =="
mkdir -p "reference"
git mv "scripts/output_offres.py" "reference/offres_partenaires_reelles.py" 2>/dev/null || true

echo "== 4. Fichiers de configuration =="
echo "-> Copie manuellement le nouveau README.md, .gitignore et requirements.txt"
echo "   fournis à la racine du repo (ils remplacent les fichiers existants)."

echo ""
echo "== Terminé. Vérifie maintenant avec : =="
echo "   git status"
echo "   git diff --cached --stat"
echo "Puis :"
echo "   git add README.md .gitignore requirements.txt"
echo "   git commit -m \"Nettoyage du repo : retrait des artefacts de build, fusion des captures DWH, correction du README\""
echo "   git push"
