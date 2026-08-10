"""
=============================================================================
  INTEGRATION ML CHURN -> SQL SERVER -> SSAS -> POWER BI
  Projet MJCC
=============================================================================

Ce module permet de :
  1. Scorer les bénéficiaires avec leur probabilité de churn.
  2. Écrire les scores dans DWH_MJCC.dim_beneficiaire.
  3. Mettre à jour le modèle SSAS avec de nouvelles colonnes et mesures.
  4. Déployer et effectuer un "Process Full" sur SSAS.

Fonctions principales :
    - extract_data : Extraction des données depuis la base de données.
    - feature_engineering : Construction des indicateurs explicatifs.
    - train_model : Entraînement d'un Stacking Ensemble sur la totalité des données.
    - score_beneficiaries : Génération des prédictions et segments de risque.
    - update_sql_server : Mise à jour de la table de dimension.
    - update_ssas_model : Exécution du script PowerShell TOM pour SSAS.
"""

import os
import subprocess
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pyodbc
from imblearn.over_sampling import SMOTE
from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
    StackingClassifier,
)
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings('ignore')


def extract_data(conn_str: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extrait les bénéficiaires et opérations depuis DWH_MJCC."""
    print("=" * 70)
    print("ETAPE 1 : Extraction & Feature Engineering")
    print("=" * 70)

    conn = pyodbc.connect(conn_str)

    df_benef = pd.read_sql("""
        SELECT beneficiaire_id, genre, tranche_age, statut_pass,
               en_situation_handicap, est_membre_association, date_inscription
        FROM dbo.dim_beneficiaire
    """, conn)

    df_ops = pd.read_sql("""
        SELECT f.beneficiaire_id, f.montant_reduction, f.nb_operations,
               f.offre_id, t.date_complete, t.mois, t.annee, t.trimestre,
               t.est_weekend, t.jour_semaine,
               r.region, o.secteur, o.categorie, o.type_avantage
        FROM dbo.fait_operations f
        INNER JOIN dbo.dim_temps t ON f.temps_id = t.temps_id
        INNER JOIN dbo.dim_region r ON f.region_id = r.region_id
        INNER JOIN dbo.dim_offre o ON f.offre_id = o.offre_id
    """, conn)
    
    conn.close()

    print(f"  Bénéficiaires : {len(df_benef):,}")
    print(f"  Opérations    : {len(df_ops):,}")
    return df_benef, df_ops


def feature_engineering(df_benef: pd.DataFrame, df_ops: pd.DataFrame, cutoff_date: pd.Timestamp):
    """Calcule les caractéristiques RFM et comportementales."""
    df_ops['date_complete'] = pd.to_datetime(df_ops['date_complete'])
    df_benef['date_inscription'] = pd.to_datetime(df_benef['date_inscription'])

    df_obs = df_ops[df_ops['date_complete'] <= cutoff_date].copy()
    df_future = df_ops[df_ops['date_complete'] > cutoff_date].copy()
    active_after = set(df_future['beneficiaire_id'].unique())

    rfm = df_obs.groupby('beneficiaire_id').agg(
        recency=('date_complete', lambda x: (cutoff_date - x.max()).days),
        frequency=('nb_operations', 'sum'),
        monetary=('montant_reduction', 'sum'),
    ).reset_index()

    behavior = df_obs.groupby('beneficiaire_id').agg(
        montant_moyen=('montant_reduction', 'mean'),
        montant_std=('montant_reduction', 'std'),
        montant_max=('montant_reduction', 'max'),
        montant_min=('montant_reduction', 'min'),
        nb_offres_distinctes=('offre_id', 'nunique'),
        nb_secteurs_distincts=('secteur', 'nunique'),
        nb_categories_distinctes=('categorie', 'nunique'),
        nb_regions=('region', 'nunique'),
        premiere_operation=('date_complete', 'min'),
        derniere_operation=('date_complete', 'max'),
        nb_jours_actifs=('date_complete', 'nunique'),
        nb_weekends=('est_weekend', 'sum'),
    ).reset_index()

    behavior['montant_std'] = behavior['montant_std'].fillna(0)
    behavior['duree_activite_jours'] = (behavior['derniere_operation'] - behavior['premiere_operation']).dt.days
    behavior['frequence_mensuelle'] = behavior['nb_jours_actifs'] / np.maximum(behavior['duree_activite_jours'] / 30.0, 1)
    
    rfm_indexed = rfm.set_index('beneficiaire_id')
    behavior['ratio_weekend'] = behavior['nb_weekends'] / np.maximum(rfm_indexed.loc[behavior['beneficiaire_id']]['frequency'].values, 1)
    behavior['intensite'] = rfm_indexed.loc[behavior['beneficiaire_id']]['monetary'].values / np.maximum(behavior['nb_jours_actifs'], 1)
    behavior.drop(columns=['premiere_operation', 'derniere_operation'], inplace=True)

    mid_date = pd.Timestamp('2023-06-30')
    ops_h1 = df_obs[df_obs['date_complete'] <= mid_date].groupby('beneficiaire_id').agg(
        ops_h1=('nb_operations', 'sum'), montant_h1=('montant_reduction', 'sum')).reset_index()
    ops_h2 = df_obs[df_obs['date_complete'] > mid_date].groupby('beneficiaire_id').agg(
        ops_h2=('nb_operations', 'sum'), montant_h2=('montant_reduction', 'sum')).reset_index()
    last_q = df_obs[df_obs['date_complete'] >= pd.Timestamp('2024-04-01')].groupby('beneficiaire_id').agg(
        ops_last_q=('nb_operations', 'sum'), montant_last_q=('montant_reduction', 'sum')).reset_index()
    last_6m = df_obs[df_obs['date_complete'] >= pd.Timestamp('2024-01-01')].groupby('beneficiaire_id').agg(
        ops_last_6m=('nb_operations', 'sum')).reset_index()

    features = rfm.merge(behavior, on='beneficiaire_id', how='left')
    features = features.merge(ops_h1, on='beneficiaire_id', how='left')
    features = features.merge(ops_h2, on='beneficiaire_id', how='left')
    features = features.merge(last_q, on='beneficiaire_id', how='left')
    features = features.merge(last_6m, on='beneficiaire_id', how='left')

    for col in ['ops_h1', 'montant_h1', 'ops_h2', 'montant_h2', 'ops_last_q', 'montant_last_q', 'ops_last_6m']:
        features[col] = features[col].fillna(0)

    features['trend_ops'] = features['ops_h2'] - features['ops_h1']
    features['trend_montant'] = features['montant_h2'] - features['montant_h1']
    features['ratio_ops_recent'] = features['ops_last_q'] / np.maximum(features['frequency'], 1)
    features['ratio_ops_6m'] = features['ops_last_6m'] / np.maximum(features['frequency'], 1)
    features['acceleration'] = features['ops_h2'] / np.maximum(features['ops_h1'], 1)

    df = features.merge(df_benef, on='beneficiaire_id', how='inner')
    df['anciennete_jours'] = (cutoff_date - df['date_inscription']).dt.days

    benef_with_ops = set(df_obs['beneficiaire_id'].unique())
    benef_no_ops = df_benef[~df_benef['beneficiaire_id'].isin(benef_with_ops)].copy()
    if len(benef_no_ops) > 0:
        num_cols = [c for c in features.columns if c != 'beneficiaire_id']
        for col in num_cols:
            benef_no_ops[col] = 0
        benef_no_ops['recency'] = 999
        benef_no_ops['anciennete_jours'] = (cutoff_date - benef_no_ops['date_inscription']).dt.days
        df = pd.concat([df, benef_no_ops], ignore_index=True)

    df['churned'] = df['beneficiaire_id'].apply(lambda x: 0 if x in active_after else 1)

    benef_ids = df['beneficiaire_id'].values
    df_model = df.drop(columns=['date_inscription', 'beneficiaire_id'])

    df_model = pd.get_dummies(df_model, columns=['genre', 'tranche_age', 'statut_pass'], drop_first=True)
    df_model['en_situation_handicap'] = df_model['en_situation_handicap'].fillna(0).astype(int)
    df_model['est_membre_association'] = df_model['est_membre_association'].fillna(0).astype(int)

    y = df_model['churned']
    X = df_model.drop(columns=['churned']).fillna(0).replace([np.inf, -np.inf], 0)

    print(f"  Features générées : {X.shape[1]}")
    return X, y, benef_ids


def train_model(X: pd.DataFrame, y: pd.Series) -> StackingClassifier:
    """Entraîne un modèle d'ensemble sur toutes les données."""
    print("\n" + "=" * 70)
    print("ETAPE 2 : Entraînement du Stacking Ensemble (100% des données)")
    print("=" * 70)

    smote = SMOTE(random_state=42)
    X_sm, y_sm = smote.fit_resample(X, y)

    try:
        from xgboost import XGBClassifier
        estimators = [
            ('rf', RandomForestClassifier(n_estimators=500, max_depth=15, min_samples_split=5,
                                          min_samples_leaf=2, max_features='sqrt',
                                          class_weight='balanced', random_state=42, n_jobs=-1)),
            ('gb', GradientBoostingClassifier(n_estimators=500, max_depth=6, learning_rate=0.05,
                                              subsample=0.8, random_state=42)),
            ('xgb', XGBClassifier(n_estimators=500, max_depth=7, learning_rate=0.05,
                                  subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)),
        ]
    except ImportError:
        estimators = [
            ('rf', RandomForestClassifier(n_estimators=500, max_depth=15, class_weight='balanced', random_state=42, n_jobs=-1)),
            ('gb', GradientBoostingClassifier(n_estimators=500, max_depth=6, learning_rate=0.05, random_state=42)),
        ]

    stack = StackingClassifier(
        estimators=estimators,
        final_estimator=LogisticRegression(max_iter=1000, random_state=42),
        cv=5, n_jobs=-1
    )
    stack.fit(X_sm, y_sm)
    print("  Stacking Ensemble entraîné!")
    return stack


def risk_segment(prob: float) -> str:
    """Attribue un segment de risque selon la probabilité de churn."""
    if prob < 0.3:
        return 'Faible'
    elif prob < 0.6:
        return 'Moyen'
    else:
        return 'Eleve'


def score_beneficiaries(model, X: pd.DataFrame) -> tuple:
    """Score l'ensemble des bénéficiaires."""
    print("\n" + "=" * 70)
    print("ETAPE 3 : Scoring de tous les bénéficiaires")
    print("=" * 70)

    churn_probabilities = model.predict_proba(X)[:, 1]
    churn_predictions = (churn_probabilities >= 0.5).astype(int)
    risk_segments = [risk_segment(p) for p in churn_probabilities]

    print(f"  Bénéficiaires scorés    : {len(churn_probabilities):,}")
    print(f"  Risque Faible (<30%)    : {sum(1 for s in risk_segments if s == 'Faible'):,}")
    print(f"  Risque Moyen (30-60%)   : {sum(1 for s in risk_segments if s == 'Moyen'):,}")
    print(f"  Risque Elevé (>60%)     : {sum(1 for s in risk_segments if s == 'Eleve'):,}")

    return churn_probabilities, churn_predictions, risk_segments


def update_sql_server(benef_ids, probs, preds, segments, conn_str: str):
    """Met à jour DWH_MJCC avec les scores."""
    print("\n" + "=" * 70)
    print("ETAPE 4 : Ecriture des scores dans SQL Server (DWH_MJCC)")
    print("=" * 70)

    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='dim_beneficiaire' AND COLUMN_NAME='churn_probability')
    BEGIN
        ALTER TABLE dbo.dim_beneficiaire ADD churn_probability DECIMAL(5,4) DEFAULT 0;
        ALTER TABLE dbo.dim_beneficiaire ADD churn_predicted BIT DEFAULT 0;
        ALTER TABLE dbo.dim_beneficiaire ADD churn_risk_segment NVARCHAR(20) DEFAULT 'Faible';
    END
    """)
    print("  Colonnes ajoutées à dim_beneficiaire")

    for i in range(len(benef_ids)):
        cursor.execute("""
            UPDATE dbo.dim_beneficiaire 
            SET churn_probability = ?, churn_predicted = ?, churn_risk_segment = ?
            WHERE beneficiaire_id = ?
        """, (round(float(probs[i]), 4), int(preds[i]), segments[i], int(benef_ids[i])))

    cursor.execute("SELECT COUNT(*) FROM dbo.dim_beneficiaire WHERE churn_probability > 0")
    updated = cursor.fetchone()[0]
    print(f"  Bénéficiaires mis à jour : {updated:,}")
    conn.close()


def update_ssas_model():
    """Déploie les métadonnées SSAS via script PowerShell."""
    print("\n" + "=" * 70)
    print("ETAPE 5 : Mise à jour du modèle SSAS (TOM)")
    print("=" * 70)

    dll_path = r"C:\Program Files\Microsoft SQL Server Management Studio 22\Release\Common7\IDE\Microsoft.AnalysisServices.Tabular.dll"
    ps_path = str(Path(__file__).parent / "update_ssas_churn.ps1")

    ps_script = f"""
    Add-Type -Path "{dll_path}"
    $server = New-Object Microsoft.AnalysisServices.Tabular.Server
    $server.Connect("localhost\\SSASTAB")

    $db = $server.Databases["SSAS_MJCC_PROD"]
    $tbl = $db.Model.Tables["dim_beneficiaire"]

    if (-not $tbl.Columns.Contains("churn_probability")) {{
        $col1 = New-Object Microsoft.AnalysisServices.Tabular.DataColumn
        $col1.Name = "churn_probability"
        $col1.DataType = [Microsoft.AnalysisServices.Tabular.DataType]::Decimal
        $col1.SourceColumn = "churn_probability"
        $col1.FormatString = "0.00%"
        $tbl.Columns.Add($col1)
    }}

    if (-not $tbl.Columns.Contains("churn_predicted")) {{
        $col2 = New-Object Microsoft.AnalysisServices.Tabular.DataColumn
        $col2.Name = "churn_predicted"
        $col2.DataType = [Microsoft.AnalysisServices.Tabular.DataType]::Boolean
        $col2.SourceColumn = "churn_predicted"
        $tbl.Columns.Add($col2)
    }}

    if (-not $tbl.Columns.Contains("churn_risk_segment")) {{
        $col3 = New-Object Microsoft.AnalysisServices.Tabular.DataColumn
        $col3.Name = "churn_risk_segment"
        $col3.DataType = [Microsoft.AnalysisServices.Tabular.DataType]::String
        $col3.SourceColumn = "churn_risk_segment"
        $tbl.Columns.Add($col3)
    }}

    if (-not $tbl.Measures.Contains("Taux_Churn_Predit")) {{
        $m1 = New-Object Microsoft.AnalysisServices.Tabular.Measure
        $m1.Name = "Taux_Churn_Predit"
        $m1.Expression = 'DIVIDE(CALCULATE(COUNTROWS(dim_beneficiaire), dim_beneficiaire[churn_predicted] = TRUE()), COUNTROWS(dim_beneficiaire), 0)'
        $m1.FormatString = "0.0%"
        $tbl.Measures.Add($m1)
    }}

    if (-not $tbl.Measures.Contains("Nb_Beneficiaires_A_Risque")) {{
        $m2 = New-Object Microsoft.AnalysisServices.Tabular.Measure
        $m2.Name = "Nb_Beneficiaires_A_Risque"
        $m2.Expression = 'CALCULATE(COUNTROWS(dim_beneficiaire), dim_beneficiaire[churn_risk_segment] = "Eleve")'
        $m2.FormatString = "#,##0"
        $tbl.Measures.Add($m2)
    }}

    if (-not $tbl.Measures.Contains("Score_Churn_Moyen")) {{
        $m3 = New-Object Microsoft.AnalysisServices.Tabular.Measure
        $m3.Name = "Score_Churn_Moyen"
        $m3.Expression = 'AVERAGE(dim_beneficiaire[churn_probability])'
        $m3.FormatString = "0.0%"
        $tbl.Measures.Add($m3)
    }}

    $db.Model.SaveChanges()
    Write-Host "SaveChanges OK"

    $db.Model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
    $db.Model.SaveChanges()
    Write-Host "Process Full OK"

    $server.Disconnect()
    """

    with open(ps_path, "w", encoding="utf-8") as f:
        f.write(ps_script)

    r = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_path], capture_output=True, text=True)
    print("  STDOUT:", r.stdout.strip())
    if r.stderr.strip():
        print("  STDERR:", r.stderr.strip())

    # os.remove(ps_path)  # Commenté pour conserver le script et pouvoir le relancer manuellement


def main():
    """Point d'entrée du pipeline d'intégration Power BI."""
    CONN_STR = 'Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=DWH_MJCC;Trusted_Connection=yes;'
    CUTOFF_DATE = pd.Timestamp('2024-06-30')

    df_benef, df_ops = extract_data(CONN_STR)
    X, y, benef_ids = feature_engineering(df_benef, df_ops, CUTOFF_DATE)
    model = train_model(X, y)
    probs, preds, segments = score_beneficiaries(model, X)
    
    update_sql_server(benef_ids, probs, preds, segments, CONN_STR)
    update_ssas_model()

    print("\n" + "=" * 70)
    print("INTEGRATION TERMINEE!")
    print("=" * 70)
    print("  Les colonnes suivantes sont maintenant dans Power BI :")
    print("    - churn_probability    (Score 0.00 - 1.00)")
    print("    - churn_predicted      (Oui / Non)")
    print("    - churn_risk_segment   (Faible / Moyen / Eleve)")
    print("  Les mesures DAX suivantes sont disponibles :")
    print("    - Taux_Churn_Predit")
    print("    - Nb_Beneficiaires_A_Risque")
    print("    - Score_Churn_Moyen")
    print("  >>> Cliquez sur Refresh dans Power BI Desktop!")


if __name__ == "__main__":
    main()
