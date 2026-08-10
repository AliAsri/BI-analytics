"""
=============================================================================
  MOTEUR DE RECOMMANDATION D'OFFRES PERSONNALISEES
  Projet MJCC - Pass Jeunes
=============================================================================

Ce module implémente un moteur de recommandation hybride :
    1. Collaborative Filtering (Similarité Cosinus sur matrice bénéficiaire x offre).
    2. Content-Based Filtering (Affinité par secteur en fallback).
    3. Recommandation des 3 meilleures offres par jeune.
    4. Intégration dans SQL Server puis dans SSAS (via TOM) pour Power BI.

Fonctions principales :
    - extract_data : Importation des données du Data Warehouse.
    - build_interaction_matrix : Création de la matrice user-item et similarités.
    - generate_recommendations : Génération des recommandations personnalisées.
    - visualize_recommendations : Création du tableau de bord d'analyse.
    - update_sql_and_ssas : Sauvegarde dans la base de données et modèle SSAS.
"""

import os
import subprocess
import warnings
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import pyodbc
from matplotlib.gridspec import GridSpec
from sklearn.metrics.pairwise import cosine_similarity

warnings.filterwarnings('ignore')
matplotlib.use('Agg')


def extract_data(conn_str: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Extrait les données nécessaires depuis DWH_MJCC."""
    print("=" * 70)
    print("ETAPE 1 : Extraction des données")
    print("=" * 70)

    conn = pyodbc.connect(conn_str)

    df_benef = pd.read_sql("""
        SELECT beneficiaire_id, genre, tranche_age, statut_pass,
               en_situation_handicap, est_membre_association
        FROM dbo.dim_beneficiaire
    """, conn)

    df_ops = pd.read_sql("""
        SELECT f.beneficiaire_id, f.offre_id, f.nb_operations, f.montant_reduction,
               r.region, o.nom_offre, o.nom_partenaire, o.secteur, o.categorie
        FROM dbo.fait_operations f
        INNER JOIN dbo.dim_region r ON f.region_id = r.region_id
        INNER JOIN dbo.dim_offre o ON f.offre_id = o.offre_id
    """, conn)

    df_offres = pd.read_sql("""
        SELECT offre_id, nom_offre, nom_partenaire, secteur, categorie, region_offre, actif
        FROM dbo.dim_offre
        WHERE actif = 1
    """, conn)

    conn.close()
    
    print(f"  Bénéficiaires : {len(df_benef):,}")
    print(f"  Opérations    : {len(df_ops):,}")
    print(f"  Offres actives : {len(df_offres):,}")
    return df_benef, df_ops, df_offres


def build_interaction_matrix(df_ops: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Construit la matrice user-item et calcule les similarités d'items."""
    print("\n" + "=" * 70)
    print("ETAPE 2 : Construction de la Matrice d'Interaction & Scoring")
    print("=" * 70)

    user_item_matrix = df_ops.pivot_table(
        index='beneficiaire_id',
        columns='offre_id',
        values='nb_operations',
        aggfunc='sum',
        fill_value=0
    )

    print(f"  Matrice User-Item : {user_item_matrix.shape[0]:,} utilisateurs x {user_item_matrix.shape[1]:,} offres")

    item_similarity = cosine_similarity(user_item_matrix.T)
    item_similarity_df = pd.DataFrame(
        item_similarity,
        index=user_item_matrix.columns,
        columns=user_item_matrix.columns
    )

    top_global_offres = df_ops.groupby('offre_id').agg(
        total_ops=('nb_operations', 'sum'),
        nom_offre=('nom_offre', 'first'),
        secteur=('secteur', 'first')
    ).sort_values('total_ops', ascending=False)

    return user_item_matrix, item_similarity_df, top_global_offres


def generate_recommendations(df_benef: pd.DataFrame, df_ops: pd.DataFrame, df_offres: pd.DataFrame, 
                             user_item_matrix: pd.DataFrame, item_similarity_df: pd.DataFrame, 
                             top_global_offres: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Génère le top 3 des offres recommandées pour chaque bénéficiaire."""
    print("\n" + "=" * 70)
    print("ETAPE 3 : Génération des Top 3 Recommandations")
    print("=" * 70)

    offre_name_map = {r['offre_id']: f"{r['nom_offre']} ({r['nom_partenaire']})" for _, r in df_offres.iterrows()}

    user_fav_secteur = df_ops.groupby(['beneficiaire_id', 'secteur'])['nb_operations'].sum().reset_index()
    user_fav_secteur = user_fav_secteur.sort_values(['beneficiaire_id', 'nb_operations'], ascending=[True, False])
    user_top_secteur = user_fav_secteur.groupby('beneficiaire_id').first()['secteur'].to_dict()

    global_top_secteurs = df_ops['secteur'].value_counts().index.tolist()
    recommandations = []

    for bid in df_benef['beneficiaire_id']:
        fav_sec = user_top_secteur.get(bid, global_top_secteurs[0])
        
        if bid in user_item_matrix.index:
            user_history = user_item_matrix.loc[bid]
            used_offres = set(user_history[user_history > 0].index)
            
            scores = pd.Series(0.0, index=user_item_matrix.columns)
            for used_id, weight in user_history[user_history > 0].items():
                if used_id in item_similarity_df.index:
                    scores += item_similarity_df[used_id] * weight
            
            scores = scores.drop(labels=list(used_offres), errors='ignore')
            top_ids = scores.sort_values(ascending=False).head(3).index.tolist()
            
            if len(top_ids) < 3:
                fallback_ids = [oid for oid in top_global_offres.index if oid not in used_offres and oid not in top_ids]
                top_ids.extend(fallback_ids[:3 - len(top_ids)])
        else:
            top_ids = top_global_offres.index[:3].tolist()
        
        rec_1 = offre_name_map.get(top_ids[0], 'Offre Culturelle Pass') if len(top_ids) > 0 else 'Offre Culture'
        rec_2 = offre_name_map.get(top_ids[1], 'Offre Transport Pass') if len(top_ids) > 1 else 'Offre Transport'
        rec_3 = offre_name_map.get(top_ids[2], 'Offre Sport Pass') if len(top_ids) > 2 else 'Offre Sport'
        
        recommandations.append({
            'beneficiaire_id': bid,
            'recommandation_offre_1': rec_1,
            'recommandation_offre_2': rec_2,
            'recommandation_offre_3': rec_3,
            'secteur_recommande': fav_sec
        })

    df_recs = pd.DataFrame(recommandations)
    print(f"  Recommandations générées pour {len(df_recs):,} bénéficiaires")
    
    return df_recs, offre_name_map


def visualize_recommendations(df_recs: pd.DataFrame, df_offres: pd.DataFrame, user_item_matrix: pd.DataFrame, 
                              item_similarity_df: pd.DataFrame, offre_name_map: dict, output_dir: str):
    """Crée un tableau de bord visuel des recommandations générées."""
    print("\n" + "=" * 70)
    print("ETAPE 4 : Visualisations")
    print("=" * 70)

    os.makedirs(output_dir, exist_ok=True)

    COLORS = {'bg_dark': '#0A1628', 'bg_card': '#1A2A44', 'text': '#E0E0E0', 'grid': '#2A3A54'}
    plt.rcParams.update({'figure.facecolor': COLORS['bg_dark'], 'axes.facecolor': COLORS['bg_card'],
                         'axes.edgecolor': COLORS['grid'], 'axes.labelcolor': COLORS['text'],
                         'text.color': COLORS['text'], 'xtick.color': COLORS['text'],
                         'ytick.color': COLORS['text'], 'font.size': 11})

    fig = plt.figure(figsize=(18, 10))
    gs = GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.3)
    fig.suptitle('MOTEUR DE RECOMMANDATION D\'OFFRES PERSONNALISEES', fontsize=18, fontweight='bold', color='white', y=0.98)

    ax1 = fig.add_subplot(gs[0, 0])
    sec_counts = df_recs['secteur_recommande'].value_counts()
    ax1.barh(sec_counts.index, sec_counts.values, color=['#4FC3F7', '#66BB6A', '#FFA726', '#EF5350', '#AB47BC', '#26C6DA'][:len(sec_counts)])
    ax1.set_title('Secteurs Recommandés', fontweight='bold')

    ax2 = fig.add_subplot(gs[0, 1])
    top_rec1 = df_recs['recommandation_offre_1'].value_counts().head(10).sort_values(ascending=True)
    labels = [t[:35] + '...' if len(t) > 35 else t for t in top_rec1.index]
    ax2.barh(labels, top_rec1.values, color='#66BB6A')
    ax2.set_title('Top 10 Offres #1 Recommandées', fontweight='bold')

    ax3 = fig.add_subplot(gs[1, 0])
    sample_sim = item_similarity_df.iloc[:12, :12]
    sample_labels = [offre_name_map.get(col, f'Offre_{col}')[:20] for col in sample_sim.columns]
    ax3.imshow(sample_sim.values, cmap='YlGnBu')
    ax3.set_xticks(range(12)); ax3.set_yticks(range(12))
    ax3.set_xticklabels(sample_labels, rotation=45, ha='right', fontsize=7)
    ax3.set_yticklabels(sample_labels, fontsize=7)
    ax3.set_title('Similarité Cosinus (Sample)', fontweight='bold')

    ax4 = fig.add_subplot(gs[1, 1])
    ax4.axis('off')
    stats = f"Bénéficiaires: {len(df_recs):,}\nOffres: {len(df_offres):,}\nMatrice: {user_item_matrix.shape[0]}x{user_item_matrix.shape[1]}"
    ax4.text(0.1, 0.5, stats, fontsize=12, bbox=dict(facecolor='#1A2A44', edgecolor='#4FC3F7', alpha=0.9))

    plt.savefig(os.path.join(output_dir, '01_recommandation_dashboard.png'), dpi=150, bbox_inches='tight', facecolor=COLORS['bg_dark'], edgecolor='none')
    plt.close()


def update_sql_and_ssas(df_recs: pd.DataFrame, conn_str: str):
    """Enregistre les recommandations dans SQL Server et déploie sur SSAS."""
    print("\n" + "=" * 70)
    print("ETAPE 5 : Intégration SQL Server (DWH_MJCC) + SSAS (TOM)")
    print("=" * 70)

    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    cursor.execute("""
    IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='dim_beneficiaire' AND COLUMN_NAME='recommandation_offre_1')
    BEGIN
        ALTER TABLE dbo.dim_beneficiaire ADD recommandation_offre_1 NVARCHAR(255) DEFAULT 'Non definie';
        ALTER TABLE dbo.dim_beneficiaire ADD recommandation_offre_2 NVARCHAR(255) DEFAULT 'Non definie';
        ALTER TABLE dbo.dim_beneficiaire ADD recommandation_offre_3 NVARCHAR(255) DEFAULT 'Non definie';
        ALTER TABLE dbo.dim_beneficiaire ADD secteur_recommande NVARCHAR(100) DEFAULT 'Culture';
    END
    """)

    for _, row in df_recs.iterrows():
        cursor.execute("""
            UPDATE dbo.dim_beneficiaire 
            SET recommandation_offre_1 = ?, recommandation_offre_2 = ?, recommandation_offre_3 = ?, secteur_recommande = ?
            WHERE beneficiaire_id = ?
        """, (row['recommandation_offre_1'], row['recommandation_offre_2'], row['recommandation_offre_3'], row['secteur_recommande'], int(row['beneficiaire_id'])))

    conn.close()

    ps_script = f"""
    Add-Type -Path "C:\\Program Files\\Microsoft SQL Server Management Studio 22\\Release\\Common7\\IDE\\Microsoft.AnalysisServices.Tabular.dll"
    $server = New-Object Microsoft.AnalysisServices.Tabular.Server
    $server.Connect("localhost\\SSASTAB")
    $db = $server.Databases["SSAS_MJCC_PROD"]
    $tbl = $db.Model.Tables["dim_beneficiaire"]

    $cols = @("recommandation_offre_1", "recommandation_offre_2", "recommandation_offre_3", "secteur_recommande")
    foreach ($colName in $cols) {{
        if (-not $tbl.Columns.Contains($colName)) {{
            $col = New-Object Microsoft.AnalysisServices.Tabular.DataColumn
            $col.Name = $colName
            $col.DataType = [Microsoft.AnalysisServices.Tabular.DataType]::String
            $col.SourceColumn = $colName
            $tbl.Columns.Add($col)
        }}
    }}

    $db.Model.SaveChanges()
    $db.Model.RequestRefresh([Microsoft.AnalysisServices.Tabular.RefreshType]::Full)
    $db.Model.SaveChanges()
    $server.Disconnect()
    """

    ps_path = str(Path(__file__).parent / "update_ssas_rec.ps1")
    with open(ps_path, "w", encoding="utf-8") as f:
        f.write(ps_script)

    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_path], capture_output=True, text=True)
    # os.remove(ps_path)  # Commenté pour conserver le script et pouvoir le relancer manuellement


def main():
    """Point d'entrée du moteur de recommandation."""
    CONN_STR = 'Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=DWH_MJCC;Trusted_Connection=yes;'
    OUTPUT_DIR = str(Path(__file__).parent)

    df_benef, df_ops, df_offres = extract_data(CONN_STR)
    user_item_matrix, item_similarity_df, top_global_offres = build_interaction_matrix(df_ops)
    df_recs, offre_name_map = generate_recommendations(df_benef, df_ops, df_offres, user_item_matrix, item_similarity_df, top_global_offres)
    
    visualize_recommendations(df_recs, df_offres, user_item_matrix, item_similarity_df, offre_name_map, OUTPUT_DIR)
    update_sql_and_ssas(df_recs, CONN_STR)


if __name__ == "__main__":
    main()
