"""
=============================================================================
  PRÉDICTION DU CHURN (Attrition des Bénéficiaires Pass Jeunes)
  Projet MJCC - Ministère de la Jeunesse, de la Culture et de la Communication
=============================================================================

Ce module permet de prédire le risque d'attrition (churn) des jeunes 
bénéficiaires du Pass Jeunes. Il extrait les données depuis le Data Warehouse,
effectue le feature engineering, entraîne plusieurs modèles de classification
(Régression Logistique, Random Forest, Gradient Boosting) et génère des
visualisations de performance.

Fonctions :
    - extract_data : Extraction des données depuis SQL Server.
    - feature_engineering : Création des variables explicatives et de la cible.
    - prepare_data : Encodage et séparation des données.
    - train_and_evaluate_models : Entraînement et évaluation des modèles.
    - generate_visualizations : Création des graphiques de performance.
"""

import os
import warnings

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyodbc
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
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings('ignore')
matplotlib.use('Agg')


def extract_data(conn_str: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Extrait les données des bénéficiaires et de leurs opérations depuis DWH_MJCC.

    Args:
        conn_str (str): Chaîne de connexion à la base de données SQL Server.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: DataFrames contenant respectivement 
                                           les bénéficiaires et les opérations.
    """
    print("=" * 70)
    print("ÉTAPE 1 : Extraction des données depuis DWH_MJCC")
    print("=" * 70)

    conn = pyodbc.connect(conn_str)

    df_benef = pd.read_sql("""
        SELECT beneficiaire_id, genre, tranche_age, statut_pass,
               en_situation_handicap, est_membre_association, date_inscription
        FROM dbo.dim_beneficiaire
    """, conn)

    df_ops = pd.read_sql("""
        SELECT f.beneficiaire_id, f.montant_reduction, f.nb_operations,
               f.offre_id, t.date_complete, r.region, o.secteur
        FROM dbo.fait_operations f
        INNER JOIN dbo.dim_temps t ON f.temps_id = t.temps_id
        INNER JOIN dbo.dim_region r ON f.region_id = r.region_id
        INNER JOIN dbo.dim_offre o ON f.offre_id = o.offre_id
    """, conn)

    conn.close()
    
    print(f"  Bénéficiaires chargés   : {len(df_benef):,}")
    print(f"  Opérations chargées     : {len(df_ops):,}")
    print(f"  Période des opérations  : {df_ops['date_complete'].min()} -> {df_ops['date_complete'].max()}")
    
    return df_benef, df_ops


def feature_engineering(df_benef: pd.DataFrame, df_ops: pd.DataFrame, cutoff_date: pd.Timestamp) -> tuple[pd.DataFrame, list]:
    """
    Construit les variables explicatives (features) et la variable cible (churn).

    Args:
        df_benef (pd.DataFrame): Données des bénéficiaires.
        df_ops (pd.DataFrame): Données des opérations.
        cutoff_date (pd.Timestamp): Date de séparation entre observation et futur.

    Returns:
        tuple[pd.DataFrame, list]: Le DataFrame final et la liste des colonnes explicatives.
    """
    print("\n" + "=" * 70)
    print("ÉTAPE 2 : Feature Engineering & Définition du Churn")
    print("=" * 70)

    df_ops['date_complete'] = pd.to_datetime(df_ops['date_complete'])
    df_benef['date_inscription'] = pd.to_datetime(df_benef['date_inscription'])

    # Séparer observations (avant cutoff) et futur (après cutoff)
    df_obs = df_ops[df_ops['date_complete'] <= cutoff_date].copy()
    df_future = df_ops[df_ops['date_complete'] > cutoff_date].copy()

    active_after = set(df_future['beneficiaire_id'].unique())

    # Feature engineering par bénéficiaire (période d'observation)
    features = df_obs.groupby('beneficiaire_id').agg(
        nb_operations=('nb_operations', 'sum'),
        montant_total=('montant_reduction', 'sum'),
        montant_moyen=('montant_reduction', 'mean'),
        nb_offres_distinctes=('offre_id', 'nunique'),
        nb_secteurs_distincts=('secteur', 'nunique'),
        derniere_operation=('date_complete', 'max'),
        premiere_operation=('date_complete', 'min'),
        nb_regions=('region', 'nunique'),
    ).reset_index()

    features['jours_depuis_derniere_op'] = (cutoff_date - features['derniere_operation']).dt.days
    features['duree_activite_jours'] = (features['derniere_operation'] - features['premiere_operation']).dt.days
    features['frequence_mensuelle'] = features['nb_operations'] / np.maximum(features['duree_activite_jours'] / 30.0, 1)

    features.drop(columns=['derniere_operation', 'premiere_operation'], inplace=True)

    df = features.merge(df_benef, on='beneficiaire_id', how='inner')
    df['anciennete_jours'] = (cutoff_date - df['date_inscription']).dt.days
    df.drop(columns=['date_inscription'], inplace=True)

    df['churned'] = df['beneficiaire_id'].apply(lambda x: 0 if x in active_after else 1)

    # Bénéficiaires sans aucune opération (très probablement churned)
    benef_no_ops = df_benef[~df_benef['beneficiaire_id'].isin(df_obs['beneficiaire_id'].unique())].copy()
    if len(benef_no_ops) > 0:
        for col in ['nb_operations', 'montant_total', 'montant_moyen', 'nb_offres_distinctes',
                    'nb_secteurs_distincts', 'nb_regions', 'jours_depuis_derniere_op',
                    'duree_activite_jours', 'frequence_mensuelle']:
            benef_no_ops[col] = 0
        benef_no_ops['jours_depuis_derniere_op'] = 999
        benef_no_ops['anciennete_jours'] = (cutoff_date - benef_no_ops['date_inscription']).dt.days
        benef_no_ops['churned'] = benef_no_ops['beneficiaire_id'].apply(lambda x: 0 if x in active_after else 1)
        benef_no_ops.drop(columns=['date_inscription'], inplace=True)
        df = pd.concat([df, benef_no_ops], ignore_index=True)

    feature_cols = [
        'nb_operations', 'montant_total', 'montant_moyen',
        'nb_offres_distinctes', 'nb_secteurs_distincts', 'nb_regions',
        'jours_depuis_derniere_op', 'duree_activite_jours', 'frequence_mensuelle',
        'anciennete_jours', 'genre', 'tranche_age', 'statut_pass',
        'en_situation_handicap', 'est_membre_association'
    ]

    print(f"  Dataset final           : {len(df):,} bénéficiaires")
    print(f"  Churned (inactifs)      : {df['churned'].sum():,} ({df['churned'].mean()*100:.1f}%)")
    print(f"  Actifs (non-churned)    : {(df['churned']==0).sum():,} ({(1-df['churned'].mean())*100:.1f}%)")

    return df, feature_cols


def prepare_data(df: pd.DataFrame, feature_cols: list) -> tuple:
    """
    Encode les variables catégorielles et sépare les données en ensembles d'entraînement et de test.

    Args:
        df (pd.DataFrame): DataFrame complet.
        feature_cols (list): Liste des colonnes explicatives.

    Returns:
        tuple: (X_train, X_test, y_train, y_test, DataFrame_viz, dictionnaire_encodeurs)
    """
    print("\n" + "=" * 70)
    print("ÉTAPE 3 : Préparation des données pour le ML")
    print("=" * 70)

    cat_cols = ['genre', 'tranche_age', 'statut_pass']
    le_dict = {}
    
    df_viz = df.copy()  # Copie pour la visualisation ultérieure

    for col in cat_cols:
        le = LabelEncoder()
        df[col] = df[col].fillna('Inconnu')
        df[col] = le.fit_transform(df[col])
        le_dict[col] = le

    df['en_situation_handicap'] = df['en_situation_handicap'].fillna(0).astype(int)
    df['est_membre_association'] = df['est_membre_association'].fillna(0).astype(int)

    X = df[feature_cols].fillna(0)
    y = df['churned']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    print(f"  Features utilisées      : {len(feature_cols)}")
    print(f"  Train set               : {len(X_train):,} ({len(X_train)/len(X)*100:.0f}%)")
    print(f"  Test set                : {len(X_test):,} ({len(X_test)/len(X)*100:.0f}%)")

    return X_train, X_test, y_train, y_test, df_viz, le_dict


def train_and_evaluate_models(X_train, X_test, y_train, y_test) -> tuple[dict, str]:
    """
    Entraîne différents modèles de machine learning et évalue leurs performances.

    Args:
        X_train, X_test: Variables explicatives d'entraînement et de test.
        y_train, y_test: Variables cibles d'entraînement et de test.

    Returns:
        tuple[dict, str]: Résultats des évaluations et le nom du meilleur modèle.
    """
    print("\n" + "=" * 70)
    print("ÉTAPE 4 : Entraînement des modèles")
    print("=" * 70)

    models = {
        'Logistic Regression': LogisticRegression(max_iter=1000, random_state=42),
        'Random Forest': RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1),
        'Gradient Boosting': GradientBoostingClassifier(n_estimators=200, max_depth=5, learning_rate=0.1, random_state=42),
    }

    results = {}
    for name, model in models.items():
        print(f"\n  🔄 Entraînement : {name}...")
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]

        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred)
        rec = recall_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        auc = roc_auc_score(y_test, y_proba)

        results[name] = {
            'model': model, 'accuracy': acc, 'precision': prec,
            'recall': rec, 'f1': f1, 'auc': auc,
            'y_pred': y_pred, 'y_proba': y_proba
        }
        
        print(f"    ✅ Accuracy  : {acc:.4f}")
        print(f"    ✅ Precision : {prec:.4f}")
        print(f"    ✅ Recall    : {rec:.4f}")
        print(f"    ✅ F1-Score  : {f1:.4f}")
        print(f"    ✅ AUC-ROC   : {auc:.4f}")

    best_model_name = max(results, key=lambda k: results[k]['f1'])
    return results, best_model_name


def generate_visualizations(results: dict, best_model_name: str, y_test, df_viz: pd.DataFrame, 
                            le_dict: dict, feature_cols: list, output_dir: str, cutoff_date: pd.Timestamp):
    """
    Génère et sauvegarde les graphiques d'analyse des modèles.

    Args:
        results (dict): Résultats des modèles évalués.
        best_model_name (str): Nom du modèle le plus performant.
        y_test: Vraies valeurs de la cible (test set).
        df_viz (pd.DataFrame): DataFrame non encodé pour l'affichage démographique.
        le_dict (dict): Dictionnaire des encodeurs de labels.
        feature_cols (list): Noms des colonnes explicatives.
        output_dir (str): Chemin du dossier d'enregistrement.
        cutoff_date (pd.Timestamp): Date de coupure utilisée.
    """
    print("\n" + "=" * 70)
    print("ÉTAPE 5 : Génération des Visualisations")
    print("=" * 70)

    os.makedirs(output_dir, exist_ok=True)

    COLORS = {
        'primary': '#134074', 'secondary': '#0B6E4F', 'accent': '#E76F51',
        'bg_dark': '#0A1628', 'bg_card': '#1A2A44', 'text': '#E0E0E0', 'grid': '#2A3A54',
        'blue': '#4FC3F7', 'green': '#66BB6A', 'orange': '#FFA726',
        'red': '#EF5350', 'purple': '#AB47BC',
    }

    plt.rcParams.update({
        'figure.facecolor': COLORS['bg_dark'], 'axes.facecolor': COLORS['bg_card'],
        'axes.edgecolor': COLORS['grid'], 'axes.labelcolor': COLORS['text'],
        'text.color': COLORS['text'], 'xtick.color': COLORS['text'],
        'ytick.color': COLORS['text'], 'font.family': 'sans-serif', 'font.size': 11,
    })

    # FIGURE 1 : Comparaison
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('Comparaison des Performances des Modèles de Prédiction du Churn',
                 fontsize=16, fontweight='bold', color='white', y=1.02)

    metrics = ['accuracy', 'precision', 'recall', 'f1', 'auc']
    metric_labels = ['Accuracy', 'Précision', 'Recall', 'F1-Score', 'AUC-ROC']
    model_names = list(results.keys())
    bar_colors = [COLORS['blue'], COLORS['green'], COLORS['orange']]

    ax = axes[0]
    x = np.arange(len(metrics))
    width = 0.25
    for i, name in enumerate(model_names):
        values = [results[name][m] for m in metrics]
        bars = ax.bar(x + i * width, values, width, label=name, color=bar_colors[i], alpha=0.85, edgecolor='white', linewidth=0.5)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01, f'{val:.2f}',
                    ha='center', va='bottom', fontsize=8, fontweight='bold')

    ax.set_xticks(x + width)
    ax.set_xticklabels(metric_labels, fontsize=9)
    ax.set_ylim(0, 1.15)
    ax.set_title('Métriques de Classification', fontweight='bold', fontsize=12)
    ax.legend(fontsize=8, loc='upper left')
    ax.grid(axis='y', alpha=0.2)

    ax = axes[1]
    for i, name in enumerate(model_names):
        fpr, tpr, _ = roc_curve(y_test, results[name]['y_proba'])
        ax.plot(fpr, tpr, color=bar_colors[i], linewidth=2, label=f"{name} (AUC={results[name]['auc']:.3f})")

    ax.plot([0, 1], [0, 1], 'w--', alpha=0.3, linewidth=1)
    ax.set_xlabel('Taux de Faux Positifs (FPR)')
    ax.set_ylabel('Taux de Vrais Positifs (TPR)')
    ax.set_title('Courbes ROC', fontweight='bold', fontsize=12)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.2)

    cm = confusion_matrix(y_test, results[best_model_name]['y_pred'])
    ax = axes[2]
    ax.imshow(cm, cmap='Blues', alpha=0.8)
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(['Actif', 'Churné'], fontsize=10)
    ax.set_yticklabels(['Actif', 'Churné'], fontsize=10)
    ax.set_xlabel('Prédiction')
    ax.set_ylabel('Réalité')
    ax.set_title(f'Matrice de Confusion\n({best_model_name})', fontweight='bold', fontsize=12)

    for i in range(2):
        for j in range(2):
            color = 'white' if cm[i, j] > cm.max() / 2 else COLORS['text']
            ax.text(j, i, f'{cm[i, j]:,}', ha='center', va='center', fontsize=16, fontweight='bold', color=color)

    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, '01_model_comparison.png'), dpi=150, bbox_inches='tight',
                facecolor=COLORS['bg_dark'], edgecolor='none')
    plt.close()
    print("  ✅ 01_model_comparison.png")

    # FIGURE 2 : Feature Importance
    best_model = results[best_model_name]['model']
    importances = best_model.feature_importances_ if hasattr(best_model, 'feature_importances_') else np.abs(best_model.coef_[0])
    feature_imp = pd.Series(importances, index=feature_cols).sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=(10, 8))
    colors_gradient = plt.cm.viridis(np.linspace(0.3, 0.9, len(feature_imp)))
    bars = ax.barh(feature_imp.index, feature_imp.values, color=colors_gradient, edgecolor='white', linewidth=0.5)

    for bar, val in zip(bars, feature_imp.values):
        ax.text(val + 0.002, bar.get_y() + bar.get_height()/2, f'{val:.3f}', va='center', fontsize=9, fontweight='bold')

    ax.set_title(f'Importance des Features ({best_model_name})', fontweight='bold', fontsize=14, pad=15)
    ax.set_xlabel('Importance')
    ax.grid(axis='x', alpha=0.2)
    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, '02_feature_importance.png'), dpi=150, bbox_inches='tight',
                facecolor=COLORS['bg_dark'], edgecolor='none')
    plt.close()
    print("  ✅ 02_feature_importance.png")

    # FIGURE 3 : Distribution Probabilités
    fig, ax = plt.subplots(figsize=(10, 6))
    proba_churned = results[best_model_name]['y_proba']
    ax.hist(proba_churned[y_test == 0], bins=40, alpha=0.7, color=COLORS['green'], label='Actifs', edgecolor='white', linewidth=0.5)
    ax.hist(proba_churned[y_test == 1], bins=40, alpha=0.7, color=COLORS['red'], label='Churnés', edgecolor='white', linewidth=0.5)
    ax.axvline(x=0.5, color='white', linestyle='--', linewidth=1.5, alpha=0.7, label='Seuil (0.5)')
    ax.set_xlabel('Probabilité de Churn', fontsize=12)
    ax.set_ylabel('Nombre de Bénéficiaires', fontsize=12)
    ax.set_title('Distribution des Scores de Probabilité', fontweight='bold', fontsize=14, pad=15)
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.2)
    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, '03_churn_probability_distribution.png'), dpi=150, bbox_inches='tight',
                facecolor=COLORS['bg_dark'], edgecolor='none')
    plt.close()
    print("  ✅ 03_churn_probability_distribution.png")

    # FIGURE 4 : Churn Demographics
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for col in ['genre', 'tranche_age', 'statut_pass']:
        if col in le_dict:
            df_viz[col] = le_dict[col].inverse_transform(df_viz[col])

    churn_age = df_viz.groupby('tranche_age')['churned'].agg(['mean', 'count']).sort_values('mean', ascending=True)
    ax = axes[0]
    bars = ax.barh(churn_age.index, churn_age['mean'] * 100, color=COLORS['orange'], alpha=0.85, edgecolor='white', linewidth=0.5)
    for bar, val, cnt in zip(bars, churn_age['mean'], churn_age['count']):
        ax.text(val * 100 + 0.5, bar.get_y() + bar.get_height()/2, f'{val*100:.1f}% (n={cnt:,})', va='center', fontsize=9, fontweight='bold')
    ax.set_xlabel('Taux de Churn (%)')
    ax.set_title('Taux de Churn par Tranche d\'Âge', fontweight='bold', fontsize=12)
    ax.grid(axis='x', alpha=0.2)

    churn_genre = df_viz.groupby('genre')['churned'].agg(['mean', 'count']).sort_values('mean', ascending=True)
    ax = axes[1]
    genre_colors = [COLORS['blue'], COLORS['purple'], COLORS['green']]
    bars = ax.barh(churn_genre.index, churn_genre['mean'] * 100, color=genre_colors[:len(churn_genre)], alpha=0.85, edgecolor='white', linewidth=0.5)
    for bar, val, cnt in zip(bars, churn_genre['mean'], churn_genre['count']):
        ax.text(val * 100 + 0.5, bar.get_y() + bar.get_height()/2, f'{val*100:.1f}% (n={cnt:,})', va='center', fontsize=9, fontweight='bold')
    ax.set_xlabel('Taux de Churn (%)')
    ax.set_title('Taux de Churn par Genre', fontweight='bold', fontsize=12)
    ax.grid(axis='x', alpha=0.2)

    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, '04_churn_demographics.png'), dpi=150, bbox_inches='tight',
                facecolor=COLORS['bg_dark'], edgecolor='none')
    plt.close()
    print("  ✅ 04_churn_demographics.png")

    best_report = classification_report(y_test, results[best_model_name]['y_pred'], target_names=['Actif', 'Churné'])
    print(f"\n{'='*70}\nRAPPORT DE CLASSIFICATION - {best_model_name}\n{'='*70}\n{best_report}")

    with open(os.path.join(output_dir, 'churn_model_summary.txt'), 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\nPRÉDICTION DU CHURN - RÉSUMÉ DES RÉSULTATS\nProjet MJCC - Pass Jeunes\n" + "=" * 70 + "\n\n")
        f.write(f"Date de référence (cutoff) : {cutoff_date.date()}\n")
        f.write(f"Dataset : {len(df_viz):,} bénéficiaires\n")
        f.write(f"Churned : {df_viz['churned'].sum():,} ({df_viz['churned'].mean()*100:.1f}%)\n")
        f.write(f"Actifs  : {(df_viz['churned']==0).sum():,} ({(1-df_viz['churned'].mean())*100:.1f}%)\n\n")
        f.write(f"Meilleur modèle : {best_model_name}\n")
        f.write(f"  Accuracy  : {results[best_model_name]['accuracy']:.4f}\n")
        f.write(f"  Precision : {results[best_model_name]['precision']:.4f}\n")
        f.write(f"  Recall    : {results[best_model_name]['recall']:.4f}\n")
        f.write(f"  F1-Score  : {results[best_model_name]['f1']:.4f}\n")
        f.write(f"  AUC-ROC   : {results[best_model_name]['auc']:.4f}\n\n")
        f.write("Classification Report:\n")
        f.write(best_report)

    print(f"\n✅ Tous les fichiers sauvegardés dans : {output_dir}")


def main():
    """Point d'entrée principal du script."""
    CONN_STR = 'Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=DWH_MJCC;Trusted_Connection=yes;'
    CUTOFF_DATE = pd.Timestamp('2024-06-30')
    OUTPUT_DIR = r'c:\Users\moali\OneDrive\Desktop\Projet MJCC\ML_Churn'

    df_benef, df_ops = extract_data(CONN_STR)
    df, feature_cols = feature_engineering(df_benef, df_ops, CUTOFF_DATE)
    X_train, X_test, y_train, y_test, df_viz, le_dict = prepare_data(df, feature_cols)
    results, best_model_name = train_and_evaluate_models(X_train, X_test, y_train, y_test)
    generate_visualizations(results, best_model_name, y_test, df_viz, le_dict, feature_cols, OUTPUT_DIR, CUTOFF_DATE)


if __name__ == "__main__":
    main()
