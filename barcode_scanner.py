"""
NutriTrack Pro — Scanner de codes-barres
Deux modes :
  - MANUEL  : saisie du code-barres + API Open Food Facts (requires: requests)
  - CAMÉRA  : webcam temps réel (requires: opencv-python + pyzbar + zbar DLL)
"""
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from logger import get_logger
from theme import T

_log = get_logger("barcode_scanner")

# ── Mode Manuel : uniquement requests ────────────────────────────────────────
try:
    import requests
    MANUAL_OK = True
except ImportError:
    MANUAL_OK = False

# ── Mode Caméra : opencv + pyzbar + DLL zbar ─────────────────────────────────
CV2_OK    = False
PYZBAR_OK = False
pyzbar    = None
PIL       = None

try:
    import cv2
    CV2_OK = True
except (ImportError, OSError):
    pass

if CV2_OK:
    # Précharger les DLLs ZBar sur Windows avant d'importer pyzbar
    import sys, os
    if sys.platform == "win32":
        import ctypes
        _ZBAR_DIRS = [
            r"C:\Program Files (x86)\ZBar\bin",
            r"C:\Program Files\ZBar\bin",
            r"C:\ZBar\bin",
        ]
        _DLL_ORDER = [
            "zlib1.dll", "libiconv-2.dll", "libjpeg-7.dll",
            "libpng12-0.dll", "libtiff-3.dll", "libxml2-2.dll",
            "libzbar-0.dll",
        ]
        for _folder in _ZBAR_DIRS:
            if not os.path.isdir(_folder):
                continue
            try:
                os.add_dll_directory(_folder)
            except (AttributeError, OSError):
                pass
            os.environ["PATH"] = _folder + os.pathsep + os.environ.get("PATH", "")
            for _dll in _DLL_ORDER:
                _p = os.path.join(_folder, _dll)
                if os.path.exists(_p):
                    try:
                        ctypes.CDLL(_p)
                    except OSError:
                        pass
            break

    try:
        from pyzbar import pyzbar as _pyzbar
        pyzbar    = _pyzbar
        PYZBAR_OK = True
    except (ImportError, FileNotFoundError, OSError, Exception):
        pass

if CV2_OK:
    try:
        import PIL.Image
        import PIL.ImageTk
    except ImportError:
        CV2_OK = False

# ── Résumé des capacités ──────────────────────────────────────────────────────
CAMERA_OK  = CV2_OK and PYZBAR_OK   # scan webcam disponible
SCANNER_OK = MANUAL_OK              # bouton toujours visible si requests OK


# ── Constantes ────────────────────────────────────────────────────────────────
OFF_API    = "https://world.openfoodfacts.org/api/v0/product/{}.json"
OFF_SEARCH = "https://world.openfoodfacts.org/cgi/search.pl"

# Remappage clavier AZERTY → chiffres pour scanner code-barres USB
# (le scanner envoie des touches sans Shift, comme QWERTY, mais AZERTY
#  les interprète comme des caractères spéciaux)
_AZERTY_TO_DIGIT = {
    '&': '1', 'é': '2', '"': '3', "'": '4', '(': '5',
    '-': '6', 'è': '7', '_': '8', 'ç': '9', 'à': '0',
    # Variantes belges / suisses
    '§': '!', '°': ')',
}
TIMEOUT    = 6

# ─────────────────────────────────────────────────────────────────────────────
#  Requête Open Food Facts
# ─────────────────────────────────────────────────────────────────────────────

def fetch_product(barcode: str) -> dict | None:
    """
    Interroge l'API Open Food Facts avec un code-barres.
    Vérifie d'abord le cache local (off_cache.db) avant tout appel réseau.
    Retourne un dict compatible avec le schéma 'aliments', None si produit inconnu.
    Lève ConnectionError en cas de problème réseau.
    """
    # Vérification du cache local en priorité
    try:
        from off_cache import lookup as _cache_lookup
        cached = _cache_lookup(barcode)
        if cached:
            return cached
    except Exception as _e:
        _log.debug("off_cache lookup skipped: %s", _e)

    if not MANUAL_OK:
        return None
    try:
        r = requests.get(OFF_API.format(barcode), timeout=TIMEOUT,
                         headers={"User-Agent": "NutriTrackPro/1.0"})
        data = r.json()
    except requests.exceptions.Timeout:
        raise ConnectionError("Délai dépassé — vérifiez votre connexion (Open Food Facts)")
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Impossible de joindre Open Food Facts — vérifiez votre connexion Internet")
    except Exception as e:
        raise ConnectionError(f"Erreur réseau : {e}")

    if data.get("status") != 1:
        return None

    p  = data.get("product", {})
    n  = p.get("nutriments", {})

    def _f(key, fallback=0.0):
        """Lecture sécurisée d'une valeur nutritionnelle pour 100g."""
        v = n.get(key + "_100g") or n.get(key) or fallback
        try:
            return round(float(v), 1)
        except (ValueError, TypeError):
            return fallback

    # Nom
    nom = (p.get("product_name_fr")
           or p.get("product_name")
           or p.get("abbreviated_product_name")
           or "Produit " + barcode)

    # Catégorie → mapper vers nos catégories internes
    cat_off = (p.get("categories_tags") or [""])
    categorie = _map_category(cat_off, p.get("categories", ""))

    return {
        "nom":       nom.strip()[:80],
        "categorie": categorie,
        "calories":  _f("energy-kcal"),
        "proteines": _f("proteins"),
        "glucides":  _f("carbohydrates"),
        "lipides":   _f("fat"),
        "fibres":    _f("fiber"),
        "ig":        0,          # non fourni par OFF
        "unite":     "g",
        "notes":     f"Code-barres : {barcode}  |  Source : Open Food Facts",
    }


def _map_category(tags: list, cats_str: str) -> str:
    """Mappe les catégories Open Food Facts vers les catégories internes."""
    combined = " ".join(tags) + " " + cats_str.lower()

    rules = [
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
        (["vegetable", "legume", "carrot", "tomato", "salad",
          "legume", "carotte", "tomate", "salade", "brocoli"],
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

    for keywords, category in rules:
        if any(k in combined for k in keywords):
            return category

    return "Autre"


# ─────────────────────────────────────────────────────────────────────────────
#  Fenêtre scanner webcam
# ─────────────────────────────────────────────────────────────────────────────

class BarcodeScannerDialog(ctk.CTkToplevel):
    """
    Ouvre la webcam, détecte les codes-barres en temps réel
    et appelle `on_barcode(barcode_str)` quand un code est trouvé.
    """

    def __init__(self, parent, on_barcode):
        super().__init__(parent)
        self.on_barcode  = on_barcode
        self._cap        = None
        self._running    = False
        self._last_code  = None

        self.title("🔍  Recherche par code-barres")
        self.geometry("620x500")
        self.resizable(False, False)
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._build()
        self._start_camera()

    # ── UI ───────────────────────────────────────────────────────

    def _build(self):
        # Titre adapté selon le mode disponible
        if CAMERA_OK:
            titre = "📷  Pointez la caméra vers le code-barres"
            sous   = "Détection automatique EAN-8, EAN-13, UPC-A, QR Code…"
        else:
            titre = "🔍  Recherche par code-barres"
            sous   = "Saisissez le code-barres pour récupérer les infos nutritionnelles"

        ctk.CTkLabel(self, text=titre,
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T["tx1"]).pack(pady=(18, 4))
        ctk.CTkLabel(self, text=sous,
                     font=ctk.CTkFont(size=11),
                     text_color=T["tx2"]).pack()

        # Zone vidéo (cachée si pas de caméra)
        self.video_label = ctk.CTkLabel(
            self, text="",
            width=560, height=240 if CAMERA_OK else 80,
            fg_color=T["bg_app"], corner_radius=10)
        self.video_label.pack(padx=20, pady=(12, 4))

        # Statut
        init_status = "⏳  Démarrage de la caméra…" if CAMERA_OK else "📝  Mode saisie manuelle"
        self.status_var = ctk.StringVar(value=init_status)
        self.status_lbl = ctk.CTkLabel(
            self, textvariable=self.status_var,
            font=ctk.CTkFont(size=12), text_color=T["tx2"])
        self.status_lbl.pack(pady=(0, 8))

        # ── Saisie manuelle (TOUJOURS visible) ───────────────────
        manual_card = ctk.CTkFrame(self, fg_color=T["bg_el"], corner_radius=12)
        manual_card.pack(padx=20, pady=(4, 0), fill="x")

        ctk.CTkLabel(manual_card,
                     text="🔢  Saisie du code-barres",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=T["tx1"]).pack(
            padx=14, pady=(12, 6), anchor="w")

        row = ctk.CTkFrame(manual_card, fg_color="transparent")
        row.pack(padx=14, pady=(0, 12), fill="x")
        row.grid_columnconfigure(0, weight=1)

        self._manual_var = ctk.StringVar()
        self._manual_entry = ctk.CTkEntry(
            row, textvariable=self._manual_var,
            placeholder_text="Ex : 3017620422003  (EAN-13 au dos du produit)",
            height=38, fg_color=T["bg_card"], border_color=T["bg_hl"],
            font=ctk.CTkFont(size=13))
        self._manual_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self._manual_entry.bind("<Return>", lambda _: self._submit_manual())
        self._fixing_azerty = False
        self._manual_var.trace_add("write", self._fix_azerty_input)
        self._manual_entry.focus()

        ctk.CTkButton(row, text="🔍  Rechercher",
                      fg_color=T["blue"], hover_color=T["blue_dm"],
                      text_color="#ffffff", height=38, width=130,
                      corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"),
                      command=self._submit_manual).grid(row=0, column=1)

        # Bouton fermer
        ctk.CTkButton(self, text="Fermer",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=36, width=120, corner_radius=8,
                      command=self._close).pack(pady=(12, 16))

    # ── Caméra (optionnelle) ──────────────────────────────────────

    def _start_camera(self):
        """Démarre la webcam seulement si CAMERA_OK. Sinon, mode saisie seule."""
        if not CAMERA_OK:
            # Expliquer pourquoi la caméra est absente, mais rester ouvert
            if CV2_OK and not PYZBAR_OK:
                info = ("⚠️  Scanner caméra indisponible (DLL zbar manquante)\n"
                        "Saisie manuelle ci-dessous pleinement opérationnelle")
            elif not CV2_OK:
                info = ("⚠️  Scanner caméra indisponible (opencv non installé)\n"
                        "Saisie manuelle ci-dessous pleinement opérationnelle")
            else:
                info = "📝  Mode saisie manuelle"

            self.video_label.configure(
                text=info,
                text_color=T["lip"],
                font=ctk.CTkFont(size=12),
                wraplength=500, justify="center")
            self.status_var.set("📝  Saisissez le code-barres ci-dessous")
            self.status_lbl.configure(text_color=T["blue"])
            return

        # Tentative d'ouverture caméra
        for idx in (0, 1, 2):
            self._cap = cv2.VideoCapture(idx)
            if self._cap.isOpened():
                break

        if not self._cap.isOpened():
            self.video_label.configure(
                text="🚫  Aucune caméra détectée\nUtilisez la saisie manuelle ci-dessous",
                text_color=T["lip"], font=ctk.CTkFont(size=13),
                justify="center")
            self.status_var.set("📝  Mode saisie manuelle — aucune caméra")
            self.status_lbl.configure(text_color=T["blue"])
            return

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._running = True
        self.status_var.set("🟢  Caméra active — pointez vers un code-barres")
        self.status_lbl.configure(text_color=T["ac"])
        self._update_frame()

    def _update_frame(self):
        if not self._running or self._cap is None:
            return

        ret, frame = self._cap.read()
        if not ret:
            if self._running:
                self.after(100, self._update_frame)
            return

        # Détection des codes-barres
        barcodes = pyzbar.decode(frame)
        detected = None

        for bc in barcodes:
            data = bc.data.decode("utf-8").strip()
            if not data:
                continue
            detected = data

            # Rectangle vert autour du code détecté
            pts = bc.polygon
            if len(pts) == 4:
                import numpy as np
                pts_arr = [(p.x, p.y) for p in pts]
                for i in range(4):
                    cv2.line(frame, pts_arr[i], pts_arr[(i+1) % 4],
                             (34, 197, 94), 3)

            # Label
            x, y = bc.rect.left, bc.rect.top - 12
            cv2.putText(frame, f"{bc.type}: {data}",
                        (max(x, 0), max(y, 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (34, 197, 94), 2)

        # Convertir BGR → PIL → CTkImage
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img   = PIL.Image.fromarray(rgb).resize((560, 360), PIL.Image.LANCZOS)
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(560, 360))
        self.video_label.configure(image=ctk_img, text="")
        self.video_label._image = ctk_img

        # Code trouvé ?
        if detected and detected != self._last_code:
            self._last_code = detected
            self.status_var.set(f"✅  Code détecté : {detected} — Recherche en cours…")
            self.status_lbl.configure(text_color=T["ac"])
            self._running = False
            self.after(400, lambda: self._on_code_found(detected))
            return

        if self._running:
            self.after(30, self._update_frame)

    def _fix_azerty_input(self, *_):
        """Post-traite le StringVar après chaque frappe : remplace les caractères
        AZERTY (envoyés par le scanner sans Shift) par leurs chiffres correspondants."""
        if self._fixing_azerty:
            return
        val = self._manual_var.get()
        fixed = ''.join(_AZERTY_TO_DIGIT.get(c, c) for c in val)
        if fixed != val:
            self._fixing_azerty = True
            self._manual_var.set(fixed)
            self._fixing_azerty = False

    def _submit_manual(self):
        code = self._manual_var.get().strip()
        if not code:
            return
        self.status_var.set(f"🔍  Recherche de « {code} »…")
        self._running = False
        self.after(100, lambda: self._on_code_found(code))

    def _on_code_found(self, code: str):
        """Lance la requête OFF dans un thread pour ne pas bloquer l'UI."""
        def _fetch():
            try:
                product = fetch_product(code)
                self.after(0, lambda: self._handle_result(code, product, None))
            except ConnectionError as e:
                _log.warning("Erreur réseau barcode %s : %s", code, e)
                err = str(e)
                self.after(0, lambda: self._handle_result(code, None, err))

        threading.Thread(target=_fetch, daemon=True).start()

    def _handle_result(self, code: str, product, network_error: str | None):
        if network_error:
            self.status_var.set(f"⚠️  {network_error}")
            self.status_lbl.configure(text_color=T["lip"])
            self._last_code = None
            self._running   = True
            if self._cap and self._cap.isOpened():
                self._update_frame()
        elif product:
            self.status_var.set(f"✅  Produit trouvé : {product['nom']}")
            self.status_lbl.configure(text_color=T["ac"])
            self._close()
            self.on_barcode(product)
        else:
            self.status_var.set(f"❌  Produit introuvable pour le code {code}")
            self.status_lbl.configure(text_color=T["err"])
            # Permettre un nouvel essai
            self._last_code = None
            self._running   = True
            if self._cap and self._cap.isOpened():
                self._update_frame()

    # ── Fermeture ────────────────────────────────────────────────

    def _close(self):
        self._running = False
        if self._cap:
            self._cap.release()
            self._cap = None
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
#  Dialog résultat : confirmation avant ajout
# ─────────────────────────────────────────────────────────────────────────────

class ProductFoundDialog(ctk.CTkToplevel):
    """
    Affiche les données récupérées depuis Open Food Facts
    et permet de les éditer avant de les ajouter à la BDD.
    """

    CATEGORIES = [
        "Viandes & Poissons", "Œufs & Laitiers", "Céréales & Féculents",
        "Légumineuses", "Légumes", "Fruits & Oléagineux",
        "Matières grasses", "Boissons", "Autre",
    ]

    def __init__(self, parent, data: dict, on_confirm):
        super().__init__(parent)
        self.data       = data
        self.on_confirm = on_confirm
        self.title("Produit trouvé — Vérification")
        self.geometry("520x660")
        self.resizable(False, False)
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()
        self._build()

    def _build(self):
        # Entête
        ctk.CTkLabel(self,
                     text="✅  Produit récupéré depuis Open Food Facts",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T["ac"]).pack(padx=24, pady=(20, 4), anchor="w")
        ctk.CTkLabel(self,
                     text="Vérifiez et corrigez les valeurs si nécessaire (pour 100 g)",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(
            padx=24, anchor="w")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                         scrollbar_button_color=T["bg_el"])
        scroll.pack(fill="both", expand=True, padx=24, pady=10)
        scroll.grid_columnconfigure((0, 1), weight=1)

        self.vars = {}

        def e(label, key, row, col=0, span=2):
            ctk.CTkLabel(scroll, text=label,
                         font=ctk.CTkFont(size=12), text_color=T["tx2"]).grid(
                row=row * 2, column=col, columnspan=span,
                padx=6, pady=(10, 2), sticky="w")
            var = ctk.StringVar(value=str(self.data.get(key, "") or ""))
            ctk.CTkEntry(scroll, textvariable=var, height=36,
                         fg_color=T["bg_el"], border_color=T["bg_hl"],
                         font=ctk.CTkFont(size=13)).grid(
                row=row * 2 + 1, column=col, columnspan=span, padx=6, sticky="ew")
            self.vars[key] = var

        def combo(label, key, row, col=0, span=1):
            ctk.CTkLabel(scroll, text=label,
                         font=ctk.CTkFont(size=12), text_color=T["tx2"]).grid(
                row=row * 2, column=col, columnspan=span,
                padx=6, pady=(10, 2), sticky="w")
            var = ctk.StringVar(value=str(self.data.get(key, self.CATEGORIES[0]) or self.CATEGORIES[0]))
            ctk.CTkOptionMenu(scroll, variable=var, values=self.CATEGORIES,
                              fg_color=T["bg_el"], button_color=T["bg_hl"],
                              height=36, font=ctk.CTkFont(size=12)).grid(
                row=row * 2 + 1, column=col, columnspan=span, padx=6, sticky="ew")
            self.vars[key] = var

        e("Nom du produit",          "nom",       0, 0, 2)
        combo("Catégorie",            "categorie", 1, 0, 2)
        e("Calories (kcal / 100g)",  "calories",  2, 0, 1)
        e("Protéines (g / 100g)",    "proteines", 2, 1, 1)
        e("Glucides (g / 100g)",     "glucides",  3, 0, 1)
        e("Lipides (g / 100g)",      "lipides",   3, 1, 1)
        e("Fibres (g / 100g)",       "fibres",    4, 0, 1)
        e("Index glycémique (0-100)","ig",        4, 1, 1)
        e("Notes",                   "notes",     5, 0, 2)

        # Boutons
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(padx=24, pady=(6, 20), fill="x")

        ctk.CTkButton(bf, text="Annuler",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=38, width=120, corner_radius=8,
                      command=self.destroy).pack(side="left")

        ctk.CTkButton(bf, text="Aliments seulement",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=38, width=160, corner_radius=8,
                      command=self._confirm).pack(side="left", padx=8)

        ctk.CTkButton(bf, text="Aliments + Stock",
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000000",
                      height=38, width=160, corner_radius=8,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._confirm_and_stock).pack(side="right")

    def _confirm(self):
        data = {k: v.get().strip() for k, v in self.vars.items()}
        if not data.get("nom"):
            messagebox.showwarning("Champ requis", "Le nom est obligatoire.", parent=self)
            return
        for key in ("calories", "proteines", "glucides", "lipides", "fibres"):
            try:
                data[key] = float(data[key]) if data[key] else 0.0
            except ValueError:
                data[key] = 0.0
        try:
            data["ig"] = int(data["ig"]) if data["ig"] else 0
        except ValueError:
            data["ig"] = 0
        data.setdefault("unite", "g")
        self.on_confirm(data)
        self.destroy()

    def _confirm_and_stock(self):
        """Ajoute a la BDD aliments puis ouvre AddToStockDialog."""
        data = {k: v.get().strip() for k, v in self.vars.items()}
        if not data.get("nom"):
            messagebox.showwarning("Champ requis", "Le nom est obligatoire.", parent=self)
            return
        for key in ("calories", "proteines", "glucides", "lipides", "fibres"):
            try:
                data[key] = float(data[key]) if data[key] else 0.0
            except ValueError:
                data[key] = 0.0
        try:
            data["ig"] = int(data["ig"]) if data["ig"] else 0
        except ValueError:
            data["ig"] = 0
        data.setdefault("unite", "g")
        self.on_confirm(data)
        try:
            from pages.stock import AddToStockDialog as _AddToStockDialog
        except ImportError:
            _AddToStockDialog = None
        if _AddToStockDialog:
            import database as _db
            alims = _db.get_aliments(search=data.get("nom", ""))
            parent = self.master
            self.destroy()
            if alims:
                _AddToStockDialog(parent, alims[0])
        else:
            self.destroy()
