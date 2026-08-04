"""
Mock data generation for Moroccan demography.

This module provides lists of realistic Moroccan, Sub-Saharan, expatriate, 
and immigrant names, as well as functions to generate random names, emails, 
and phone numbers for use in the ETL data simulation.
"""

# ── Prenoms masculins marocains courants ──────────────────
PRENOMS_HOMMES = [
    "Mohammed", "Ahmed", "Youssef", "Ali", "Hamza", "Omar", "Amine",
    "Adam", "Ayoub", "Zakaria", "Ismail", "Yassine", "Anas", "Karim",
    "Rachid", "Said", "Khalid", "Hassan", "Hicham", "Reda", "Mehdi",
    "Nabil", "Tarik", "Younes", "Bilal", "Marouane", "Soufiane",
    "Abdellah", "Abderrahim", "Aziz", "Fouad", "Jamal", "Kamal",
    "Mustapha", "Noureddine", "Othmane", "Rida", "Salah", "Walid",
    "Yassir", "Zouhair", "Adil", "Badr", "Driss", "Fahd", "Ghali",
    "Idriss", "Jawad", "Lahcen", "Mounir", "Nassim", "Oussama",
    "Rayan", "Samir", "Taha", "Wissam", "Yahya", "Ziad", "Achraf",
    "Brahim", "Chakib", "El Mehdi", "Faycal", "Hamid", "Imad",
    "Junaid", "Kenza", "Laila", "Mahdi", "Naoufal", "Rabii",
]

# ── Prenoms feminins marocains courants ───────────────────
PRENOMS_FEMMES = [
    "Fatima", "Khadija", "Aicha", "Salma", "Meryem", "Imane", "Sara",
    "Nour", "Yasmine", "Hind", "Malak", "Rim", "Ghita", "Zineb",
    "Loubna", "Siham", "Karima", "Naima", "Latifa", "Samira", "Amina",
    "Hajar", "Ikram", "Jihane", "Kawtar", "Lamiae", "Nadia", "Ouiam",
    "Rania", "Sanae", "Wafae", "Zahra", "Asmae", "Btissam", "Chaimae",
    "Dounia", "Fadwa", "Hafsa", "Ibtissam", "Jamila", "Khaoula",
    "Layla", "Mouna", "Nawal", "Oumaima", "Rajae", "Soukaina",
    "Widad", "Yousra", "Zakia", "Ilham", "Manal", "Nisrine", "Rihab",
    "Safae", "Touria", "Amal", "Bouchra", "Dalal", "Faiza", "Hanane",
]

# ── Noms de famille marocains courants ────────────────────
NOMS_FAMILLE = [
    "Alaoui", "Bennani", "El Fassi", "Tazi", "Berrada", "Idrissi",
    "Chraibi", "Lahlou", "Benjelloun", "Squalli", "Kabbaj", "Sefrioui",
    "El Amrani", "Benkirane", "Cherkaoui", "Ziani", "Fassi Fihri",
    "El Ouazzani", "Guessous", "Sbai", "Benabdellah", "Bakkali",
    "El Mansouri", "Tahiri", "Zerouali", "Benhaddou", "El Yacoubi",
    "Ammor", "Bensaid", "Chakir", "Doukkali", "El Khayat", "Fadili",
    "Ghazi", "Hajji", "Kadiri", "Lamrani", "Mekouar", "Naciri",
    "Ouazzani", "Qandil", "Raissouni", "Slaoui", "Tibari", "Wahbi",
    "Zniber", "Amrani", "Benomar", "Chami", "Douiri", "Essakalli",
    "Filali", "Ghannam", "Haddaoui", "Iraqi", "Jabri", "Kettani",
    "Loukili", "Maazouzi", "Ouali", "Rifai", "Skalli", "Tahri",
    "Benslimane", "Chaoui", "Drissi", "Fassi", "Harakat", "Jaidi",
    "Kettouch", "Mernissi", "Ouahbi", "Rachidi", "Souiri", "Zerhouni",
]

# ── Prenoms masculins subsahariens courants ────────────────
PRENOMS_HOMMES_SUBSAHARIENS = [
    "Mamadou", "Ousmane", "Ibrahima", "Moussa", "Abdoulaye", "Cheikh",
    "Boubacar", "Modou", "Amadou", "Demba", "Lamine", "Saliou",
    "Pape", "Seydou", "Tidiane", "Babacar", "Souleymane", "Aliou",
    "Djibril", "Thierno", "Koffi", "Kouadio", "Yao", "Kouame",
    "Jean-Pierre", "Patrick", "Alassane", "Bakary", "Diallo",
    "Emmanuel", "Paul", "Christian", "Parfait", "Blaise", "Fabrice",
]

# ── Prenoms feminins subsahariens courants ─────────────────
PRENOMS_FEMMES_SUBSAHARIENNES = [
    "Aminata", "Fatou", "Mariama", "Awa", "Aissatou", "Binta",
    "Coumba", "Djeneba", "Kadiatou", "Maimouna", "Ndèye", "Oumou",
    "Ramatoulaye", "Sira", "Adja", "Khady", "Mariam", "Nafi",
    "Rokia", "Safiatou", "Adjoua", "Akissi", "Aya", "Lou",
    "Grace", "Esther", "Blessing", "Precious", "Divine", "Carine",
]

# ── Noms de famille subsahariens courants ──────────────────
NOMS_FAMILLE_SUBSAHARIENS = [
    "Diallo", "Diop", "Ndiaye", "Fall", "Sow", "Ba", "Sy", "Gueye",
    "Niang", "Mbaye", "Diouf", "Sarr", "Cissé", "Thiam", "Wade",
    "Touré", "Konaté", "Traoré", "Coulibaly", "Keita", "Camara",
    "Ouattara", "Koné", "Bamba", "Yao", "Kouassi", "N'Guessan",
    "Eboué", "Mbemba", "Ndong", "Obi", "Mensah", "Asante",
    "Fofana", "Soumaré", "Kanté", "Condé", "Baldé", "Bah",
]

# ── Prenoms masculins expatriés (européens) ───────────────
PRENOMS_HOMMES_EXPATRIES = [
    "Jean", "Pierre", "Marc", "François", "Nicolas", "Antoine",
    "Philippe", "Laurent", "Thomas", "Christophe", "Alexandre", "David",
    "Carlos", "Pablo", "Miguel", "Alejandro", "Diego", "Fernando",
    "Hans", "Stefan", "Klaus", "Michael", "Robert", "James",
    "William", "Daniel", "Lucas", "Hugo", "Luca", "Matteo",
]

# ── Prenoms feminins expatriés ────────────────────────────
PRENOMS_FEMMES_EXPATRIEES = [
    "Marie", "Sophie", "Isabelle", "Catherine", "Claire", "Julie",
    "Anne", "Céline", "Nathalie", "Valérie", "Camille", "Emma",
    "Carmen", "María", "Laura", "Ana", "Elena", "Lucia",
    "Heidi", "Ingrid", "Anna", "Sarah", "Lisa", "Charlotte",
    "Alice", "Clara", "Léa", "Margaux", "Chiara", "Giulia",
]

# ── Noms de famille expatriés ─────────────────────────────
NOMS_FAMILLE_EXPATRIES = [
    "Dupont", "Martin", "Bernard", "Petit", "Moreau", "Leroy",
    "Roux", "Simon", "Laurent", "Michel", "Lefèvre", "Garcia",
    "Martinez", "Lopez", "Rodriguez", "Hernandez", "Fernandez",
    "González", "Müller", "Schmidt", "Fischer", "Weber", "Meyer",
    "Smith", "Johnson", "Brown", "Wilson", "Taylor", "Anderson",
    "Rossi", "Bianchi", "Romano", "Costa", "Santos", "Silva",
]

# ── Prenoms masculins immigrés (arabes non-marocains) ─────
PRENOMS_HOMMES_IMMIGRES = [
    "Bashar", "Fadi", "Rami", "Samer", "Tarek", "Nizar",
    "Khaled", "Ayman", "Riad", "Wassim", "Mazen", "Ziad",
    "Abdelkader", "Lotfi", "Nassim", "Sofiane", "Lyes", "Nadir",
    "Saif", "Sultan", "Faisal", "Majed", "Nasser", "Turki",
    "Ammar", "Muntasir", "Qais", "Haytham", "Ghassan", "Wael",
]

# ── Prenoms feminins immigrés ─────────────────────────────
PRENOMS_FEMMES_IMMIGREES = [
    "Lina", "Dalia", "Reem", "Nour", "Rana", "Maya",
    "Hala", "Dina", "Yara", "Lamia", "Sana", "Rasha",
    "Amira", "Sabrina", "Lydia", "Nesrine", "Houda", "Dalila",
    "Ghada", "Maha", "Abeer", "Noura", "Farah", "Zeina",
    "Ruba", "Tala", "Jumana", "Asma", "Bouchra", "Wafa",
]

# ── Noms de famille immigrés (arabes non-marocains) ───────
NOMS_FAMILLE_IMMIGRES = [
    "Al-Assad", "Al-Masri", "Al-Ahmad", "Al-Hussein", "Al-Sharif",
    "Boudiaf", "Belkacem", "Boumediene", "Bensalah", "Hadjadj",
    "Khelifi", "Mebarki", "Rahmani", "Saidi", "Zeroual",
    "Al-Rashid", "Al-Bakr", "Al-Nasser", "Al-Hamad", "Al-Dosari",
    "Hammoud", "Khoury", "Nassar", "Sabbagh", "Haddad",
    "Mansour", "Ibrahim", "Khalil", "Saleh", "Abbas",
]

# ── Domaines email courants au Maroc ──────────────────────
DOMAINES_EMAIL = ["gmail.com", "yahoo.fr", "hotmail.com", "outlook.com", "menara.ma"]

# ── Prefixes telephone mobile marocain ────────────────────
# 06 et 07 sont les prefixes mobiles au Maroc (format +212 6XX XXXXXX)
PREFIXES_TEL = ["06", "07"]


def prenom_nom_aleatoire(genre: str, rng) -> tuple:
    """
    Generate a random Moroccan first and last name.
    
    Args:
        genre (str): 'Homme' or 'Femme'.
        rng (random.Random): A seeded random number generator.
        
    Returns:
        tuple: (first_name, last_name).
    """
    prenom = rng.choice(PRENOMS_HOMMES) if genre == "Homme" else rng.choice(PRENOMS_FEMMES)
    nom = rng.choice(NOMS_FAMILLE)
    return prenom, nom


def prenom_nom_subsaharien(genre: str, rng) -> tuple:
    """
    Generate a random Sub-Saharan first and last name.
    
    Args:
        genre (str): 'Homme' or 'Femme'.
        rng (random.Random): A seeded random number generator.
        
    Returns:
        tuple: (first_name, last_name).
    """
    prenom = rng.choice(PRENOMS_HOMMES_SUBSAHARIENS) if genre == "Homme" else rng.choice(PRENOMS_FEMMES_SUBSAHARIENNES)
    nom = rng.choice(NOMS_FAMILLE_SUBSAHARIENS)
    return prenom, nom


def prenom_nom_expatrie(genre: str, rng) -> tuple:
    """
    Generate a random expatriate (European) first and last name.
    
    Args:
        genre (str): 'Homme' or 'Femme'.
        rng (random.Random): A seeded random number generator.
        
    Returns:
        tuple: (first_name, last_name).
    """
    prenom = rng.choice(PRENOMS_HOMMES_EXPATRIES) if genre == "Homme" else rng.choice(PRENOMS_FEMMES_EXPATRIEES)
    nom = rng.choice(NOMS_FAMILLE_EXPATRIES)
    return prenom, nom


def prenom_nom_immigre(genre: str, rng) -> tuple:
    """
    Generate a random immigrant (non-Moroccan Arab) first and last name.
    
    Args:
        genre (str): 'Homme' or 'Femme'.
        rng (random.Random): A seeded random number generator.
        
    Returns:
        tuple: (first_name, last_name).
    """
    prenom = rng.choice(PRENOMS_HOMMES_IMMIGRES) if genre == "Homme" else rng.choice(PRENOMS_FEMMES_IMMIGREES)
    nom = rng.choice(NOMS_FAMILLE_IMMIGRES)
    return prenom, nom


def telephone_marocain(rng) -> str:
    """
    Generate a plausible Moroccan mobile phone number.
    
    Args:
        rng (random.Random): A seeded random number generator.
        
    Returns:
        str: Phone number formatted as +2126XXXXXXXX or +2127XXXXXXXX.
    """
    prefix = rng.choice(PREFIXES_TEL)
    suffix = "".join(str(rng.randint(0, 9)) for _ in range(8))
    return f"+212{prefix[1]}{suffix}"


def email_marocain(prenom: str, nom: str, idx: int, rng) -> str:
    """
    Generate a plausible Moroccan email address.
    
    Args:
        prenom (str): First name.
        nom (str): Last name.
        idx (int): A unique index to prevent duplicate emails.
        rng (random.Random): A seeded random number generator.
        
    Returns:
        str: The generated email address.
    """
    p = prenom.lower().replace(" ", "").replace("-", "").replace("'", "")
    n = nom.lower().replace(" ", "").replace("-", "").replace("'", "")
    domaine = rng.choice(DOMAINES_EMAIL)
    return f"{p}.{n}{idx}@{domaine}"

