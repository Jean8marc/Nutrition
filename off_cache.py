"""
NutriTrack Pro — Cache local Open Food Facts
Construit un SQLite compact depuis le CSV OFF (~12 Go → ~300 Mo).
Utilisé par barcode_scanner.fetch_product() avant tout appel réseau.
"""
import sqlite3
import csv
import os
import threading
from logger import get_logger
from theme import T

logger = get_logger("off_cache")

_ROOT     = os.path.dirname(__file__)
_DB_PATH  = os.path.join(_ROOT, "off_cache.db")
_CSV_HINT = os.path.join(_ROOT, "Telechargement", "fr.openfoodfacts.org.products.csv")

# Indices des colonnes dans le CSV OFF (210 colonnes, tab-séparé)
_I_CODE      = 0
_I_NOM       = 10
_I_MARQUE    = 18
_I_CAT_FR    = 81   # main_category_fr
_I_ALLERGENES= 45
_I_NUTRISCORE= 58
_I_KCAL      = 89   # energy-kcal_100g
_I_KJ        = 90   # energy_100g (kJ de secours)
_I_FAT       = 92   # fat_100g
_I_CARBS     = 129  # carbohydrates_100g
_I_FIBER     = 146  # fiber_100g
_I_PROT      = 150  # proteins_100g
_I_SALT      = 154  # salt_100g


# ── Mappage catégorie ────────────────────────────────────────────────────────

_CATEGORY_RULES = [
    (["meat", "poultry", "fish", "seafood", "viande", "poisson",
      "poulet", "boeuf", "saumon", "thon", "jambon"],
     "Viandes & Poissons"),
    (["dairy", "milk", "cheese", "yogurt", "egg", "lait",
      "fromage", "yaourt", "oeuf"],
     "Œufs & Laitiers"),
    (["cereal", "bread", "pasta", "rice", "flour", "oat",
      "cereale", "pain", "pates", "riz", "farine", "avoine"],
     "Céréales & Féculents"),
    (["legume", "bean", "lentil", "pea", "chickpea",
      "lentille", "pois", "haricot"],
     "Légumineuses"),
    (["vegetable", "carrot", "tomato", "salad",
      "carotte", "tomate", "salade", "brocoli", "legumes"],
     "Légumes"),
    (["fruit", "nuts", "avocado", "banana", "apple",
      "noix", "amande", "avocat", "banane", "pomme"],
     "Fruits & Oléagineux"),
    (["oil", "fat", "butter", "cream",
      "huile", "beurre", "creme", "graisse"],
     "Matières grasses"),
    (["beverage", "drink", "juice", "water", "soda",
      "boisson", "jus", "eau"],
     "Boissons"),
]


def _map_category(cat_str: str) -> str:
    s = cat_str.lower()
    for keywords, label in _CATEGORY_RULES:
        if any(k in s for k in keywords):
            return label
    return "Autre"


# ── Infos cache ──────────────────────────────────────────────────────────────

def cache_exists() -> bool:
    return os.path.exists(_DB_PATH) and os.path.getsize(_DB_PATH) > 1024


def cache_info() -> dict:
    """Retourne nb de produits et taille du fichier."""
    if not cache_exists():
        return {"count": 0, "size_mb": 0}
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            count = conn.execute("SELECT COUNT(*) FROM produits").fetchone()[0]
        size_mb = round(os.path.getsize(_DB_PATH) / 1024 / 1024, 1)
        return {"count": count, "size_mb": size_mb}
    except Exception:
        return {"count": 0, "size_mb": 0}


# ── Recherche dans le cache ──────────────────────────────────────────────────

def lookup(barcode: str) -> dict | None:
    """
    Cherche un produit par code-barres dans le cache local.
    Retourne un dict compatible avec barcode_scanner.fetch_product(), ou None.
    """
    if not cache_exists():
        return None
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM produits WHERE code=?", (barcode.strip(),)
            ).fetchone()
        if row is None:
            return None
        r = dict(row)
        marque = r.get("marque") or ""
        return {
            "nom":       r["nom"][:80],
            "categorie": r.get("categorie") or "Autre",
            "calories":  float(r.get("calories") or 0),
            "proteines": float(r.get("proteines") or 0),
            "glucides":  float(r.get("glucides") or 0),
            "lipides":   float(r.get("lipides") or 0),
            "fibres":    float(r.get("fibres") or 0),
            "ig":        0,
            "unite":     "g",
            "notes":     f"Code : {barcode}  |  {marque}  |  Cache local OFF",
        }
    except Exception as e:
        logger.error("off_cache lookup error: %s", e)
        return None


# ── Construction du cache ────────────────────────────────────────────────────

def build_cache(csv_path: str,
                progress_cb=None,
                cancel_event: threading.Event | None = None) -> tuple[int, str]:
    """
    Construit le cache SQLite à partir du CSV Open Food Facts.
    progress_cb(pct: int, count: int) est appelé toutes les ~5000 lignes.
    Retourne (nb_produits_insérés, "ok" | "annulé" | message_erreur).
    """
    db_tmp = _DB_PATH + ".tmp"
    try:
        csv_size = os.path.getsize(csv_path)

        with sqlite3.connect(db_tmp) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-32000")  # 32 MB cache
            conn.execute("""
                CREATE TABLE IF NOT EXISTS produits (
                    code       TEXT PRIMARY KEY,
                    nom        TEXT NOT NULL,
                    marque     TEXT,
                    categorie  TEXT,
                    allergenes TEXT,
                    nutriscore TEXT,
                    calories   REAL,
                    lipides    REAL,
                    glucides   REAL,
                    fibres     REAL,
                    proteines  REAL,
                    sel        REAL
                )
            """)

            count = 0
            batch: list = []
            BATCH = 5000

            def _s(row, idx):
                try:
                    return row[idx].strip() or None
                except IndexError:
                    return None

            def _f(row, idx):
                try:
                    v = row[idx].strip()
                    return round(float(v), 2) if v else None
                except (ValueError, IndexError):
                    return None

            with open(csv_path, encoding="utf-8", errors="replace",
                      newline="") as f:
                reader = csv.reader(f, delimiter="\t")
                next(reader)   # skip header

                for row in reader:
                    if cancel_event and cancel_event.is_set():
                        conn.close()
                        if os.path.exists(db_tmp):
                            os.remove(db_tmp)
                        return count, "annulé"

                    if len(row) < 155:
                        continue

                    code = (row[_I_CODE] or "").strip()
                    nom  = (row[_I_NOM]  or "").strip()
                    if not code or not nom:
                        continue

                    # Calories : préférer kcal, sinon kJ → kcal
                    kcal = _f(row, _I_KCAL)
                    if kcal is None:
                        kj = _f(row, _I_KJ)
                        kcal = round(kj / 4.184, 1) if kj else None

                    cat_str = _s(row, _I_CAT_FR) or _s(row, 21) or ""
                    categorie = _map_category(cat_str)

                    batch.append((
                        code, nom,
                        _s(row, _I_MARQUE),
                        categorie,
                        _s(row, _I_ALLERGENES),
                        _s(row, _I_NUTRISCORE),
                        kcal,
                        _f(row, _I_FAT),
                        _f(row, _I_CARBS),
                        _f(row, _I_FIBER),
                        _f(row, _I_PROT),
                        _f(row, _I_SALT),
                    ))
                    count += 1

                    if len(batch) >= BATCH:
                        conn.executemany(
                            "INSERT OR REPLACE INTO produits VALUES "
                            "(?,?,?,?,?,?,?,?,?,?,?,?)",
                            batch)
                        conn.commit()
                        batch.clear()
                        if progress_cb:
                            try:
                                pct = min(98, int(f.tell() / csv_size * 100))
                                progress_cb(pct, count)
                            except Exception:
                                pass

            # Dernier batch
            if batch:
                conn.executemany(
                    "INSERT OR REPLACE INTO produits VALUES "
                    "(?,?,?,?,?,?,?,?,?,?,?,?)",
                    batch)
                conn.commit()

            conn.execute("CREATE INDEX IF NOT EXISTS idx_code ON produits(code)")
            conn.commit()

        # Remplace l'ancien cache
        if os.path.exists(_DB_PATH):
            os.remove(_DB_PATH)
        os.rename(db_tmp, _DB_PATH)

        if progress_cb:
            progress_cb(100, count)

        logger.info("off_cache built: %d products", count)
        return count, "ok"

    except Exception as e:
        logger.error("build_cache error: %s", e)
        if os.path.exists(db_tmp):
            try:
                os.remove(db_tmp)
            except Exception:
                pass
        return 0, str(e)


# ── Dialog d'import ──────────────────────────────────────────────────────────

import customtkinter as ctk
from tkinter import filedialog, messagebox


class ImportCacheDialog(ctk.CTkToplevel):
    """
    Dialogue de construction du cache OFF depuis le CSV.
    Lance l'import en thread de fond avec barre de progression.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("🗄️  Construire le cache Open Food Facts")
        self.geometry("540x360")
        self.resizable(False, False)
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()

        self._csv_path   = _CSV_HINT if os.path.exists(_CSV_HINT) else ""
        self._cancel_evt = threading.Event()
        self._running    = False

        self._build()

    def _build(self):
        ctk.CTkLabel(self,
                     text="🗄️  Cache Open Food Facts hors-ligne",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T["tx1"]).pack(padx=24, pady=(22, 4), anchor="w")
        ctk.CTkLabel(self,
                     text="Convertit le CSV (~12 Go) en base SQLite locale.\n"
                          "Les recherches par code-barres fonctionneront sans internet.",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"],
                     justify="left").pack(padx=24, anchor="w")

        # Sélection du fichier CSV
        file_frame = ctk.CTkFrame(self, fg_color=T["bg_el"], corner_radius=10)
        file_frame.pack(padx=24, pady=(16, 0), fill="x")
        file_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(file_frame, text="Fichier CSV :",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).grid(
            row=0, column=0, padx=12, pady=(10, 2), sticky="w")

        self._path_lbl = ctk.CTkLabel(
            file_frame,
            text=self._csv_path if self._csv_path else "Aucun fichier sélectionné",
            font=ctk.CTkFont(size=10),
            text_color=T["ac"] if self._csv_path else T["tx2"],
            anchor="w", wraplength=400)
        self._path_lbl.grid(row=1, column=0, padx=12, pady=(0, 4), sticky="w")

        ctk.CTkButton(file_frame, text="📂 Parcourir…",
                      fg_color=T["bg_hl"], hover_color=T["bg_el"],
                      text_color=T["tx1"], height=30, width=120,
                      font=ctk.CTkFont(size=11),
                      command=self._browse).grid(
            row=1, column=1, padx=12, pady=(0, 8))

        # Progression
        self._status_lbl = ctk.CTkLabel(
            self, text="Prêt à démarrer.",
            font=ctk.CTkFont(size=12), text_color=T["tx2"])
        self._status_lbl.pack(padx=24, pady=(18, 4), anchor="w")

        self._progress = ctk.CTkProgressBar(self, height=10,
                                             progress_color=T["ac"],
                                             fg_color=T["bg_el"])
        self._progress.pack(padx=24, fill="x")
        self._progress.set(0)

        self._count_lbl = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=10), text_color=T["tx2"])
        self._count_lbl.pack(padx=24, pady=(4, 0), anchor="w")

        # Boutons
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(padx=24, pady=16, fill="x")

        self._cancel_btn = ctk.CTkButton(
            bf, text="Annuler",
            fg_color=T["bg_el"], hover_color=T["bg_hl"],
            height=38, width=110, command=self._cancel)
        self._cancel_btn.pack(side="left")

        self._start_btn = ctk.CTkButton(
            bf, text="▶  Démarrer l'import",
            fg_color=T["ac"], hover_color=T["ac_d"],
            text_color="#000", height=38, width=180,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._start)
        self._start_btn.pack(side="right")

        # Afficher infos cache existant
        if cache_exists():
            info = cache_info()
            ctk.CTkLabel(
                self,
                text=f"Cache existant : {info['count']:,} produits · {info['size_mb']} Mo",
                font=ctk.CTkFont(size=10), text_color=T["ac"]).pack(
                padx=24, pady=(0, 4), anchor="w")

    def _browse(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Sélectionner le CSV Open Food Facts",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=os.path.join(_ROOT, "Telechargement"))
        if path:
            self._csv_path = path
            self._path_lbl.configure(text=path, text_color=T["ac"])

    def _start(self):
        if not self._csv_path or not os.path.exists(self._csv_path):
            messagebox.showwarning("Fichier manquant",
                                   "Sélectionnez le fichier CSV Open Food Facts.",
                                   parent=self)
            return
        if self._running:
            return

        self._running = True
        self._cancel_evt.clear()
        self._start_btn.configure(state="disabled")
        self._status_lbl.configure(text="⏳  Import en cours…", text_color=T["tx1"])

        import time
        self._t0 = time.time()

        def _run():
            count, status = build_cache(
                self._csv_path,
                progress_cb=self._on_progress,
                cancel_event=self._cancel_evt)
            self.after(0, lambda: self._on_done(count, status))

        threading.Thread(target=_run, daemon=True).start()

    def _on_progress(self, pct: int, count: int):
        import time
        elapsed = time.time() - self._t0
        eta = ""
        if pct > 2:
            remaining = elapsed / pct * (100 - pct)
            m, s = divmod(int(remaining), 60)
            eta = f"  —  ~{m}m{s:02d}s restant"

        def _update():
            self._progress.set(pct / 100)
            self._status_lbl.configure(
                text=f"⏳  Import en cours… {pct} %{eta}")
            self._count_lbl.configure(
                text=f"{count:,} produits traités")

        self.after(0, _update)

    def _on_done(self, count: int, status: str):
        self._running = False
        self._start_btn.configure(state="normal")
        if status == "ok":
            info = cache_info()
            self._progress.set(1.0)
            self._status_lbl.configure(
                text=f"✅  Cache prêt — {count:,} produits importés",
                text_color=T["ac"])
            self._count_lbl.configure(
                text=f"Fichier : {info['size_mb']} Mo  |  "
                     "Les scans hors-ligne sont maintenant disponibles.")
            messagebox.showinfo(
                "Cache construit",
                f"{count:,} produits importés avec succès.\n"
                f"Taille du cache : {info['size_mb']} Mo",
                parent=self)
        elif status == "annulé":
            self._status_lbl.configure(text="⛔  Import annulé.",
                                        text_color=T["lip"])
        else:
            self._status_lbl.configure(text=f"❌  Erreur : {status}",
                                        text_color=T["err"])

    def _cancel(self):
        if self._running:
            self._cancel_evt.set()
            self._status_lbl.configure(text="⏳  Annulation en cours…",
                                        text_color=T["lip"])
        else:
            self.destroy()
