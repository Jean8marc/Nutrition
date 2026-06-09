"""
NutriTrack Pro — Recettes (v2 complète)
Gestion complète : unités culinaires, coefficients de cuisson,
étapes détaillées, tags régime, allergènes, difficulté, coût.
"""
import os, sys
import customtkinter as ctk
from tkinter import messagebox
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import database as db
from colors import tint_low
from theme import T

# ── Couleurs par catégorie ────────────────────────────────────────
CAT_COLORS = {
    "Petit-déjeuner": T["lip"], "Déjeuner": T["blue"],
    "Dîner": T["vio"], "Collation": T["ac"],
    "Plat principal": T["blue"], "Dessert": T["cal"],
    "Entrée": T["ac"], "Soupe": "#f97316",
    "Sauce": "#06b6d4", "Boisson": "#14b8a6",
}
CAT_ICONS = {
    "Petit-déjeuner":"🌅","Déjeuner":"☀️","Dîner":"🌙",
    "Collation":"🍎","Plat principal":"🍽️","Dessert":"🍰",
    "Entrée":"🥗","Soupe":"🍲","Sauce":"🫙","Boisson":"🥤",
}
CATEGORIES = list(CAT_ICONS.keys())
DIFF_COLORS = {"Facile":T["ac"],"Moyen":T["lip"],"Difficile":T["err"]}
COUT_LABELS = {"€":"Économique","€€":"Moyen","€€€":"Gastronomique"}


class RecettesPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=T["bg_app"], corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=28, pady=(28,0), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="👨‍🍳  Recettes",
                     font=ctk.CTkFont(family="Helvetica", size=26, weight="bold"),
                     text_color=T["tx1"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header,
                     text="Recettes complètes avec étapes, unités culinaires et calcul nutritionnel",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).grid(
            row=1, column=0, sticky="w", pady=(2,0))

        ctk.CTkButton(header, text="＋  Nouvelle recette",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000", height=38, width=200, corner_radius=8,
                      command=self._open_add).grid(row=0, column=1, rowspan=2, sticky="e")

        # Barre filtres
        fbar = ctk.CTkFrame(self, fg_color="transparent")
        fbar.grid(row=1, column=0, padx=28, pady=14, sticky="ew")

        self.search_var = ctk.StringVar()
        s = ctk.CTkEntry(fbar, textvariable=self.search_var,
                         placeholder_text="🔍   Rechercher…",
                         width=280, height=36,
                         fg_color=T["bg_card"], border_color=T["bg_hl"],
                         font=ctk.CTkFont(size=13))
        s.pack(side="left", padx=(0,10))
        s.bind("<KeyRelease>", lambda _: self.refresh())

        self._favori_only = False
        self._fav_btn = ctk.CTkButton(
            fbar, text="☆  Favoris",
            font=ctk.CTkFont(size=12),
            fg_color=T["bg_el"], hover_color=T["bg_hl"],
            text_color=T["lip"], height=36, width=110, corner_radius=8,
            command=self._toggle_favori_filter)
        self._fav_btn.pack(side="left", padx=(0, 10))

        self._faisable_only = False
        self._faisable_btn = ctk.CTkButton(
            fbar, text="✅  Faisables",
            font=ctk.CTkFont(size=12),
            fg_color=T["bg_el"], hover_color=T["bg_hl"],
            text_color=T["ac"], height=36, width=120, corner_radius=8,
            command=self._toggle_faisable_filter)
        self._faisable_btn.pack(side="left", padx=(0, 10))

        self.count_lbl = ctk.CTkLabel(fbar, text="",
                                       font=ctk.CTkFont(size=12), text_color=T["tx2"])
        self.count_lbl.pack(side="right")

        # Grille
        self.grid_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=T["bg_el"],
            scrollbar_button_hover_color=T["bg_hl"])
        self.grid_frame.grid(row=2, column=0, padx=28, pady=(0,28), sticky="nsew")
        for c in range(3):
            self.grid_frame.grid_columnconfigure(c, weight=1)

        self.refresh()

    def _toggle_favori_filter(self):
        self._favori_only = not self._favori_only
        if self._favori_only:
            self._fav_btn.configure(text="⭐  Favoris", fg_color="#2d2200")
        else:
            self._fav_btn.configure(text="☆  Favoris", fg_color=T["bg_el"])
        self.refresh()

    def _toggle_faisable_filter(self):
        self._faisable_only = not self._faisable_only
        if self._faisable_only:
            self._faisable_btn.configure(fg_color=T["ac_bg"],
                                          text_color=T["ac"])
        else:
            self._faisable_btn.configure(fg_color=T["bg_el"],
                                          text_color=T["ac"])
        self.refresh()

    def refresh(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        recettes = db.get_recettes(self.search_var.get(), favori_only=self._favori_only)

        uid = db.get_current_user_id()
        stock = db.get_stock() if uid else []
        if stock:
            for r in recettes:
                r['_stock_result'] = db.check_recette_faisable(r['id'])
        else:
            for r in recettes:
                r['_stock_result'] = None

        if self._faisable_only and stock:
            recettes = [r for r in recettes if r['_stock_result'] and r['_stock_result']['faisable']]

        self.count_lbl.configure(text=f"{len(recettes)} recette(s)")
        if not recettes:
            ctk.CTkLabel(self.grid_frame,
                         text="Aucune recette\n\nCliquez sur « + Nouvelle recette » pour commencer",
                         text_color=T["tx2"], font=ctk.CTkFont(size=14),
                         justify="center").grid(row=0, column=0, columnspan=3, pady=60)
            return
        for i, r in enumerate(recettes):
            self._make_card(r, i//3, i%3)

    def _make_card(self, r, row, col):
        nutrition = db.calc_recette_nutrition(r['id'])
        pp   = nutrition['par_portion']
        cat  = r.get('categorie', 'Plat principal')
        col_c = CAT_COLORS.get(cat, T["tx2"])
        icon  = CAT_ICONS.get(cat, "🍽️")
        diff  = r.get('difficulte', 'Facile')
        cout  = r.get('cout', '€')
        tags  = r.get('tags_regime', '') or ''
        etapes = db.get_recette_etapes(r['id'])
        ings   = db.get_recette_ingredients(r['id'])

        card = ctk.CTkFrame(self.grid_frame, fg_color=T["bg_card"], corner_radius=14)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        # Ligne 1 : badges + bouton favori
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.grid(row=0, column=0, padx=12, pady=(12,4), sticky="ew")
        top_row.grid_columnconfigure(0, weight=1)

        badges = ctk.CTkFrame(top_row, fg_color="transparent")
        badges.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(badges, text=f"  {icon} {cat}  ",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=col_c, fg_color=tint_low(col_c),
                     corner_radius=6).pack(side="left", padx=(0,4))
        ctk.CTkLabel(badges, text=f"  {diff}  ",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=DIFF_COLORS.get(diff,T["tx2"]),
                     fg_color=tint_low(DIFF_COLORS.get(diff,T["tx2"])),
                     corner_radius=6).pack(side="left", padx=(0,4))
        ctk.CTkLabel(badges, text=f"  {cout}  ",
                     font=ctk.CTkFont(size=10),
                     text_color=T["lip"],
                     fg_color=tint_low(T["lip"]),
                     corner_radius=6).pack(side="left")

        is_fav = bool(r.get('favori'))
        fav_btn = ctk.CTkButton(
            top_row,
            text="⭐" if is_fav else "☆",
            width=28, height=28, corner_radius=6,
            fg_color="#2d2200" if is_fav else "transparent",
            hover_color="#2d2200",
            font=ctk.CTkFont(size=14),
            command=lambda rid=r['id']: self._toggle_fav(rid))
        fav_btn.grid(row=0, column=1, sticky="e")

        # Titre
        ctk.CTkLabel(card, text=r['nom'],
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T["tx1"], anchor="w",
                     wraplength=240).grid(row=1, column=0, padx=14, pady=(2,2), sticky="w")

        if r.get('description'):
            ctk.CTkLabel(card, text=r['description'],
                         font=ctk.CTkFont(size=11), text_color=T["tx2"],
                         anchor="w", wraplength=240, justify="left").grid(
                row=2, column=0, padx=14, pady=(0,6), sticky="w")

        # Tags régime
        if tags:
            tag_list = [t.strip() for t in tags.split(',') if t.strip()][:3]
            tag_row = ctk.CTkFrame(card, fg_color="transparent")
            tag_row.grid(row=3, column=0, padx=12, pady=(0,4), sticky="w")
            for t in tag_list:
                ctk.CTkLabel(tag_row, text=f" {t} ",
                             font=ctk.CTkFont(size=9),
                             text_color=T["ac"],
                             fg_color=tint_low(T["ac"]),
                             corner_radius=4).pack(side="left", padx=(0,3))

        # Bloc nutritionnel
        nf = ctk.CTkFrame(card, fg_color=T["bg_el"], corner_radius=10)
        nf.grid(row=4, column=0, padx=12, pady=(0,6), sticky="ew")
        for j in range(4):
            nf.grid_columnconfigure(j, weight=1)

        nutri = [
            (f"{pp['calories']}", "kcal",  T["tx1"]),
            (f"{pp['proteines']}g","Prot.",T["ac"]),
            (f"{pp['glucides']}g", "Gluc.",T["blue"]),
            (f"{pp['lipides']}g",  "Lip.", T["lip"]),
        ]
        for j,(val,lbl,c2) in enumerate(nutri):
            nb = ctk.CTkFrame(nf, fg_color="transparent")
            nb.grid(row=0, column=j, padx=4, pady=8)
            ctk.CTkLabel(nb, text=val,
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=c2).pack()
            ctk.CTkLabel(nb, text=lbl,
                         font=ctk.CTkFont(size=10),
                         text_color=T["tx2"]).pack()

        poids_p = nutrition.get('poids_par_portion_g', 0)
        ctk.CTkLabel(nf,
                     text=f"par portion  •  ≈ {int(poids_p)} g/portion",
                     font=ctk.CTkFont(size=9), text_color=T["tx3"]).grid(
            row=1, column=0, columnspan=4, pady=(0,6))

        # Temps + infos
        meta = ctk.CTkFrame(card, fg_color="transparent")
        meta.grid(row=5, column=0, padx=14, pady=(0,4), sticky="ew")
        meta.grid_columnconfigure(0, weight=1)

        temps_total = (r.get('temps_prep') or 0) + (r.get('temps_cuisson') or 0)
        ctk.CTkLabel(meta,
                     text=f"⏱ {r.get('temps_prep',0)}' prép.  +  🔥 {r.get('temps_cuisson',0)}' cuisson  =  {temps_total}'",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(meta,
                     text=f"  {len(ings)} ingréd.  •  {len(etapes)} étape(s)  •  {r.get('portions',1)} portion(s)",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).grid(row=1, column=0, sticky="w")

        if r.get('type_cuisson'):
            ctk.CTkLabel(meta, text=f"🍳 {r['type_cuisson']}",
                         font=ctk.CTkFont(size=10), text_color=T["tx2"]).grid(
                row=2, column=0, sticky="w")

        # Badge stock faisabilité
        stock_result = r.get('_stock_result')
        if stock_result is None:
            badge_txt = '— Stock non géré'
            badge_col = T['tx3']
            badge_bg  = T['bg_el']
        elif stock_result['faisable']:
            badge_txt = '✅  Faisable'
            badge_col = T['ac']
            badge_bg  = T['ac_bg']
        else:
            n = len(stock_result['manquants'])
            badge_txt = f"⚠️  {n} ingrédient(s) manquant(s)"
            badge_col = T['cal']
            badge_bg  = T['bg_el']

        stock_badge = ctk.CTkLabel(card, text=badge_txt,
                                    font=ctk.CTkFont(size=11),
                                    text_color=badge_col,
                                    fg_color=badge_bg,
                                    corner_radius=6)
        stock_badge.grid(row=6, column=0, padx=14, pady=(2, 4), sticky='w')

        if stock_result and not stock_result['faisable']:
            manquants_txt = '\n'.join(
                f"  • {m['nom']} : {m['qte_stock']}g dispo / {m['qte_requise']}g requis"
                for m in stock_result['manquants']
            )
            stock_badge.bind('<Enter>', lambda e, t=manquants_txt: self._show_tooltip(e, t))
            stock_badge.bind('<Leave>', lambda e: self._hide_tooltip())

        # Boutons
        bf = ctk.CTkFrame(card, fg_color="transparent")
        bf.grid(row=7, column=0, padx=12, pady=(4,12), sticky="ew")
        ctk.CTkButton(bf, text="📖  Voir / Modifier",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=30, font=ctk.CTkFont(size=12), corner_radius=6,
                      command=lambda rec=r: self._open_edit(rec)).pack(side="left", padx=(0,6))
        ctk.CTkButton(bf, text="⚖️  Adapter",
                      fg_color=T["blue_d"], hover_color=T["blue_dm"],
                      height=30, font=ctk.CTkFont(size=12), corner_radius=6,
                      command=lambda rec=r: ScaleDialog(self, rec)).pack(side="left", padx=(0,6))
        ctk.CTkButton(bf, text="🗑", fg_color=T["bg_el"], hover_color=T["err_bg"],
                      height=30, width=34, font=ctk.CTkFont(size=12), corner_radius=6,
                      command=lambda rec=r: self._confirm_delete(rec)).pack(side="left")

    def _show_tooltip(self, event, text: str):
        self._tooltip = ctk.CTkToplevel(self)
        self._tooltip.overrideredirect(True)
        self._tooltip.configure(fg_color=T['bg_card'])
        ctk.CTkLabel(self._tooltip, text=text,
                     font=ctk.CTkFont(size=11),
                     text_color=T['tx1'],
                     justify='left').pack(padx=10, pady=8)
        x = event.widget.winfo_rootx() + 10
        y = event.widget.winfo_rooty() + 24
        self._tooltip.geometry(f"+{x}+{y}")

    def _hide_tooltip(self):
        if hasattr(self, '_tooltip') and self._tooltip.winfo_exists():
            self._tooltip.destroy()

    def _toggle_fav(self, rid: int):
        db.toggle_recette_favori(rid)
        self.refresh()

    def _open_add(self):
        RecetteDialog(self, None, self.refresh)

    def _open_edit(self, r):
        RecetteDialog(self, r, self.refresh)

    def _confirm_delete(self, r):
        if messagebox.askyesno("Supprimer",
                               f"Supprimer « {r['nom']} » ?", parent=self):
            db.delete_recette(r['id'])
            self.refresh()


# ─────────────────────── Dialogue Recette complet ────────────────────────────

class RecetteDialog(ctk.CTkToplevel):
    def __init__(self, parent, recette, callback):
        super().__init__(parent)
        self.recette  = recette
        self.callback = callback
        self.ings     = []
        self.etapes   = []
        self.title("Modifier la recette" if recette else "Nouvelle recette")
        self.geometry("760x860")
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()
        self._build()
        if recette:
            self._populate()

    # ── Build ─────────────────────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(self,
                     text="Modifier la recette" if self.recette else "Nouvelle recette",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=T["tx1"]).pack(padx=24, pady=(20,4), anchor="w")

        # Onglets
        tabs = ctk.CTkTabview(self, fg_color=T["bg_card"],
                               segmented_button_fg_color=T["bg_el"],
                               segmented_button_selected_color=T["ac"],
                               segmented_button_selected_hover_color=T["ac_d"],
                               segmented_button_unselected_hover_color=T["bg_hl"],
                               text_color=T["tx1"])
        tabs.pack(fill="both", expand=True, padx=16, pady=4)

        t1 = tabs.add("📋  Infos générales")
        t2 = tabs.add("🥑  Ingrédients")
        t3 = tabs.add("👨‍🍳  Étapes")
        t4 = tabs.add("⚙️  Avancé")

        self._build_tab_infos(t1)
        self._build_tab_ingredients(t2)
        self._build_tab_etapes(t3)
        self._build_tab_avance(t4)

        # Boutons
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(padx=24, pady=(6,18), fill="x")
        ctk.CTkButton(bf, text="Annuler",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=40, width=120, corner_radius=8,
                      command=self.destroy).pack(side="left")
        ctk.CTkButton(bf, text="✔  Enregistrer la recette",
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000", height=40, width=220,
                      corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._save).pack(side="right")

    # ── Onglet 1 : Infos ──────────────────────────────────────────

    def _build_tab_infos(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                         scrollbar_button_color=T["bg_el"])
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure((0,1), weight=1)

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

        def combo(label, key, r, col, opts, span=1, default=None):
            ctk.CTkLabel(scroll, text=label, font=ctk.CTkFont(size=12),
                         text_color=T["tx2"]).grid(
                row=r*2, column=col, columnspan=span, padx=6, pady=(10,2), sticky="w")
            var = ctk.StringVar(value=default or opts[0])
            ctk.CTkOptionMenu(scroll, variable=var, values=opts,
                              fg_color=T["bg_el"], button_color=T["bg_hl"],
                              height=36, font=ctk.CTkFont(size=12)).grid(
                row=r*2+1, column=col, columnspan=span, padx=6, sticky="ew")
            self.vars[key] = var

        entry("Nom de la recette *",       "nom",         0, span=2)
        entry("Description courte",        "description", 1, span=2,
              ph="Ex : Bol protéiné complet aux légumes de saison")
        combo("Catégorie",                 "categorie",   2, 0, CATEGORIES, span=2)
        entry("Temps de préparation (min)","temps_prep",  3, 0, ph="15")
        entry("Temps de cuisson (min)",    "temps_cuisson",3, 1, ph="20")
        entry("Nombre de portions",        "portions",    4, 0, ph="2")
        combo("Difficulté",                "difficulte",  4, 1,
              ["Facile","Moyen","Difficile"])
        combo("Coût estimé",               "cout",        5, 0,
              ["€","€€","€€€"],
              span=1)
        combo("Type de cuisson principal", "type_cuisson",5, 1,
              db.TYPES_CUISSON, span=1)
        entry("Température (°C, si four)","temperature",  6, 0, ph="180")
        entry("Conservation",             "conservation", 6, 1,
              ph="Ex : 3 jours au réfrigérateur")
        entry("Astuce du chef",           "astuce",       7, span=2,
              ph="Ex : Faire mariner la viande 30 min au préalable")
        entry("Notes supplémentaires",    "notes",        8, span=2)

    # ── Onglet 2 : Ingrédients ────────────────────────────────────

    def _build_tab_ingredients(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # Aide contextuelle unités
        aide = ctk.CTkFrame(parent, fg_color=T["bg_el"], corner_radius=8)
        aide.grid(row=0, column=0, padx=4, pady=(4,6), sticky="ew")
        ctk.CTkLabel(aide,
                     text="💡  CAS = Cuillère à Soupe (~15g)  ·  CAC = Cuillère à Café (~5g)  "
                          "·  pincée ≈ 0,5g  ·  verre ≈ 200ml  ·  tasse ≈ 250ml",
                     font=ctk.CTkFont(size=10), text_color=T["tx2"]).pack(
            padx=12, pady=8)

        # Formulaire ajout ingrédient
        add_card = ctk.CTkFrame(parent, fg_color=T["bg_el"], corner_radius=10)
        add_card.grid(row=1, column=0, padx=4, pady=(0,6), sticky="ew")
        add_card.grid_columnconfigure(0, weight=1)

        row1 = ctk.CTkFrame(add_card, fg_color="transparent")
        row1.pack(padx=10, pady=(10,4), fill="x")
        row1.grid_columnconfigure(0, weight=1)

        aliments = db.get_aliments()
        self._alim_list = aliments
        names = [f"{a['nom']}" for a in aliments]

        self._ing_name_var = ctk.StringVar()
        self._ing_combo = ctk.CTkComboBox(
            row1, variable=self._ing_name_var, values=names,
            height=34, fg_color=T["bg_el"], border_color=T["bg_hl"],
            font=ctk.CTkFont(size=12))
        self._ing_combo.grid(row=0, column=0, padx=(0,8), sticky="ew")

        row2 = ctk.CTkFrame(add_card, fg_color="transparent")
        row2.pack(padx=10, pady=(0,10), fill="x")

        # Quantité
        ctk.CTkLabel(row2, text="Qté", font=ctk.CTkFont(size=11),
                     text_color=T["tx2"]).pack(side="left")
        self._qty_var = ctk.StringVar(value="100")
        ctk.CTkEntry(row2, textvariable=self._qty_var, width=70, height=32,
                     fg_color=T["bg_card"], border_color=T["bg_hl"],
                     font=ctk.CTkFont(size=13)).pack(side="left", padx=(4,8))

        # Unité
        ctk.CTkLabel(row2, text="Unité", font=ctk.CTkFont(size=11),
                     text_color=T["tx2"]).pack(side="left")
        self._unite_var = ctk.StringVar(value="g")
        ctk.CTkOptionMenu(row2, variable=self._unite_var,
                          values=db.UNITS_CULINAIRES,
                          fg_color=T["bg_el"], button_color=T["bg_hl"],
                          height=32, width=100,
                          font=ctk.CTkFont(size=12)).pack(side="left", padx=(4,8))

        # État
        ctk.CTkLabel(row2, text="État", font=ctk.CTkFont(size=11),
                     text_color=T["tx2"]).pack(side="left")
        self._etat_var = ctk.StringVar(value="cru")
        ctk.CTkOptionMenu(row2, variable=self._etat_var,
                          values=["cru","cuit","blanchi","mariné","émincé","râpé","autres"],
                          fg_color=T["bg_el"], button_color=T["bg_hl"],
                          height=32, width=110,
                          font=ctk.CTkFont(size=12)).pack(side="left", padx=(4,8))

        # Coefficient cuisson
        ctk.CTkLabel(row2, text="Coeff.", font=ctk.CTkFont(size=11),
                     text_color=T["tx2"]).pack(side="left")
        self._coeff_var = ctk.StringVar(value="1.0")
        self._coeff_menu = ctk.CTkOptionMenu(
            row2,
            variable=self._coeff_var,
            values=[f"{k} ({v})" for k,v in db.COEFFICIENTS_CUISSON.items()],
            fg_color=T["bg_el"], button_color=T["bg_hl"],
            height=32, width=160,
            font=ctk.CTkFont(size=11),
            command=self._on_coeff_select)
        self._coeff_menu.pack(side="left", padx=(4,0))

        row3 = ctk.CTkFrame(add_card, fg_color="transparent")
        row3.pack(padx=10, pady=(0,10), fill="x")
        row3.grid_columnconfigure(0, weight=1)

        self._ing_notes_var = ctk.StringVar()
        ctk.CTkEntry(row3, textvariable=self._ing_notes_var, height=30,
                     placeholder_text="Note de préparation (ex: émincé finement, décongelé...)",
                     fg_color=T["bg_card"], border_color=T["bg_hl"],
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(0,8), sticky="ew")
        ctk.CTkButton(row3, text="＋ Ajouter",
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000", height=30, width=100,
                      font=ctk.CTkFont(size=12), corner_radius=6,
                      command=self._add_ing).grid(row=0, column=1)

        # Liste ingrédients
        self.ing_list = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                                scrollbar_button_color=T["bg_el"],
                                                height=280)
        self.ing_list.grid(row=2, column=0, padx=4, pady=0, sticky="nsew")
        self.ing_list.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        # Résumé nutritionnel ingrédients
        self._nutri_summary = ctk.CTkLabel(parent, text="",
                                            font=ctk.CTkFont(size=11),
                                            text_color=T["tx2"])
        self._nutri_summary.grid(row=3, column=0, padx=8, pady=(4,4), sticky="w")

    # ── Onglet 3 : Étapes ─────────────────────────────────────────

    def _build_tab_etapes(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # Aide
        aide = ctk.CTkFrame(parent, fg_color=T["bg_el"], corner_radius=8)
        aide.grid(row=0, column=0, padx=4, pady=(4,6), sticky="ew")
        ctk.CTkLabel(aide,
                     text="📝  Décrivez chaque étape dans l'ordre. Indiquez les températures et durées.",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(
            padx=12, pady=8)

        # Formulaire ajout étape
        add_card = ctk.CTkFrame(parent, fg_color=T["bg_el"], corner_radius=10)
        add_card.grid(row=1, column=0, padx=4, pady=(0,6), sticky="ew")
        add_card.grid_columnconfigure(0, weight=1)

        row1 = ctk.CTkFrame(add_card, fg_color="transparent")
        row1.pack(padx=10, pady=(10,4), fill="x")
        row1.grid_columnconfigure(0, weight=1)

        self._etape_titre_var = ctk.StringVar()
        ctk.CTkEntry(row1, textvariable=self._etape_titre_var,
                     placeholder_text="Titre de l'étape (ex: Préparer la marinade)",
                     height=32, fg_color=T["bg_card"], border_color=T["bg_hl"],
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0,8), sticky="ew")

        row2 = ctk.CTkFrame(add_card, fg_color="transparent")
        row2.pack(padx=10, pady=(0,4), fill="x")
        row2.grid_columnconfigure(0, weight=1)

        self._etape_desc_var = ctk.StringVar()
        ctk.CTkEntry(row2, textvariable=self._etape_desc_var,
                     placeholder_text="Description détaillée de l'étape…",
                     height=60, fg_color=T["bg_card"], border_color=T["bg_hl"],
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0,8), sticky="ew")

        row3 = ctk.CTkFrame(add_card, fg_color="transparent")
        row3.pack(padx=10, pady=(0,10), fill="x")

        for label, var_name, width, ph in [
            ("⏱ Durée (min)", "_etape_duree_var", 60, "10"),
            ("🌡 Température (°C)", "_etape_temp_var", 60, "180"),
        ]:
            ctk.CTkLabel(row3, text=label, font=ctk.CTkFont(size=11),
                         text_color=T["tx2"]).pack(side="left")
            var = ctk.StringVar(value="0")
            setattr(self, var_name, var)
            ctk.CTkEntry(row3, textvariable=var, width=width, height=30,
                         placeholder_text=ph,
                         fg_color=T["bg_card"], border_color=T["bg_hl"],
                         font=ctk.CTkFont(size=12)).pack(side="left", padx=(4,12))

        ctk.CTkLabel(row3, text="Type", font=ctk.CTkFont(size=11),
                     text_color=T["tx2"]).pack(side="left")
        self._etape_type_var = ctk.StringVar(value="Préparation")
        ctk.CTkOptionMenu(row3, variable=self._etape_type_var,
                          values=["Préparation","Cuisson","Repos","Assemblage",
                                  "Marinade","Refroidissement","Service","Autre"],
                          fg_color=T["bg_el"], button_color=T["bg_hl"],
                          height=30, width=130,
                          font=ctk.CTkFont(size=11)).pack(side="left", padx=(4,8))

        ctk.CTkButton(row3, text="＋",
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000", height=30, width=50,
                      font=ctk.CTkFont(size=14), corner_radius=6,
                      command=self._add_etape).pack(side="left")

        # Liste étapes
        self.etape_list = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                                  scrollbar_button_color=T["bg_el"])
        self.etape_list.grid(row=2, column=0, padx=4, pady=0, sticky="nsew")
        self.etape_list.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

    # ── Onglet 4 : Avancé ─────────────────────────────────────────

    def _build_tab_avance(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                         scrollbar_button_color=T["bg_el"])
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure(0, weight=1)

        # Tags régime
        ctk.CTkLabel(scroll, text="🏷️  Tags régime alimentaire",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["tx1"]).grid(row=0, column=0, padx=6, pady=(12,4), sticky="w")
        ctk.CTkLabel(scroll, text="Cochez les régimes auxquels cette recette est adaptée :",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).grid(
            row=1, column=0, padx=6, pady=(0,6), sticky="w")

        tags_grid = ctk.CTkFrame(scroll, fg_color=T["bg_el"], corner_radius=10)
        tags_grid.grid(row=2, column=0, padx=6, pady=(0,12), sticky="ew")
        for j in range(4):
            tags_grid.grid_columnconfigure(j, weight=1)

        self._tag_vars = {}
        for i, tag in enumerate(db.TAGS_REGIME):
            var = ctk.BooleanVar(value=False)
            self._tag_vars[tag] = var
            ctk.CTkCheckBox(tags_grid, text=tag, variable=var,
                            font=ctk.CTkFont(size=11),
                            text_color=T["tx1"],
                            fg_color=T["ac"],
                            hover_color=T["ac_d"],
                            checkmark_color="#000").grid(
                row=i//4, column=i%4, padx=8, pady=6, sticky="w")

        # Allergènes
        ctk.CTkLabel(scroll, text="⚠️  Allergènes présents",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["tx1"]).grid(row=3, column=0, padx=6, pady=(12,4), sticky="w")

        allerg_grid = ctk.CTkFrame(scroll, fg_color=T["bg_el"], corner_radius=10)
        allerg_grid.grid(row=4, column=0, padx=6, pady=(0,12), sticky="ew")
        for j in range(4):
            allerg_grid.grid_columnconfigure(j, weight=1)

        self._allerg_vars = {}
        for i, allerg in enumerate(db.ALLERGENES_LISTE):
            var = ctk.BooleanVar(value=False)
            self._allerg_vars[allerg] = var
            ctk.CTkCheckBox(allerg_grid, text=allerg, variable=var,
                            font=ctk.CTkFont(size=11),
                            text_color=T["tx1"],
                            fg_color=T["lip"],
                            hover_color="#d97706",
                            checkmark_color="#000").grid(
                row=i//4, column=i%4, padx=8, pady=6, sticky="w")

    # ── Gestion ingrédients ───────────────────────────────────────

    def _on_coeff_select(self, val):
        """Extrait le coefficient numérique du label sélectionné."""
        import re
        m = re.search(r'\(([0-9.]+)\)', val)
        if m:
            self._coeff_var.set(m.group(1))

    def _find_aliment(self, name):
        for a in self._alim_list:
            if a['nom'] == name:
                return a
        for a in self._alim_list:
            if a['nom'].lower().startswith(name.lower()):
                return a
        return None

    def _add_ing(self):
        name = self._ing_name_var.get().strip()
        alim = self._find_aliment(name)
        if not alim:
            messagebox.showwarning("Introuvable",
                                   f"Aliment « {name} » non trouvé.", parent=self)
            return
        try:
            qty = float(self._qty_var.get().replace(',','.'))
        except ValueError:
            qty = 100.0

        coeff_str = self._coeff_var.get()
        try:
            import re
            m = re.search(r'([0-9.]+)', coeff_str)
            coeff = float(m.group(1)) if m else 1.0
        except:
            coeff = 1.0

        self.ings.append({
            'aliment_id':         alim['id'],
            'nom':                alim['nom'],
            'quantite':           qty,
            'unite_recette':      self._unite_var.get(),
            'etat':               self._etat_var.get(),
            'coefficient_cuisson':coeff,
            'notes_preparation':  self._ing_notes_var.get().strip(),
            'aliment':            alim,
        })
        self._ing_notes_var.set("")
        self._refresh_ing_list()

    def _refresh_ing_list(self):
        for w in self.ing_list.winfo_children():
            w.destroy()

        total_cal = 0.0
        for i, ing in enumerate(self.ings):
            row = ctk.CTkFrame(self.ing_list, fg_color=T["bg_el"], corner_radius=8)
            row.grid(row=i, column=0, pady=2, sticky="ew")
            row.grid_columnconfigure(1, weight=1)

            # Numéro
            ctk.CTkLabel(row, text=f"{i+1}.",
                         font=ctk.CTkFont(size=11), text_color=T["tx2"],
                         width=24).grid(row=0, column=0, padx=(8,4), pady=6)

            # Nom + infos
            alim = ing.get('aliment') or db.get_aliment_by_id(ing['aliment_id']) or {}
            unite = ing['unite_recette']
            qty   = ing['quantite']
            coeff = ing['coefficient_cuisson']

            # Calcul calorique pour cette ligne
            qte_g    = db.quantite_en_grammes(qty, unite, alim)
            qte_crue = qte_g / coeff if coeff else qte_g
            cal_line = round(float(alim.get('calories', 0) or 0) * qte_crue / 100, 1)
            total_cal += cal_line

            main_txt = f"{ing['nom']}"
            sub_txt  = (f"{qty} {unite}  •  état: {ing['etat']}  "
                        f"•  coeff: ×{coeff}"
                        f"  •  ≈{cal_line} kcal")
            if ing.get('notes_preparation'):
                sub_txt += f"  •  {ing['notes_preparation']}"

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
            ctk.CTkLabel(info, text=main_txt,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=T["tx1"], anchor="w").pack(anchor="w")
            ctk.CTkLabel(info, text=sub_txt,
                         font=ctk.CTkFont(size=10), text_color=T["tx2"],
                         anchor="w").pack(anchor="w")

            # Bouton supprimer
            ctk.CTkButton(row, text="✕", width=26, height=26,
                          fg_color="transparent", hover_color=T["err_bg"],
                          text_color=T["err"],
                          command=lambda idx=i: self._remove_ing(idx)).grid(
                row=0, column=2, padx=6)

        # Résumé
        try:
            portions = int(self.vars.get('portions', ctk.StringVar(value='2')).get() or 2)
        except:
            portions = 2
        self._nutri_summary.configure(
            text=f"Total estimé : ≈ {round(total_cal)} kcal  •  ≈ {round(total_cal/max(1,portions))} kcal/portion")

    def _remove_ing(self, idx):
        self.ings.pop(idx)
        self._refresh_ing_list()

    # ── Gestion étapes ────────────────────────────────────────────

    def _add_etape(self):
        desc = self._etape_desc_var.get().strip()
        if not desc:
            messagebox.showwarning("Champ requis",
                                   "La description de l'étape est obligatoire.", parent=self)
            return
        try:
            duree = int(self._etape_duree_var.get() or 0)
        except:
            duree = 0
        try:
            temp = int(self._etape_temp_var.get() or 0)
        except:
            temp = 0

        self.etapes.append({
            'titre':       self._etape_titre_var.get().strip(),
            'description': desc,
            'duree_min':   duree,
            'temperature': temp,
            'type_action': self._etape_type_var.get(),
        })
        self._etape_titre_var.set("")
        self._etape_desc_var.set("")
        self._etape_duree_var.set("0")
        self._etape_temp_var.set("0")
        self._refresh_etape_list()

    def _refresh_etape_list(self):
        for w in self.etape_list.winfo_children():
            w.destroy()

        TYPE_ICONS = {
            "Préparation":"✂️","Cuisson":"🔥","Repos":"⏳","Assemblage":"🔧",
            "Marinade":"🫙","Refroidissement":"❄️","Service":"🍽️","Autre":"📝",
        }
        for i, etape in enumerate(self.etapes):
            row = ctk.CTkFrame(self.etape_list, fg_color=T["bg_el"], corner_radius=8)
            row.grid(row=i, column=0, pady=2, sticky="ew")
            row.grid_columnconfigure(1, weight=1)

            icon = TYPE_ICONS.get(etape.get('type_action',''), '📝')
            ctk.CTkLabel(row, text=f"{icon}",
                         font=ctk.CTkFont(size=16), width=36).grid(
                row=0, column=0, padx=(10,4), pady=8)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

            titre = etape.get('titre') or f"Étape {i+1}"
            ctk.CTkLabel(info, text=f"{i+1}. {titre}",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=T["tx1"], anchor="w").pack(anchor="w")
            ctk.CTkLabel(info, text=etape['description'],
                         font=ctk.CTkFont(size=11), text_color=T["tx2"],
                         anchor="w", wraplength=500, justify="left").pack(anchor="w")

            meta_parts = []
            if etape.get('duree_min'):
                meta_parts.append(f"⏱ {etape['duree_min']} min")
            if etape.get('temperature'):
                meta_parts.append(f"🌡 {etape['temperature']}°C")
            if etape.get('type_action'):
                meta_parts.append(etape['type_action'])
            if meta_parts:
                ctk.CTkLabel(info, text="  ·  ".join(meta_parts),
                             font=ctk.CTkFont(size=10), text_color=T["blue"]).pack(anchor="w")

            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.grid(row=0, column=2, padx=6)
            if i > 0:
                ctk.CTkButton(btn_frame, text="▲", width=26, height=22,
                              fg_color=T["bg_hl"], hover_color=T["bg_hl"],
                              font=ctk.CTkFont(size=10),
                              command=lambda idx=i: self._move_etape(idx,-1)).pack(pady=1)
            ctk.CTkButton(btn_frame, text="✕", width=26, height=22,
                          fg_color="transparent", hover_color=T["err_bg"],
                          text_color=T["err"],
                          command=lambda idx=i: self._remove_etape(idx)).pack(pady=1)
            if i < len(self.etapes)-1:
                ctk.CTkButton(btn_frame, text="▼", width=26, height=22,
                              fg_color=T["bg_hl"], hover_color=T["bg_hl"],
                              font=ctk.CTkFont(size=10),
                              command=lambda idx=i: self._move_etape(idx,1)).pack(pady=1)

    def _remove_etape(self, idx):
        self.etapes.pop(idx)
        self._refresh_etape_list()

    def _move_etape(self, idx, direction):
        new_idx = idx + direction
        if 0 <= new_idx < len(self.etapes):
            self.etapes[idx], self.etapes[new_idx] = self.etapes[new_idx], self.etapes[idx]
            self._refresh_etape_list()

    # ── Populate & Save ───────────────────────────────────────────

    def _populate(self):
        # Infos
        for key, var in self.vars.items():
            v = self.recette.get(key, '') or ''
            var.set(str(v))

        # Ingrédients
        raw_ings = db.get_recette_ingredients(self.recette['id'])
        self.ings = [{
            'aliment_id':          i['aliment_id'],
            'nom':                 i['nom'],
            'quantite':            i['quantite'],
            'unite_recette':       i.get('unite_recette', 'g') or 'g',
            'etat':                i.get('etat', 'cru') or 'cru',
            'coefficient_cuisson': i.get('coefficient_cuisson', 1.0) or 1.0,
            'notes_preparation':   i.get('notes_preparation', '') or '',
            'aliment':             db.get_aliment_by_id(i['aliment_id']) or {},
        } for i in raw_ings]
        self._refresh_ing_list()

        # Étapes
        self.etapes = [dict(e) for e in db.get_recette_etapes(self.recette['id'])]
        self._refresh_etape_list()

        # Tags régime
        tags_str = self.recette.get('tags_regime', '') or ''
        active_tags = {t.strip() for t in tags_str.split(',') if t.strip()}
        for tag, var in self._tag_vars.items():
            var.set(tag in active_tags)

        # Allergènes
        allerg_str = self.recette.get('allergenes', '') or ''
        active_allerg = {a.strip() for a in allerg_str.split(',') if a.strip()}
        for allerg, var in self._allerg_vars.items():
            var.set(allerg in active_allerg)

    def _save(self):
        data = {k: v.get().strip() for k, v in self.vars.items()}
        if not data.get('nom'):
            messagebox.showwarning("Champ requis", "Le nom est obligatoire.", parent=self)
            return

        # Tags et allergènes
        data['tags_regime'] = ', '.join(t for t,v in self._tag_vars.items() if v.get())
        data['allergenes']  = ', '.join(a for a,v in self._allerg_vars.items() if v.get())

        if self.recette:
            db.update_recette(self.recette['id'], data, self.ings, self.etapes)
        else:
            db.add_recette(data, self.ings, self.etapes)

        self.callback()
        self.destroy()


# ─────────────────────── Dialogue mise à l'échelle ───────────────────────────

class ScaleDialog(ctk.CTkToplevel):
    """Affiche les quantités d'ingrédients recalculées pour N portions."""

    def __init__(self, parent, recette: dict):
        super().__init__(parent)
        self._r    = recette
        self._base = max(1, int(recette.get('portions') or 1))
        self.title(f"⚖️  Adapter — {recette.get('nom','')}")
        self.geometry("440x520")
        self.resizable(False, False)
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text=f"⚖️  Mise à l'échelle",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T["tx1"]).pack(padx=20, pady=(16, 2), anchor="w")
        ctk.CTkLabel(self, text=f"Recette de base : {self._base} portion(s)",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(padx=20, anchor="w")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=20, pady=12, fill="x")
        ctk.CTkLabel(row, text="Nombre de portions souhaité :",
                     font=ctk.CTkFont(size=12), text_color=T["tx1"]).pack(side="left")
        self._n_var = ctk.StringVar(value=str(self._base))
        e = ctk.CTkEntry(row, textvariable=self._n_var, width=70, height=32,
                         fg_color=T["bg_el"], border_color=T["bg_hl"],
                         font=ctk.CTkFont(size=13))
        e.pack(side="left", padx=(10, 0))
        ctk.CTkButton(row, text="Calculer", width=90, height=32,
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000", font=ctk.CTkFont(size=12, weight="bold"),
                      command=self._refresh).pack(side="left", padx=(8, 0))

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=T["bg_app"],
                                               scrollbar_button_color=T["bg_el"])
        self._scroll.pack(padx=12, pady=(0, 12), fill="both", expand=True)
        self._scroll.grid_columnconfigure((0, 1), weight=1)

        self._refresh()

    def _refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        try:
            n = max(0.1, float(self._n_var.get().replace(",", ".")))
        except ValueError:
            return
        factor = n / self._base
        ings = db.get_recette_ingredients(self._r['id'])
        for i, ing in enumerate(ings):
            alim = db.get_aliment_by_id(ing['aliment_id']) or {}
            qte_scaled = round(float(ing.get('quantite') or 0) * factor, 1)
            unite = ing.get('unite_recette') or 'g'
            name  = alim.get('nom', f"Aliment #{ing['aliment_id']}")
            bg = T["bg_card"] if i % 2 == 0 else T["bg_row"]
            fr = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=6)
            fr.grid(row=i, column=0, columnspan=2, sticky="ew", pady=2, padx=4)
            fr.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(fr, text=name, font=ctk.CTkFont(size=12),
                         text_color=T["tx1"], anchor="w").grid(
                row=0, column=0, padx=10, pady=6, sticky="w")
            ctk.CTkLabel(fr, text=f"{qte_scaled} {unite}",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=T["ac"]).grid(row=0, column=1, padx=10, sticky="e")
