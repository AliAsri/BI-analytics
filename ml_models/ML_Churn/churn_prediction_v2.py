"""
=============================================================================
  PREDICTION DU CHURN - VERSION OPTIMISEE v2
  Projet MJCC - Pass Jeunes
=============================================================================

Ce module améliore la prédiction du churn grâce à des optimisations avancées :
    1. Feature Engineering poussé (RFM, tendances, interactions, ratios).
    2. Utilisation de SMOTE pour l'équilibrage des classes.
    3. Intégration de modèles puissants (XGBoost) et Stacking Ensemble.
    4. One-Hot Encoding et Scaling des données.

Fonctions principales :
    - extract_data : Importation des données depuis le DWH.
    - feature_engineering_advanced : Création d'indicateurs RFM et tendances.
    - prepare_advanced_data : Encodage, Scaling et Oversampling (SMOTE).
    - train_optimized_models : Entraînement des modèles et du Stacking Ensemble.
    - generate_advanced_visualizations : Tableaux de bord et graphiques complets.
"""

import os
import warnings
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyodbc
from imblearn.over_sampling import SMOTE
from matplotlib.gridspec import GridSpec
from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
    StackingClassifier,
)
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
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')
matplotlib.use('Agg')


def extract_data(conn_str: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Extrait les données bénéficiaires et opérations depuis DWH_MJCC.

    Args:
        conn_str (str): Chaîne de connexion à SQL Server.

    Returns:
        tuple: (Dataframe des bénéficiaires, Dataframe des opérations)
    """
    print("=" * 70)
    print("ETAPE 1 : Extraction des données depuis DWH_MJCC")
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
    
    print(f"  Bénéficiaires chargés   : {len(df_benef):,}")
    print(f"  Opérations chargées     : {len(df_ops):,}")
    return df_benef, df_ops


def feature_engineering_advanced(df_benef: pd.DataFrame, df_ops: pd.DataFrame, cutoff_date: pd.Timestamp) -> pd.DataFrame:
    """
    Applique un feature engineering avancé (RFM, comportement, tendances).

    Args:
        df_benef (pd.DataFrame): Données des bénéficiaires.
        df_ops (pd.DataFrame): Données des opérations.
        cutoff_date (pd.Timestamp): Date de coupure pour le churn.

    Returns:
        pd.DataFrame: Données enrichies prêtes pour la préparation ML.
    """
    print("\n" + "=" * 70)
    print("ETAPE 2 : Feature Engineering Avancé (RFM + Tendances + Interactions)")
    print("=" * 70)

    df_ops['date_complete'] = pd.to_datetime(df_ops['date_complete'])
    df_benef['date_inscription'] = pd.to_datetime(df_benef['date_inscription'])

    df_obs = df_ops[df_ops['date_complete'] <= cutoff_date].copy()
    df_future = df_ops[df_ops['date_complete'] > cutoff_date].copy()

    active_after = set(df_future['beneficiaire_id'].unique())

    # --- RFM Features ---
    rfm = df_obs.groupby('beneficiaire_id').agg(
        recency=('date_complete', lambda x: (cutoff_date - x.max()).days),
        frequency=('nb_operations', 'sum'),
        monetary=('montant_reduction', 'sum'),
    ).reset_index()

    # --- Comportement ---
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
    behavior['ratio_weekend'] = behavior['nb_weekends'] / np.maximum(rfm['frequency'], 1)
    behavior['intensite'] = rfm['monetary'] / np.maximum(behavior['nb_jours_actifs'], 1)
    behavior.drop(columns=['premiere_operation', 'derniere_operation'], inplace=True)

    # --- Tendances ---
    mid_date = pd.Timestamp('2023-06-30')
    ops_h1 = df_obs[df_obs['date_complete'] <= mid_date].groupby('beneficiaire_id').agg(
        ops_h1=('nb_operations', 'sum'), montant_h1=('montant_reduction', 'sum')
    ).reset_index()

    ops_h2 = df_obs[df_obs['date_complete'] > mid_date].groupby('beneficiaire_id').agg(
        ops_h2=('nb_operations', 'sum'), montant_h2=('montant_reduction', 'sum')
    ).reset_index()

    last_q = df_obs[df_obs['date_complete'] >= pd.Timestamp('2024-04-01')].groupby('beneficiaire_id').agg(
        ops_last_q=('nb_operations', 'sum'), montant_last_q=('montant_reduction', 'sum')
    ).reset_index()

    last_6m = df_obs[df_obs['date_complete'] >= pd.Timestamp('2024-01-01')].groupby('beneficiaire_id').agg(
        ops_last_6m=('nb_operations', 'sum')
    ).reset_index()

    # --- Merge ---
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
    df.drop(columns=['date_inscription', 'beneficiaire_id'], inplace=True)

    print(f"  Dataset final           : {len(df):,} bénéficiaires")
    print(f"  Churned (inactifs)      : {df['churned'].sum():,} ({df['churned'].mean()*100:.1f}%)")
    print(f"  Actifs (non-churned)    : {(df['churned']==0).sum():,} ({(1-df['churned'].mean())*100:.1f}%)")
    print(f"  Total features          : {len(df.columns) - 1}")

    return df


def prepare_advanced_data(df: pd.DataFrame) -> tuple:
    """
    Applique le One-Hot Encoding, le StandardScaler et le SMOTE.

    Args:
        df (pd.DataFrame): DataFrame complet.

    Returns:
        tuple: Composants nécessaires pour l'entraînement (X_train_sm, X_test, etc.)
    """
    print("\n" + "=" * 70)
    print("ETAPE 3 : Préparation (One-Hot, Scaling, SMOTE)")
    print("=" * 70)

    df_viz = df.copy()  # Pour la visualisation (démographie non encodée)
    df_encoded = pd.get_dummies(df, columns=['genre', 'tranche_age', 'statut_pass'], drop_first=True)
    df_encoded['en_situation_handicap'] = df_encoded['en_situation_handicap'].fillna(0).astype(int)
    df_encoded['est_membre_association'] = df_encoded['est_membre_association'].fillna(0).astype(int)

    y = df_encoded['churned']
    X = df_encoded.drop(columns=['churned']).fillna(0)
    X = X.replace([np.inf, -np.inf], 0)

    feature_names = X.columns.tolist()
    print(f"  Features finales        : {len(feature_names)}")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    smote = SMOTE(random_state=42)
    X_train_sm, y_train_sm = smote.fit_resample(X_train, y_train)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_sm)
    X_test_scaled = scaler.transform(X_test)

    print(f"  Train (avant SMOTE)     : {len(X_train):,}")
    print(f"  Train (après SMOTE)     : {len(X_train_sm):,}")
    print(f"  Test set                : {len(X_test):,}")

    return X, y, X_train_sm, X_test, y_train_sm, y_test, X_train_scaled, X_test_scaled, scaler, feature_names, df_viz


def train_optimized_models(X_train_sm, X_train_scaled, X_test, X_test_scaled, y_train_sm, y_test) -> tuple[dict, str]:
    """
    Entraîne des modèles optimisés dont le Stacking Ensemble.

    Args:
        Données d'entraînement et de test encodées, balancées et mises à l'échelle.

    Returns:
        tuple[dict, str]: Résultats des modèles et nom du meilleur modèle.
    """
    print("\n" + "=" * 70)
    print("ETAPE 4 : Entraînement des modèles optimisés")
    print("=" * 70)

    models = {}

    print("\n  [1/5] Logistic Regression (régularisée)...")
    lr = LogisticRegression(C=0.5, penalty='l2', max_iter=2000, random_state=42, solver='lbfgs')
    lr.fit(X_train_scaled, y_train_sm)
    models['Logistic Regression'] = ('scaled', lr)

    print("  [2/5] Random Forest (optimisé)...")
    rf = RandomForestClassifier(n_estimators=500, max_depth=15, min_samples_split=5,
                                min_samples_leaf=2, max_features='sqrt',
                                class_weight='balanced', random_state=42, n_jobs=-1)
    rf.fit(X_train_sm, y_train_sm)
    models['Random Forest'] = ('raw', rf)

    print("  [3/5] Gradient Boosting (optimisé)...")
    gb = GradientBoostingClassifier(n_estimators=500, max_depth=6, learning_rate=0.05,
                                    subsample=0.8, min_samples_split=10, min_samples_leaf=5,
                                    max_features='sqrt', random_state=42)
    gb.fit(X_train_sm, y_train_sm)
    models['Gradient Boosting'] = ('raw', gb)

    print("  [4/5] XGBoost...")
    try:
        from xgboost import XGBClassifier
        xgb = XGBClassifier(n_estimators=500, max_depth=7, learning_rate=0.05,
                            subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
                            gamma=0.1, reg_alpha=0.1, reg_lambda=1.0,
                            eval_metric='logloss', random_state=42, n_jobs=-1)
        xgb.fit(X_train_sm, y_train_sm)
        models['XGBoost'] = ('raw', xgb)
    except ImportError:
        print("    XGBoost non installé, passage...")

    print("  [5/5] Stacking Ensemble...")
    estimators = [
        ('rf', RandomForestClassifier(n_estimators=200, max_depth=12, class_weight='balanced', random_state=42, n_jobs=-1)),
        ('gb', GradientBoostingClassifier(n_estimators=200, max_depth=5, learning_rate=0.08, random_state=42)),
    ]
    if 'XGBoost' in models:
        estimators.append(('xgb', XGBClassifier(n_estimators=200, max_depth=6, learning_rate=0.08,
                                                eval_metric='logloss', random_state=42, n_jobs=-1)))

    stack = StackingClassifier(
        estimators=estimators,
        final_estimator=LogisticRegression(max_iter=1000, random_state=42),
        cv=5, n_jobs=-1
    )
    stack.fit(X_train_sm, y_train_sm)
    models['Stacking Ensemble'] = ('raw', stack)

    print("\n" + "=" * 70)
    print("Evaluation des modèles")
    print("=" * 70)

    results = {}
    for name, (data_type, model) in models.items():
        X_eval = X_test_scaled if data_type == 'scaled' else X_test
        y_pred = model.predict(X_eval)
        y_proba = model.predict_proba(X_eval)[:, 1]

        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred)
        rec = recall_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        auc = roc_auc_score(y_test, y_proba)

        results[name] = {
            'model': model, 'data_type': data_type, 'accuracy': acc,
            'precision': prec, 'recall': rec, 'f1': f1, 'auc': auc,
            'y_pred': y_pred, 'y_proba': y_proba
        }
        print(f"\n  {name}:")
        print(f"    Accuracy  : {acc:.4f} | Precision : {prec:.4f} | Recall : {rec:.4f} | F1-Score : {f1:.4f} | AUC : {auc:.4f}")

    best_name = max(results, key=lambda k: results[k]['f1'])
    print(f"\n  >>> MEILLEUR MODELE : {best_name} (F1={results[best_name]['f1']:.4f}, AUC={results[best_name]['auc']:.4f})")
    
    return results, best_name


def generate_advanced_visualizations(results: dict, best_name: str, models: dict, y_test, df_viz: pd.DataFrame, 
                                     feature_names: list, output_dir: str, cutoff_date: pd.Timestamp, cv_score_mean: float, cv_score_std: float):
    """
    Crée et enregistre les graphiques pour la version optimisée.

    Args:
        results (dict): Résultats des modèles.
        best_name (str): Nom du meilleur modèle.
        models (dict): Dictionnaire des modèles instanciés.
        y_test: Vraies étiquettes de test.
        df_viz (pd.DataFrame): DataFrame original pour les démographies.
        feature_names (list): Noms des features explicatives.
        output_dir (str): Dossier cible.
        cutoff_date (pd.Timestamp): Date de coupure.
        cv_score_mean (float): Moyenne de cross-validation F1.
        cv_score_std (float): Écart-type de cross-validation F1.
    """
    print("\n" + "=" * 70)
    print("ETAPE 6 : Génération des Visualisations Professionnelles")
    print("=" * 70)

    os.makedirs(output_dir, exist_ok=True)
    
    COLORS = {
        'bg_dark': '#0A1628', 'bg_card': '#1A2A44', 'text': '#E0E0E0', 'grid': '#2A3A54',
        'blue': '#4FC3F7', 'green': '#66BB6A', 'orange': '#FFA726', 'red': '#EF5350',
        'purple': '#AB47BC', 'cyan': '#26C6DA', 'yellow': '#FFEE58',
    }

    plt.rcParams.update({
        'figure.facecolor': COLORS['bg_dark'], 'axes.facecolor': COLORS['bg_card'],
        'axes.edgecolor': COLORS['grid'], 'axes.labelcolor': COLORS['text'],
        'text.color': COLORS['text'], 'xtick.color': COLORS['text'],
        'ytick.color': COLORS['text'], 'font.family': 'sans-serif', 'font.size': 11,
    })

    model_colors = {
        'Logistic Regression': COLORS['blue'], 'Random Forest': COLORS['green'],
        'Gradient Boosting': COLORS['orange'], 'XGBoost': COLORS['red'],
        'Stacking Ensemble': COLORS['purple'],
    }

    fig = plt.figure(figsize=(20, 10))
    gs = GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.3)
    fig.suptitle('PRÉDICTION DU CHURN - Comparaison des Modèles Optimisés (v2)', fontsize=18, fontweight='bold', color='white', y=0.98)

    ax1 = fig.add_subplot(gs[0, 0:2])
    metrics = ['accuracy', 'precision', 'recall', 'f1', 'auc']
    metric_labels = ['Accuracy', 'Precision', 'Recall', 'F1-Score', 'AUC-ROC']
    model_names = list(results.keys())
    x = np.arange(len(metrics))
    width = 0.15

    for i, name in enumerate(model_names):
        values = [results[name][m] for m in metrics]
        color = model_colors.get(name, COLORS['cyan'])
        bars = ax1.bar(x + i * width, values, width, label=name, color=color, alpha=0.85, edgecolor='white', linewidth=0.5)
        for bar, val in zip(bars, values):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.008, f'{val:.2f}', ha='center', va='bottom', fontsize=7, fontweight='bold')

    ax1.set_xticks(x + width * (len(model_names) - 1) / 2)
    ax1.set_xticklabels(metric_labels, fontsize=10)
    ax1.set_ylim(0, 1.12)
    ax1.set_title('Métriques de Classification', fontweight='bold', fontsize=13)
    ax1.legend(fontsize=8, loc='upper right', ncol=2)
    ax1.grid(axis='y', alpha=0.2)

    ax2 = fig.add_subplot(gs[0, 2])
    for name in model_names:
        fpr, tpr, _ = roc_curve(y_test, results[name]['y_proba'])
        color = model_colors.get(name, COLORS['cyan'])
        ax2.plot(fpr, tpr, color=color, linewidth=2, label=f"{name} ({results[name]['auc']:.3f})")
    ax2.plot([0, 1], [0, 1], 'w--', alpha=0.3)
    ax2.set_xlabel('FPR')
    ax2.set_ylabel('TPR')
    ax2.set_title('Courbes ROC', fontweight='bold', fontsize=13)
    ax2.legend(fontsize=7, loc='lower right')
    ax2.grid(alpha=0.2)

    ax3 = fig.add_subplot(gs[1, 0])
    cm = confusion_matrix(y_test, results[best_name]['y_pred'])
    ax3.imshow(cm, cmap='Blues', alpha=0.8)
    ax3.set_xticks([0, 1]); ax3.set_yticks([0, 1])
    ax3.set_xticklabels(['Actif', 'Churné'], fontsize=10)
    ax3.set_yticklabels(['Actif', 'Churné'], fontsize=10)
    ax3.set_title(f'Matrice de Confusion\n({best_name})', fontweight='bold', fontsize=12)
    for i in range(2):
        for j in range(2):
            color = 'white' if cm[i, j] > cm.max() / 2 else COLORS['text']
            ax3.text(j, i, f'{cm[i, j]:,}', ha='center', va='center', fontsize=18, fontweight='bold', color=color)

    ax4 = fig.add_subplot(gs[1, 1])
    proba = results[best_name]['y_proba']
    ax4.hist(proba[y_test == 0], bins=40, alpha=0.7, color=COLORS['green'], label='Actifs', edgecolor='white', linewidth=0.3)
    ax4.hist(proba[y_test == 1], bins=40, alpha=0.7, color=COLORS['red'], label='Churnés', edgecolor='white', linewidth=0.3)
    ax4.axvline(x=0.5, color='white', linestyle='--', linewidth=1.5, alpha=0.7, label='Seuil 0.5')
    ax4.set_title('Distribution des Probabilités', fontweight='bold', fontsize=12)
    ax4.legend(fontsize=9)
    ax4.grid(axis='y', alpha=0.2)

    ax5 = fig.add_subplot(gs[1, 2])
    f1_scores = sorted([(n, results[n]['f1']) for n in model_names], key=lambda x: x[1])
    bars = ax5.barh([x[0] for x in f1_scores], [x[1] for x in f1_scores], color=[model_colors.get(n, COLORS['cyan']) for n in [x[0] for x in f1_scores]], alpha=0.85, edgecolor='white')
    for bar, val in zip(bars, [x[1] for x in f1_scores]):
        ax5.text(val + 0.005, bar.get_y() + bar.get_height()/2, f'{val:.3f}', va='center', fontsize=10, fontweight='bold')
    ax5.set_title('Classement par F1-Score', fontweight='bold', fontsize=12)
    ax5.grid(axis='x', alpha=0.2)

    plt.savefig(os.path.join(output_dir, '01_model_comparison_v2.png'), dpi=150, bbox_inches='tight', facecolor=COLORS['bg_dark'], edgecolor='none')
    plt.close()

    # Feature Importance (Top 20)
    fig, ax = plt.subplots(figsize=(12, 9))
    best_raw_model = models[best_name] if best_name != 'Stacking Ensemble' else models['Random Forest']
    importances = best_raw_model.feature_importances_ if hasattr(best_raw_model, 'feature_importances_') else np.abs(best_raw_model.coef_[0])
    
    fi = pd.Series(importances, index=feature_names).sort_values(ascending=True).tail(20)
    colors_grad = plt.cm.viridis(np.linspace(0.3, 0.95, len(fi)))
    bars = ax.barh(fi.index, fi.values, color=colors_grad, edgecolor='white', linewidth=0.5)
    for bar, val in zip(bars, fi.values):
        ax.text(val + 0.001, bar.get_y() + bar.get_height()/2, f'{val:.4f}', va='center', fontsize=9, fontweight='bold')
    ax.set_title(f'Top 20 Features les plus Importantes', fontweight='bold', fontsize=14, pad=15)
    ax.grid(axis='x', alpha=0.2)
    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, '02_feature_importance_v2.png'), dpi=150, bbox_inches='tight', facecolor=COLORS['bg_dark'], edgecolor='none')
    plt.close()

    # Classification Report
    best_report = classification_report(y_test, results[best_name]['y_pred'], target_names=['Actif', 'Churné'])
    print(f"\n{'='*70}\nRAPPORT DE CLASSIFICATION FINAL - {best_name}\n{'='*70}\n{best_report}")

    with open(os.path.join(output_dir, 'churn_model_summary_v2.txt'), 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\nPRÉDICTION DU CHURN - RÉSULTATS OPTIMISÉS v2\nProjet MJCC - Pass Jeunes\n" + "=" * 70 + "\n\n")
        f.write(f"Date de référence (cutoff) : {cutoff_date.date()}\n")
        f.write(f"Dataset : {len(df_viz):,} bénéficiaires\n")
        f.write(f"Features : {len(feature_names)}\n\n")
        f.write("RÉSULTATS:\n")
        for name in results:
            r = results[name]
            f.write(f"\n  {name}:\n    Accuracy={r['accuracy']:.4f}  Precision={r['precision']:.4f}  Recall={r['recall']:.4f}  F1={r['f1']:.4f}  AUC={r['auc']:.4f}\n")
        f.write(f"\nMEILLEUR MODÈLE : {best_name} (F1={results[best_name]['f1']:.4f})\n")
        f.write(f"Cross-Validation F1 (5-fold) : {cv_score_mean:.4f} (+/- {cv_score_std:.4f})\n\n")
        f.write("RAPPORT DE CLASSIFICATION:\n" + best_report)

    print(f"\nTous les fichiers sauvegardés dans : {output_dir}")


def main():
    """Point d'entrée principal du script optimisé."""
    CONN_STR = 'Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=DWH_MJCC;Trusted_Connection=yes;'
    CUTOFF_DATE = pd.Timestamp('2024-06-30')
    OUTPUT_DIR = str(Path(__file__).parent)

    df_benef, df_ops = extract_data(CONN_STR)
    df = feature_engineering_advanced(df_benef, df_ops, CUTOFF_DATE)
    
    # Préparation et Entraînement
    X, y, X_train_sm, X_test, y_train_sm, y_test, X_train_scaled, X_test_scaled, scaler, feature_names, df_viz = prepare_advanced_data(df)
    results, best_name = train_optimized_models(X_train_sm, X_train_scaled, X_test, X_test_scaled, y_train_sm, y_test)

    # Cross-validation
    best_data_type, best_model = results[best_name]['data_type'], results[best_name]['model']
    X_cv = scaler.transform(X) if best_data_type == 'scaled' else X
    cv_scores = cross_val_score(best_model, X_cv, y, cv=StratifiedKFold(5, shuffle=True, random_state=42), scoring='f1')
    print(f"  Cross-Validation F1 (5-fold) : {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

    # Visualisation
    models_dict = {name: results[name]['model'] for name in results}
    generate_advanced_visualizations(results, best_name, models_dict, y_test, df_viz, feature_names, OUTPUT_DIR, CUTOFF_DATE, cv_scores.mean(), cv_scores.std())


if __name__ == "__main__":
    main()
