"""
=============================================================================
  SEGMENTATION DES BENEFICIAIRES (K-Means Clustering)
  Projet MJCC - Pass Jeunes
=============================================================================

Pipeline complet : 
    - Feature Engineering RFM + Comportemental
    - Clustering K-Means (optimisation via Elbow + Silhouette)
    - Analyse et nommage dynamique des segments
    - Intégration vers SQL Server, SSAS et Power BI
"""

import subprocess
import warnings
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyodbc
from matplotlib.gridspec import GridSpec
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')
matplotlib.use('Agg')


def extract_data(conn_str: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    """Extrait les données bénéficiaires et opérations pour la segmentation."""
    print("=" * 70)
    print("ETAPE 1 : Extraction des données")
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
               r.region, o.secteur
        FROM dbo.fait_operations f
        INNER JOIN dbo.dim_temps t ON f.temps_id = t.temps_id
        INNER JOIN dbo.dim_region r ON f.region_id = r.region_id
        INNER JOIN dbo.dim_offre o ON f.offre_id = o.offre_id
    """, conn)
    conn.close()

    df_ops['date_complete'] = pd.to_datetime(df_ops['date_complete'])
    df_benef['date_inscription'] = pd.to_datetime(df_benef['date_inscription'])
    ref_date = df_ops['date_complete'].max()
    
    return df_benef, df_ops, ref_date


def feature_engineering(df_benef: pd.DataFrame, df_ops: pd.DataFrame, ref_date: pd.Timestamp) -> tuple[pd.DataFrame, list]:
    """Prépare les métriques RFM et comportementales par bénéficiaire."""
    print("\n" + "=" * 70)
    print("ETAPE 2 : Feature Engineering RFM + Comportemental")
    print("=" * 70)

    rfm = df_ops.groupby('beneficiaire_id').agg(
        recency=('date_complete', lambda x: (ref_date - x.max()).days),
        frequency=('nb_operations', 'sum'),
        monetary=('montant_reduction', 'sum'),
        montant_moyen=('montant_reduction', 'mean'),
        nb_offres=('offre_id', 'nunique'),
        nb_secteurs=('secteur', 'nunique'),
        nb_regions=('region', 'nunique'),
        nb_jours_actifs=('date_complete', 'nunique'),
        premiere_op=('date_complete', 'min'),
        derniere_op=('date_complete', 'max'),
        nb_weekends=('est_weekend', 'sum'),
    ).reset_index()

    rfm['duree_activite'] = (rfm['derniere_op'] - rfm['premiere_op']).dt.days
    rfm['frequence_mensuelle'] = rfm['frequency'] / np.maximum(rfm['duree_activite'] / 30.0, 1)
    rfm['ratio_weekend'] = rfm['nb_weekends'] / np.maximum(rfm['frequency'], 1)
    rfm['diversite_offres'] = rfm['nb_offres'] / np.maximum(rfm['frequency'], 1)
    rfm['intensite'] = rfm['monetary'] / np.maximum(rfm['nb_jours_actifs'], 1)
    rfm.drop(columns=['premiere_op', 'derniere_op'], inplace=True)

    df = rfm.merge(df_benef[['beneficiaire_id', 'date_inscription', 'est_membre_association']], on='beneficiaire_id', how='left')
    df['anciennete'] = (ref_date - df['date_inscription']).dt.days
    df['est_membre_association'] = df['est_membre_association'].fillna(0).astype(int)
    df.drop(columns=['date_inscription'], inplace=True)

    benef_no_ops = df_benef[~df_benef['beneficiaire_id'].isin(rfm['beneficiaire_id'])].copy()
    if len(benef_no_ops) > 0:
        no_ops_data = pd.DataFrame({
            'beneficiaire_id': benef_no_ops['beneficiaire_id'],
            'recency': 999, 'frequency': 0, 'monetary': 0, 'montant_moyen': 0,
            'nb_offres': 0, 'nb_secteurs': 0, 'nb_regions': 0, 'nb_jours_actifs': 0,
            'nb_weekends': 0, 'duree_activite': 0, 'frequence_mensuelle': 0,
            'ratio_weekend': 0, 'diversite_offres': 0, 'intensite': 0,
            'anciennete': (ref_date - benef_no_ops['date_inscription']).dt.days.values,
            'est_membre_association': benef_no_ops['est_membre_association'].fillna(0).astype(int).values,
        })
        df = pd.concat([df, no_ops_data], ignore_index=True)

    feature_cols = [c for c in df.columns if c != 'beneficiaire_id']
    return df, feature_cols


def perform_clustering(df: pd.DataFrame, feature_cols: list) -> tuple:
    """Détermine le K optimal et applique l'algorithme K-Means."""
    print("\n" + "=" * 70)
    print("ETAPE 3 : K-Means Clustering (Elbow + Silhouette)")
    print("=" * 70)

    X = df[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    inertias, silhouettes = [], []
    K_range = range(2, 9)

    for k in K_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
        labels = km.fit_predict(X_scaled)
        inertias.append(km.inertia_)
        silhouettes.append(silhouette_score(X_scaled, labels, sample_size=5000, random_state=42))

    best_k = list(K_range)[np.argmax(silhouettes)]
    if 4 in K_range and silhouettes[list(K_range).index(4)] > max(silhouettes) * 0.9:
        best_k = 4  # Privilégier 4 segments pour l'interprétabilité

    km_final = KMeans(n_clusters=best_k, random_state=42, n_init=20, max_iter=500)
    cluster_labels = km_final.fit_predict(X_scaled)
    
    return cluster_labels, best_k, inertias, silhouettes, K_range


def name_segments(df: pd.DataFrame, cluster_labels: np.ndarray) -> dict:
    """Attribue des noms métiers aux clusters générés."""
    df['cluster'] = cluster_labels
    cluster_stats = df.groupby('cluster').agg(
        avg_frequency=('frequency', 'mean'),
        avg_monetary=('monetary', 'mean'),
    ).reset_index()

    cluster_stats['engagement_score'] = cluster_stats['avg_frequency'] * cluster_stats['avg_monetary']
    cluster_stats = cluster_stats.sort_values('engagement_score', ascending=False).reset_index(drop=True)

    segment_names_pool = ['Super-Actif', 'Régulier', 'Occasionnel', 'Dormant', 'Très Dormant', 'Débutant', 'Explorateur']
    segment_map = {row['cluster']: segment_names_pool[i] if i < len(segment_names_pool) else f'Segment_{i+1}' for i, row in cluster_stats.iterrows()}
    df['segment'] = df['cluster'].map(segment_map)
    return segment_map


def visualize_clusters(df: pd.DataFrame, segment_map: dict, K_range, inertias, silhouettes, best_k: int, output_dir: str):
    """Crée le dashboard des segments identifiés."""
    print("\n" + "=" * 70)
    print("ETAPE 5 : Visualisations")
    print("=" * 70)

    os.makedirs(output_dir, exist_ok=True)
    COLORS = {'bg_dark': '#0A1628', 'bg_card': '#1A2A44', 'text': '#E0E0E0', 'grid': '#2A3A54'}
    seg_colors = ['#4FC3F7', '#66BB6A', '#FFA726', '#EF5350', '#AB47BC', '#26C6DA', '#FFEE58']
    
    plt.rcParams.update({'figure.facecolor': COLORS['bg_dark'], 'axes.facecolor': COLORS['bg_card'],
                         'axes.edgecolor': COLORS['grid'], 'axes.labelcolor': COLORS['text'],
                         'text.color': COLORS['text'], 'xtick.color': COLORS['text'],
                         'ytick.color': COLORS['text'], 'font.size': 11})

    fig = plt.figure(figsize=(20, 12))
    gs = GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.3)
    fig.suptitle('SEGMENTATION DES BENEFICIAIRES (K-Means)', fontsize=18, fontweight='bold', color='white', y=0.98)

    ax1 = fig.add_subplot(gs[0, 0])
    seg_counts = df['segment'].value_counts()
    ax1.pie(seg_counts.values, labels=seg_counts.index, autopct='%1.1f%%', colors=seg_colors[:len(seg_counts)], startangle=90)
    ax1.add_artist(plt.Circle((0, 0), 0.55, fc=COLORS['bg_card']))
    ax1.set_title('Répartition des Segments', fontweight='bold')

    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(list(K_range), inertias, 'o-', color='#4FC3F7')
    ax2.set_ylabel('Inertie', color='#4FC3F7')
    ax2_twin = ax2.twinx()
    ax2_twin.plot(list(K_range), silhouettes, 's-', color='#66BB6A')
    ax2_twin.set_ylabel('Score Silhouette', color='#66BB6A')
    ax2.set_title(f'Méthode Elbow & Silhouette (K={best_k})', fontweight='bold')

    ax3 = fig.add_subplot(gs[0, 2], polar=True)
    radar_features = ['frequency', 'monetary', 'nb_offres', 'nb_jours_actifs', 'frequence_mensuelle']
    angles = np.linspace(0, 2 * np.pi, len(radar_features), endpoint=False).tolist()
    angles += angles[:1]
    for i, seg in enumerate(seg_counts.index):
        seg_data = df[df['segment'] == seg][radar_features].mean()
        seg_normalized = (seg_data - df[radar_features].min()) / (df[radar_features].max() - df[radar_features].min() + 1e-9)
        values = seg_normalized.tolist() + [seg_normalized.tolist()[0]]
        ax3.plot(angles, values, 'o-', linewidth=2, color=seg_colors[i], label=seg)
        ax3.fill(angles, values, alpha=0.1, color=seg_colors[i])
    ax3.set_xticks(angles[:-1])
    ax3.set_xticklabels(radar_features, fontsize=8)
    ax3.set_title('Profil Radar par Segment', fontweight='bold', pad=20)
    ax3.legend(fontsize=7, loc='upper right', bbox_to_anchor=(1.3, 1.1))

    ax4 = fig.add_subplot(gs[1, 0])
    seg_freq = df.groupby('segment')['frequency'].mean().sort_values()
    ax4.barh(seg_freq.index, seg_freq.values, color='#4FC3F7')
    ax4.set_title('Fréquence Moyenne par Segment', fontweight='bold')

    ax5 = fig.add_subplot(gs[1, 1])
    seg_monetary = df.groupby('segment')['monetary'].mean().sort_values()
    ax5.barh(seg_monetary.index, seg_monetary.values, color='#66BB6A')
    ax5.set_title('Montant Moyen par Segment', fontweight='bold')

    ax6 = fig.add_subplot(gs[1, 2])
    for i, seg in enumerate(seg_counts.index):
        mask = df['segment'] == seg
        ax6.scatter(df[mask]['frequency'], df[mask]['monetary'], c=seg_colors[i], label=seg, alpha=0.5, s=15)
    ax6.set_xlabel('Fréquence')
    ax6.set_ylabel('Montant Total (DH)')
    ax6.set_title('Fréquence vs Montant', fontweight='bold')
    ax6.legend(fontsize=8)

    plt.savefig(os.path.join(output_dir, '01_segmentation_dashboard.png'), dpi=150, bbox_inches='tight', facecolor=COLORS['bg_dark'], edgecolor='none')
    plt.close()


def update_sql_and_ssas(df: pd.DataFrame, conn_str: str):
    """Insère les segments dans SQL Server et déploie le cube SSAS."""
    print("\n" + "=" * 70)
    print("ETAPE 6 & 7 : Ecriture dans SQL Server et SSAS")
    print("=" * 70)

    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='dim_beneficiaire' AND COLUMN_NAME='segment_beneficiaire')
    BEGIN
        ALTER TABLE dbo.dim_beneficiaire ADD segment_beneficiaire NVARCHAR(30) DEFAULT 'Non classe';
    END
    """)

    for _, row in df.iterrows():
        cursor.execute("UPDATE dbo.dim_beneficiaire SET segment_beneficiaire = ? WHERE beneficiaire_id = ?", (row['segment'], int(row['beneficiaire_id'])))
    conn.close()

    ps_script = f"""
    Add-Type -Path "C:\\Program Files\\Microsoft SQL Server Management Studio 22\\Release\\Common7\\IDE\\Microsoft.AnalysisServices.Tabular.dll"
    $server = New-Object Microsoft.AnalysisServices.Tabular.Server
    $server.Connect("localhost\\SSASTAB")
    $db = $server.Databases["SSAS_MJCC_PROD"]
    $tbl = $db.Model.Tables["dim_beneficiaire"]

    if (-not $tbl.Columns.Contains("segment_beneficiaire")) {{
        $col = New-Object Microsoft.AnalysisServices.Tabular.DataColumn
        $col.Name = "segment_beneficiaire"
        $col.DataType = [Microsoft.AnalysisServices.Tabular.DataType]::String
        $col.SourceColumn = "segment_beneficiaire"
        $tbl.Columns.Add($col)
    }}

    $db.Model.SaveChanges()
    $db.Model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
    $db.Model.SaveChanges()
    $server.Disconnect()
    """

    ps_path = str(Path(__file__).parent / "update_ssas_seg.ps1")
    with open(ps_path, "w", encoding="utf-8") as f:
        f.write(ps_script)

    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_path], capture_output=True, text=True)
    # os.remove(ps_path)  # Commenté pour conserver le script et pouvoir le relancer manuellement


def main():
    """Point d'entrée principal de la segmentation."""
    CONN_STR = 'Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=DWH_MJCC;Trusted_Connection=yes;'
    OUTPUT_DIR = str(Path(__file__).parent)

    df_benef, df_ops, ref_date = extract_data(CONN_STR)
    df, feature_cols = feature_engineering(df_benef, df_ops, ref_date)
    cluster_labels, best_k, inertias, silhouettes, k_range = perform_clustering(df, feature_cols)
    segment_map = name_segments(df, cluster_labels)
    
    visualize_clusters(df, segment_map, k_range, inertias, silhouettes, best_k, OUTPUT_DIR)
    update_sql_and_ssas(df, CONN_STR)


if __name__ == "__main__":
    main()
