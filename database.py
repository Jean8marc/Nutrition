"""
NutriTrack Pro — Couche base de données (SQLite)
"""
import sqlite3
import math
import shutil
from datetime import datetime, date, timedelta

DB_PATH = "nutrition.db"

# ─────────────────────────── SESSION UTILISATEUR ─────────────────────────────

_current_user_id: int | None = None

def set_current_user(user_id: int):
    global _current_user_id
    _current_user_id = user_id

def get_current_user_id() -> int | None:
    return _current_user_id

def get_current_user() -> dict:
    if _current_user_id is None:
        return {}
    return get_user(_current_user_id) or {}

# ─────────────────────────── CONNEXION ───────────────────────────

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate():
    """Ajoute les nouvelles colonnes aux BDD existantes sans les recréer."""
    conn = get_connection()
    c = conn.cursor()

    # ── aliments ──────────────────────────────────────────────────
    existing_alim = {r[1] for r in c.execute("PRAGMA table_info(aliments)").fetchall()}
    for col, typedef in [
        ("sucres",              "REAL DEFAULT 0"),
        ("acides_gras_satures", "REAL DEFAULT 0"),
        ("sel",                 "REAL DEFAULT 0"),
        ("cholesterol",         "REAL DEFAULT 0"),
        ("poids_unite_g",       "REAL DEFAULT 0"),
        ("allergenes",          "TEXT DEFAULT ''"),
    ]:
        if col not in existing_alim:
            c.execute(f"ALTER TABLE aliments ADD COLUMN {col} {typedef}")

    # ── recettes ──────────────────────────────────────────────────
    existing_rec = {r[1] for r in c.execute("PRAGMA table_info(recettes)").fetchall()}
    for col, typedef in [
        ("temps_cuisson", "INTEGER DEFAULT 20"),
        ("difficulte",    "TEXT DEFAULT 'Facile'"),
        ("cout",          "TEXT DEFAULT '€'"),
        ("type_cuisson",  "TEXT DEFAULT ''"),
        ("temperature",   "INTEGER DEFAULT 0"),
        ("tags_regime",   "TEXT DEFAULT ''"),
        ("allergenes",    "TEXT DEFAULT ''"),
        ("conservation",  "TEXT DEFAULT ''"),
        ("astuce",        "TEXT DEFAULT ''"),
        ("favori",        "INTEGER DEFAULT 0"),
    ]:
        if col not in existing_rec:
            c.execute(f"ALTER TABLE recettes ADD COLUMN {col} {typedef}")

    # ── journal_repas ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS journal_repas (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        date        TEXT    NOT NULL,
        heure       TEXT    DEFAULT '',
        aliment_id  INTEGER,
        nom         TEXT    DEFAULT '',
        quantite_g  REAL    DEFAULT 100,
        calories    REAL    DEFAULT 0,
        proteines   REAL    DEFAULT 0,
        glucides    REAL    DEFAULT 0,
        lipides     REAL    DEFAULT 0,
        fibres      REAL    DEFAULT 0,
        notes       TEXT    DEFAULT ''
    )""")

    # ── recette_ingredients ───────────────────────────────────────
    existing_ri = {r[1] for r in c.execute("PRAGMA table_info(recette_ingredients)").fetchall()}
    for col, typedef in [
        ("unite_recette",       "TEXT DEFAULT 'g'"),
        ("etat",                "TEXT DEFAULT 'cru'"),
        ("coefficient_cuisson", "REAL DEFAULT 1.0"),
        ("notes_preparation",   "TEXT DEFAULT ''"),
        ("ordre",               "INTEGER DEFAULT 0"),
    ]:
        if col not in existing_ri:
            c.execute(f"ALTER TABLE recette_ingredients ADD COLUMN {col} {typedef}")

    # ── recette_etapes (nouvelle table) ───────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS recette_etapes (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        recette_id   INTEGER REFERENCES recettes(id) ON DELETE CASCADE,
        ordre        INTEGER DEFAULT 1,
        titre        TEXT    DEFAULT '',
        description  TEXT    NOT NULL,
        duree_min    INTEGER DEFAULT 0,
        temperature  INTEGER DEFAULT 0,
        type_action  TEXT    DEFAULT ''
    )""")

    # ── users (multi-utilisateurs) ───────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        prenom          TEXT    NOT NULL,
        nom             TEXT    DEFAULT '',
        age             INTEGER DEFAULT 0,
        sexe            TEXT    DEFAULT 'H',
        poids           REAL    DEFAULT 70,
        taille          REAL    DEFAULT 170,
        tour_de_taille  REAL    DEFAULT 0,
        objectif        TEXT    DEFAULT 'maintien',
        activite        TEXT    DEFAULT 'sedentaire',
        poids_cible     REAL    DEFAULT 0,
        allergies       TEXT    DEFAULT '',
        notes_sante     TEXT    DEFAULT '',
        avatar_color    TEXT    DEFAULT '#22c55e',
        created_at      TEXT    DEFAULT ''
    )""")

    # ── suivi_poids (avec user_id + tour_de_taille) ───────────────
    existing_sp = {r[1] for r in c.execute("PRAGMA table_info(suivi_poids)").fetchall()}
    for col, typedef in [
        ("user_id",        "INTEGER DEFAULT 1"),
        ("tour_de_taille", "REAL DEFAULT 0"),
    ]:
        if col not in existing_sp:
            c.execute(f"ALTER TABLE suivi_poids ADD COLUMN {col} {typedef}")

    # ── users : protéines dynamiques + objectif eau ───────────────
    existing_users = {r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()}
    for col, typedef in [
        ("coefficient_proteines", "REAL DEFAULT 0"),
        ("objectif_eau_ml",       "INTEGER DEFAULT 2000"),
    ]:
        if col not in existing_users:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {typedef}")

    # ── suivi_eau ─────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS suivi_eau (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id  INTEGER NOT NULL,
        date     TEXT    NOT NULL,
        heure    TEXT    DEFAULT '',
        ml       INTEGER DEFAULT 0,
        notes    TEXT    DEFAULT ''
    )""")

    # ── activites_sport ───────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS activites_sport (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id          INTEGER NOT NULL,
        date             TEXT    NOT NULL,
        heure            TEXT    DEFAULT '',
        type_activite    TEXT    NOT NULL,
        duree_min        INTEGER DEFAULT 0,
        vitesse_kmh      REAL    DEFAULT 0,
        intensite        TEXT    DEFAULT 'leger',
        calories_brulees REAL    DEFAULT 0,
        notes            TEXT    DEFAULT ''
    )""")
    try:
        conn.execute("ALTER TABLE users ADD COLUMN fc_max INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE activites_sport ADD COLUMN fc_observee INTEGER DEFAULT 0")
    except Exception:
        pass

    # ── programmes : scope par utilisateur ────────────────────────
    existing_prog = {r[1] for r in c.execute("PRAGMA table_info(programmes)").fetchall()}
    if "user_id" not in existing_prog:
        c.execute("ALTER TABLE programmes ADD COLUMN user_id INTEGER DEFAULT 1")

    # Créer des programmes par défaut pour chaque utilisateur qui n'en a pas
    users = c.execute("SELECT id, sexe, poids, taille, age, activite, objectif FROM users").fetchall()
    facteurs = {'sedentaire': 1.2, 'leger': 1.375, 'modere': 1.55, 'actif': 1.725, 'tres_actif': 1.9}
    for u in users:
        uid = u[0]
        has = c.execute("SELECT COUNT(*) FROM programmes WHERE user_id=?", (uid,)).fetchone()[0]
        if has:
            continue
        sexe, poids, taille, age, activite = u[1], u[2], u[3], u[4], u[5]
        if sexe == 'H':
            bmr = 10 * poids + 6.25 * taille - 5 * age + 5
        else:
            bmr = 10 * poids + 6.25 * taille - 5 * age - 161
        tdee = int(bmr * facteurs.get(activite, 1.2))
        cal_perte   = max(1200, tdee - 300)
        cal_maintien = tdee
        cal_masse   = tdee + 300
        actif_perte = 1 if u[6] == 'perte_poids' else 0
        actif_maint = 1 if u[6] == 'maintien'    else 0
        actif_masse = 1 if u[6] == 'prise_masse'  else 0
        c.executemany("""INSERT INTO programmes
            (user_id,nom,objectif,duree_semaines,calories_jour,
             proteines_pct,glucides_pct,lipides_pct,description,actif)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", [
            (uid, "Perte de poids — 12 sem.", "perte_poids", 12, cal_perte,
             35, 35, 30, "Programme déficitaire modéré.", actif_perte),
            (uid, "Maintien & Équilibre",     "maintien",    8,  cal_maintien,
             25, 50, 25, "Programme d'entretien équilibré.", actif_maint),
            (uid, "Prise de masse musculaire","prise_masse",  8,  cal_masse,
             30, 45, 25, "Programme hypercalorique modéré.", actif_masse),
        ])

    # ── stock ─────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS stock (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id          INTEGER NOT NULL,
        aliment_id       INTEGER REFERENCES aliments(id),
        quantite         REAL    DEFAULT 0,
        unite            TEXT    DEFAULT 'g',
        date_peremption  TEXT    NULL,
        notes            TEXT    DEFAULT '',
        updated_at       TEXT    DEFAULT ''
    )""")

    # ── stock v2 : seuils, staples, fréquence, eau ────────────────
    for col, typedef in [
        ("quantite_min",    "REAL DEFAULT 0"),
        ("est_staple",      "INTEGER DEFAULT 0"),
        ("quantite_cible",  "REAL DEFAULT 0"),
        ("nb_utilisations", "INTEGER DEFAULT 0"),
        ("est_eau",         "INTEGER DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE stock ADD COLUMN {col} {typedef}")
        except Exception:
            pass

    conn.commit()
    conn.close()


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS profil (
        id            INTEGER PRIMARY KEY DEFAULT 1,
        nom           TEXT    DEFAULT '',
        prenom        TEXT    DEFAULT '',
        age           INTEGER DEFAULT 0,
        sexe          TEXT    DEFAULT 'H',
        poids         REAL    DEFAULT 70,
        taille        REAL    DEFAULT 170,
        objectif      TEXT    DEFAULT 'maintien',
        activite      TEXT    DEFAULT 'sedentaire',
        poids_cible   REAL    DEFAULT 0,
        allergies     TEXT    DEFAULT '',
        notes_sante   TEXT    DEFAULT '',
        updated_at    TEXT    DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS aliments (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        nom                 TEXT    NOT NULL,
        categorie           TEXT    DEFAULT 'Autre',
        calories            REAL    DEFAULT 0,
        proteines           REAL    DEFAULT 0,
        glucides            REAL    DEFAULT 0,
        sucres              REAL    DEFAULT 0,
        lipides             REAL    DEFAULT 0,
        acides_gras_satures REAL    DEFAULT 0,
        fibres              REAL    DEFAULT 0,
        sel                 REAL    DEFAULT 0,
        cholesterol         REAL    DEFAULT 0,
        ig                  INTEGER DEFAULT 0,
        unite               TEXT    DEFAULT 'g',
        poids_unite_g       REAL    DEFAULT 0,
        allergenes          TEXT    DEFAULT '',
        notes               TEXT    DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS recettes (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        nom              TEXT    NOT NULL,
        description      TEXT    DEFAULT '',
        categorie        TEXT    DEFAULT 'Plat principal',
        temps_prep       INTEGER DEFAULT 15,
        temps_cuisson    INTEGER DEFAULT 20,
        portions         INTEGER DEFAULT 2,
        difficulte       TEXT    DEFAULT 'Facile',
        cout             TEXT    DEFAULT '€',
        type_cuisson     TEXT    DEFAULT '',
        temperature      INTEGER DEFAULT 0,
        tags_regime      TEXT    DEFAULT '',
        allergenes       TEXT    DEFAULT '',
        conservation     TEXT    DEFAULT '',
        astuce           TEXT    DEFAULT '',
        notes            TEXT    DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS recette_ingredients (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        recette_id           INTEGER REFERENCES recettes(id) ON DELETE CASCADE,
        aliment_id           INTEGER REFERENCES aliments(id),
        quantite             REAL    DEFAULT 100,
        unite_recette        TEXT    DEFAULT 'g',
        etat                 TEXT    DEFAULT 'cru',
        coefficient_cuisson  REAL    DEFAULT 1.0,
        notes_preparation    TEXT    DEFAULT '',
        ordre                INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS recette_etapes (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        recette_id   INTEGER REFERENCES recettes(id) ON DELETE CASCADE,
        ordre        INTEGER DEFAULT 1,
        titre        TEXT    DEFAULT '',
        description  TEXT    NOT NULL,
        duree_min    INTEGER DEFAULT 0,
        temperature  INTEGER DEFAULT 0,
        type_action  TEXT    DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS programmes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        nom             TEXT    NOT NULL,
        objectif        TEXT    DEFAULT 'perte_poids',
        duree_semaines  INTEGER DEFAULT 4,
        calories_jour   INTEGER DEFAULT 1800,
        proteines_pct   INTEGER DEFAULT 30,
        glucides_pct    INTEGER DEFAULT 40,
        lipides_pct     INTEGER DEFAULT 30,
        description     TEXT    DEFAULT '',
        actif           INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS suivi_poids (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER DEFAULT 1,
        date            TEXT,
        poids           REAL,
        tour_de_taille  REAL    DEFAULT 0,
        notes           TEXT    DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        prenom          TEXT    NOT NULL,
        nom             TEXT    DEFAULT '',
        age             INTEGER DEFAULT 0,
        sexe            TEXT    DEFAULT 'H',
        poids           REAL    DEFAULT 70,
        taille          REAL    DEFAULT 170,
        tour_de_taille  REAL    DEFAULT 0,
        objectif        TEXT    DEFAULT 'maintien',
        activite        TEXT    DEFAULT 'sedentaire',
        poids_cible     REAL    DEFAULT 0,
        allergies       TEXT    DEFAULT '',
        notes_sante     TEXT    DEFAULT '',
        avatar_color    TEXT    DEFAULT '#22c55e',
        created_at      TEXT    DEFAULT ''
    )""")

    conn.commit()

    # Données exemples
    c.execute("SELECT COUNT(*) FROM aliments")
    if c.fetchone()[0] == 0:
        _insert_sample_aliments(c)
        _insert_sample_recettes(c)
        _insert_sample_programmes(c)
        conn.commit()

    conn.close()
    # Migration pour les BDD existantes
    _migrate()
    # Table planning (créée séparément car peut manquer dans les BDD existantes)
    _create_planning_table()


def _insert_sample_aliments(c):
    data = [
        # (nom, categorie, cal, prot, gluc, lip, fibres, ig, unite)
        ("Poulet (blanc)", "Viandes & Poissons", 165, 31.0, 0.0, 3.6, 0.0, 0, "g"),
        ("Bœuf haché 5%", "Viandes & Poissons", 137, 21.0, 0.0, 5.5, 0.0, 0, "g"),
        ("Saumon frais", "Viandes & Poissons", 208, 20.0, 0.0, 13.0, 0.0, 0, "g"),
        ("Thon en conserve", "Viandes & Poissons", 116, 26.0, 0.0, 1.0, 0.0, 0, "g"),
        ("Crevettes", "Viandes & Poissons", 99, 24.0, 0.0, 0.3, 0.0, 0, "g"),
        ("Dinde (blanc)", "Viandes & Poissons", 135, 30.0, 0.0, 1.0, 0.0, 0, "g"),
        ("Œuf entier", "Œufs & Laitiers", 155, 13.0, 1.1, 11.0, 0.0, 0, "unité"),
        ("Fromage blanc 0%", "Œufs & Laitiers", 50, 8.0, 4.0, 0.1, 0.0, 27, "g"),
        ("Yaourt grec nature", "Œufs & Laitiers", 97, 9.0, 3.6, 5.0, 0.0, 35, "g"),
        ("Lait demi-écrémé", "Œufs & Laitiers", 46, 3.2, 4.8, 1.5, 0.0, 32, "ml"),
        ("Cottage cheese", "Œufs & Laitiers", 98, 11.0, 3.4, 4.3, 0.0, 30, "g"),
        ("Riz blanc cuit", "Céréales & Féculents", 130, 2.7, 28.0, 0.3, 0.4, 64, "g"),
        ("Riz brun cuit", "Céréales & Féculents", 112, 2.6, 23.0, 0.9, 1.8, 50, "g"),
        ("Flocons d'avoine", "Céréales & Féculents", 389, 17.0, 66.0, 7.0, 10.0, 55, "g"),
        ("Pain complet", "Céréales & Féculents", 247, 8.5, 47.0, 3.4, 7.0, 51, "g"),
        ("Quinoa cuit", "Céréales & Féculents", 120, 4.4, 22.0, 1.9, 2.8, 53, "g"),
        ("Patate douce", "Céréales & Féculents", 86, 1.6, 20.0, 0.1, 3.0, 50, "g"),
        ("Pâtes complètes cuites", "Céréales & Féculents", 157, 5.5, 31.0, 0.9, 4.5, 50, "g"),
        ("Lentilles cuites", "Légumineuses", 116, 9.0, 20.0, 0.4, 8.0, 32, "g"),
        ("Pois chiches cuits", "Légumineuses", 164, 8.9, 27.0, 2.6, 7.6, 28, "g"),
        ("Haricots rouges cuits", "Légumineuses", 127, 8.7, 22.8, 0.5, 6.4, 29, "g"),
        ("Edamame", "Légumineuses", 121, 11.9, 8.9, 5.2, 5.2, 18, "g"),
        ("Brocoli", "Légumes", 34, 2.8, 7.0, 0.4, 2.6, 15, "g"),
        ("Épinards", "Légumes", 23, 2.9, 3.6, 0.4, 2.2, 15, "g"),
        ("Tomate", "Légumes", 18, 0.9, 3.9, 0.2, 1.2, 30, "g"),
        ("Courgette", "Légumes", 17, 1.2, 3.1, 0.3, 1.0, 15, "g"),
        ("Poivron rouge", "Légumes", 31, 1.0, 7.0, 0.3, 2.1, 15, "g"),
        ("Champignons", "Légumes", 22, 3.1, 3.3, 0.3, 1.0, 15, "g"),
        ("Carotte", "Légumes", 41, 0.9, 10.0, 0.2, 2.8, 47, "g"),
        ("Concombre", "Légumes", 15, 0.7, 3.6, 0.1, 0.5, 15, "g"),
        ("Avocat", "Fruits & Oléagineux", 160, 2.0, 9.0, 15.0, 7.0, 15, "g"),
        ("Banane", "Fruits & Oléagineux", 89, 1.1, 23.0, 0.3, 2.6, 52, "g"),
        ("Pomme", "Fruits & Oléagineux", 52, 0.3, 14.0, 0.2, 2.4, 38, "g"),
        ("Myrtilles", "Fruits & Oléagineux", 57, 0.7, 14.5, 0.3, 2.4, 25, "g"),
        ("Fraises", "Fruits & Oléagineux", 32, 0.7, 7.7, 0.3, 2.0, 40, "g"),
        ("Amandes", "Fruits & Oléagineux", 579, 21.0, 22.0, 50.0, 12.5, 15, "g"),
        ("Noix", "Fruits & Oléagineux", 654, 15.0, 14.0, 65.0, 6.7, 15, "g"),
        ("Huile d'olive", "Matières grasses", 884, 0.0, 0.0, 100.0, 0.0, 0, "ml"),
        ("Huile de coco", "Matières grasses", 862, 0.0, 0.0, 100.0, 0.0, 0, "ml"),
        ("Beurre", "Matières grasses", 717, 0.9, 0.6, 81.0, 0.0, 0, "g"),
    ]
    c.executemany("""INSERT INTO aliments
        (nom,categorie,calories,proteines,glucides,lipides,fibres,ig,unite)
        VALUES (?,?,?,?,?,?,?,?,?)""", data)


def _insert_sample_recettes(c):
    # Quelques recettes de démo
    recettes = [
        ("Bowl poulet & quinoa", "Bowl protéiné complet avec légumes colorés", "Déjeuner", 25, 2),
        ("Overnight oats", "Flocons d'avoine préparés la veille, riches en fibres", "Petit-déjeuner", 5, 1),
        ("Omelette aux épinards", "Omelette légère et protéinée", "Petit-déjeuner", 10, 1),
        ("Saumon grillé & patate douce", "Repas équilibré riche en oméga-3", "Dîner", 20, 2),
        ("Soupe de lentilles", "Soupe réconfortante à IG bas", "Dîner", 35, 4),
    ]
    for nom, desc, cat, temps, portions in recettes:
        c.execute("""INSERT INTO recettes (nom,description,categorie,temps_prep,portions)
                     VALUES (?,?,?,?,?)""", (nom, desc, cat, temps, portions))


def _insert_sample_programmes(c):
    programmes = [
        ("Perte de poids — 12 sem.", "perte_poids", 12, 1600, 35, 35, 30,
         "Programme déficitaire modéré. Favorise la perte de masse grasse tout en préservant la masse musculaire."),
        ("Maintien & Équilibre", "maintien", 8, 2000, 25, 50, 25,
         "Programme d'entretien avec alimentation équilibrée et variée."),
        ("Prise de masse musculaire", "prise_masse", 8, 2800, 30, 45, 25,
         "Programme hypercalorique modéré pour favoriser la prise de muscle."),
    ]
    for nom, obj, duree, cal, prot, gluc, lip, desc in programmes:
        c.execute("""INSERT INTO programmes
            (nom,objectif,duree_semaines,calories_jour,proteines_pct,glucides_pct,lipides_pct,description)
            VALUES (?,?,?,?,?,?,?,?)""", (nom, obj, duree, cal, prot, gluc, lip, desc))


# ─────────────────────────── UTILISATEURS ────────────────────────────────────

AVATAR_COLORS = [
    "#22c55e","#3b82f6","#f59e0b","#ec4899",
    "#8b5cf6","#06b6d4","#f97316","#ef4444",
]

def get_users() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM users ORDER BY prenom").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user(user_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(prenom: str, nom: str = "", poids: float = 70,
                taille: float = 170, avatar_color: str = "#22c55e") -> int:
    conn = get_connection()
    cur = conn.execute("""INSERT INTO users
        (prenom, nom, poids, taille, avatar_color, created_at)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (prenom.strip(), nom.strip(), poids, taille,
         avatar_color, datetime.now().isoformat()))
    uid = cur.lastrowid
    # Entrée initiale dans l'historique
    conn.execute("""INSERT INTO suivi_poids (user_id, date, poids, tour_de_taille, notes)
                    VALUES (?, ?, ?, 0, 'Entrée initiale — création du profil')""",
                 (uid, date.today().isoformat(), poids))
    conn.commit()
    conn.close()
    return uid

def save_user(user_id: int, data: dict):
    conn = get_connection()
    conn.execute("""UPDATE users SET
        prenom=:prenom, nom=:nom, age=:age, sexe=:sexe,
        poids=:poids, taille=:taille, tour_de_taille=:tour_de_taille,
        objectif=:objectif, activite=:activite, poids_cible=:poids_cible,
        allergies=:allergies, notes_sante=:notes_sante,
        coefficient_proteines=:coefficient_proteines,
        objectif_eau_ml=:objectif_eau_ml,
        fc_max=:fc_max WHERE id=:id""",
        {**data, 'id': user_id,
         'coefficient_proteines': float(data.get('coefficient_proteines') or 0),
         'objectif_eau_ml': int(data.get('objectif_eau_ml') or 2000),
         'fc_max': int(data.get('fc_max') or 0)})
    conn.commit()
    conn.close()

def delete_user(user_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM suivi_poids WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

def user_initials(user: dict) -> str:
    p = (user.get('prenom') or '?')[0].upper()
    n = (user.get('nom') or '')[0].upper() if user.get('nom') else ''
    return p + n


# ─────────────────────────── PROFIL (compat.) ────────────────────────────────

def get_profil() -> dict:
    return get_current_user()

def save_profil(data: dict):
    uid = get_current_user_id()
    if uid:
        save_user(uid, data)

def calc_imc(poids, taille_cm):
    if taille_cm <= 0 or poids <= 0:
        return 0.0
    t = taille_cm / 100
    return round(poids / (t * t), 1)

def calc_calories_cible(profil):
    try:
        poids    = float(profil.get('poids', 70) or 70)
        taille   = float(profil.get('taille', 170) or 170)
        age      = int(profil.get('age', 30) or 30)
        sexe     = profil.get('sexe', 'H')
        activite = profil.get('activite', 'sedentaire')
        objectif = profil.get('objectif', 'maintien')
        if sexe == 'H':
            bmr = 10 * poids + 6.25 * taille - 5 * age + 5
        else:
            bmr = 10 * poids + 6.25 * taille - 5 * age - 161
        facteurs = {'sedentaire':1.2,'leger':1.375,'modere':1.55,'actif':1.725,'tres_actif':1.9}
        tdee = bmr * facteurs.get(activite, 1.2)
        if objectif == 'perte_poids':   return int(tdee - 500)
        elif objectif == 'prise_masse': return int(tdee + 300)
        else:                           return int(tdee)
    except Exception:
        return 2000

def calc_macros_cibles(profil):
    cal   = calc_calories_cible(profil)
    coeff = float(profil.get('coefficient_proteines') or 0)
    poids = float(profil.get('poids') or 70)
    prot  = round(poids * coeff) if coeff >= 0.1 else round(cal * 0.30 / 4)
    return {
        'calories':  cal,
        'proteines': prot,
        'glucides':  round(cal * 0.40 / 4),
        'lipides':   round(cal * 0.30 / 9),
    }


# ─────────────────────────── SUIVI POIDS ─────────────────────────────────────

def add_suivi_poids(poids: float, tour_de_taille: float = 0.0, notes: str = ""):
    uid = get_current_user_id()
    if not uid:
        return
    conn = get_connection()
    conn.execute("""INSERT INTO suivi_poids (user_id, date, poids, tour_de_taille, notes)
                    VALUES (?, ?, ?, ?, ?)""",
                 (uid, date.today().isoformat(), poids, tour_de_taille, notes))
    conn.commit()
    conn.close()

def get_suivi_poids(limit: int = 90, frequence: str = "tous") -> list:
    uid = get_current_user_id()
    if not uid:
        return []
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM suivi_poids WHERE user_id=? ORDER BY date ASC LIMIT ?",
        (uid, limit)).fetchall()
    conn.close()
    data = [dict(r) for r in rows]

    if frequence == "tous" or not data:
        return data

    from collections import defaultdict
    buckets: dict = defaultdict(list)
    for row in data:
        try:
            d = datetime.strptime(row['date'][:10], "%Y-%m-%d")
        except (ValueError, TypeError, KeyError):
            d = datetime.now()
        if frequence == "hebdo":
            key = f"{d.year}-S{d.isocalendar()[1]:02d}"
        elif frequence == "quinzaine":
            half = 1 if d.day <= 15 else 2
            key = f"{d.year}-{d.month:02d}-Q{half}"
        else:
            key = f"{d.year}-{d.month:02d}"
        buckets[key].append(row)

    result = []
    for key in sorted(buckets.keys()):
        group = buckets[key]
        avg_p = round(sum(r['poids'] for r in group) / len(group), 1)
        avg_t = round(sum((r.get('tour_de_taille') or 0) for r in group) / len(group), 1)
        result.append({**group[-1], 'poids': avg_p, 'tour_de_taille': avg_t, 'date': key})
    return result

def delete_suivi_poids(sid: int):
    conn = get_connection()
    conn.execute("DELETE FROM suivi_poids WHERE id=?", (sid,))
    conn.commit()
    conn.close()


# ─────────────────────────── ALIMENTS ───────────────────────────

def get_aliments(search="", categorie=""):
    conn = get_connection()
    q, params = "SELECT * FROM aliments WHERE 1=1", []
    if search:
        q += " AND nom LIKE ?"
        params.append(f"%{search}%")
    if categorie and categorie not in ("Toutes", ""):
        q += " AND categorie=?"
        params.append(categorie)
    q += " ORDER BY categorie, nom"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_aliment_by_id(aid):
    conn = get_connection()
    row = conn.execute("SELECT * FROM aliments WHERE id=?", (aid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_aliment(data):
    conn = get_connection()
    conn.execute("""INSERT INTO aliments
        (nom,categorie,calories,proteines,glucides,sucres,lipides,acides_gras_satures,
         fibres,sel,cholesterol,ig,unite,poids_unite_g,allergenes,notes)
        VALUES (:nom,:categorie,:calories,:proteines,:glucides,:sucres,:lipides,
                :acides_gras_satures,:fibres,:sel,:cholesterol,:ig,:unite,
                :poids_unite_g,:allergenes,:notes)""",
        {**_alim_defaults(data)})
    conn.commit()
    conn.close()


def update_aliment(aid, data):
    conn = get_connection()
    d = _alim_defaults(data)
    conn.execute("""UPDATE aliments SET
        nom=:nom, categorie=:categorie, calories=:calories,
        proteines=:proteines, glucides=:glucides, sucres=:sucres,
        lipides=:lipides, acides_gras_satures=:acides_gras_satures,
        fibres=:fibres, sel=:sel, cholesterol=:cholesterol,
        ig=:ig, unite=:unite, poids_unite_g=:poids_unite_g,
        allergenes=:allergenes, notes=:notes WHERE id=:id""",
        {**d, 'id': aid})
    conn.commit()
    conn.close()


def _alim_defaults(data: dict) -> dict:
    """Garantit que tous les champs numériques sont présents."""
    d = dict(data)
    for k in ('calories','proteines','glucides','sucres','lipides',
              'acides_gras_satures','fibres','sel','cholesterol','poids_unite_g'):
        try:
            d[k] = float(str(d.get(k) or 0).replace(',', '.'))
        except (ValueError, TypeError):
            d[k] = 0.0
    try:
        d['ig'] = int(float(str(d.get('ig') or 0).replace(',', '.')))
    except (ValueError, TypeError):
        d['ig'] = 0
    d.setdefault('unite', 'g')
    d.setdefault('categorie', 'Autre')
    d.setdefault('allergenes', '')
    d.setdefault('notes', '')
    return d


def delete_aliment(aid):
    conn = get_connection()
    conn.execute("DELETE FROM aliments WHERE id=?", (aid,))
    conn.commit()
    conn.close()


def get_categories_aliments():
    """Retourne les catégories présentes en BDD (dynamique)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT categorie FROM aliments WHERE categorie IS NOT NULL ORDER BY categorie"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


# ─────────────────────────── NUTRI-SCORE ───────────────────────────

def calc_nutri_score(aliment: dict) -> tuple[str, str]:
    """
    Calcule un Nutri-Score simplifié (A→E) avec sa couleur.
    Basé sur la méthode officielle FSA adaptée.
    """
    cal    = float(aliment.get('calories', 0) or 0)
    lip    = float(aliment.get('lipides',  0) or 0)
    gluc   = float(aliment.get('glucides', 0) or 0)
    fibres = float(aliment.get('fibres',   0) or 0)
    prot   = float(aliment.get('proteines',0) or 0)

    if cal == 0 and prot == 0:
        return '?', '#64748b'

    # Points négatifs
    kj = cal * 4.184
    n_energy  = min(10, int(kj / 335))
    n_fat     = min(10, int(lip / 4))
    n_sugars  = min(10, int(gluc / 9))    # proxy sucres totaux
    pts_neg   = n_energy + n_fat + n_sugars

    # Points positifs
    p_fibre   = min(5, int(fibres / 0.9))
    p_protein = min(5, int(prot   / 5.7))
    pts_pos   = p_fibre + p_protein

    score = pts_neg - pts_pos

    if score <= 0:   return 'A', '#22c55e'
    elif score <= 3: return 'B', '#84cc16'
    elif score <= 10:return 'C', '#eab308'
    elif score <= 18:return 'D', '#f97316'
    else:            return 'E', '#ef4444'


def nutri_score_label(aliment: dict) -> tuple[str, str, str]:
    """Retourne (lettre, couleur, conseil) pour l'affichage."""
    score, color = calc_nutri_score(aliment)
    conseils = {
        'A': "Excellent choix nutritionnel",
        'B': "Bon choix nutritionnel",
        'C': "Qualité nutritionnelle correcte",
        'D': "À consommer avec modération",
        'E': "À consommer occasionnellement",
        '?': "Données insuffisantes",
    }
    return score, color, conseils.get(score, '')


# ─────────────────────────── IMPORT CSV ───────────────────────────

def import_csv_aliments(filepath: str) -> dict:
    """
    Importe un fichier CSV d'aliments.
    Colonnes attendues (séparateur ; ou ,) :
      Aliment;Catégorie;Calories;Protéines;Glucides;Lipides;Fibres;IG;Unité;Poids_unité_g

    Retourne {'imported': N, 'skipped': N, 'errors': [...]}
    """
    import csv
    result = {'imported': 0, 'skipped': 0, 'errors': []}

    # Lire les noms existants pour détection doublons
    conn = get_connection()
    existing = {r[0].strip().lower()
                for r in conn.execute("SELECT nom FROM aliments").fetchall()}

    with open(filepath, newline='', encoding='utf-8-sig') as f:
        # Détecter le séparateur
        sample = f.read(2048); f.seek(0)
        sep = ';' if sample.count(';') >= sample.count(',') else ','
        reader = csv.DictReader(f, delimiter=sep)

        # Normaliser les noms de colonnes (minuscules, sans accents)
        def _norm(s):
            s = s.strip().lower()
            replacements = {'é':'e','è':'e','ê':'e','à':'a','â':'a',
                            'ô':'o','î':'i','û':'u','ç':'c','ù':'u'}
            for k,v in replacements.items():
                s = s.replace(k, v)
            return s

        COL_MAP = {
            'aliment': 'nom', 'nom': 'nom',
            'categorie': 'categorie', 'catégorie': 'categorie',
            'calories': 'calories', 'energie': 'calories',
            'proteines': 'proteines', 'protéines': 'proteines', 'proteins': 'proteines',
            'glucides': 'glucides', 'carbohydrates': 'glucides',
            'lipides': 'lipides', 'matieres grasses': 'lipides', 'fat': 'lipides',
            'fibres': 'fibres', 'fibres alimentaires': 'fibres', 'fiber': 'fibres',
            'ig': 'ig', 'index glycemique': 'ig',
            'unite': 'unite', 'unité': 'unite', 'unit': 'unite',
            'poids unite g': 'poids_unite_g', 'poids_unite_g': 'poids_unite_g',
            'notes': 'notes',
        }

        for i, row in enumerate(reader, start=2):
            try:
                # Mapper les colonnes
                data = {}
                for raw_key, val in row.items():
                    mapped = COL_MAP.get(_norm(raw_key or ''))
                    if mapped:
                        data[mapped] = val.strip() if val else ''

                nom = data.get('nom', '').strip()
                if not nom:
                    result['errors'].append(f"Ligne {i} : nom manquant")
                    continue

                if nom.lower() in existing:
                    result['skipped'] += 1
                    continue

                # Valeurs numériques
                for key in ('calories','proteines','glucides','lipides','fibres','poids_unite_g'):
                    try:
                        data[key] = float(str(data.get(key, 0)).replace(',', '.') or 0)
                    except (ValueError, TypeError):
                        data[key] = 0.0
                try:
                    data['ig'] = int(float(str(data.get('ig', 0)).replace(',', '.') or 0))
                except (ValueError, TypeError):
                    data['ig'] = 0

                data.setdefault('categorie', 'Autre')
                data.setdefault('unite', 'g')
                data.setdefault('notes', '')

                conn.execute("""INSERT INTO aliments
                    (nom,categorie,calories,proteines,glucides,lipides,fibres,ig,unite,poids_unite_g,notes)
                    VALUES (:nom,:categorie,:calories,:proteines,:glucides,:lipides,
                            :fibres,:ig,:unite,:poids_unite_g,:notes)""", data)
                existing.add(nom.lower())
                result['imported'] += 1

            except Exception as e:
                result['errors'].append(f"Ligne {i} : {e}")

    conn.commit()
    conn.close()
    return result


def export_csv_aliments(filepath: str):
    """Exporte tous les aliments en CSV."""
    import csv
    aliments = get_aliments()
    fields = ['nom','categorie','calories','proteines','glucides','lipides',
              'fibres','ig','unite','poids_unite_g','notes']
    headers = ['Aliment','Catégorie','Calories','Protéines','Glucides','Lipides',
               'Fibres','IG','Unité','Poids_unité_g','Notes']
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(headers)
        for a in aliments:
            w.writerow([a.get(k, '') for k in fields])


# ─────────────────────────── RECETTES ───────────────────────────

# Unités culinaires et leur équivalent en grammes
UNITS_CONVERSION = {
    'g':       1.0,
    'kg':      1000.0,
    'ml':      1.0,
    'cl':      10.0,
    'L':       1000.0,
    'CAS':     15.0,    # cuillère à soupe
    'CAC':     5.0,     # cuillère à café
    'pincée':  0.5,
    'verre':   200.0,
    'tasse':   250.0,
    'bol':     350.0,
    'tranche': None,    # utilise poids_unite_g
    'unité':   None,    # utilise poids_unite_g
    'gousse':  None,    # utilise poids_unite_g
    'filet':   5.0,
}

UNITS_CULINAIRES = list(UNITS_CONVERSION.keys())

# Coefficients de cuisson typiques (ratio poids cuit / poids cru)
COEFFICIENTS_CUISSON = {
    'cru':              1.0,
    'vapeur':           0.88,
    'poêle':            0.78,
    'four':             0.72,
    'eau (bouilli)':    0.85,
    'pâtes cuites':     2.50,   # les pâtes absorbent l'eau
    'riz cuit':         2.50,
    'légumineuses cuites': 2.20,
    'grillé':           0.70,
    'friture':          0.85,
    'mariné':           1.05,
}

TYPES_CUISSON = ["Aucune (cru)", "Vapeur", "Four", "Poêle / sauté",
                 "Eau bouillante", "Mijotage", "Grill / BBQ", "Friture",
                 "Micro-ondes", "Autre"]

TAGS_REGIME = ["Végétarien", "Vegan", "Sans gluten", "Sans lactose",
               "Sans œuf", "Halal", "Kasher", "Low-carb", "Keto",
               "Riche en protéines", "Faible en calories"]

ALLERGENES_LISTE = ["Gluten", "Crustacés", "Œufs", "Poissons", "Arachides",
                    "Soja", "Lait", "Fruits à coque", "Céleri", "Moutarde",
                    "Sésame", "Anhydride sulfureux", "Lupin", "Mollusques"]


def quantite_en_grammes(quantite: float, unite: str, aliment: dict) -> float:
    """Convertit une quantité dans son unité vers les grammes."""
    coeff = UNITS_CONVERSION.get(unite)
    if coeff is not None:
        return quantite * coeff
    # unité / tranche → utilise poids_unite_g
    poids = float(aliment.get('poids_unite_g') or 0)
    if poids > 0:
        return quantite * poids
    return quantite  # fallback: assume g


_recette_nutrition_cache: dict[int, dict] = {}


def invalidate_recette_cache(recette_id: int | None = None):
    if recette_id is None:
        _recette_nutrition_cache.clear()
    else:
        _recette_nutrition_cache.pop(recette_id, None)


def calc_recette_nutrition(recette_id: int) -> dict:
    """
    Calcule les apports nutritionnels de la recette en tenant compte
    des unités culinaires et des coefficients de cuisson.
    Résultat mis en cache ; invalider via invalidate_recette_cache().
    """
    if recette_id in _recette_nutrition_cache:
        return _recette_nutrition_cache[recette_id]
    ings    = get_recette_ingredients(recette_id)
    recette = get_recette_by_id(recette_id)
    portions = max(1, recette.get('portions', 1) or 1)

    keys = ['calories', 'proteines', 'glucides', 'sucres',
            'lipides', 'acides_gras_satures', 'fibres', 'sel']
    tot = {k: 0.0 for k in keys}

    for ing in ings:
        alim   = get_aliment_by_id(ing['aliment_id']) or {}
        unite  = ing.get('unite_recette') or 'g'
        coeff  = float(ing.get('coefficient_cuisson') or 1.0)
        qte_g  = quantite_en_grammes(ing['quantite'], unite, alim)
        # Poids réel après cuisson ; les calories sont basées sur le poids cru
        # qte_g est en cru si coeff < 1 (viande), ou cuit si coeff > 1 (pâtes)
        # On ramène toujours à l'équivalent cru pour lire les tables de nutri
        qte_crue = qte_g / coeff if coeff != 0 else qte_g
        ratio = qte_crue / 100.0
        for k in keys:
            tot[k] += float(alim.get(k) or 0) * ratio

    total   = {k: round(v, 1) for k, v in tot.items()}
    par_p   = {k: round(v / portions, 1) for k, v in tot.items()}
    poids_total = sum(
        quantite_en_grammes(i['quantite'], i.get('unite_recette','g'),
                            get_aliment_by_id(i['aliment_id']) or {})
        * float(i.get('coefficient_cuisson') or 1.0)
        for i in ings
    )
    result = {
        'total':       total,
        'par_portion': par_p,
        'poids_total_g': round(poids_total, 0),
        'poids_par_portion_g': round(poids_total / portions, 0),
    }
    _recette_nutrition_cache[recette_id] = result
    return result


def get_recettes(search="", favori_only=False):
    conn = get_connection()
    q, params = "SELECT * FROM recettes WHERE 1=1", []
    if favori_only:
        q += " AND favori=1"
    if search:
        q += " AND (nom LIKE ? OR description LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    q += " ORDER BY favori DESC, categorie, nom"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def toggle_recette_favori(rid: int):
    conn = get_connection()
    conn.execute("UPDATE recettes SET favori = 1 - COALESCE(favori,0) WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    invalidate_recette_cache(rid)


def get_recette_by_id(rid):
    conn = get_connection()
    row = conn.execute("SELECT * FROM recettes WHERE id=?", (rid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_recette_ingredients(recette_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT ri.*, a.nom, a.calories, a.proteines, a.glucides, a.sucres,
               a.lipides, a.acides_gras_satures, a.fibres, a.sel,
               a.unite, a.poids_unite_g
        FROM recette_ingredients ri
        JOIN aliments a ON ri.aliment_id = a.id
        WHERE ri.recette_id=?
        ORDER BY ri.ordre, ri.id
    """, (recette_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recette_etapes(recette_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM recette_etapes WHERE recette_id=? ORDER BY ordre",
        (recette_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_recette(data: dict, ingredients: list, etapes: list) -> int:
    conn = get_connection()
    cur = conn.execute("""INSERT INTO recettes
        (nom,description,categorie,temps_prep,temps_cuisson,portions,
         difficulte,cout,type_cuisson,temperature,tags_regime,allergenes,
         conservation,astuce,notes)
        VALUES (:nom,:description,:categorie,:temps_prep,:temps_cuisson,:portions,
                :difficulte,:cout,:type_cuisson,:temperature,:tags_regime,:allergenes,
                :conservation,:astuce,:notes)""", _recette_defaults(data))
    rid = cur.lastrowid
    _save_ingredients(conn, rid, ingredients)
    _save_etapes(conn, rid, etapes)
    conn.commit()
    conn.close()
    return rid


def update_recette(rid: int, data: dict, ingredients: list, etapes: list):
    conn = get_connection()
    conn.execute("""UPDATE recettes SET
        nom=:nom, description=:description, categorie=:categorie,
        temps_prep=:temps_prep, temps_cuisson=:temps_cuisson, portions=:portions,
        difficulte=:difficulte, cout=:cout, type_cuisson=:type_cuisson,
        temperature=:temperature, tags_regime=:tags_regime, allergenes=:allergenes,
        conservation=:conservation, astuce=:astuce, notes=:notes WHERE id=:id""",
        {**_recette_defaults(data), 'id': rid})
    conn.execute("DELETE FROM recette_ingredients WHERE recette_id=?", (rid,))
    conn.execute("DELETE FROM recette_etapes WHERE recette_id=?", (rid,))
    _save_ingredients(conn, rid, ingredients)
    _save_etapes(conn, rid, etapes)
    conn.commit()
    conn.close()
    invalidate_recette_cache(rid)


def delete_recette(rid):
    conn = get_connection()
    conn.execute("DELETE FROM recette_ingredients WHERE recette_id=?", (rid,))
    conn.execute("DELETE FROM recette_etapes WHERE recette_id=?", (rid,))
    conn.execute("DELETE FROM recettes WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    invalidate_recette_cache(rid)


def _recette_defaults(data: dict) -> dict:
    d = dict(data)
    for k in ('temps_prep', 'temps_cuisson', 'portions', 'temperature'):
        try:
            d[k] = int(d.get(k) or 0)
        except (ValueError, TypeError):
            d[k] = 0
    d.setdefault('description', '')
    d.setdefault('categorie', 'Plat principal')
    d.setdefault('difficulte', 'Facile')
    d.setdefault('cout', '€')
    d.setdefault('type_cuisson', '')
    d.setdefault('tags_regime', '')
    d.setdefault('allergenes', '')
    d.setdefault('conservation', '')
    d.setdefault('astuce', '')
    d.setdefault('notes', '')
    return d


def _save_ingredients(conn, rid, ingredients):
    for i, ing in enumerate(ingredients):
        conn.execute("""INSERT INTO recette_ingredients
            (recette_id,aliment_id,quantite,unite_recette,etat,
             coefficient_cuisson,notes_preparation,ordre)
            VALUES (?,?,?,?,?,?,?,?)""",
            (rid, ing['aliment_id'],
             float(ing.get('quantite', 100) or 100),
             ing.get('unite_recette', 'g') or 'g',
             ing.get('etat', 'cru') or 'cru',
             float(ing.get('coefficient_cuisson', 1.0) or 1.0),
             ing.get('notes_preparation', '') or '',
             i))


def _save_etapes(conn, rid, etapes):
    for i, etape in enumerate(etapes, start=1):
        conn.execute("""INSERT INTO recette_etapes
            (recette_id,ordre,titre,description,duree_min,temperature,type_action)
            VALUES (?,?,?,?,?,?,?)""",
            (rid, i,
             etape.get('titre', '') or '',
             etape.get('description', '') or '',
             int(etape.get('duree_min', 0) or 0),
             int(etape.get('temperature', 0) or 0),
             etape.get('type_action', '') or ''))


# ─────────────────────────── STOCK ───────────────────────────────────────────

def get_stock() -> list:
    """Retourne tout le stock de l'utilisateur courant avec nom et catégorie."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.*, a.nom, a.categorie, a.unite as unite_aliment
        FROM stock s
        JOIN aliments a ON s.aliment_id = a.id
        WHERE s.user_id = ?
        ORDER BY a.categorie, a.nom
    """, (_current_user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_stock(aliment_id: int, quantite: float,
                 unite: str = 'g', date_peremption: str = None,
                 notes: str = '') -> None:
    """Insert ou update l'entrée stock de l'utilisateur courant pour cet aliment."""
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM stock WHERE user_id=? AND aliment_id=?",
        (_current_user_id, aliment_id)
    ).fetchone()
    now = datetime.now().isoformat()
    if existing:
        conn.execute("""UPDATE stock SET quantite=?, unite=?, date_peremption=?,
                        notes=?, updated_at=? WHERE id=?""",
                     (quantite, unite, date_peremption, notes, now, existing[0]))
    else:
        conn.execute("""INSERT INTO stock
            (user_id, aliment_id, quantite, unite, date_peremption, notes, updated_at)
            VALUES (?,?,?,?,?,?,?)""",
                     (_current_user_id, aliment_id, quantite, unite,
                      date_peremption, notes, now))
    conn.commit()
    conn.close()


def delete_stock(stock_id: int) -> None:
    """Supprime une entrée du stock de l'utilisateur courant."""
    conn = get_connection()
    conn.execute("DELETE FROM stock WHERE id=? AND user_id=?",
                 (stock_id, _current_user_id))
    conn.commit()
    conn.close()


def add_to_stock_from_aliment(aliment_id: int, quantite: float,
                               unite: str = None) -> None:
    """
    Ajoute (additionne) une quantité au stock. Smart defaults sur nouvel item.
    Incrémente nb_utilisations.
    """
    alim = get_aliment_by_id(aliment_id) or {}
    if unite is None:
        u = alim.get('unite', 'g')
        unite = u if u in ('g', 'ml', 'kg', 'L', 'unité') else 'g'
    conn = get_connection()
    existing = conn.execute(
        "SELECT id, quantite FROM stock WHERE user_id=? AND aliment_id=?",
        (_current_user_id, aliment_id)
    ).fetchone()
    now = datetime.now().isoformat()
    if existing:
        conn.execute("""UPDATE stock SET quantite=quantite+?, nb_utilisations=nb_utilisations+1,
                        updated_at=? WHERE id=?""",
                     (quantite, now, existing[0]))
    else:
        cat = alim.get('categorie', '').lower()
        if unite == 'unité':
            qmin = 1.0
        elif any(k in cat for k in ('epices', 'épices', 'herbes')):
            qmin = round(quantite * 0.10, 1)
        else:
            qmin = 0.0
        conn.execute("""INSERT INTO stock
            (user_id, aliment_id, quantite, unite, quantite_min, nb_utilisations, updated_at)
            VALUES (?,?,?,?,?,1,?)""",
                     (_current_user_id, aliment_id, quantite, unite, qmin, now))
    conn.commit()
    conn.close()


def deduct_stock(ingredients: list) -> list:
    """
    Déduit du stock courant une liste [{aliment_id, quantite_g}].
    Plancher à 0 ; supprime les entrées à 0.
    Retourne la liste des items passés sous quantite_min :
    [{nom, quantite, quantite_min, unite}]
    """
    sous_seuil = []
    conn = get_connection()
    for ing in ingredients:
        aid = ing['aliment_id']
        qte_deduire_g = float(ing.get('quantite_g', 0))
        row = conn.execute(
            "SELECT * FROM stock WHERE user_id=? AND aliment_id=?",
            (_current_user_id, aid)
        ).fetchone()
        if not row:
            continue
        alim = conn.execute("SELECT * FROM aliments WHERE id=?", (aid,)).fetchone()
        alim_dict = dict(alim) if alim else {}
        stock_g = quantite_en_grammes(row['quantite'], row['unite'], alim_dict)
        new_g = max(0.0, stock_g - qte_deduire_g)
        if new_g == 0:
            conn.execute("DELETE FROM stock WHERE id=?", (row['id'],))
        else:
            coeff = UNITS_CONVERSION.get(row['unite'])
            if coeff and coeff > 0:
                new_qty = new_g / coeff
            else:
                poids = float(alim_dict.get('poids_unite_g') or 0)
                new_qty = (new_g / poids) if poids > 0 else new_g
            new_qty = round(new_qty, 2)
            conn.execute("UPDATE stock SET quantite=?, updated_at=? WHERE id=?",
                         (new_qty, datetime.now().isoformat(), row['id']))
            qmin = float(row['quantite_min'] or 0) if 'quantite_min' in row.keys() else 0.0
            if qmin > 0 and new_qty < qmin:
                sous_seuil.append({
                    'nom':          alim_dict.get('nom', '?'),
                    'quantite':     new_qty,
                    'quantite_min': qmin,
                    'unite':        row['unite'],
                })
    conn.commit()
    conn.close()
    return sous_seuil


def get_stock_sous_seuil() -> list:
    """Items où quantite < quantite_min (et quantite_min > 0)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.*, a.nom, a.categorie
        FROM stock s JOIN aliments a ON s.aliment_id = a.id
        WHERE s.user_id=? AND s.quantite_min > 0 AND s.quantite < s.quantite_min
        ORDER BY (s.quantite_min - s.quantite) DESC
    """, (_current_user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_staples_a_reapprovisionner() -> list:
    """Staples dont la quantite < quantite_cible."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.*, a.nom, a.categorie
        FROM stock s JOIN aliments a ON s.aliment_id = a.id
        WHERE s.user_id=? AND s.est_staple=1 AND s.quantite_cible > 0
          AND s.quantite < s.quantite_cible
        ORDER BY a.categorie, a.nom
    """, (_current_user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_liste_courses_stock(nb_jours: int = 7) -> dict:
    """
    Retourne {staples, recettes, suggestions} pour la liste de courses.
    - staples  : [{nom, manque, quantite_cible, unite}]
    - recettes : [{nom, manque_g, nom_recette, date_repas}]
    - suggestions : [{nom, nb_utilisations, aliment_id}]
    """
    end_date = (date.today() + timedelta(days=nb_jours)).isoformat()
    today_str = date.today().isoformat()

    staples_raw = get_staples_a_reapprovisionner()
    staples = [{'nom': s['nom'],
                'manque': round(s['quantite_cible'] - s['quantite'], 1),
                'quantite_cible': s['quantite_cible'],
                'unite': s['unite']}
               for s in staples_raw]

    conn = get_connection()
    planning = conn.execute("""
        SELECT pr.recette_id, pr.date, r.nom as recette_nom, pr.portions
        FROM planning_repas pr
        JOIN recettes r ON pr.recette_id = r.id
        WHERE pr.user_id=? AND pr.date >= ? AND pr.date <= ?
          AND pr.recette_id IS NOT NULL
        ORDER BY pr.date
    """, (_current_user_id, today_str, end_date)).fetchall()
    conn.close()

    recettes = []
    seen = set()
    for repas in planning:
        result = check_recette_faisable(repas['recette_id'])
        for m in result['manquants']:
            key = (m['nom'], repas['recette_id'])
            if key not in seen:
                seen.add(key)
                recettes.append({
                    'nom':         m['nom'],
                    'manque_g':    round(m['qte_requise'] - m['qte_stock'], 0),
                    'nom_recette': repas['recette_nom'],
                    'date_repas':  repas['date'],
                })

    conn = get_connection()
    sugg_rows = conn.execute("""
        SELECT s.aliment_id, a.nom, s.nb_utilisations
        FROM stock s JOIN aliments a ON s.aliment_id = a.id
        WHERE s.user_id=? AND s.est_staple=0 AND s.nb_utilisations >= 3
        ORDER BY s.nb_utilisations DESC
        LIMIT 5
    """, (_current_user_id,)).fetchall()
    conn.close()

    return {'staples': staples, 'recettes': recettes,
            'suggestions': [dict(r) for r in sugg_rows]}


def get_stock_eau_aliment_id() -> int | None:
    """Retourne l'aliment_id de l'item stock marqué est_eau=1, ou None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT aliment_id FROM stock WHERE user_id=? AND est_eau=1 LIMIT 1",
        (_current_user_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def set_stock_eau(stock_id: int) -> None:
    """Marque cet item comme source d'eau, remet à 0 les autres."""
    conn = get_connection()
    conn.execute("UPDATE stock SET est_eau=0 WHERE user_id=?", (_current_user_id,))
    conn.execute("UPDATE stock SET est_eau=1 WHERE id=? AND user_id=?",
                 (stock_id, _current_user_id))
    conn.commit()
    conn.close()


def increment_stock_usage(aliment_id: int) -> None:
    """Incrémente nb_utilisations pour l'aliment dans le stock du user courant."""
    conn = get_connection()
    conn.execute("""UPDATE stock SET nb_utilisations=nb_utilisations+1
                    WHERE user_id=? AND aliment_id=?""",
                 (_current_user_id, aliment_id))
    conn.commit()
    conn.close()


def get_stock_alerts(jours: int = 3) -> list:
    """Items périmés ou expirant dans <= jours jours pour l'utilisateur courant."""
    cutoff = (date.today() + timedelta(days=jours)).isoformat()
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.*, a.nom, a.categorie
        FROM stock s
        JOIN aliments a ON s.aliment_id = a.id
        WHERE s.user_id = ?
          AND s.date_peremption IS NOT NULL
          AND s.date_peremption != ''
          AND s.date_peremption <= ?
        ORDER BY s.date_peremption
    """, (_current_user_id, cutoff)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def check_recette_faisable(recette_id: int) -> dict:
    """
    Retourne {faisable: bool, manquants: [{nom, qte_requise, qte_stock, unite}]}
    Ignore les ingrédients non comparables (poids_unite_g=0 pour unité).
    """
    ings = get_recette_ingredients(recette_id)
    if not ings:
        return {'faisable': True, 'manquants': []}

    conn = get_connection()
    stock_rows = conn.execute(
        "SELECT aliment_id, quantite, unite FROM stock WHERE user_id=?",
        (_current_user_id,)
    ).fetchall()
    conn.close()
    stock_by_alim = {r['aliment_id']: dict(r) for r in stock_rows}

    manquants = []
    for ing in ings:
        alim_id = ing['aliment_id']
        alim = get_aliment_by_id(alim_id) or {}
        qte_requise_g = quantite_en_grammes(
            ing['quantite'], ing.get('unite_recette', 'g'), alim)

        if alim_id in stock_by_alim:
            s = stock_by_alim[alim_id]
            coeff = UNITS_CONVERSION.get(s['unite'])
            if coeff is not None:
                stock_g = s['quantite'] * coeff
            else:
                poids = float(alim.get('poids_unite_g') or 0)
                if poids == 0:
                    continue  # unité incomparable → ignorée
                stock_g = s['quantite'] * poids

            if stock_g < qte_requise_g - 0.5:  # tolérance 0.5g
                manquants.append({
                    'nom':         ing.get('nom', alim.get('nom', '?')),
                    'qte_requise': round(qte_requise_g, 0),
                    'qte_stock':   round(stock_g, 0),
                    'unite':       'g',
                })
        else:
            manquants.append({
                'nom':         ing.get('nom', alim.get('nom', '?')),
                'qte_requise': round(qte_requise_g, 0),
                'qte_stock':   0,
                'unite':       'g',
            })

    return {'faisable': len(manquants) == 0, 'manquants': manquants}


# ─────────────────────────── PROGRAMMES ───────────────────────────

def get_programmes():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM programmes WHERE user_id=? ORDER BY actif DESC, nom",
        (_current_user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_programme_actif():
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM programmes WHERE user_id=? AND actif=1",
        (_current_user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_programme(data):
    conn = get_connection()
    conn.execute("""INSERT INTO programmes
        (user_id,nom,objectif,duree_semaines,calories_jour,
         proteines_pct,glucides_pct,lipides_pct,description)
        VALUES (:user_id,:nom,:objectif,:duree_semaines,:calories_jour,
                :proteines_pct,:glucides_pct,:lipides_pct,:description)""",
        {**data, 'user_id': _current_user_id})
    conn.commit()
    conn.close()


def update_programme(pid, data):
    conn = get_connection()
    conn.execute("""UPDATE programmes SET
        nom=:nom, objectif=:objectif, duree_semaines=:duree_semaines,
        calories_jour=:calories_jour, proteines_pct=:proteines_pct,
        glucides_pct=:glucides_pct, lipides_pct=:lipides_pct,
        description=:description WHERE id=:id""",
        {**data, 'id': pid})
    conn.commit()
    conn.close()


def delete_programme(pid):
    conn = get_connection()
    conn.execute("DELETE FROM programmes WHERE id=?", (pid,))
    conn.commit()
    conn.close()


def set_programme_actif(pid):
    conn = get_connection()
    conn.execute("UPDATE programmes SET actif=0 WHERE user_id=?", (_current_user_id,))
    conn.execute("UPDATE programmes SET actif=1 WHERE id=? AND user_id=?", (pid, _current_user_id))
    conn.commit()
    conn.close()


# ─────────────────────────── SPORT & ACTIVITÉ ────────────────────────

# Formule : calories = MET × poids_kg × (duree_min / 60)
_MET_SPORT = {
    'tapis_marche': lambda v, i: (
        2.0 if v < 2.5 else
        2.5 if v < 3.0 else
        2.8 if v < 3.5 else
        3.2 if v < 4.0 else
        3.8 if v < 4.5 else
        4.3 if v < 5.0 else
        5.0 if v < 6.0 else 6.0
    ),
    'velo_appart': lambda v, i: {'leger': 4.0, 'modere': 6.0, 'intense': 8.5}.get(i, 4.0),
    'rameur':      lambda v, i: {'leger': 4.5, 'modere': 7.0, 'intense': 9.0}.get(i, 4.5),
    'vae':         lambda v, i: 3.5,
    'marche_ext':  lambda v, i: {'leger': 2.8, 'modere': 3.5, 'intense': 4.5}.get(i, 2.8),
}

ACTIVITES_SPORT = {
    'tapis_marche': {'label': 'Tapis de marche',   'icon': '🏃', 'param': 'vitesse'},
    'velo_appart':  {'label': 'Vélo appartement',  'icon': '🚴', 'param': 'intensite'},
    'rameur':       {'label': 'Rameur',             'icon': '🚣', 'param': 'intensite'},
    'vae':          {'label': 'VAE',                'icon': '⚡', 'param': 'none'},
    'marche_ext':   {'label': 'Marche extérieure',  'icon': '🚶', 'param': 'intensite'},
}

INTENSITES_LABELS = {'leger': 'Léger', 'modere': 'Modéré', 'intense': 'Intense'}


def get_fc_max() -> int:
    """FC max du profil si renseignée, sinon 220 − âge."""
    user = get_current_user()
    if not user:
        return 160
    fc = int(user.get('fc_max') or 0)
    if fc > 0:
        return fc
    return max(100, 220 - int(user.get('age') or 40))


def get_zones_cardiaques(fc_max: int) -> list:
    """5 zones cardiaques en bpm. color_key = clé dans T[]."""
    zones_def = [
        (1, 'Récupération',      0.50, 0.60, 'ac'),
        (2, 'Endurance de base', 0.60, 0.70, 'blue'),
        (3, 'Aérobie',           0.70, 0.80, 'lip'),
        (4, 'Seuil',             0.80, 0.90, 'cal'),
        (5, 'Maximum',           0.90, 1.00, 'err'),
    ]
    return [
        {
            'num':       num,
            'label':     label,
            'bpm_min':   int(fc_max * pmin),
            'bpm_max':   int(fc_max * pmax),
            'pct_min':   int(pmin * 100),
            'pct_max':   int(pmax * 100),
            'color_key': color_key,
        }
        for num, label, pmin, pmax, color_key in zones_def
    ]


def get_zone_for_fc(fc_obs: int, fc_max: int):
    """Zone correspondant à fc_obs, ou None si fc_obs == 0."""
    if not fc_obs or fc_obs <= 0:
        return None
    zones = get_zones_cardiaques(fc_max)
    for z in reversed(zones):
        if fc_obs >= z['bpm_min']:
            return z
    return zones[0]


def is_fc_alert(fc_obs: int, fc_max: int) -> bool:
    """True si fc_obs dépasse 85 % de fc_max."""
    return fc_obs > 0 and fc_obs > fc_max * 0.85


def calc_calories_sport(type_activite: str, duree_min: int,
                         vitesse_kmh: float = 0, intensite: str = 'leger',
                         poids_kg: float = 75) -> float:
    met_fn = _MET_SPORT.get(type_activite, lambda v, i: 3.0)
    met    = met_fn(vitesse_kmh, intensite.lower())
    return round(met * poids_kg * (duree_min / 60), 1)


def add_activite_sport(data: dict) -> int:
    conn = get_connection()
    cur  = conn.execute("""INSERT INTO activites_sport
        (user_id, date, heure, type_activite, duree_min,
         vitesse_kmh, intensite, calories_brulees, notes, fc_observee)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (_current_user_id,
         data.get('date', date.today().isoformat()),
         data.get('heure', ''),
         data['type_activite'],
         int(data.get('duree_min', 0)),
         float(data.get('vitesse_kmh', 0)),
         data.get('intensite', 'leger'),
         float(data.get('calories_brulees', 0)),
         data.get('notes', ''),
         int(data.get('fc_observee', 0))))
    conn.commit()
    conn.close()
    return cur.lastrowid


def get_activites_sport_jour(date_str: str) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM activites_sport WHERE user_id=? AND date=? ORDER BY heure, id",
        (_current_user_id, date_str)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_activite_sport(aid: int):
    conn = get_connection()
    conn.execute("DELETE FROM activites_sport WHERE id=? AND user_id=?",
                 (aid, _current_user_id))
    conn.commit()
    conn.close()


def get_calories_sport_jour(date_str: str) -> float:
    conn = get_connection()
    row  = conn.execute(
        "SELECT COALESCE(SUM(calories_brulees),0) FROM activites_sport WHERE user_id=? AND date=?",
        (_current_user_id, date_str)).fetchone()
    conn.close()
    return round(float(row[0]), 1)


def get_stats_sport_semaine() -> dict:
    from datetime import date as _date, timedelta
    today      = _date.today()
    week_start = today - timedelta(days=today.weekday())
    prev_start = week_start - timedelta(days=7)
    prev_end   = week_start - timedelta(days=1)

    conn = get_connection()

    def _sum(start, end):
        r = conn.execute("""SELECT
            COALESCE(SUM(calories_brulees),0) as calories,
            COALESCE(SUM(duree_min),0)        as minutes,
            COUNT(*)                           as seances
            FROM activites_sport
            WHERE user_id=? AND date>=? AND date<=?""",
            (_current_user_id, start.isoformat(), end.isoformat())).fetchone()
        return {'calories': round(float(r[0]), 1),
                'minutes':  int(r[1]),
                'seances':  int(r[2])}

    result = {
        'cette_semaine':    _sum(week_start, today),
        'semaine_precedente': _sum(prev_start, prev_end),
    }
    conn.close()
    return result


def get_progression_sport(nb_jours: int = 7) -> list:
    from datetime import date as _date, timedelta
    today  = _date.today()
    debut  = (today - timedelta(days=nb_jours - 1)).isoformat()
    conn   = get_connection()
    rows   = conn.execute("""SELECT date,
        COALESCE(SUM(calories_brulees),0) as calories,
        COALESCE(SUM(duree_min),0)        as minutes
        FROM activites_sport
        WHERE user_id=? AND date>=?
        GROUP BY date ORDER BY date""",
        (_current_user_id, debut)).fetchall()
    conn.close()
    # Compléter les jours manquants avec 0
    by_date = {r['date']: dict(r) for r in rows}
    result  = []
    for i in range(nb_jours):
        d = (today - timedelta(days=nb_jours - 1 - i)).isoformat()
        result.append(by_date.get(d, {'date': d, 'calories': 0.0, 'minutes': 0}))
    return result


# ─────────────────────────── PLANNING REPAS ───────────────────────────

TYPES_REPAS = [
    ("petit_dejeuner", "🌅 Petit-déjeuner", 0.25),
    ("collation_matin","☕ Collation matin", 0.10),
    ("dejeuner",       "☀️  Déjeuner",       0.35),
    ("collation_soir", "🍎 Collation soir",  0.10),
    ("diner",          "🌙 Dîner",           0.30),
]
TYPES_REPAS_KEYS   = [t[0] for t in TYPES_REPAS]
TYPES_REPAS_LABELS = {t[0]: t[1] for t in TYPES_REPAS}
TYPES_REPAS_PARTS  = {t[0]: t[2] for t in TYPES_REPAS}

# Catégories de recettes suggérées par type de repas
REPAS_CAT_HINTS = {
    "petit_dejeuner": ["Petit-déjeuner"],
    "collation_matin":["Collation","Dessert"],
    "dejeuner":       ["Déjeuner","Plat principal","Entrée","Soupe"],
    "collation_soir": ["Collation","Dessert","Boisson"],
    "diner":          ["Dîner","Plat principal","Soupe"],
}


def _create_planning_table():
    conn = get_connection()
    conn.execute("""CREATE TABLE IF NOT EXISTS planning_repas (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER NOT NULL,
        date            TEXT    NOT NULL,
        type_repas      TEXT    NOT NULL,
        recette_id      INTEGER,
        nom_custom      TEXT    DEFAULT '',
        calories_custom REAL    DEFAULT 0,
        proteines_custom REAL   DEFAULT 0,
        glucides_custom REAL    DEFAULT 0,
        lipides_custom  REAL    DEFAULT 0,
        fibres_custom   REAL    DEFAULT 0,
        portions        REAL    DEFAULT 1,
        notes           TEXT    DEFAULT ''
    )""")
    conn.commit()
    conn.close()


def get_planning_jour(jour: str) -> list:
    """Retourne tous les repas planifiés pour un jour (user courant)."""
    uid = get_current_user_id()
    if not uid:
        return []
    conn = get_connection()
    rows = conn.execute("""
        SELECT pr.*, r.nom as recette_nom, r.categorie as recette_cat
        FROM planning_repas pr
        LEFT JOIN recettes r ON pr.recette_id = r.id
        WHERE pr.user_id=? AND pr.date=?
        ORDER BY pr.type_repas
    """, (uid, jour)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_planning_semaine(lundi: str) -> dict:
    """Retourne le planning de la semaine (lundi = date ISO du lundi)."""
    from datetime import timedelta
    d = datetime.strptime(lundi, "%Y-%m-%d")
    result = {}
    for i in range(7):
        jour = (d + timedelta(days=i)).strftime("%Y-%m-%d")
        result[jour] = get_planning_jour(jour)
    return result


def get_nutri_jour(jour: str) -> dict:
    """Totaux nutritionnels consommés/planifiés pour un jour donné."""
    repas = get_planning_jour(jour)
    totaux = {'calories': 0.0, 'proteines': 0.0, 'glucides': 0.0,
              'lipides': 0.0, 'fibres': 0.0}
    for r in repas:
        for k in totaux:
            totaux[k] += float(r.get(f'{k}_custom') or 0)
    return {k: round(v, 1) for k, v in totaux.items()}


def add_planning_repas(jour: str, type_repas: str,
                        recette_id: int = None, portions: float = 1,
                        nom_custom: str = "", notes: str = "") -> int:
    uid = get_current_user_id()
    if not uid:
        return -1

    # Récupérer les valeurs nutritionnelles
    cal = prot = gluc = lip = fib = 0.0
    if recette_id:
        nutri = calc_recette_nutrition(recette_id)
        pp = nutri['par_portion']
        cal  = pp['calories']  * portions
        prot = pp['proteines'] * portions
        gluc = pp['glucides']  * portions
        lip  = pp['lipides']   * portions
        fib  = pp.get('fibres', 0) * portions

    conn = get_connection()
    cur = conn.execute("""INSERT INTO planning_repas
        (user_id, date, type_repas, recette_id, nom_custom,
         calories_custom, proteines_custom, glucides_custom,
         lipides_custom, fibres_custom, portions, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (uid, jour, type_repas, recette_id, nom_custom,
         cal, prot, gluc, lip, fib, portions, notes))
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid


def delete_planning_repas(pid: int):
    conn = get_connection()
    conn.execute("DELETE FROM planning_repas WHERE id=?", (pid,))
    conn.commit()
    conn.close()


def calc_planning_jour_nutrition(jour: str) -> dict:
    """Calcule les apports nutritionnels du jour planifié."""
    repas = get_planning_jour(jour)
    tot = {'calories': 0.0, 'proteines': 0.0, 'glucides': 0.0,
           'lipides': 0.0, 'fibres': 0.0}
    for r in repas:
        tot['calories']  += r.get('calories_custom') or 0
        tot['proteines'] += r.get('proteines_custom') or 0
        tot['glucides']  += r.get('glucides_custom') or 0
        tot['lipides']   += r.get('lipides_custom') or 0
        tot['fibres']    += r.get('fibres_custom') or 0
    return {k: round(v, 1) for k, v in tot.items()}


def generer_menu_jour(jour: str) -> list:
    """
    Génère automatiquement un menu pour la journée basé sur le programme actif.
    Retourne une liste de suggestions : [{type_repas, recette_id, recette_nom, calories}]
    """
    import random
    prog    = get_programme_actif()
    profil  = get_profil()
    cal_cible = (prog['calories_jour'] if prog
                 else calc_calories_cible(profil))

    recettes = get_recettes()
    if not recettes:
        return []

    suggestions = []
    cal_restantes = float(cal_cible)

    for type_rep, label, part in TYPES_REPAS:
        cible_type = cal_cible * part
        hints = REPAS_CAT_HINTS.get(type_rep, [])

        # Filtrer recettes par catégorie suggérée
        candidates = [r for r in recettes if r.get('categorie') in hints]
        if not candidates:
            candidates = recettes[:]

        # Trouver la meilleure correspondance
        best = None
        best_diff = float('inf')
        for rec in candidates:
            nutri = calc_recette_nutrition(rec['id'])
            cal_rec = nutri['par_portion']['calories']
            if cal_rec <= 0:
                continue
            # Nombre de portions optimal
            portions = max(0.5, round(cible_type / cal_rec, 1))
            portions = min(portions, 3.0)
            cal_effective = cal_rec * portions
            diff = abs(cal_effective - cible_type)
            if diff < best_diff:
                best_diff = diff
                best = (rec, portions, cal_effective)

        if best:
            rec, portions, cal_eff = best
            suggestions.append({
                'type_repas':   type_rep,
                'label':        label,
                'recette_id':   rec['id'],
                'recette_nom':  rec['nom'],
                'portions':     portions,
                'calories':     round(cal_eff, 0),
            })
            cal_restantes -= cal_eff

    return suggestions


def appliquer_menu_jour(jour: str, suggestions: list):
    """Applique les suggestions au planning du jour (supprime d'abord l'existant)."""
    uid = get_current_user_id()
    if not uid:
        return
    conn = get_connection()
    conn.execute("DELETE FROM planning_repas WHERE user_id=? AND date=?", (uid, jour))
    conn.commit()
    conn.close()
    for s in suggestions:
        add_planning_repas(jour, s['type_repas'],
                           recette_id=s['recette_id'],
                           portions=s['portions'])


# ─────────────────────────── STATS GLOBALES ───────────────────────────

def get_stats():
    conn = get_connection()
    return {
        'nb_aliments':   conn.execute("SELECT COUNT(*) FROM aliments").fetchone()[0],
        'nb_recettes':   conn.execute("SELECT COUNT(*) FROM recettes").fetchone()[0],
        'nb_programmes': conn.execute("SELECT COUNT(*) FROM programmes").fetchone()[0],
    }


# ─────────────────────────── HELPERS ───────────────────────────

OBJECTIFS_LABELS = {
    'perte_poids': '🔥 Perte de poids',
    'maintien':    '⚖️  Maintien',
    'prise_masse': '💪 Prise de masse',
}

ACTIVITE_LABELS = {
    'sedentaire': 'Sédentaire (peu/pas de sport)',
    'leger':      'Légèrement actif (1-3x/sem.)',
    'modere':     'Modérément actif (3-5x/sem.)',
    'actif':      'Très actif (6-7x/sem.)',
    'tres_actif': 'Extrêmement actif (2x/jour)',
}

IMC_CATEGORIES = [
    (18.5, "Insuffisance pondérale", "#3b82f6"),
    (25.0, "Poids normal",           "#22c55e"),
    (30.0, "Surpoids",               "#f59e0b"),
    (35.0, "Obésité modérée",        "#f97316"),
    (999,  "Obésité sévère",         "#ef4444"),
]


def imc_category(imc):
    for threshold, label, color in IMC_CATEGORIES:
        if imc < threshold:
            return label, color
    return "Obésité sévère", "#ef4444"


# ─────────────────────────── BACKUP ──────────────────────────────────────────

# ─────────────────────────── JOURNAL REPAS ───────────────────────────────────

def add_journal_entry(date_str: str, heure: str, nom: str,
                      quantite_g: float, aliment_id: int | None = None,
                      calories: float = 0, proteines: float = 0,
                      glucides: float = 0, lipides: float = 0,
                      fibres: float = 0, notes: str = "") -> int:
    uid = get_current_user_id()
    if not uid:
        return -1
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO journal_repas
           (user_id,date,heure,aliment_id,nom,quantite_g,
            calories,proteines,glucides,lipides,fibres,notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (uid, date_str, heure, aliment_id, nom, quantite_g,
         calories, proteines, glucides, lipides, fibres, notes))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def get_journal_jour(jour_str: str) -> list:
    uid = get_current_user_id()
    if not uid:
        return []
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM journal_repas WHERE user_id=? AND date=? ORDER BY heure,id",
        (uid, jour_str)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_journal_entry(eid: int):
    conn = get_connection()
    conn.execute("DELETE FROM journal_repas WHERE id=?", (eid,))
    conn.commit()
    conn.close()


def get_nutri_journal_jour(jour_str: str) -> dict:
    """Totaux nutritionnels du journal pour un jour donné."""
    entries = get_journal_jour(jour_str)
    totaux = {'calories': 0.0, 'proteines': 0.0,
              'glucides': 0.0, 'lipides': 0.0, 'fibres': 0.0}
    for e in entries:
        for k in totaux:
            totaux[k] += float(e.get(k) or 0)
    return {k: round(v, 1) for k, v in totaux.items()}


def get_journal_frequents(limit: int = 8) -> list:
    """
    Retourne les aliments récemment utilisés dans le journal (dédoublonnés par nom),
    triés par date de dernière utilisation.
    """
    uid = get_current_user_id()
    if not uid:
        return []
    conn = get_connection()
    rows = conn.execute("""
        SELECT nom, aliment_id,
               ROUND(AVG(quantite_g), 0) as quantite_g,
               ROUND(AVG(calories),   1) as calories,
               ROUND(AVG(proteines),  1) as proteines,
               ROUND(AVG(glucides),   1) as glucides,
               ROUND(AVG(lipides),    1) as lipides,
               ROUND(AVG(fibres),     1) as fibres,
               MAX(date) as last_date,
               COUNT(*)  as nb_fois
        FROM journal_repas
        WHERE user_id=?
        GROUP BY nom
        ORDER BY last_date DESC, nb_fois DESC
        LIMIT ?
    """, (uid, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_calories_14j() -> list[dict]:
    """Retourne les totaux calories du journal sur les 14 derniers jours."""
    uid = get_current_user_id()
    if not uid:
        return []
    conn = get_connection()
    rows = conn.execute(
        """SELECT date, SUM(calories) as calories
           FROM journal_repas
           WHERE user_id=?
           GROUP BY date
           ORDER BY date DESC LIMIT 14""",
        (uid,)).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_liste_courses(date_debut: str, date_fin: str) -> list[dict]:
    """
    Retourne la liste agrégée des ingrédients nécessaires pour tous les repas
    planifiés entre date_debut et date_fin (format ISO YYYY-MM-DD).
    Chaque entrée : {nom, total_g, unite, categorie}.
    """
    uid = get_current_user_id()
    if not uid:
        return []
    conn = get_connection()
    repas = conn.execute(
        """SELECT recette_id, portions FROM planning_repas
           WHERE user_id=? AND date BETWEEN ? AND ? AND recette_id IS NOT NULL""",
        (uid, date_debut, date_fin)).fetchall()
    conn.close()

    totaux: dict[int, float] = {}
    for row in repas:
        rid     = row['recette_id']
        portions = float(row['portions'] or 1)
        recette  = get_recette_by_id(rid)
        base_p   = max(1, int(recette.get('portions') or 1))
        factor   = portions / base_p
        for ing in get_recette_ingredients(rid):
            alim_id = ing['aliment_id']
            qte_g   = quantite_en_grammes(
                ing['quantite'], ing.get('unite_recette', 'g'),
                get_aliment_by_id(alim_id) or {})
            totaux[alim_id] = totaux.get(alim_id, 0.0) + qte_g * factor

    result = []
    for alim_id, total_g in sorted(totaux.items(), key=lambda x: -x[1]):
        alim = get_aliment_by_id(alim_id) or {}
        result.append({
            'nom':       alim.get('nom', f'Aliment #{alim_id}'),
            'total_g':   round(total_g, 0),
            'categorie': alim.get('categorie', ''),
        })
    return result


def export_backup(dest_path: str) -> bool:
    """Copie nutrition.db vers dest_path via l'API SQLite online backup (safe)."""
    try:
        src = get_connection()
        dst = sqlite3.connect(dest_path)
        src.backup(dst)
        dst.close()
        src.close()
        return True
    except Exception:
        return False


# ─────────────────────────── STATISTIQUES NUTRITIONNELLES ────────────────────

def get_stats_nutrition(days: int = 30) -> list:
    """Totaux journaliers du journal sur les N derniers jours."""
    uid = get_current_user_id()
    if not uid:
        return []
    from datetime import timedelta
    debut = (date.today() - timedelta(days=days - 1)).isoformat()
    conn = get_connection()
    rows = conn.execute("""
        SELECT date,
               SUM(calories)  as calories,
               SUM(proteines) as proteines,
               SUM(glucides)  as glucides,
               SUM(lipides)   as lipides,
               SUM(fibres)    as fibres
        FROM journal_repas
        WHERE user_id=? AND date >= ?
        GROUP BY date
        ORDER BY date ASC
    """, (uid, debut)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_adherence_stats(days: int = 30) -> dict:
    """
    Statistiques d'adhérence aux objectifs nutritionnels.
    Retourne: avg_cal, avg_prot, pct_cal_ok, pct_prot_ok,
              macro_dist, best_week, worst_week, week_avgs, cible_cal.
    """
    prog   = get_programme_actif()
    profil = get_current_user()
    cible_cal  = prog['calories_jour'] if prog else calc_calories_cible(profil)
    prot_pct   = prog.get('proteines_pct', 30) if prog else 30
    cible_prot = round(cible_cal * prot_pct / 100 / 4)

    data = get_stats_nutrition(days)
    if not data:
        return {'cible_cal': cible_cal, 'cible_prot': cible_prot, 'jours': 0,
                'avg_cal': 0, 'avg_prot': 0, 'avg_gluc': 0, 'avg_lip': 0,
                'pct_cal_ok': 0, 'pct_prot_ok': 0,
                'macro_dist': {'Protéines': 33, 'Glucides': 34, 'Lipides': 33},
                'best_week': '—', 'worst_week': '—', 'week_avgs': {}}

    n = len(data)
    avg_cal  = round(sum(float(r['calories']  or 0) for r in data) / n, 0)
    avg_prot = round(sum(float(r['proteines'] or 0) for r in data) / n, 1)
    avg_gluc = round(sum(float(r['glucides']  or 0) for r in data) / n, 1)
    avg_lip  = round(sum(float(r['lipides']   or 0) for r in data) / n, 1)

    tol_cal  = cible_cal * 0.10
    tol_prot = cible_prot * 0.10 if cible_prot > 0 else 5
    days_cal_ok  = sum(1 for r in data if abs(float(r['calories']  or 0) - cible_cal)  <= tol_cal)
    days_prot_ok = sum(1 for r in data if abs(float(r['proteines'] or 0) - cible_prot) <= tol_prot)

    total_kcal = (avg_prot * 4) + (avg_gluc * 4) + (avg_lip * 9)
    if total_kcal > 0:
        macro_dist = {
            'Protéines': round(avg_prot * 4 / total_kcal * 100, 1),
            'Glucides':  round(avg_gluc * 4 / total_kcal * 100, 1),
            'Lipides':   round(avg_lip  * 9 / total_kcal * 100, 1),
        }
    else:
        macro_dist = {'Protéines': 33, 'Glucides': 34, 'Lipides': 33}

    from collections import defaultdict
    semaines: dict = defaultdict(list)
    for r in data:
        try:
            d = datetime.strptime(r['date'][:10], "%Y-%m-%d")
            key = f"{d.year}-S{d.isocalendar()[1]:02d}"
        except Exception:
            key = "?"
        semaines[key].append(float(r['calories'] or 0))

    week_avgs = {k: round(sum(v) / len(v), 0) for k, v in semaines.items()}
    best_week  = min(week_avgs, key=lambda k: abs(week_avgs[k] - cible_cal)) if week_avgs else "—"
    worst_week = max(week_avgs, key=lambda k: abs(week_avgs[k] - cible_cal)) if week_avgs else "—"

    return {
        'jours':       n,
        'cible_cal':   cible_cal,
        'cible_prot':  cible_prot,
        'avg_cal':     avg_cal,
        'avg_prot':    avg_prot,
        'avg_gluc':    avg_gluc,
        'avg_lip':     avg_lip,
        'pct_cal_ok':  round(days_cal_ok  / n * 100),
        'pct_prot_ok': round(days_prot_ok / n * 100),
        'macro_dist':  macro_dist,
        'best_week':   best_week,
        'worst_week':  worst_week,
        'week_avgs':   week_avgs,
    }


# ─────────────────────────── RÉÉQUILIBRAGE PROGRESSIF ────────────────────────

def get_reequilibrage_data() -> dict:
    """
    Calcule la trajectoire projetée vs réelle semaine par semaine.
    Suggère un ajustement calorique si l'écart dépasse 0.5 kg.
    """
    prog   = get_programme_actif()
    profil = get_current_user()
    if not prog or not profil:
        return {}

    cal_cible  = int(prog['calories_jour'])
    objectif   = prog.get('objectif', 'maintien')
    poids_init = float(profil.get('poids') or 70)

    # TDEE du profil en mode maintien
    cal_tdee = calc_calories_cible({**dict(profil), 'objectif': 'maintien'})
    delta_cal = cal_cible - cal_tdee          # négatif = déficit
    kg_par_semaine = delta_cal * 7 / 7700     # 7700 kcal ≈ 1 kg graisse

    suivi = get_suivi_poids(limit=90, frequence="hebdo")
    semaines = suivi[-8:] if len(suivi) >= 8 else suivi

    projections = []
    poids_proj  = poids_init
    for i, s in enumerate(semaines):
        poids_reel  = float(s.get('poids') or poids_init)
        poids_proj  = round(poids_init + kg_par_semaine * (i + 1), 2)
        projections.append({
            'semaine':    s.get('date', f"S{i+1}"),
            'poids_reel': poids_reel,
            'poids_proj': poids_proj,
            'delta':      round(poids_reel - poids_proj, 2),
        })

    # Suggestion basée sur les 4 dernières semaines
    adjustment = 0
    delta_moyen = 0.0
    if len(projections) >= 2:
        recentes    = projections[-min(4, len(projections)):]
        delta_moyen = sum(p['delta'] for p in recentes) / len(recentes)
        if objectif == 'perte_poids':
            if delta_moyen > 0.5:    adjustment = -100
            elif delta_moyen < -0.5: adjustment = +100
        elif objectif == 'prise_masse':
            if delta_moyen < -0.5:   adjustment = +100
            elif delta_moyen > 0.5:  adjustment = -100

    return {
        'cal_cible':      cal_cible,
        'cal_tdee':       cal_tdee,
        'delta_cal':      delta_cal,
        'kg_par_semaine': round(kg_par_semaine, 2),
        'semaines':       projections,
        'adjustment':     adjustment,
        'cal_ajustees':   cal_cible + adjustment,
        'objectif':       objectif,
        'delta_moyen':    round(delta_moyen, 2),
    }


def apply_reequilibrage(new_calories: int):
    """Met à jour calories_jour du programme actif."""
    prog = get_programme_actif()
    if not prog:
        return
    conn = get_connection()
    conn.execute("UPDATE programmes SET calories_jour=? WHERE id=?",
                 (int(new_calories), prog['id']))
    conn.commit()
    conn.close()


# ─────────────────────────── SUIVI EAU ───────────────────────────────────────

def add_eau(ml: int, date_str: str = None, notes: str = "") -> int:
    uid = get_current_user_id()
    if not uid:
        return -1
    if date_str is None:
        date_str = date.today().isoformat()
    heure = datetime.now().strftime("%H:%M")
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO suivi_eau (user_id, date, heure, ml, notes) VALUES (?,?,?,?,?)",
        (uid, date_str, heure, ml, notes))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def get_eau_jour(date_str: str) -> list:
    uid = get_current_user_id()
    if not uid:
        return []
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM suivi_eau WHERE user_id=? AND date=? ORDER BY heure, id",
        (uid, date_str)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_total_eau_jour(date_str: str) -> int:
    return sum(int(e.get('ml') or 0) for e in get_eau_jour(date_str))


def delete_eau_entry(eid: int):
    conn = get_connection()
    conn.execute("DELETE FROM suivi_eau WHERE id=?", (eid,))
    conn.commit()
    conn.close()


def get_objectif_eau() -> int:
    user = get_current_user()
    return int(user.get('objectif_eau_ml') or 2000)


def get_rapport_semaine(date_lundi_iso: str) -> dict:
    """Agrège les données journal + eau + sport pour la semaine commençant date_lundi_iso."""
    from datetime import date as _date, timedelta

    lundi    = _date.fromisoformat(date_lundi_iso)
    dimanche = lundi + timedelta(days=6)

    user   = get_current_user()
    profil = get_profil()
    prog   = get_programme_actif()
    cible_cal = prog['calories_jour'] if prog else calc_calories_cible(profil)
    macros    = calc_macros_cibles(profil)

    _JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    _MOIS  = ["", "janvier", "février", "mars", "avril", "mai", "juin",
               "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

    jours = []
    for i in range(7):
        d        = lundi + timedelta(days=i)
        date_str = d.isoformat()
        label    = f"{_JOURS[d.weekday()]} {d.day} {_MOIS[d.month]}"
        nutri    = get_nutri_journal_jour(date_str)
        eau      = get_total_eau_jour(date_str)

        conn = get_connection()
        nb   = conn.execute(
            "SELECT COUNT(*) FROM journal_repas WHERE user_id=? AND date=?",
            (_current_user_id, date_str)).fetchone()[0]
        conn.close()

        enregistre = nb > 0
        a_objectif = (enregistre and
                      abs(nutri['calories'] - cible_cal) <= cible_cal * 0.10)

        jours.append({
            'date':        date_str,
            'label':       label,
            'calories':    nutri['calories'],
            'proteines':   nutri['proteines'],
            'glucides':    nutri['glucides'],
            'lipides':     nutri['lipides'],
            'fibres':      nutri['fibres'],
            'eau_ml':      eau,
            'a_objectif':  a_objectif,
            'enregistre':  enregistre,
        })

    jours_enr = [j for j in jours if j['enregistre']]
    nb_enr    = len(jours_enr)
    moyennes  = {
        k: round(sum(j[k] for j in jours_enr) / max(1, nb_enr), 1)
        for k in ('calories', 'proteines', 'glucides', 'lipides')
    }
    moyennes['eau_ml'] = round(sum(j['eau_ml'] for j in jours_enr) / max(1, nb_enr))

    # Sport
    conn       = get_connection()
    sport_rows = conn.execute(
        """SELECT type_activite, date, duree_min, calories_brulees
           FROM activites_sport
           WHERE user_id=? AND date>=? AND date<=?
           ORDER BY date, heure""",
        (_current_user_id, date_lundi_iso, dimanche.isoformat())).fetchall()
    conn.close()

    seances_sport = [
        {
            'label':           f"{ACTIVITES_SPORT.get(r['type_activite'],{}).get('icon','🏋️')} "
                               f"{ACTIVITES_SPORT.get(r['type_activite'],{}).get('label', r['type_activite'])}",
            'date':            r['date'],
            'duree_min':       r['duree_min'],
            'calories_brulees': round(float(r['calories_brulees']), 1),
        }
        for r in sport_rows
    ]

    jours_ok = sum(1 for j in jours if j['a_objectif'])

    semaine_label = (f"Semaine du {lundi.day} au {dimanche.day} "
                     f"{_MOIS[dimanche.month]} {dimanche.year}")

    return {
        'semaine_label': semaine_label,
        'date_lundi':    date_lundi_iso,
        'user': {
            'prenom':   user.get('prenom', '') if user else '',
            'nom':      user.get('nom', '') if user else '',
            'objectif': OBJECTIFS_LABELS.get(profil.get('objectif', ''), '—'),
        },
        'cible': {
            'calories':  int(cible_cal),
            'proteines': macros['proteines'],
            'glucides':  macros['glucides'],
            'lipides':   macros['lipides'],
        },
        'jours':    jours,
        'moyennes': moyennes,
        'sport': {
            'seances':    seances_sport,
            'total_cal':  round(sum(s['calories_brulees'] for s in seances_sport), 1),
            'total_min':  sum(s['duree_min'] for s in seances_sport),
            'nb_seances': len(seances_sport),
        },
        'adherence': {
            'jours_ok':         jours_ok,
            'jours_enregistres': nb_enr,
            'pct':              int(jours_ok / 7 * 100),
        },
    }
