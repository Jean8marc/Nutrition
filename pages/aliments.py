"""
NutriTrack Pro — Gestion des aliments (v2)
Nouveautés : Nutri-Score, poids_unite_g, import/export CSV,
             analyse photo, filtre catégories corrigé.
"""
import os, sys, time, threading
import customtkinter as ctk
from tkinter import messagebox, filedialog
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import database as db
from colors import tint_low
from barcode_scanner import (BarcodeScannerDialog, ProductFoundDialog,
                             SCANNER_OK, CAMERA_OK, MANUAL_OK,
                             fetch_product, _AZERTY_TO_DIGIT)
from photo_analyzer import PhotoAnalyzerDialog, ANTHROPIC_OK
from pages.stock import AddToStockDialog
from theme import T

CATEGORIES = [
    "Viandes & Poissons", "Œufs & Laitiers", "Céréales & Féculents",
    "Légumineuses", "Légumes", "Fruits & Oléagineux",
    "Matières grasses", "Boissons", "Herbes, épices et assaisonnements", "Autre",
]

def _ig_color(ig):
    if not ig or int(ig) == 0: return T["tx2"]
    return T["ac"] if int(ig) < 55 else T["lip"] if int(ig) < 70 else T["err"]

def _ig_label(ig):
    if not ig or int(ig) == 0: return "—"
    ig = int(ig)
    if ig < 55:  return f"{ig} 🟢"
    if ig < 70:  return f"{ig} 🟡"
    return f"{ig} 🔴"


class AlimentsPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=T["bg_app"], corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._scanner_buf = []
        self._scanner_last_t = 0.0
        self._build()
        self.after(500, self._start_usb_listener)

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=28, pady=(28, 0), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="🥑  Aliments",
                     font=ctk.CTkFont(family="Helvetica", size=26, weight="bold"),
                     text_color=T["tx1"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header,
                     text="Valeurs pour 100 g · 100 ml · 1 unité  |  "
                          "Lipides = Matières grasses  ·  Fibres = Fibres alimentaires",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).grid(
            row=1, column=0, sticky="w", pady=(2, 0))

        btn_row = ctk.CTkFrame(header, fg_color="transparent")
        btn_row.grid(row=0, column=1, rowspan=2, sticky="e")

        ctk.CTkButton(btn_row, text="📸  Photo IA",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color=T["vio"], hover_color=T["vio_d"],
                      text_color="#ffffff", height=36, width=125, corner_radius=8,
                      command=self._open_photo_analyzer).pack(side="left", padx=(0, 6))

        ctk.CTkButton(btn_row, text="🗄️  Cache OFF",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color="#0d9488", hover_color="#0f766e",
                      text_color="#ffffff", height=36, width=115, corner_radius=8,
                      command=self._open_cache_off).pack(side="left", padx=(0, 6))

        ctk.CTkButton(btn_row,
                      text="📷  Scanner" if CAMERA_OK else "🔍  Code-barres",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color=T["blue"] if MANUAL_OK else T["bg_hl"],
                      hover_color=T["blue_dm"],
                      text_color="#ffffff", height=36, width=135, corner_radius=8,
                      command=self._open_scanner).pack(side="left", padx=(0, 6))

        ctk.CTkButton(btn_row, text="⚖  Comparer",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color="#6366f1", hover_color="#4f46e5",
                      text_color="#ffffff", height=36, width=110, corner_radius=8,
                      command=self._open_comparateur).pack(side="left", padx=(0, 6))

        ctk.CTkButton(btn_row, text="📥  CSV",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color="#0d9488", hover_color="#0f766e",
                      text_color="#ffffff", height=36, width=90, corner_radius=8,
                      command=self._import_csv).pack(side="left", padx=(0, 6))

        ctk.CTkButton(btn_row, text="＋  Ajouter",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000000", height=36, width=110, corner_radius=8,
                      command=self._open_add).pack(side="left")

        # Barre filtres
        fbar = ctk.CTkFrame(self, fg_color="transparent")
        fbar.grid(row=1, column=0, padx=28, pady=12, sticky="ew")

        self.search_var = ctk.StringVar()
        search = ctk.CTkEntry(fbar, textvariable=self.search_var,
                              placeholder_text="🔍   Rechercher…",
                              width=260, height=36,
                              fg_color=T["bg_card"], border_color=T["bg_hl"],
                              font=ctk.CTkFont(size=13))
        search.pack(side="left", padx=(0, 10))
        search.bind("<KeyRelease>", lambda _: self._refresh_table())

        self.cat_var = ctk.StringVar(value="Toutes")
        self.cat_menu = ctk.CTkOptionMenu(
            fbar, variable=self.cat_var, values=["Toutes"],
            fg_color=T["bg_card"], button_color=T["bg_el"],
            button_hover_color=T["bg_hl"],
            height=36, width=220, font=ctk.CTkFont(size=13),
            command=self._on_cat_change)
        self.cat_menu.pack(side="left")

        ctk.CTkButton(fbar, text="📤 Export",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=36, width=90, corner_radius=8,
                      font=ctk.CTkFont(size=12),
                      command=self._export_csv).pack(side="left", padx=(10, 0))

        self.count_lbl = ctk.CTkLabel(fbar, text="",
                                       font=ctk.CTkFont(size=12), text_color=T["tx2"])
        self.count_lbl.pack(side="right")

        # Tableau
        container = ctk.CTkFrame(self, fg_color=T["bg_card"], corner_radius=14)
        container.grid(row=2, column=0, padx=28, pady=(0, 28), sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)

        self.COL_W = [185, 155, 72, 72, 72, 72, 65, 55, 75, 95]
        COLS = ["Aliment", "Catégorie", "Calories", "Protéines", "Glucides",
                "Lipides", "Fibres", "IG", "Nutri-Score", "Actions"]

        th = ctk.CTkFrame(container, fg_color=T["bg_el"], corner_radius=8, height=38)
        th.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        th.grid_propagate(False)
        x = 12
        for col_name, w in zip(COLS, self.COL_W):
            ctk.CTkLabel(th, text=col_name,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=T["tx2"], width=w, anchor="w").place(
                x=x, rely=0.5, anchor="w")
            x += w + 2

        self.body = ctk.CTkScrollableFrame(container, fg_color="transparent",
                                            scrollbar_button_color=T["bg_el"],
                                            scrollbar_button_hover_color=T["bg_hl"])
        self.body.grid(row=1, column=0, padx=10, pady=8, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)

        self.refresh()

    def refresh(self):
        cats_in_db = db.get_categories_aliments()
        all_cats   = ["Toutes"] + cats_in_db
        current    = self.cat_var.get()
        self.cat_menu.configure(values=all_cats)
        # CTkOptionMenu.configure(values=...) réinitialise la variable liée à values[0]
        # → on restaure explicitement la sélection courante
        self.cat_var.set(current if current in all_cats else "Toutes")
        self._refresh_table()

    def _on_cat_change(self, value: str):
        # Reçoit la valeur directement depuis le menu (plus fiable que cat_var.get())
        self.cat_var.set(value)
        self._refresh_table()

    def _refresh_table(self):
        for w in self.body.winfo_children():
            w.destroy()

        aliments = db.get_aliments(self.search_var.get().strip(), self.cat_var.get())
        self.count_lbl.configure(text=f"{len(aliments)} résultat(s)")

        if not aliments:
            ctk.CTkLabel(self.body, text="Aucun aliment trouvé",
                         text_color=T["tx2"],
                         font=ctk.CTkFont(size=14)).grid(pady=50)
            return

        for i, alim in enumerate(aliments):
            bg  = T["bg_row"] if i % 2 == 0 else "transparent"
            row = ctk.CTkFrame(self.body, fg_color=bg, corner_radius=6, height=38)
            row.grid(row=i, column=0, pady=1, sticky="ew")
            row.grid_propagate(False)

            ns_letter, ns_color = db.calc_nutri_score(alim)

            vals = [
                (alim['nom'],                T["tx1"]),
                (alim['categorie'],          "#7c93b0"),
                (f"{alim['calories']} kcal", T["tx1"]),
                (f"{alim['proteines']} g",   T["ac"]),
                (f"{alim['glucides']} g",    T["tx1"]),
                (f"{alim['lipides']} g",     T["tx1"]),
                (f"{alim['fibres']} g",      T["tx2"]),
                (_ig_label(alim['ig']),       _ig_color(alim['ig'])),
            ]

            x = 12
            for (txt, color), w in zip(vals, self.COL_W[:-2]):
                ctk.CTkLabel(row, text=txt, font=ctk.CTkFont(size=12),
                             text_color=color, width=w, anchor="w").place(
                    x=x, rely=0.5, anchor="w")
                x += w + 2

            ns_w = self.COL_W[-2]
            ctk.CTkLabel(row, text=f"  {ns_letter}  ",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=ns_color,
                         fg_color=tint_low(ns_color),
                         corner_radius=6).place(x=x, rely=0.5, anchor="w")
            x += ns_w + 2

            bf = ctk.CTkFrame(row, fg_color="transparent")
            bf.place(x=x, rely=0.5, anchor="w")
            ctk.CTkButton(bf, text="St", width=30, height=26,
                          fg_color=T["bg_el"], hover_color=T["ac_bg"],
                          font=ctk.CTkFont(size=11), corner_radius=6,
                          command=lambda a=alim: AddToStockDialog(self, a)).pack(side="left", padx=2)
            ctk.CTkButton(bf, text="✏", width=30, height=26,
                          fg_color=T["bg_el"], hover_color=T["bg_hl"],
                          font=ctk.CTkFont(size=12), corner_radius=6,
                          command=lambda a=alim: self._open_edit(a)).pack(side="left", padx=2)
            ctk.CTkButton(bf, text="🗑", width=30, height=26,
                          fg_color=T["bg_el"], hover_color=T["err_bg"],
                          font=ctk.CTkFont(size=12), corner_radius=6,
                          command=lambda a=alim: self._confirm_delete(a)).pack(side="left", padx=2)

    def _open_add(self):
        AlimentDialog(self, None, self.refresh)

    def _open_edit(self, alim):
        AlimentDialog(self, alim, self.refresh)

    def _confirm_delete(self, alim):
        if messagebox.askyesno("Supprimer",
                               f"Supprimer « {alim['nom']} » ?", parent=self):
            db.delete_aliment(alim['id'])
            self.refresh()

    def _open_comparateur(self):
        ComparateurDialog(self)

    def _open_cache_off(self):
        from off_cache import ImportCacheDialog
        ImportCacheDialog(self)

    # ── Listener scanner USB ──────────────────────────────────────────────────

    def _start_usb_listener(self):
        """Écoute les frappes clavier rapides du scanner USB sur toute la fenêtre."""
        try:
            top = self.winfo_toplevel()
            top.bind("<KeyPress>", self._on_usb_key, add="+")
        except Exception:
            pass

    def _on_usb_key(self, event):
        # Ignorer si le focus est sur un champ de saisie (l'utilisateur tape)
        focused = event.widget
        if isinstance(focused, (ctk.CTkEntry, ctk.CTkTextbox)):
            return
        try:
            if focused.winfo_class() in ("Entry", "Text"):
                return
        except Exception:
            pass

        now = time.time()
        # Délai > 80 ms = saisie humaine → reset du buffer
        if now - self._scanner_last_t > 0.08:
            self._scanner_buf = []
        self._scanner_last_t = now

        char = _AZERTY_TO_DIGIT.get(event.char, event.char)

        if event.keysym in ("Return", "KP_Enter"):
            code = "".join(self._scanner_buf)
            self._scanner_buf = []
            if len(code) >= 8 and code.isdigit() and MANUAL_OK:
                self._usb_lookup(code)
        elif char.isdigit():
            self._scanner_buf.append(char)

    def _usb_lookup(self, code: str):
        def _fetch():
            try:
                product = fetch_product(code)
                self.after(0, lambda: self._on_usb_result(code, product, None))
            except ConnectionError as e:
                self.after(0, lambda: self._on_usb_result(code, None, str(e)))

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_usb_result(self, code, product, err):
        if err:
            messagebox.showwarning("Scanner", f"Erreur réseau :\n{err}", parent=self)
        elif product:
            self._on_product_found(product)
        else:
            messagebox.showinfo("Scanner", f"Produit introuvable pour le code :\n{code}", parent=self)

    # ─────────────────────────────────────────────────────────────────────────

    def _open_scanner(self):
        if not MANUAL_OK:
            messagebox.showinfo("Module manquant",
                                "pip install requests", parent=self)
            return
        BarcodeScannerDialog(self, self._on_product_found)

    def _open_photo_analyzer(self):
        if not ANTHROPIC_OK:
            messagebox.showinfo("Module manquant",
                                "Installez le SDK Anthropic :\n  pip install anthropic\n\n"
                                "Puis créez une clé sur console.anthropic.com", parent=self)
            return
        PhotoAnalyzerDialog(self, self._on_product_found)

    def _on_product_found(self, data: dict):
        ProductFoundDialog(self, data, self._on_product_confirmed)

    def _on_product_confirmed(self, data: dict):
        db.add_aliment(data)
        self.refresh()
        messagebox.showinfo("Ajouté ✅",
                            f"« {data['nom']} » a été ajouté.", parent=self)

    def _import_csv(self):
        path = filedialog.askopenfilename(
            parent=self, title="Importer un CSV",
            filetypes=[("CSV", "*.csv *.txt"), ("Tous", "*.*")])
        if not path:
            return
        try:
            r = db.import_csv_aliments(path)
            msg = (f"Import terminé :\n\n"
                   f"  ✅  {r['imported']} importé(s)\n"
                   f"  ⏭  {r['skipped']} doublon(s) ignoré(s)\n"
                   f"  ❌  {len(r['errors'])} erreur(s)")
            if r['errors']:
                msg += "\n\nErreurs :\n" + "\n".join(r['errors'][:5])
            messagebox.showinfo("Import CSV", msg, parent=self)
            self.refresh()
        except Exception as e:
            messagebox.showerror("Erreur import", str(e), parent=self)

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="Exporter",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            db.export_csv_aliments(path)
            messagebox.showinfo("Exporté ✅", f"Fichier : {path}", parent=self)
        except Exception as e:
            messagebox.showerror("Erreur", str(e), parent=self)


# ─────────────────────────── Dialogue CRUD ───────────────────────────────────

class AlimentDialog(ctk.CTkToplevel):
    def __init__(self, parent, alim, callback):
        super().__init__(parent)
        self.alim     = alim
        self.callback = callback
        self.title("Modifier" if alim else "Nouvel aliment")
        self.geometry("540x740")
        self.resizable(False, False)
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()
        self._build()
        if alim:
            self._populate()

    def _build(self):
        ctk.CTkLabel(self,
                     text="Modifier l'aliment" if self.alim else "Nouvel aliment",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=T["tx1"]).pack(padx=24, pady=(22, 4), anchor="w")
        ctk.CTkLabel(self, text="Valeurs pour 100 g / 100 ml / 1 unité",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(padx=24, anchor="w")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                         scrollbar_button_color=T["bg_el"])
        scroll.pack(fill="both", expand=True, padx=24, pady=8)
        scroll.grid_columnconfigure((0, 1), weight=1)

        self.vars = {}

        def entry(label, key, r, col=0, span=2, ph=""):
            ctk.CTkLabel(scroll, text=label, font=ctk.CTkFont(size=12),
                         text_color=T["tx2"]).grid(
                row=r*2, column=col, columnspan=span, padx=6, pady=(10,2), sticky="w")
            var = ctk.StringVar()
            ctk.CTkEntry(scroll, textvariable=var, height=36,
                         placeholder_text=ph,
                         fg_color=T["bg_el"], border_color=T["bg_hl"],
                         font=ctk.CTkFont(size=13)).grid(
                row=r*2+1, column=col, columnspan=span, padx=6, sticky="ew")
            self.vars[key] = var

        def combo(label, key, r, col, opts, span=1):
            ctk.CTkLabel(scroll, text=label, font=ctk.CTkFont(size=12),
                         text_color=T["tx2"]).grid(
                row=r*2, column=col, columnspan=span, padx=6, pady=(10,2), sticky="w")
            var = ctk.StringVar(value=opts[0])
            ctk.CTkOptionMenu(scroll, variable=var, values=opts,
                              fg_color=T["bg_el"], button_color=T["bg_hl"],
                              height=36, font=ctk.CTkFont(size=12)).grid(
                row=r*2+1, column=col, columnspan=span, padx=6, sticky="ew")
            self.vars[key] = var

        entry("Nom de l'aliment *",             "nom",          0, span=2)
        combo("Catégorie",                       "categorie",    1, 0, CATEGORIES, span=2)
        entry("Calories (kcal / 100g)",          "calories",             2, 0, ph="ex: 165")
        entry("Protéines (g / 100g)",            "proteines",            2, 1, ph="ex: 31")
        entry("Glucides (g / 100g)",             "glucides",             3, 0, ph="ex: 28")
        entry("dont Sucres (g / 100g)",          "sucres",               3, 1, ph="ex: 5.5")
        entry("Lipides (g / 100g) = Mat. grasses","lipides",             4, 0, ph="ex: 3.6")
        entry("dont Acides gras saturés (g)",    "acides_gras_satures",  4, 1, ph="ex: 0.8")
        entry("Fibres alim. (g / 100g)",         "fibres",               5, 0, ph="ex: 2.5")
        entry("Sel (g / 100g)",                  "sel",                  5, 1, ph="ex: 0.13")
        entry("Cholestérol (mg / 100g)",         "cholesterol",          6, 0, ph="ex: 45")
        entry("Index glycémique (0-100)",        "ig",                   6, 1, ph="ex: 55")
        combo("Unité de référence",              "unite",                7, 0,
              ["g", "ml"] + [u for u in db.UNITS_CULINAIRES if u not in ("g","ml")])
        entry("Poids par unité (g)  ← si 'unité'",
              "poids_unite_g", 7, 1, ph="ex: 60")
        entry("Allergènes",                      "allergenes",           8, span=2,
              ph="ex: Gluten, Lait, Œufs")

        ctk.CTkLabel(scroll,
                     text="💡  Exemple : Œuf → unité + 60 g → app calcule 93 kcal/œuf automatiquement",
                     font=ctk.CTkFont(size=10), text_color=T["blue"],
                     wraplength=460).grid(
            row=17, column=0, columnspan=2, padx=6, pady=(2, 0), sticky="w")

        entry("Notes",                           "notes",                9, span=2)

        # Nutri-Score live
        self._ns_frame = ctk.CTkFrame(scroll, fg_color=T["bg_el"], corner_radius=8)
        self._ns_frame.grid(row=15, column=0, columnspan=2, padx=6, pady=(14,4), sticky="ew")
        self._ns_lbl = ctk.CTkLabel(self._ns_frame,
                                     text="Nutri-Score : —",
                                     font=ctk.CTkFont(size=12),
                                     text_color=T["tx2"])
        self._ns_lbl.pack(padx=14, pady=10)

        for key in ("calories","proteines","glucides","sucres","lipides",
                    "acides_gras_satures","fibres","sel"):
            self.vars[key].trace_add("write", lambda *a: self._update_ns())

        # Boutons
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(padx=24, pady=(4, 20), fill="x")
        ctk.CTkButton(bf, text="Annuler",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=38, width=120, corner_radius=8,
                      command=self.destroy).pack(side="left")
        ctk.CTkButton(bf, text="✔  Enregistrer",
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000000", height=38, width=160,
                      corner_radius=8, command=self._save).pack(side="right")

    def _update_ns(self):
        try:
            fake = {k: float(self.vars[k].get().replace(",",".") or 0)
                    for k in ("calories","proteines","glucides","lipides","fibres")}
            letter, color, conseil = db.nutri_score_label(fake)
            self._ns_lbl.configure(
                text=f"Nutri-Score :  {letter}  —  {conseil}",
                text_color=color)
        except Exception:
            pass

    def _populate(self):
        for key, var in self.vars.items():
            v = self.alim.get(key, "")
            var.set("" if v is None else str(v))

    def _save(self):
        data = {k: v.get().strip() for k, v in self.vars.items()}
        if not data.get("nom"):
            messagebox.showwarning("Champ requis", "Le nom est obligatoire.", parent=self)
            return
        for key in ("calories","proteines","glucides","sucres","lipides",
                    "acides_gras_satures","fibres","sel","cholesterol","poids_unite_g"):
            try:
                data[key] = float(str(data[key]).replace(",",".")) if data[key] else 0.0
            except (ValueError, AttributeError):
                data[key] = 0.0
        try:
            data["ig"] = int(float(str(data["ig"]).replace(",",".") or 0))
        except (ValueError, TypeError):
            data["ig"] = 0
        data.setdefault("unite", "g")
        data.setdefault("categorie", "Autre")

        if self.alim:
            db.update_aliment(self.alim["id"], data)
            self.callback()
            self.destroy()
        else:
            db.add_aliment(data)
            # Récupérer l'aliment créé pour proposer l'ajout au stock
            alims = db.get_aliments(search=data.get("nom", ""))
            alim_new = next((a for a in alims
                             if a['nom'].strip().lower() == data['nom'].strip().lower()), None)
            self.callback()
            self.destroy()
            if alim_new and messagebox.askyesno(
                    "Ajouter au stock ?",
                    f"« {alim_new['nom']} » a été créé.\n\nVoulez-vous l'ajouter à votre stock maintenant ?"):
                AddToStockDialog(self.master, alim_new)


# ─────────────────────────── Comparateur d'aliments ─────────────────────────


class ComparateurDialog(ctk.CTkToplevel):
    """Comparaison côte à côte de 2 ou 3 aliments."""

    MAX  = 3
    COLS = [T["ac"], T["blue"], T["lip"]]
    NUTRIENTS = [
        ("Calories",          "calories",           "kcal"),
        ("Protéines",         "proteines",          "g"),
        ("Glucides",          "glucides",           "g"),
        ("dont Sucres",       "sucres",             "g"),
        ("Lipides",           "lipides",            "g"),
        ("dont AGS",          "acides_gras_satures","g"),
        ("Fibres",            "fibres",             "g"),
        ("Sel",               "sel",                "g"),
        ("Index glycémique",  "ig",                 ""),
        ("Nutri-Score",       "_ns",                ""),
    ]

    def __init__(self, parent):
        super().__init__(parent)
        self._sel: list[dict] = []
        self.title("Comparateur d'aliments")
        self.geometry("720x720")
        self.resizable(True, True)
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()
        self._build()

    # ── Construction ─────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Entête
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=22, pady=(18, 0), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="⚖  Comparateur d'aliments",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=T["tx1"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr, text=f"Sélectionnez jusqu'à {self.MAX} aliments  (valeurs pour 100 g)",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).grid(
            row=1, column=0, sticky="w", pady=(2, 0))

        # Zone recherche + sélection
        sel_frame = ctk.CTkFrame(self, fg_color=T["bg_card"])
        sel_frame.grid(row=1, column=0, padx=22, pady=(10, 0), sticky="ew")
        sel_frame.grid_columnconfigure(0, weight=1)

        self._search_var = ctk.StringVar()
        se = ctk.CTkEntry(sel_frame, textvariable=self._search_var,
                          placeholder_text="🔍  Rechercher un aliment à comparer…",
                          height=34, fg_color=T["bg_el"], border_color=T["bg_hl"],
                          font=ctk.CTkFont(size=12))
        se.grid(row=0, column=0, pady=(0, 6), sticky="ew")
        se.bind("<KeyRelease>", lambda _: self._update_search())

        self._results_frame = ctk.CTkScrollableFrame(
            sel_frame, fg_color="transparent",
            scrollbar_button_color=T["bg_el"], height=110)
        self._results_frame.grid(row=1, column=0, sticky="ew")
        self._results_frame.grid_columnconfigure(0, weight=1)

        # Chips sélection
        self._chips_frame = ctk.CTkFrame(sel_frame, fg_color="transparent")
        self._chips_frame.grid(row=2, column=0, pady=(6, 4), sticky="ew")

        # Corps comparaison (scrollable)
        self._body = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                             scrollbar_button_color=T["bg_el"])
        self._body.grid(row=2, column=0, padx=22, pady=(8, 0), sticky="nsew")
        self._body.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(self, text="Fermer",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=36, width=120, corner_radius=8,
                      command=self.destroy).grid(row=3, column=0, pady=(8, 16))

        self._update_search()
        self._update_comparison()

    # ── Recherche ────────────────────────────────────────────────

    def _update_search(self):
        for w in self._results_frame.winfo_children():
            w.destroy()
        search  = self._search_var.get().strip()
        aliments = db.get_aliments(search=search)[:25]
        full    = len(self._sel) >= self.MAX

        for i, a in enumerate(aliments):
            already = any(s['id'] == a['id'] for s in self._sel)
            bg      = tint_low(T["ac"]) if already else ("transparent" if i % 2 else T["bg_row"])
            tc      = T["ac"] if already else T["tx1"]

            row = ctk.CTkFrame(self._results_frame, fg_color=bg,
                               corner_radius=6, height=32)
            row.grid(row=i, column=0, pady=1, sticky="ew")
            row.grid_columnconfigure(0, weight=1)
            row.grid_propagate(False)

            ctk.CTkLabel(row, text=("✓  " if already else "") + a['nom'],
                         font=ctk.CTkFont(size=11), text_color=tc,
                         anchor="w").grid(row=0, column=0, padx=8, sticky="w")
            ctk.CTkLabel(row,
                         text=f"{a['calories']} kcal • P{a['proteines']} G{a['glucides']} L{a['lipides']}",
                         font=ctk.CTkFont(size=9), text_color=T["tx2"]).grid(
                row=0, column=1, padx=8, sticky="e")

            if already:
                cmd = lambda e, aid=a['id']: self._remove(aid)
            elif not full:
                cmd = lambda e, al=a: self._add(al)
            else:
                cmd = None

            if cmd:
                row.bind("<Button-1>", cmd)
                for child in row.winfo_children():
                    child.bind("<Button-1>", cmd)

    # ── Gestion sélection ────────────────────────────────────────

    def _add(self, alim: dict):
        if len(self._sel) >= self.MAX:
            return
        if any(s['id'] == alim['id'] for s in self._sel):
            return
        self._sel.append(alim)
        self._refresh_all()

    def _remove(self, alim_id: int):
        self._sel = [a for a in self._sel if a['id'] != alim_id]
        self._refresh_all()

    def _refresh_all(self):
        self._update_chips()
        self._update_search()
        self._update_comparison()

    def _update_chips(self):
        for w in self._chips_frame.winfo_children():
            w.destroy()
        if not self._sel:
            ctk.CTkLabel(self._chips_frame,
                         text="Aucun aliment sélectionné — cliquez dans la liste",
                         font=ctk.CTkFont(size=11), text_color=T["tx3"]).pack(side="left")
            return
        for i, alim in enumerate(self._sel):
            color = self.COLS[i % len(self.COLS)]
            chip  = ctk.CTkFrame(self._chips_frame,
                                 fg_color=tint_low(color), corner_radius=16)
            chip.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(chip, text=alim['nom'][:22],
                         font=ctk.CTkFont(size=11),
                         text_color=color).pack(side="left", padx=(10, 4), pady=4)
            ctk.CTkButton(chip, text="×", width=20, height=20,
                          fg_color="transparent", hover_color=T["err_bg"],
                          text_color=T["err"], corner_radius=10,
                          font=ctk.CTkFont(size=12),
                          command=lambda aid=alim['id']: self._remove(aid)).pack(
                side="left", padx=(0, 4))

    # ── Tableau comparatif ───────────────────────────────────────

    def _update_comparison(self):
        for w in self._body.winfo_children():
            w.destroy()

        if len(self._sel) < 2:
            ctk.CTkLabel(self._body,
                         text="Sélectionnez au moins 2 aliments pour afficher la comparaison.",
                         font=ctk.CTkFont(size=13), text_color=T["tx2"],
                         justify="center").pack(pady=50)
            return

        n      = len(self._sel)
        COL_W  = max(110, (480 - 130) // n)

        tbl = ctk.CTkFrame(self._body, fg_color=T["bg_card"], corner_radius=14)
        tbl.pack(fill="x", pady=(0, 12))
        for ci in range(n + 1):
            tbl.grid_columnconfigure(ci, weight=0 if ci == 0 else 1)

        # En-tête colonnes
        hdr = ctk.CTkFrame(tbl, fg_color=T["bg_el"], corner_radius=8)
        hdr.grid(row=0, column=0, columnspan=n + 1,
                 padx=10, pady=(10, 4), sticky="ew")
        for ci in range(n + 1):
            hdr.grid_columnconfigure(ci, weight=0 if ci == 0 else 1)

        ctk.CTkLabel(hdr, text="Nutriment",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=T["tx2"], width=130, anchor="w").grid(
            row=0, column=0, padx=10, pady=8, sticky="w")
        for ci, alim in enumerate(self._sel):
            ctk.CTkLabel(hdr, text=alim['nom'][:18],
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=self.COLS[ci % len(self.COLS)],
                         width=COL_W, anchor="center").grid(
                row=0, column=ci + 1, padx=6, pady=8)

        # Lignes nutriments
        for ri, (label, key, unit) in enumerate(self.NUTRIENTS):
            bg  = "transparent" if ri % 2 == 0 else T["bg_row"]
            row = ctk.CTkFrame(tbl, fg_color=bg, corner_radius=6)
            row.grid(row=ri + 1, column=0, columnspan=n + 1,
                     padx=10, pady=1, sticky="ew")
            for ci in range(n + 1):
                row.grid_columnconfigure(ci, weight=0 if ci == 0 else 1)

            ctk.CTkLabel(row, text=label,
                         font=ctk.CTkFont(size=11), text_color=T["tx2"],
                         width=130, anchor="w").grid(
                row=0, column=0, padx=10, pady=6, sticky="w")

            # Nutri-Score : traitement spécial
            if key == "_ns":
                for ci, alim in enumerate(self._sel):
                    ns_letter, ns_color = db.calc_nutri_score(alim)
                    ctk.CTkLabel(row,
                                 text=f"  {ns_letter}  ",
                                 font=ctk.CTkFont(size=13, weight="bold"),
                                 text_color=ns_color,
                                 fg_color=tint_low(ns_color),
                                 corner_radius=6).grid(
                        row=0, column=ci + 1, padx=6, pady=4)
                continue

            # Valeurs numériques
            raw = []
            for alim in self._sel:
                try:
                    raw.append(float(alim.get(key, 0) or 0))
                except (TypeError, ValueError):
                    raw.append(0.0)

            max_val = max(raw) if any(v > 0 for v in raw) else 1.0

            for ci, val in enumerate(raw):
                col_color = self.COLS[ci % len(self.COLS)]
                is_max    = (val == max_val and max_val > 0)

                cell = ctk.CTkFrame(row, fg_color="transparent")
                cell.grid(row=0, column=ci + 1, padx=6, pady=(4, 2))

                disp = f"{int(val)}" if key == "ig" else (
                    f"{val:.1f}" if val != int(val) else str(int(val)))
                ctk.CTkLabel(cell,
                             text=f"{disp} {unit}".strip(),
                             font=ctk.CTkFont(size=12,
                                              weight="bold" if is_max else "normal"),
                             text_color=col_color if is_max else T["tx1"],
                             width=COL_W, anchor="center").pack()

                if max_val > 0:
                    pb = ctk.CTkProgressBar(cell, height=4, width=COL_W - 24,
                                            progress_color=col_color,
                                            fg_color=T["bg_el"])
                    pb.pack(pady=(1, 4))
                    pb.set(val / max_val)
