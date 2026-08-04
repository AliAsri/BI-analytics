"""
Data generation module for source databases.

This script generates simulated data for the source databases aligned with
the v3 data model. It creates SQL insert scripts for both PassJeunesDB (SQL Server)
and jam3iya_db (MySQL). The generated data covers beneficiaries, youth offers,
associations, activities, and seasonal campuses.

Usage:
    python generate_source_data.py

Prerequisites:
    pip install tqdm numpy
"""

import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent))

from config_sources import (
    AGE_MAX_BENEFICIAIRE, AGE_MAX_MOTATAWI3, AGE_MIN_BENEFICIAIRE,
    AGE_MIN_MOTATAWI3, ANNEES, CATEGORIES_CIBLES_COLONIE,
    CONTENUS_RAPPORT_TEMPLATES, DATE_DEBUT, DATE_FIN, DOMAINES_ASSOCIATION,
    DOMAINES_VOLONTARIAT, EDITIONS_MOTATAWI3, NATIONALITES_EXPATRIES,
    NATIONALITES_IMMIGRES, NATIONALITES_SUBSAHARIENNES, NB_ASSOCIATIONS,
    NB_BENEFICIAIRES, NB_COLONIES, NB_MAISONS, NIVEAUX_ETUDES,
    NIVEAUX_ETUDES_POIDS, OFFRES_PASSJEUNES, REGIONS, SAISONS_COLONIE,
    SAISONS_POIDS, SPECIALITES_ANIMATEUR, STATUTS_ACTIVITE,
    STATUTS_ACTIVITE_POIDS, STATUTS_ASSO, STATUTS_ASSO_POIDS, STATUTS_DOSSIER,
    STATUTS_DOSSIER_POIDS, STATUTS_MAISON, STATUTS_MAISON_POIDS,
    STATUTS_MOTATAWI3, STATUTS_MOTATAWI3_POIDS, TAUX_HANDICAP, TITRES_ACTIVITES,
    TYPES_ACTIVITE, TYPES_ACTIVITE_POIDS, TYPES_JURIDIQUES, TYPES_STATUT,
    TYPES_STATUT_POIDS, VILLES_PAR_REGION
)
from maroc_data import (
    NOMS_FAMILLE, prenom_nom_aleatoire, prenom_nom_subsaharien,
    prenom_nom_expatrie, prenom_nom_immigre, telephone_marocain, email_marocain,
)

random.seed(42)
np.random.seed(42)

DATE_MIN = datetime.strptime(DATE_DEBUT, "%Y-%m-%d")
DATE_MAX = datetime.strptime(DATE_FIN,   "%Y-%m-%d")
TODAY    = DATE_MAX  # date de reference pour les calculs d'age = fin de periode simulee

OUT_DIR = Path(__file__).parent / "scripts_sql"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BATCH = 500


# ══════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════

def rand_date(start=DATE_MIN, end=DATE_MAX) -> date:
    delta = (end - start).days
    return (start + timedelta(days=random.randint(0, delta))).date()

def wc(choices, weights):
    return random.choices(choices, weights=weights, k=1)[0]

def region_weighted() -> dict:
    pops  = [r["pop"] for r in REGIONS]
    total = sum(pops)
    return random.choices(REGIONS, weights=[p / total for p in pops], k=1)[0]

def gen_cin(used: set) -> str:
    prefixes = ["A","B","BE","BH","BJ","BK","BM","C","D","E","F","G",
                "GA","GB","GK","GM","H","IB","J","JB","K","L",
                "MA","N","P","Q","R","S","T","U","V","VA","W"]
    while True:
        cin = f"{random.choice(prefixes)}{random.randint(10000, 999999)}"
        if cin not in used:
            used.add(cin)
            return cin

def date_naissance_pour_age(age: int) -> date:
    """Genere une date de naissance correspondant a un age donne (a TODAY)."""
    base = TODAY.date().replace(year=TODAY.year - age)
    return base - timedelta(days=random.randint(0, 364))

def date_naissance_pour_age_a_date(age: int, ref: date) -> date:
    """Genere une date de naissance telle que DATEDIFF(YEAR, result, ref) = age.
    Garantit que l'annee de naissance = ref.year - age, compatible avec
    la contrainte CHECK de SQL Server (DATEDIFF base sur les annees)."""
    year_naiss = ref.year - age
    start = date(year_naiss, 1, 1)
    end = date(year_naiss, 12, 31)
    return start + timedelta(days=random.randint(0, (end - start).days))

def age_a_date(date_naissance: date, ref: date) -> int:
    return ref.year - date_naissance.year - (
        (ref.month, ref.day) < (date_naissance.month, date_naissance.day)
    )

def safe_add_years(d: date, years: int) -> date:
    """Ajoute des annees a une date, en gerant le cas du 29 fevrier."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        # 29 fevrier sur une annee non bissextile -> repli au 28 fevrier
        return d.replace(year=d.year + years, day=28)

def esc_sql(v, dialect="mssql") -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    return f"N'{s}'" if dialect == "mssql" else f"'{s}'"


# ══════════════════════════════════════════════════════════
# WRITER
# ══════════════════════════════════════════════════════════

class SQLWriter:
    def __init__(self, path: Path, table: str, columns: list,
                 dialect="mssql", batch=BATCH):
        self.path, self.table, self.columns = path, table, columns
        self.dialect, self.batch = dialect, batch
        self.buffer, self.total = [], 0
        self.f = open(path, "w", encoding="utf-8")
        db = "PassJeunesDB" if dialect == "mssql" else "jam3iya_db"
        self.f.write(f"-- Auto-genere (modele v2) — table {table} — {db}\n\n")
        if dialect == "mssql":
            self.f.write("USE PassJeunesDB;\nGO\n\n")
        else:
            self.f.write("USE jam3iya_db;\n\n")

    def add(self, row: tuple):
        self.buffer.append(row)
        if len(self.buffer) >= self.batch:
            self._flush()

    def _flush(self):
        if not self.buffer:
            return
        cols = ", ".join(self.columns)
        go = "GO" if self.dialect == "mssql" else ";"
        self.f.write(f"INSERT INTO {self.table} ({cols}) VALUES\n")
        lines = [f"    ({', '.join(esc_sql(v, self.dialect) for v in row)})"
                  for row in self.buffer]
        self.f.write(",\n".join(lines))
        self.f.write(f";\n{go}\n\n")
        self.total += len(self.buffer)
        self.buffer = []

    def close(self):
        self._flush()
        self.f.close()
        print(f"  [OK] {self.path.name:<45} {self.total:>8,} lignes")


# ══════════════════════════════════════════════════════════
# 1. PASSJEUNES — Beneficiaire
# ══════════════════════════════════════════════════════════

def gen_beneficiaire() -> list:
    w = SQLWriter(OUT_DIR / "01_passjeunes_beneficiaire.sql",
                  "dbo.Beneficiaire",
                  ["cin","nom","prenom","genre","date_naissance","ville","region",
                   "email","telephone","nationalite","type_statut",
                   "en_situation_handicap","date_inscription",
                   "date_desactivation","statut_pass"],
                  dialect="mssql")

    used_cin, beneficiaires = set(), []

    for i in tqdm(range(1, NB_BENEFICIAIRES + 1), desc="Beneficiaire"):
        region  = region_weighted()
        ville   = random.choice(VILLES_PAR_REGION.get(region["nom"], ["Ville"]))
        genre   = random.choice(["Homme", "Femme"])

        date_ins     = rand_date()
        # Age au moment de l'inscription : entre AGE_MIN et AGE_MAX
        age_inscr    = random.randint(AGE_MIN_BENEFICIAIRE, AGE_MAX_BENEFICIAIRE)
        date_naiss   = date_naissance_pour_age_a_date(age_inscr, date_ins)
        date_desact  = safe_add_years(date_naiss, 30)

        # Statut pass : Actif si age actuel (a TODAY) <= 30, sinon Desactive
        age_actuel   = age_a_date(date_naiss, TODAY.date())
        statut_pass  = "Actif" if age_actuel <= AGE_MAX_BENEFICIAIRE else "Desactive"

        type_statut  = wc(TYPES_STATUT, TYPES_STATUT_POIDS)
        if type_statut == "Marocain":
            nationalite = "Marocaine"
            prenom, nom = prenom_nom_aleatoire(genre, random)
        elif type_statut == "Subsaharien_Naturalise":
            nationalite = random.choice(NATIONALITES_SUBSAHARIENNES)
            prenom, nom = prenom_nom_subsaharien(genre, random)
        elif type_statut == "Marocain_Expatrie":
            nationalite = random.choice(["Marocaine", "Francaise", "Espagnole", "Belge", "Canadienne", "Italienne", "Allemande", "Neerlandaise"])
            prenom, nom = prenom_nom_aleatoire(genre, random)  # Les MRE ont des noms marocains !
        else:  # Immigrant_Etranger
            nationalite = random.choice(NATIONALITES_IMMIGRES)
            prenom, nom = prenom_nom_immigre(genre, random)

        handicap = random.random() < TAUX_HANDICAP

        cin      = gen_cin(used_cin)
        email    = email_marocain(prenom, nom, i, random)
        tel      = telephone_marocain(random)

        w.add((cin, nom, prenom, genre, date_naiss, ville, region["nom"],
               email, tel, nationalite, type_statut, handicap,
               date_ins, date_desact, statut_pass))

        beneficiaires.append({
            "id": i, "cin": cin, "region": region["nom"], "ville": ville,
            "date_naissance": date_naiss, "date_inscription": date_ins,
            "age_actuel": age_actuel, "statut_pass": statut_pass,
        })

    w.close()
    return beneficiaires


# ══════════════════════════════════════════════════════════
# 2. PASSJEUNES — Offre
# ══════════════════════════════════════════════════════════

def gen_offre() -> list:
    w = SQLWriter(OUT_DIR / "02_passjeunes_offre.sql",
                  "dbo.Offre",
                  ["nom_partenaire","categorie","nom_offre","description","conditions",
                   "type_avantage","valeur_avantage","unite_avantage",
                   "tarif_pass_jeunes","tarif_public","montant_a_debiter",
                   "montant_a_payer","solde_initial","solde_mensuel",
                   "ville","region","actif"],
                  dialect="mssql")

    offres = []
    for idx, offre in enumerate(tqdm(OFFRES_PASSJEUNES, desc="Offre"), start=1):
        w.add((offre["partenaire"], offre["categorie"], offre["offre"],
               offre.get("description"), offre.get("conditions"),
               offre["type_avantage"], offre["valeur"], offre["unite"],
               offre.get("tarif_pass_jeunes"), offre.get("tarif_public"),
               offre.get("montant_a_debiter"), offre.get("montant_a_payer"),
               offre.get("solde"), offre.get("solde_mensuel"),
               offre["ville"], offre["region"], True))
        offres.append({
            "id": idx,
            "partenaire": offre["partenaire"],
            "categorie": offre["categorie"],
            "type_avantage": offre["type_avantage"],
            "valeur": offre["valeur"],
            "unite": offre["unite"],
            "ville": offre["ville"],
        })

    w.close()
    return offres


# ══════════════════════════════════════════════════════════
# 3. PASSJEUNES — Solde (uniquement pour beneficiaires au statut Actif)
# ══════════════════════════════════════════════════════════

def gen_solde(beneficiaires: list, offres: list) -> list:
    w = SQLWriter(OUT_DIR / "03_passjeunes_solde.sql",
                  "dbo.Solde",
                  ["beneficiaire_id","offre_id","annee",
                   "credit_initial","credit_restant","date_renouvellement"],
                  dialect="mssql")

    soldes, solde_id = [], 1
    actifs = [b for b in beneficiaires if b["statut_pass"] == "Actif"]

    # Only offers with credit/solde defined
    offres_avec_solde = [o for o in offres if o.get("solde") is not None or o.get("solde_mensuel") is not None or o.get("montant_a_debiter") is not None]
    if not offres_avec_solde:
        offres_avec_solde = offres[:5]

    for b in tqdm(actifs, desc="Solde"):
        nb_offres  = random.randint(1, 3)
        offres_used = random.sample(offres_avec_solde, min(nb_offres, len(offres_avec_solde)))
        yr_start   = max(b["date_inscription"].year, min(ANNEES))

        for offre in offres_used:
            credit_init = float(offre.get("solde") or 500.00)
            for annee in ANNEES:
                if annee < yr_start:
                    continue
                credit_rest = round(random.uniform(0, credit_init), 2)
                date_ren    = date(annee, 1, 1)

                w.add((b["id"], offre["id"], annee, credit_init, credit_rest, date_ren))
                soldes.append({"id": solde_id, "beneficiaire_id": b["id"],
                               "offre_id": offre["id"], "annee": annee,
                               "credit_rest": credit_rest, "ville": b["ville"]})
                solde_id += 1

    w.close()
    return soldes

# ══════════════════════════════════════════════════════════
# 4. PASSJEUNES — Operation (ex-Utilisation)
# ══════════════════════════════════════════════════════════

def gen_operation(soldes: list, offres: list, beneficiaires: list):
    w = SQLWriter(OUT_DIR / "04_passjeunes_operation.sql",
                  "dbo.Operation",
                  ["beneficiaire_id","offre_id","solde_id","categorie",
                   "date_operation","montant_reduction","ville"],
                  dialect="mssql")

    def saison(m):
        return {1:.7,2:.7,3:.9,4:1.0,5:1.1,6:1.3,
                7:1.5,8:1.4,9:1.2,10:1.0,11:.8,12:.9}.get(m, 1.0)

    # Index soldes by (beneficiaire_id, offre_id, annee)
    solde_lookup = {(s["beneficiaire_id"], s["offre_id"], s["annee"]): s["id"] for s in soldes}

    def montant_operation(offre, mois):
        valeur = offre.get("valeur")
        unite = offre.get("unite")
        if offre["type_avantage"] == "Gratuite":
            return 0.00
        if offre["type_avantage"] == "Tarif fixe" and valeur is not None and unite == "DH":
            return round(float(valeur), 2)
        if offre["type_avantage"] == "Reduction" and valeur is not None and unite == "%":
            base = random.uniform(30, 150) * saison(mois)
            return round(base * float(valeur) / 100, 2)
        return round(random.uniform(5, 50) * saison(mois), 2)

    actifs = [b for b in beneficiaires if b["statut_pass"] == "Actif"]

    for b in tqdm(actifs, desc="Operation"):
        nb_ops = random.randint(2, 12)
        for _ in range(nb_ops):
            annee = random.choice(ANNEES)
            if annee < b["date_inscription"].year:
                annee = b["date_inscription"].year
            mois, jour = random.randint(1, 12), random.randint(1, 28)
            try:
                d = date(annee, mois, jour)
            except ValueError:
                d = date(annee, mois, 1)
            if d < b["date_inscription"] or d > DATE_MAX.date():
                continue

            offre = random.choice(offres)
            solde_id = solde_lookup.get((b["id"], offre["id"], annee))
            montant = montant_operation(offre, mois)
            ville = offre["ville"] if offre["ville"] not in ("National", "Multi-villes", "Tout le Maroc") else b["ville"]
            w.add((b["id"], offre["id"], solde_id, offre["categorie"], d, montant, ville))

    w.close()

# ══════════════════════════════════════════════════════════
# 5. PASSJEUNES — Motatawi3 (18-22 ans uniquement, lien direct)
# ══════════════════════════════════════════════════════════

def gen_motatawi3(beneficiaires: list):
    w = SQLWriter(OUT_DIR / "05_passjeunes_motatawi3.sql",
                  "dbo.Motatawi3",
                  ["beneficiaire_id","edition","region","domaine_volontariat","niveau_etudes",
                   "code_suivi","date_inscription","date_depot_dossier",
                   "statut_dossier","statut"],
                  dialect="mssql")

    eligibles = [b for b in beneficiaires
                 if AGE_MIN_MOTATAWI3 <= age_a_date(b["date_naissance"], b["date_inscription"]) <= AGE_MAX_MOTATAWI3
                 and b["statut_pass"] == "Actif"]

    inscrits = random.sample(eligibles, int(len(eligibles) * 0.15))
    used_codes = set()

    for b in tqdm(inscrits, desc="Motatawi3"):
        edition   = random.choice(EDITIONS_MOTATAWI3)
        domaine   = random.choice(DOMAINES_VOLONTARIAT)
        niveau    = wc(NIVEAUX_ETUDES, NIVEAUX_ETUDES_POIDS)
        statut_d  = wc(STATUTS_DOSSIER, STATUTS_DOSSIER_POIDS)
        statut    = wc(STATUTS_MOTATAWI3, STATUTS_MOTATAWI3_POIDS)
        date_ins  = b["date_inscription"]
        date_dep  = date_ins + timedelta(days=random.randint(1, 30))

        while True:
            code = f"MTW-{random.randint(100000, 999999)}"
            if code not in used_codes:
                used_codes.add(code)
                break

        w.add((b["id"], edition, b["region"], domaine, niveau, code,
               date_ins, date_dep, statut_d, statut))

    w.close()

# ══════════════════════════════════════════════════════════
# 6. JAM3IYA — Maison_Jeunes
# ══════════════════════════════════════════════════════════

def gen_maison_jeunes() -> list:
    w = SQLWriter(OUT_DIR / "06_jam3iya_maison_jeunes.sql",
                  "maison_jeunes",
                  ["nom","ville","region","adresse","date_ouverture",
                   "capacite_accueil","statut"],
                  dialect="mysql")

    maisons = []
    for i in tqdm(range(1, NB_MAISONS + 1), desc="Maison Jeunes"):
        region = region_weighted()
        ville  = random.choice(VILLES_PAR_REGION.get(region["nom"], ["Ville"]))
        statut = wc(STATUTS_MAISON, STATUTS_MAISON_POIDS)
        d_ouv  = rand_date(DATE_MIN - timedelta(days=365*10), DATE_MIN)
        capa   = random.choice([50, 100, 150, 200, 300, 500])
        nom    = f"Maison des Jeunes de {ville} {i}"
        adr    = f"{random.randint(1,200)} Rue {random.choice(NOMS_FAMILLE)}, {ville}"

        w.add((nom, ville, region["nom"], adr, d_ouv, capa, statut))
        maisons.append({"id": i, "region": region["nom"], "ville": ville})

    w.close()
    return maisons


# ══════════════════════════════════════════════════════════
# 7. JAM3IYA — Association (avec finances integrees)
# ══════════════════════════════════════════════════════════

def gen_association(maisons: list) -> list:
    w = SQLWriter(OUT_DIR / "07_jam3iya_association.sql",
                  "association",
                  ["nom","type","domaine_activite","maison_jeunes_id",
                   "date_creation","date_convention","statut","nb_membres",
                   "formulaire_adhesion","recettes_annuelles",
                   "depenses_annuelles","subvention_etat","annee_exercice"],
                  dialect="mysql")

    associations = []
    for i in tqdm(range(1, NB_ASSOCIATIONS + 1), desc="Association"):
        maison  = random.choice(maisons)
        domaine = random.choice(DOMAINES_ASSOCIATION)
        typ     = random.choice(TYPES_JURIDIQUES)
        statut  = wc(STATUTS_ASSO, STATUTS_ASSO_POIDS)
        d_crea  = rand_date(DATE_MIN - timedelta(days=365*5), DATE_MAX)
        d_conv  = (d_crea + timedelta(days=random.randint(30, 180))
                   if random.random() > 0.1 else None)
        nb_mbr  = random.randint(4, 7)
        nom     = f"Association {random.choice(NOMS_FAMILLE)} {domaine}"
        formulaire = f"FORM-ADH-{2021 + i % 4}-{i:04d}"

        est_active  = statut == "Active"
        base_budget = random.uniform(10000, 80000) if est_active else random.uniform(2000, 10000)
        recettes    = round(base_budget, 2)
        depenses    = round(base_budget * random.uniform(0.75, 0.95), 2)
        subvention  = round(random.uniform(5000, 35000) if est_active else 0, 2)
        annee_ex    = random.choice(ANNEES)

        w.add((nom, typ, domaine, maison["id"], d_crea, d_conv, statut, nb_mbr,
               formulaire, recettes, depenses, subvention, annee_ex))

        associations.append({"id": i, "statut": statut,
                              "region": maison["region"], "ville": maison["ville"],
                              "maison_id": maison["id"]})

    w.close()
    return associations

# ══════════════════════════════════════════════════════════
# 8. JAM3IYA — Personne_Association (fusion Membre_Bureau + Animateur)
# ══════════════════════════════════════════════════════════

def gen_personne_association(associations: list, beneficiaires: list):
    w = SQLWriter(OUT_DIR / "08_jam3iya_personne_association.sql",
                  "personne_association",
                  ["association_id","maison_jeunes_id","jeune_cin","nom","prenom",
                   "genre","type_personne","role","specialite",
                   "date_debut","statut"],
                  dialect="mysql")

    liaisons_possibles = random.sample(beneficiaires, int(len(beneficiaires) * 0.20))
    cin_iter = iter(liaisons_possibles)

    bureau_roles = ["President", "Vice_President", "Tresorier", "Secretaire"]

    for assoc in tqdm(associations, desc="Personne_Association"):
        # Bureau members (1 of each role)
        for role in bureau_roles:
            genre  = random.choice(["Homme", "Femme"])
            prenom, nom = prenom_nom_aleatoire(genre, random)
            d_debut = rand_date()
            statut  = "Actif" if random.random() > 0.1 else "Inactif"
            cin = None
            if random.random() < 0.20:
                try: cin = next(cin_iter)["cin"]
                except StopIteration: cin = None

            w.add((assoc["id"], None, cin, nom, prenom, genre,
                   "Membre_Bureau", role, None, d_debut, statut))

        # 1-2 Animateurs per association
        for _ in range(random.randint(1, 2)):
            genre  = random.choice(["Homme", "Femme"])
            prenom, nom = prenom_nom_aleatoire(genre, random)
            d_debut = rand_date()
            statut  = "Actif" if random.random() > 0.1 else "Inactif"
            specialite = random.choice(SPECIALITES_ANIMATEUR)
            cin = None
            if random.random() < 0.20:
                try: cin = next(cin_iter)["cin"]
                except StopIteration: cin = None

            w.add((assoc["id"], assoc["maison_id"], cin, nom, prenom, genre,
                   "Animateur", "Animateur", specialite, d_debut, statut))

    w.close()

# ══════════════════════════════════════════════════════════
# 9. JAM3IYA — Colonie_Vacances (campus saisonniers)
# ══════════════════════════════════════════════════════════

def gen_colonie_vacances() -> list:
    w = SQLWriter(OUT_DIR / "09_jam3iya_colonie_vacances.sql",
                  "colonie_vacances",
                  ["nom","ville","region","saison","annee",
                   "categorie_cible","duree_jours"],
                  dialect="mysql")

    colonies = []
    for i in tqdm(range(1, NB_COLONIES + 1), desc="Colonie Vacances"):
        region  = region_weighted()
        ville   = random.choice(VILLES_PAR_REGION.get(region["nom"], ["Ville"]))
        saison  = wc(SAISONS_COLONIE, SAISONS_POIDS)
        annee   = random.choice(ANNEES)
        cible   = random.choice(CATEGORIES_CIBLES_COLONIE)
        duree   = random.choice([7, 10, 14, 15, 21])
        nom     = f"Colonie {saison} {ville} {annee}"

        w.add((nom, ville, region["nom"], saison, annee, cible, duree))
        colonies.append({"id": i, "annee": annee})

    w.close()
    return colonies


# ══════════════════════════════════════════════════════════
# 10. JAM3IYA — Activite (ex-Projet, avec lien Colonie optionnel)
# ══════════════════════════════════════════════════════════

def gen_activite(associations: list, colonies: list) -> list:
    w = SQLWriter(OUT_DIR / "10_jam3iya_activite.sql",
                  "activite",
                  ["association_id","maison_jeunes_id","titre","description",
                   "type_activite","colonie_vacances_id","budget",
                   "date_debut","date_fin","statut"],
                  dialect="mysql")

    activites = []
    for assoc in tqdm(associations, desc="Activite"):
        nb_act = random.randint(0, 1) if assoc["statut"] == "Inactive" else random.randint(1, 5)

        for _ in range(nb_act):
            statut  = wc(STATUTS_ACTIVITE, STATUTS_ACTIVITE_POIDS)
            type_a  = wc(TYPES_ACTIVITE, TYPES_ACTIVITE_POIDS)
            d_deb   = rand_date()
            duree   = random.randint(1, 14) if type_a == "Saisonniere_Campus" else random.randint(1, 3)
            d_fin   = (d_deb + timedelta(days=duree)) if statut in ("Terminee", "En cours") else None
            budget  = round(random.uniform(500, 12000), 2)
            titre   = random.choice(TITRES_ACTIVITES)
            desc    = f"Activite '{titre.lower()}' organisee par l'association."

            colonie_id = None
            if type_a == "Saisonniere_Campus" and colonies and random.random() < 0.6:
                colonie_id = random.choice(colonies)["id"]

            w.add((assoc["id"], assoc["maison_id"], titre, desc, type_a,
                   colonie_id, budget, d_deb, d_fin, statut))

            activites.append({"assoc_id": assoc["id"], "statut": statut, "budget": budget})

    w.close()
    return activites

# ══════════════════════════════════════════════════════════
# 11. JAM3IYA — Rapport_Activite (texte + stats simples)
# ══════════════════════════════════════════════════════════

def gen_rapport_activite(activites: list):
    w = SQLWriter(OUT_DIR / "11_jam3iya_rapport_activite.sql",
                  "rapport_activite",
                  ["activite_id","date_envoi","contenu_texte",
                   "nb_participants","taux_satisfaction","budget_consomme"],
                  dialect="mysql")

    for idx, act in enumerate(tqdm(activites, desc="Rapport Activite"), start=1):
        if act["statut"] not in ("Terminee", "En cours"):
            continue
        if random.random() > 0.7:
            continue

        date_envoi = rand_date()
        contenu    = random.choice(CONTENUS_RAPPORT_TEMPLATES)
        nb_part    = random.randint(10, 120)
        satisf     = round(random.uniform(3.0, 5.0), 2)
        budget_c   = round(act["budget"] * random.uniform(0.70, 0.98), 2)

        w.add((idx, date_envoi, contenu, nb_part, satisf, budget_c))

    w.close()

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 60)
    print("  GENERATION DES DONNEES SOURCES — MJCC (Modele v3.1)")
    print(f"  {NB_BENEFICIAIRES:,} beneficiaires | {len(OFFRES_PASSJEUNES)} offres PassJeunes | {NB_ASSOCIATIONS:,} associations | {NB_MAISONS} maisons")
    print("=" * 60 + "\n")

    print("--- PassJeunesDB (SQL Server) ---")
    beneficiaires = gen_beneficiaire()
    offres        = gen_offre()
    soldes        = gen_solde(beneficiaires, offres)
    gen_operation(soldes, offres, beneficiaires)
    gen_motatawi3(beneficiaires)

    print("\n--- jam3iya_db (MySQL) ---")
    maisons       = gen_maison_jeunes()
    associations  = gen_association(maisons)
    gen_personne_association(associations, beneficiaires)
    colonies      = gen_colonie_vacances()
    activites     = gen_activite(associations, colonies)
    gen_rapport_activite(activites)

if __name__ == "__main__":
    main()
