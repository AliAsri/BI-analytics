"""
Script to apply changes to the config_sources.py file.
It reads new offers from output_offres.py and updates the configuration.
"""

import re
from pathlib import Path


def apply_configuration_changes(config_path: str, offers_path: str) -> None:
    """
    Reads the configuration file and the new offers file, updates various
    configuration parameters, and writes the changes back.

    Args:
        config_path (str): The path to the configuration file to be updated.
        offers_path (str): The path to the file containing the new offers.
    """
    with open(config_path, 'r', encoding='utf-8') as file:
        content = file.read()

    with open(offers_path, 'r', encoding='utf-8') as file:
        offers_content = file.read()

    # Extract only the OFFRES_PASSJEUNES definition to avoid injecting docstrings
    match = re.search(r'(OFFRES_PASSJEUNES = \[.*?\]\n)', offers_content, flags=re.DOTALL)
    new_offers = match.group(1) if match else offers_content

    # Remove NB_PARTENAIRES
    content = re.sub(r'NB_PARTENAIRES\s*=\s*\d+\s*#.*?\n', '', content)

    # Replace OFFRES_PASSJEUNES
    content = re.sub(r'OFFRES_PASSJEUNES = \[.*?\]\n', new_offers, content, flags=re.DOTALL)

    # Remove TYPES_DECOMPTE and TYPES_DECOMPTE_POIDS
    content = re.sub(r'# ── Type de decompte du credit partenaire ─────────────────\n', '', content)
    content = re.sub(r'TYPES_DECOMPTE = \[.*?\]\n', '', content)
    content = re.sub(r'TYPES_DECOMPTE_POIDS = \[.*?\]\n', '', content)

    # Update CATEGORIES_CIBLES_COLONIE
    new_cat_colonie = (
        'CATEGORIES_CIBLES_COLONIE = [\n'
        '    "Enfants 7-15 ans", "Adolescents 15-18 ans", "Jeunes 18-45 ans",\n'
        '    "Enfants en situation de handicap"\n'
        ']\n'
    )
    content = re.sub(r'CATEGORIES_CIBLES_COLONIE = \[.*?\]\n', new_cat_colonie, content, flags=re.DOTALL)

    # Add NIVEAUX_ETUDES after DOMAINES_VOLONTARIAT
    niveaux_etudes = (
        '\nNIVEAUX_ETUDES = [\'Lycee\', \'Bac\', \'Licence\', \'Master\', \'Doctorat\', \'Non_Scolarise\']\n'
        'NIVEAUX_ETUDES_POIDS = [15, 25, 30, 15, 5, 10]\n'
    )
    content = re.sub(r'(STATUTS_MOTATAWI3_POIDS = \[40, 60\]\n)', r'\g<1>' + niveaux_etudes, content)

    with open(config_path, 'w', encoding='utf-8') as file:
        file.write(content)


if __name__ == '__main__':
    base_dir = Path(__file__).parent.parent
    CONFIG_FILE_PATH = str(base_dir / 'etl_dwh' / 'db' / 'source_data_sql' / 'config_sources.py')
    OFFERS_FILE_PATH = str(base_dir / 'reference' / 'offres_partenaires_reelles.py')
    apply_configuration_changes(CONFIG_FILE_PATH, OFFERS_FILE_PATH)

