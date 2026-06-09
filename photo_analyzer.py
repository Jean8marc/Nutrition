"""
NutriTrack Pro — Analyse de photo d'étiquette nutritionnelle
Utilise l'API Anthropic Claude Vision pour extraire les données.
"""
import os
import json
import base64
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from logger import get_logger
from theme import T

_log = get_logger("photo_analyzer")

try:
    import anthropic
    ANTHROPIC_OK = True
except ImportError:
    ANTHROPIC_OK = False

try:
    import PIL.Image
    import PIL.ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

CONFIG_FILE = "config.json"

PROMPT = """Tu es un expert en nutrition. Analyse cette photo d'étiquette nutritionnelle.
Extrais les informations et réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ni après, sans balises markdown.

Structure exacte à respecter :
{
  "nom": "nom complet du produit (marque + variété)",
  "categorie": "une seule valeur parmi : Viandes & Poissons | Œufs & Laitiers | Céréales & Féculents | Légumineuses | Légumes | Fruits & Oléagineux | Matières grasses | Boissons | Autre",
  "calories": nombre (kcal pour 100g),
  "proteines": nombre (g pour 100g),
  "glucides": nombre (g pour 100g — correspond à 'Glucides' ou 'Carbohydrates'),
  "lipides": nombre (g pour 100g — correspond à 'Matières grasses' ou 'Fat'),
  "fibres": nombre (g pour 100g — correspond à 'Fibres alimentaires'),
  "ig": 0,
  "unite": "g",
  "poids_unite_g": 0,
  "notes": "autres infos utiles (portion, marque, allergènes...)"
}

Règles :
- Utilise TOUJOURS les valeurs pour 100g/100ml (colonne 'pour 100g' si plusieurs colonnes)
- Si une valeur est absente, utilise 0
- Tous les nombres sont sans unité dans le JSON
- Matières grasses = lipides
- Fibres alimentaires = fibres"""


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(cfg: dict):
    json.dump(cfg, open(CONFIG_FILE, 'w', encoding='utf-8'), indent=2)


def get_api_key() -> str:
    return load_config().get('anthropic_api_key', '')


def set_api_key(key: str):
    cfg = load_config()
    cfg['anthropic_api_key'] = key
    save_config(cfg)


def analyze_image(image_path: str, api_key: str) -> dict | None:
    """Envoie l'image à Claude Vision et retourne les données nutritionnelles."""
    if not ANTHROPIC_OK:
        raise RuntimeError("Le module 'anthropic' n'est pas installé.\nRun: pip install anthropic")

    # Encode image
    ext = os.path.splitext(image_path)[1].lower()
    media_types = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                   '.png': 'image/png', '.webp': 'image/webp', '.gif': 'image/gif'}
    media_type = media_types.get(ext, 'image/jpeg')

    with open(image_path, 'rb') as f:
        img_b64 = base64.standard_b64encode(f.read()).decode('utf-8')

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": media_type, "data": img_b64}},
                {"type": "text", "text": PROMPT}
            ]
        }]
    )

    raw = message.content[0].text.strip()
    # Nettoyer les éventuelles balises markdown
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude a retourné une réponse non-JSON : {e}\n\nRéponse brute :\n{raw[:300]}")


# ─────────────────────────────────────────────────────────────────
#  Dialogue principal
# ─────────────────────────────────────────────────────────────────

class PhotoAnalyzerDialog(ctk.CTkToplevel):
    """
    Dialogue pour analyser une photo d'étiquette nutritionnelle.
    1. Saisir / mémoriser la clé API Anthropic
    2. Sélectionner une image
    3. Analyser via Claude Vision
    4. Retourner les données au callback
    """

    def __init__(self, parent, on_result):
        super().__init__(parent)
        self.on_result  = on_result
        self._img_path  = None
        self._analyzing = False

        self.title("📸  Analyser une photo de label nutritionnel")
        self.geometry("580x660")
        self.resizable(False, False)
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()
        self._build()

    # ── Construction ─────────────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(self, text="📸  Analyse par intelligence artificielle",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T["tx1"]).pack(padx=24, pady=(20, 4), anchor="w")
        ctk.CTkLabel(self,
                     text="Claude Vision lit l'étiquette et extrait les valeurs nutritionnelles automatiquement",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"],
                     wraplength=520).pack(padx=24, anchor="w")

        # ── Clé API ───────────────────────────────────────────────
        api_card = ctk.CTkFrame(self, fg_color=T["bg_el"], corner_radius=10)
        api_card.pack(padx=20, pady=(14, 0), fill="x")

        hdr = ctk.CTkFrame(api_card, fg_color="transparent")
        hdr.pack(padx=14, pady=(12, 4), fill="x")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text="🔑  Clé API Anthropic",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=T["tx1"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr,
                     text="console.anthropic.com  →  API Keys",
                     font=ctk.CTkFont(size=10), text_color=T["blue"]).grid(
            row=1, column=0, sticky="w")

        self._key_var = ctk.StringVar(value=get_api_key())
        key_row = ctk.CTkFrame(api_card, fg_color="transparent")
        key_row.pack(padx=14, pady=(4, 12), fill="x")
        key_row.grid_columnconfigure(0, weight=1)

        self._key_entry = ctk.CTkEntry(key_row, textvariable=self._key_var,
                                        show="•", height=36,
                                        placeholder_text="sk-ant-api03-…",
                                        fg_color=T["bg_card"], border_color=T["bg_hl"],
                                        font=ctk.CTkFont(size=12))
        self._key_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        ctk.CTkButton(key_row, text="💾",  width=36, height=36,
                      fg_color=T["bg_hl"], hover_color=T["bg_hl"],
                      command=self._save_key).grid(row=0, column=1, padx=(0, 4))

        self._show_key_btn = ctk.CTkButton(key_row, text="👁",  width=36, height=36,
                                            fg_color=T["bg_hl"], hover_color=T["bg_hl"],
                                            command=self._toggle_key_visibility)
        self._show_key_btn.grid(row=0, column=2)
        self._key_visible = False

        # ── Sélection image ───────────────────────────────────────
        img_card = ctk.CTkFrame(self, fg_color=T["bg_el"], corner_radius=10)
        img_card.pack(padx=20, pady=(10, 0), fill="x")

        ctk.CTkLabel(img_card, text="🖼️  Photo de l'étiquette",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=T["tx1"]).pack(padx=14, pady=(12, 6), anchor="w")

        btn_row = ctk.CTkFrame(img_card, fg_color="transparent")
        btn_row.pack(padx=14, pady=(0, 8), fill="x")

        ctk.CTkButton(btn_row, text="📁  Choisir une image",
                      fg_color=T["blue"], hover_color=T["blue_dm"],
                      height=36, corner_radius=8,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=self._pick_image).pack(side="left", padx=(0, 8))

        self._file_lbl = ctk.CTkLabel(btn_row, text="Aucun fichier sélectionné",
                                       font=ctk.CTkFont(size=11), text_color=T["tx2"])
        self._file_lbl.pack(side="left")

        # Prévisualisation
        self._preview = ctk.CTkLabel(img_card, text="",
                                      width=520, height=200,
                                      fg_color=T["bg_card"], corner_radius=8)
        self._preview.pack(padx=14, pady=(0, 12))

        # ── Statut ───────────────────────────────────────────────
        self._status_var = ctk.StringVar(value="")
        self._status_lbl = ctk.CTkLabel(self, textvariable=self._status_var,
                                         font=ctk.CTkFont(size=12), text_color=T["tx2"],
                                         wraplength=520)
        self._status_lbl.pack(padx=20, pady=(8, 0))

        # ── Boutons ───────────────────────────────────────────────
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(padx=20, pady=(10, 20), fill="x")

        ctk.CTkButton(bf, text="Annuler",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=40, width=120, corner_radius=8,
                      command=self.destroy).pack(side="left")

        self._analyze_btn = ctk.CTkButton(bf,
                      text="🤖  Analyser avec Claude Vision",
                      fg_color=T["vio"], hover_color=T["vio_d"],
                      text_color="#ffffff", height=40, width=260,
                      corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._start_analysis)
        self._analyze_btn.pack(side="right")

    # ── Actions ──────────────────────────────────────────────────

    def _save_key(self):
        key = self._key_var.get().strip()
        if key:
            set_api_key(key)
            self._status_var.set("✅  Clé API enregistrée")
            self._status_lbl.configure(text_color=T["ac"])

    def _toggle_key_visibility(self):
        self._key_visible = not self._key_visible
        self._key_entry.configure(show="" if self._key_visible else "•")

    def _pick_image(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Sélectionner une photo",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.gif"),
                       ("Tous les fichiers", "*.*")])
        if not path:
            return
        self._img_path = path
        self._file_lbl.configure(text=os.path.basename(path), text_color=T["tx1"])
        self._show_preview(path)

    def _show_preview(self, path):
        if not PIL_OK:
            self._preview.configure(text="Prévisualisation non disponible\n(Pillow requis)",
                                     text_color=T["tx2"])
            return
        try:
            img = PIL.Image.open(path)
            img.thumbnail((520, 200), PIL.Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img,
                                    size=(img.width, img.height))
            self._preview.configure(image=ctk_img, text="")
            self._preview._image = ctk_img
        except Exception as e:
            self._preview.configure(text=f"Erreur prévisualisation : {e}",
                                     text_color=T["err"])

    def _start_analysis(self):
        if self._analyzing:
            return
        api_key = self._key_var.get().strip()
        if not api_key:
            messagebox.showwarning("Clé API manquante",
                                   "Saisissez votre clé API Anthropic.\n"
                                   "Créez-en une sur console.anthropic.com → API Keys",
                                   parent=self)
            return
        if not self._img_path:
            messagebox.showwarning("Image manquante",
                                   "Veuillez sélectionner une image.", parent=self)
            return
        if not ANTHROPIC_OK:
            messagebox.showerror("Module manquant",
                                  "Installez le SDK Anthropic :\n  pip install anthropic",
                                  parent=self)
            return

        self._analyzing = True
        self._analyze_btn.configure(text="⏳  Analyse en cours…", state="disabled")
        self._status_var.set("🤖  Envoi à Claude Vision… (peut prendre 5-10 s)")
        self._status_lbl.configure(text_color=T["lip"])

        # Sauvegarder la clé automatiquement
        set_api_key(api_key)

        def _worker():
            try:
                data = analyze_image(self._img_path, api_key)
                self.after(0, lambda: self._on_success(data))
            except Exception as e:
                _log.error("Analyse photo échouée : %s", e, exc_info=True)
                self.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_success(self, data: dict):
        self._analyzing = False
        self._analyze_btn.configure(text="🤖  Analyser avec Claude Vision", state="normal")
        self._status_var.set(f"✅  Analyse réussie : {data.get('nom', '?')}")
        self._status_lbl.configure(text_color=T["ac"])
        self.destroy()
        self.on_result(data)

    def _on_error(self, msg: str):
        self._analyzing = False
        self._analyze_btn.configure(text="🤖  Analyser avec Claude Vision", state="normal")
        self._status_var.set(f"❌  Erreur : {msg}")
        self._status_lbl.configure(text_color=T["err"])
