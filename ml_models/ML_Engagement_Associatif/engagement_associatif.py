"""
=============================================================================
  PREDICTION DE L'ENGAGEMENT ASSOCIATIF (PassJeunes -> Jam3iya)
  Projet MJCC
=============================================================================

Ce module permet de prédire quels bénéficiaires Pass Jeunes sont susceptibles
de devenir membres d'une association Jam3iya, en se basant sur leur comportement.

Fonctions principales :
    - extract_data : Importation des données depuis SQL Server.
    - feature_engineering : Construction des features (comportement, secteurs).
    - train_models : Entraînement et évaluation (Logistic Regression, RF, GB, XGB).
    - score_and_visualize : Génération des prédictions sur tout le dataset et graphiques.
    - update_sql_and_ssas : Intégration des scores vers DWH et SSAS.
"""

import os
import subprocess
import warnings

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyodbc
from imblearn.over_sampling import SMOTE
from matplotlib.gridspec import GridSpec
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')
matplotlib.use('Agg')


def extract_data(conn_str: str, conn_str_stg: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    """
    Extrait les données nécessaires depuis DWH_MJCC et STAGING_MJCC.

    Args:
        conn_str (str): Chaîne de connexion pour DWH_MJCC.
        conn_str_stg (str): Chaîne de connexion pour STAGING_MJCC.

    Returns:
        tuple: (Données bénéficiaires, Données opérations, Date de référence max)
    """
    print("=" * 70)
    print("ETAPE 1 : Extraction des données (PassJeunes + Jam3iya)")
    print("=" * 70)

    conn = pyodbc.connect(conn_str)
    df_benef = pd.read_sql("""
        SELECT beneficiaire_id, genre, tranche_age, statut_pass,
               en_situation_handicap, est_membre_association, date_inscription
        FROM dbo.dim_beneficiaire
    """, conn)

    df_ops = pd.read_sql("""
        SELECT f.beneficiaire_id, f.montant_reduction, f.nb_operations,
               f.offre_id, t.date_complete, t.est_weekend,
               r.region, o.secteur, o.categorie
        FROM dbo.fait_operations f
        INNER JOIN dbo.dim_temps t ON f.temps_id = t.temps_id
        INNER JOIN dbo.dim_region r ON f.region_id = r.region_id
        INNER JOIN dbo.dim_offre o ON f.offre_id = o.offre_id
    """, conn)

    df_activites = pd.read_sql("""
        SELECT a.association_id, a.type AS type_activite,
               a.nb_participants, a.budget_total, a.budget_consomme
        FROM dbo.fait_activites a
    """, conn)
    df_associations = pd.read_sql("SELECT * FROM dbo.dim_association", conn)
    conn.close()

    conn_stg = pyodbc.connect(conn_str_stg)
    df_membres = pd.read_sql("""
        SELECT jeune_cin, association_id, type_personne, role, specialite, date_debut
        FROM dbo.stg_jam3iya_personne_association
        WHERE jeune_cin IS NOT NULL
    """, conn_stg)
    conn_stg.close()

    df_ops['date_complete'] = pd.to_datetime(df_ops['date_complete'])
    df_benef['date_inscription'] = pd.to_datetime(df_benef['date_inscription'])
    ref_date = df_ops['date_complete'].max()

    membres_count = df_benef['est_membre_association'].sum()
    non_membres = len(df_benef) - membres_count

    print(f"  Bénéficiaires Pass Jeunes : {len(df_benef):,}")
    print(f"  Opérations                : {len(df_ops):,}")
    print(f"  Associations Jam3iya      : {len(df_associations):,}")
    print(f"  Activités Jam3iya         : {len(df_activites):,}")
    print(f"  Membres (CIN)             : {membres_count:,} ({membres_count/len(df_benef)*100:.1f}%)")
    
    return df_benef, df_ops, ref_date


def feature_engineering(df_benef: pd.DataFrame, df_ops: pd.DataFrame, ref_date: pd.Timestamp):
    """Calcule et agrège les variables prédictives de l'engagement associatif."""
    print("\n" + "=" * 70)
    print("ETAPE 2 : Feature Engineering")
    print("=" * 70)

    ops_features = df_ops.groupby('beneficiaire_id').agg(
        recency=('date_complete', lambda x: (ref_date - x.max()).days),
        frequency=('nb_operations', 'sum'),
        monetary=('montant_reduction', 'sum'),
        montant_moyen=('montant_reduction', 'mean'),
        montant_std=('montant_reduction', 'std'),
        nb_offres=('offre_id', 'nunique'),
        nb_secteurs=('secteur', 'nunique'),
        nb_categories=('categorie', 'nunique'),
        nb_regions=('region', 'nunique'),
        nb_jours_actifs=('date_complete', 'nunique'),
        nb_weekends=('est_weekend', 'sum'),
        premiere_op=('date_complete', 'min'),
        derniere_op=('date_complete', 'max'),
    ).reset_index()

    ops_features['montant_std'] = ops_features['montant_std'].fillna(0)
    ops_features['duree_activite'] = (ops_features['derniere_op'] - ops_features['premiere_op']).dt.days
    ops_features['frequence_mensuelle'] = ops_features['frequency'] / np.maximum(ops_features['duree_activite'] / 30.0, 1)
    ops_features['ratio_weekend'] = ops_features['nb_weekends'] / np.maximum(ops_features['frequency'], 1)
    ops_features['diversite_offres'] = ops_features['nb_offres'] / np.maximum(ops_features['frequency'], 1)
    ops_features['intensite'] = ops_features['monetary'] / np.maximum(ops_features['nb_jours_actifs'], 1)
    
    secteur_counts = df_ops.groupby(['beneficiaire_id', 'secteur']).size().unstack(fill_value=0)
    secteur_pct = secteur_counts.div(secteur_counts.sum(axis=1), axis=0)
    secteur_pct.columns = ['pct_secteur_' + str(c).replace(' ', '_') for c in secteur_pct.columns]
    secteur_pct = secteur_pct.reset_index()

    ops_features.drop(columns=['premiere_op', 'derniere_op'], inplace=True)

    df = ops_features.merge(df_benef, on='beneficiaire_id', how='right')
    df = df.merge(secteur_pct, on='beneficiaire_id', how='left')

    num_cols = [c for c in df.columns if df[c].dtype in ['float64', 'int64', 'float32'] and c != 'beneficiaire_id']
    for col in num_cols:
        df[col] = df[col].fillna(999) if col == 'recency' else df[col].fillna(0)

    df['anciennete'] = (ref_date - df['date_inscription']).dt.days
    y = df['est_membre_association'].fillna(0).astype(int)

    benef_ids = df['beneficiaire_id'].values
    X = df.drop(columns=['beneficiaire_id', 'date_inscription', 'est_membre_association'])
    X = pd.get_dummies(X, columns=['genre', 'tranche_age', 'statut_pass'], drop_first=True)
    X['en_situation_handicap'] = X['en_situation_handicap'].fillna(0).astype(int)
    X = X.fillna(0).replace([np.inf, -np.inf], 0)

    print(f"  Dataset         : {len(X):,} bénéficiaires x {len(X.columns)} features")
    return X, y, benef_ids


def train_models(X: pd.DataFrame, y: pd.Series) -> tuple:
    """Entraîne et évalue différents modèles (avec SMOTE)."""
    print("\n" + "=" * 70)
    print("ETAPE 3 & 4 : Entraînement (SMOTE) et Évaluation")
    print("=" * 70)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    smote = SMOTE(random_state=42)
    X_train_sm, y_train_sm = smote.fit_resample(X_train, y_train)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_sm)
    X_test_scaled = scaler.transform(X_test)

    models = {}
    print("\n  [1/4] Logistic Regression...")
    lr = LogisticRegression(C=0.5, max_iter=2000, random_state=42)
    lr.fit(X_train_scaled, y_train_sm)
    models['Logistic Regression'] = ('scaled', lr)

    print("  [2/4] Random Forest...")
    rf = RandomForestClassifier(n_estimators=500, max_depth=15, min_samples_leaf=2,
                                class_weight='balanced', random_state=42, n_jobs=-1)
    rf.fit(X_train_sm, y_train_sm)
    models['Random Forest'] = ('raw', rf)

    print("  [3/4] Gradient Boosting...")
    gb = GradientBoostingClassifier(n_estimators=500, max_depth=6, learning_rate=0.05,
                                    subsample=0.8, random_state=42)
    gb.fit(X_train_sm, y_train_sm)
    models['Gradient Boosting'] = ('raw', gb)

    print("  [4/4] XGBoost...")
    try:
        from xgboost import XGBClassifier
        xgb = XGBClassifier(n_estimators=500, max_depth=7, learning_rate=0.05,
                            subsample=0.8, colsample_bytree=0.8, scale_pos_weight=15,
                            random_state=42, n_jobs=-1)
        xgb.fit(X_train_sm, y_train_sm)
        models['XGBoost'] = ('raw', xgb)
    except ImportError:
        print("    XGBoost non disponible")

    results = {}
    for name, (data_type, model) in models.items():
        X_eval = X_test_scaled if data_type == 'scaled' else X_test
        y_pred = model.predict(X_eval)
        y_proba = model.predict_proba(X_eval)[:, 1]

        results[name] = {
            'model': model, 'data_type': data_type,
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred),
            'f1': f1_score(y_test, y_pred),
            'auc': roc_auc_score(y_test, y_proba),
            'y_pred': y_pred, 'y_proba': y_proba
        }
        r = results[name]
        print(f"  {name}: Acc={r['accuracy']:.4f} Prec={r['precision']:.4f} Rec={r['recall']:.4f} F1={r['f1']:.4f} AUC={r['auc']:.4f}")

    best_name = max(results, key=lambda k: results[k]['auc'])
    print(f"\n  >>> MEILLEUR MODELE : {best_name} (AUC={results[best_name]['auc']:.4f})")
    
    return results, best_name, scaler, X_test, y_test


def score_and_visualize(X: pd.DataFrame, y: pd.Series, results: dict, best_name: str, scaler: StandardScaler, y_test, output_dir: str):
    """Applique le modèle à tout le dataset et génère le tableau de bord."""
    print("\n" + "=" * 70)
    print("ETAPE 5 & 6 : Scoring global et Visualisations")
    print("=" * 70)

    best_data_type, best_model = results[best_name]['data_type'], results[best_name]['model']
    X_all = scaler.transform(X) if best_data_type == 'scaled' else X
    assoc_probabilities = best_model.predict_proba(X_all)[:, 1]

    def propensity_level(prob):
        return 'Faible' if prob < 0.3 else 'Moyen' if prob < 0.6 else 'Eleve'

    propensity_levels = [propensity_level(p) for p in assoc_probabilities]

    os.makedirs(output_dir, exist_ok=True)
    COLORS = {'bg_dark': '#0A1628', 'bg_card': '#1A2A44', 'text': '#E0E0E0', 'grid': '#2A3A54',
              'blue': '#4FC3F7', 'green': '#66BB6A', 'orange': '#FFA726', 'red': '#EF5350', 'purple': '#AB47BC'}
    
    plt.rcParams.update({'figure.facecolor': COLORS['bg_dark'], 'axes.facecolor': COLORS['bg_card'],
                         'axes.edgecolor': COLORS['grid'], 'axes.labelcolor': COLORS['text'],
                         'text.color': COLORS['text'], 'xtick.color': COLORS['text'],
                         'ytick.color': COLORS['text'], 'font.size': 11})

    fig = plt.figure(figsize=(20, 12))
    gs = GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.3)
    fig.suptitle('PREDICTION ENGAGEMENT ASSOCIATIF (Pass Jeunes -> Jam3iya)', fontsize=18, fontweight='bold', color='white', y=0.98)

    ax1 = fig.add_subplot(gs[0, 0])
    for name in results:
        fpr, tpr, _ = roc_curve(y_test, results[name]['y_proba'])
        ax1.plot(fpr, tpr, linewidth=2, label=f"{name} ({results[name]['auc']:.3f})")
    ax1.plot([0, 1], [0, 1], 'w--', alpha=0.3)
    ax1.set_title('Courbes ROC', fontweight='bold')
    ax1.legend(fontsize=7)

    ax2 = fig.add_subplot(gs[0, 1:3])
    importances = best_model.feature_importances_ if hasattr(best_model, 'feature_importances_') else np.abs(best_model.coef_[0])
    fi = pd.Series(importances, index=X.columns).sort_values().tail(15)
    ax2.barh(fi.index, fi.values, color=plt.cm.viridis(np.linspace(0.3, 0.95, len(fi))))
    ax2.set_title(f'Top 15 Features ({best_name})', fontweight='bold')

    ax3 = fig.add_subplot(gs[1, 0])
    cm = confusion_matrix(y_test, results[best_name]['y_pred'])
    ax3.imshow(cm, cmap='Blues', alpha=0.8)
    ax3.set_xticks([0, 1]); ax3.set_yticks([0, 1])
    ax3.set_xticklabels(['Non-Membre', 'Membre'])
    ax3.set_yticklabels(['Non-Membre', 'Membre'])
    for i in range(2):
        for j in range(2):
            ax3.text(j, i, f'{cm[i, j]:,}', ha='center', va='center', fontsize=18, fontweight='bold', color='white' if cm[i,j]>cm.max()/2 else COLORS['text'])
    ax3.set_title('Matrice de Confusion', fontweight='bold')

    ax4 = fig.add_subplot(gs[1, 1])
    ax4.hist(assoc_probabilities[y == 0], bins=40, alpha=0.7, color=COLORS['blue'], label='Non-Membres')
    ax4.hist(assoc_probabilities[y == 1], bins=40, alpha=0.7, color=COLORS['green'], label='Membres')
    ax4.axvline(x=0.5, color='white', linestyle='--', linewidth=1.5)
    ax4.set_title('Distribution des Scores', fontweight='bold')
    ax4.legend(fontsize=9)

    ax5 = fig.add_subplot(gs[1, 2])
    prop_counts = pd.Series(propensity_levels).value_counts()
    prop_order = ['Faible', 'Moyen', 'Eleve']
    prop_vals = [prop_counts.get(p, 0) for p in prop_order]
    ax5.pie(prop_vals, labels=prop_order, autopct='%1.1f%%', colors=[COLORS['green'], COLORS['orange'], COLORS['red']], startangle=90)
    ax5.add_artist(plt.Circle((0, 0), 0.55, fc=COLORS['bg_card']))
    ax5.set_title('Niveaux de Propension', fontweight='bold')

    plt.savefig(os.path.join(output_dir, '01_engagement_associatif_dashboard.png'), dpi=150, bbox_inches='tight', facecolor=COLORS['bg_dark'], edgecolor='none')
    plt.close()
    
    with open(os.path.join(output_dir, 'engagement_associatif_summary.txt'), 'w', encoding='utf-8') as f:
        f.write("PREDICTION ENGAGEMENT ASSOCIATIF - RESUME\n" + "=" * 50 + "\n")
        f.write(f"Meilleur modèle : {best_name}\nAUC-ROC : {results[best_name]['auc']:.4f}\n\n")
        f.write(classification_report(y_test, results[best_name]['y_pred'], target_names=['Non-Membre', 'Membre']))

    return assoc_probabilities, propensity_levels


def update_sql_and_ssas(benef_ids, probs, levels, conn_str: str):
    """Enregistre les prédictions dans le DWH et rafraîchit le cube SSAS."""
    print("\n" + "=" * 70)
    print("ETAPE 7 : Intégration SQL Server + SSAS")
    print("=" * 70)

    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='dim_beneficiaire' AND COLUMN_NAME='propension_associative')
    BEGIN
        ALTER TABLE dbo.dim_beneficiaire ADD propension_associative DECIMAL(5,4) DEFAULT 0;
        ALTER TABLE dbo.dim_beneficiaire ADD niveau_propension_assoc NVARCHAR(20) DEFAULT 'Faible';
    END
    """)

    for i in range(len(benef_ids)):
        cursor.execute("""
            UPDATE dbo.dim_beneficiaire 
            SET propension_associative = ?, niveau_propension_assoc = ?
            WHERE beneficiaire_id = ?
        """, (round(float(probs[i]), 4), levels[i], int(benef_ids[i])))
    conn.close()

    ps_script = f"""
    Add-Type -Path "C:\\Program Files\\Microsoft SQL Server Management Studio 22\\Release\\Common7\\IDE\\Microsoft.AnalysisServices.Tabular.dll"
    $server = New-Object Microsoft.AnalysisServices.Tabular.Server
    $server.Connect("localhost\\SSASTAB")
    $db = $server.Databases["SSAS_MJCC_PROD"]
    $tbl = $db.Model.Tables["dim_beneficiaire"]

    if (-not $tbl.Columns.Contains("propension_associative")) {{
        $col1 = New-Object Microsoft.AnalysisServices.Tabular.DataColumn
        $col1.Name = "propension_associative"
        $col1.DataType = [Microsoft.AnalysisServices.Tabular.DataType]::Decimal
        $col1.SourceColumn = "propension_associative"
        $tbl.Columns.Add($col1)
    }}
    if (-not $tbl.Columns.Contains("niveau_propension_assoc")) {{
        $col2 = New-Object Microsoft.AnalysisServices.Tabular.DataColumn
        $col2.Name = "niveau_propension_assoc"
        $col2.DataType = [Microsoft.AnalysisServices.Tabular.DataType]::String
        $col2.SourceColumn = "niveau_propension_assoc"
        $tbl.Columns.Add($col2)
    }}

    $db.Model.SaveChanges()
    $db.Model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
    $db.Model.SaveChanges()
    $server.Disconnect()
    """
    
    ps_path = r"c:\Users\moali\OneDrive\Desktop\Projet MJCC\update_ssas_assoc.ps1"
    with open(ps_path, "w", encoding="utf-8") as f:
        f.write(ps_script)

    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_path], capture_output=True, text=True)
    os.remove(ps_path)


def main():
    """Point d'entrée du script d'engagement associatif."""
    CONN_DWH = 'Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=DWH_MJCC;Trusted_Connection=yes;'
    CONN_STG = 'Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=STAGING_MJCC;Trusted_Connection=yes;'
    OUTPUT_DIR = r'c:\Users\moali\OneDrive\Desktop\Projet MJCC\ML_Engagement_Associatif'

    df_benef, df_ops, ref_date = extract_data(CONN_DWH, CONN_STG)
    X, y, benef_ids = feature_engineering(df_benef, df_ops, ref_date)
    results, best_name, scaler, X_test, y_test = train_models(X, y)
    probs, levels = score_and_visualize(X, y, results, best_name, scaler, y_test, OUTPUT_DIR)
    update_sql_and_ssas(benef_ids, probs, levels, CONN_DWH)


if __name__ == "__main__":
    main()
