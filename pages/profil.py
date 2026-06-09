"""
NutriTrack Pro — Profil utilisateur avec onglets (v2)
Onglets : Informations · Suivi & Historique · Bilan
"""
import os, sys
from datetime import datetime, date
import customtkinter as ctk
from tkinter import messagebox, filedialog
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import database as db
from colors import tint_low
from theme import T

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MPL_OK = True
except ImportError:
    MPL_OK = False

ACTIVITE_OPTS    = list(db.ACTIVITE_LABELS.keys())
ACTIVITE_DISPLAY = list(db.ACTIVITE_LABELS.values())
OBJECTIF_OPTS    = ["perte_poids", "maintien", "prise_masse"]
OBJECTIF_DISPLAY = ["🔥 Perte de poids", "⚖️  Maintien", "💪 Prise de masse"]
SEXE_OPTS        = ["H", "F"]
SEXE_DISPLAY     = ["Homme", "Femme"]
FREQ_OPTS        = [("tous","Tous les jours"), ("hebdo","Hebdomadaire"),
                    ("quinzaine","Quinzaine"), ("mensuel","Mensuel")]


class ProfilPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=T["bg_app"], corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    def _build(self):
        # ── Entête avec info utilisateur ──────────────────────────
        self.header = ctk.CTkFrame(self, fg_color=T["bg_card"], corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_columnconfigure(1, weight=1)

        self.avatar_lbl = ctk.CTkLabel(self.header, text="",
                                        font=ctk.CTkFont(size=20, weight="bold"),
                                        width=54, height=54, corner_radius=27)
        self.avatar_lbl.grid(row=0, column=0, padx=(20,12), pady=14)

        self.user_name_lbl = ctk.CTkLabel(self.header, text="",
                                           font=ctk.CTkFont(size=20, weight="bold"),
                                           text_color=T["tx1"], anchor="w")
        self.user_name_lbl.grid(row=0, column=1, sticky="w")

        self.user_sub_lbl = ctk.CTkLabel(self.header, text="",
                                          font=ctk.CTkFont(size=12),
                                          text_color=T["tx2"], anchor="w")
        self.user_sub_lbl.grid(row=1, column=1, sticky="w", pady=(0,14))

        # Boutons entête
        btn_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        btn_frame.grid(row=0, column=2, rowspan=2, padx=20)

        ctk.CTkButton(btn_frame, text="💾  Sauvegarder DB",
                      fg_color=T["blue_d"], hover_color=T["blue_dm"],
                      height=32, width=150, corner_radius=8,
                      font=ctk.CTkFont(size=11),
                      command=self._export_backup).pack(pady=(0, 4))

        ctk.CTkButton(btn_frame, text="⇄  Changer de profil",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=32, width=150, corner_radius=8,
                      font=ctk.CTkFont(size=12),
                      command=self._switch_profile).pack()

        # ── Onglets ───────────────────────────────────────────────
        self.tabs = ctk.CTkTabview(self, fg_color=T["bg_app"],
                                    segmented_button_fg_color=T["bg_card"],
                                    segmented_button_selected_color=T["ac"],
                                    segmented_button_selected_hover_color=T["ac_d"],
                                    segmented_button_unselected_hover_color=T["bg_el"],
                                    text_color=T["tx1"])
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

        self.t_infos  = self.tabs.add("✏️  Informations")
        self.t_suivi  = self.tabs.add("📈  Suivi & Historique")
        self.t_bilan  = self.tabs.add("📊  Bilan")
        self.t_prog   = self.tabs.add("📋  Programmes")

        self._build_infos(self.t_infos)
        self._build_suivi(self.t_suivi)
        self._build_bilan(self.t_bilan)
        self._build_programmes(self.t_prog)

        self.refresh()

    # ── Onglet Informations ───────────────────────────────────────

    def _build_infos(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent",
                                         scrollbar_button_color=T["bg_el"])
        scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        scroll.grid_columnconfigure((0,1), weight=1)

        self.vars = {}

        def entry(label, key, r, col=0, span=2, ph=""):
            ctk.CTkLabel(scroll, text=label, font=ctk.CTkFont(size=12),
                         text_color=T["tx2"]).grid(
                row=r*2, column=col, columnspan=span, padx=8, pady=(10,2), sticky="w")
            var = ctk.StringVar()
            ctk.CTkEntry(scroll, textvariable=var, height=36,
                         placeholder_text=ph,
                         fg_color=T["bg_card"], border_color=T["bg_hl"],
                         font=ctk.CTkFont(size=13)).grid(
                row=r*2+1, column=col, columnspan=span, padx=8, sticky="ew")
            self.vars[key] = var

        def combo(label, key, r, col, opts_display, opts_keys, span=1):
            ctk.CTkLabel(scroll, text=label, font=ctk.CTkFont(size=12),
                         text_color=T["tx2"]).grid(
                row=r*2, column=col, columnspan=span, padx=8, pady=(10,2), sticky="w")
            idx = 0
            var = ctk.StringVar(value=opts_display[idx])
            ctk.CTkOptionMenu(scroll, variable=var, values=opts_display,
                              fg_color=T["bg_card"], button_color=T["bg_el"],
                              button_hover_color=T["bg_hl"],
                              height=36, font=ctk.CTkFont(size=12)).grid(
                row=r*2+1, column=col, columnspan=span, padx=8, sticky="ew")
            self.vars[key]            = var
            self.vars[key+"_keys"]    = opts_keys
            self.vars[key+"_display"] = opts_display

        entry("Prénom",             "prenom",         0, ph="Marie")
        entry("Nom",                "nom",            1, ph="Dupont")
        entry("Âge",                "age",            2, 0, 1, ph="30")
        combo("Sexe",               "sexe",           2, 1,
              SEXE_DISPLAY, SEXE_OPTS)
        entry("Poids actuel (kg)",  "poids",          3, 0, 1, ph="70")
        entry("Taille (cm)",        "taille",         3, 1, 1, ph="170")
        entry("Tour de taille (cm)","tour_de_taille", 4, 0, 1, ph="80")
        entry("Poids cible (kg)",   "poids_cible",    4, 1, 1, ph="65")
        combo("Niveau d'activité",  "activite",       5, 0,
              ACTIVITE_DISPLAY, ACTIVITE_OPTS, span=2)
        combo("Objectif",           "objectif",       6, 0,
              OBJECTIF_DISPLAY, OBJECTIF_OPTS, span=2)
        entry("Allergies / intolérances","allergies", 7, span=2,
              ph="ex. gluten, lactose")
        entry("Notes de santé",     "notes_sante",    8, span=2,
              ph="ex. diabète, hypertension")

        # ── Séparateur ────────────────────────────────────────────
        ctk.CTkFrame(scroll, height=1, fg_color=T["bg_el"]).grid(
            row=18, column=0, columnspan=2, padx=8, pady=(14, 0), sticky="ew")

        # ── Protéines dynamiques ──────────────────────────────────
        ctk.CTkLabel(scroll, text="💪  Objectif protéines dynamique",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["ac"]).grid(
            row=19, column=0, columnspan=2, padx=8, pady=(10, 2), sticky="w")
        ctk.CTkLabel(scroll,
                     text="Coefficient g/kg de poids (0 = calcul auto — 30 % des calories)",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).grid(
            row=20, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="w")

        sf = ctk.CTkFrame(scroll, fg_color="transparent")
        sf.grid(row=21, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
        sf.grid_columnconfigure(1, weight=1)

        self._coeff_var = ctk.DoubleVar(value=0.0)
        self._coeff_lbl = ctk.CTkLabel(sf, text="Auto",
                                       font=ctk.CTkFont(size=13, weight="bold"),
                                       text_color=T["ac"], width=72, anchor="e")
        self._coeff_lbl.grid(row=0, column=0, padx=(0, 8))
        ctk.CTkSlider(sf, from_=0, to=2.5, number_of_steps=25,
                      variable=self._coeff_var,
                      progress_color=T["ac"], button_color=T["ac"],
                      button_hover_color=T["ac_d"],
                      command=self._on_coeff_change).grid(row=0, column=1, sticky="ew")
        self._prot_preview = ctk.CTkLabel(sf, text="",
                                          font=ctk.CTkFont(size=11),
                                          text_color=T["tx2"], width=90, anchor="e")
        self._prot_preview.grid(row=0, column=2, padx=(8, 0))

        # ── Hydratation ───────────────────────────────────────────
        ctk.CTkFrame(scroll, height=1, fg_color=T["bg_el"]).grid(
            row=22, column=0, columnspan=2, padx=8, pady=(8, 0), sticky="ew")
        ctk.CTkLabel(scroll, text="💧  Objectif hydratation",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["blue"]).grid(
            row=23, column=0, columnspan=2, padx=8, pady=(10, 2), sticky="w")

        eau_row = ctk.CTkFrame(scroll, fg_color="transparent")
        eau_row.grid(row=24, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
        ctk.CTkLabel(eau_row, text="Objectif quotidien :",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).pack(side="left")
        self._eau_obj_var = ctk.StringVar(value="2000")
        ctk.CTkEntry(eau_row, textvariable=self._eau_obj_var, width=100, height=34,
                     fg_color=T["bg_card"], border_color=T["bg_hl"],
                     font=ctk.CTkFont(size=13)).pack(side="left", padx=8)
        ctk.CTkLabel(eau_row, text="ml / jour",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(side="left")

        # ── FC max ───────────────────────────────────────────────
        ctk.CTkFrame(scroll, height=1, fg_color=T["bg_el"]).grid(
            row=25, column=0, columnspan=2, padx=8, pady=(8, 0), sticky="ew")
        ctk.CTkLabel(scroll, text="❤️  Fréquence cardiaque maximale",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["err"]).grid(
            row=26, column=0, columnspan=2, padx=8, pady=(10, 2), sticky="w")

        fc_row = ctk.CTkFrame(scroll, fg_color="transparent")
        fc_row.grid(row=27, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
        ctk.CTkLabel(fc_row, text="FC max (bpm) :",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).pack(side="left")
        self._fc_max_var = ctk.StringVar(value="")
        ctk.CTkEntry(fc_row, textvariable=self._fc_max_var, width=100, height=34,
                     fg_color=T["bg_card"], border_color=T["bg_hl"],
                     font=ctk.CTkFont(size=13),
                     placeholder_text="auto").pack(side="left", padx=8)
        ctk.CTkLabel(fc_row, text="bpm  (laisser vide = 220 − âge)",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(side="left")

        ctk.CTkButton(scroll, text="💾  Enregistrer le profil",
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000", height=40, corner_radius=8,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._save_profil).grid(
            row=29, column=0, columnspan=2, padx=8, pady=(16, 8), sticky="ew")

    # ── Onglet Suivi ─────────────────────────────────────────────

    def _build_suivi(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        # Saisie nouvelle mesure
        add_card = ctk.CTkFrame(parent, fg_color=T["bg_card"], corner_radius=12)
        add_card.grid(row=0, column=0, padx=8, pady=(8,6), sticky="ew")
        add_card.grid_columnconfigure((0,1,2,3), weight=1)

        ctk.CTkLabel(add_card, text="➕  Nouvelle mesure",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["tx1"]).grid(
            row=0, column=0, columnspan=4, padx=14, pady=(12,6), sticky="w")

        self.new_poids_var  = ctk.StringVar()
        self.new_taille_var = ctk.StringVar()
        self.new_notes_var  = ctk.StringVar()

        for col, label, var, ph in [
            (0, "Poids (kg)",          self.new_poids_var,  "ex: 72.5"),
            (1, "Tour de taille (cm)", self.new_taille_var, "ex: 82"),
            (2, "Notes",               self.new_notes_var,  "ex: après sport"),
        ]:
            ctk.CTkLabel(add_card, text=label, font=ctk.CTkFont(size=11),
                         text_color=T["tx2"]).grid(row=1, column=col, padx=8, pady=(0,2), sticky="w")
            ctk.CTkEntry(add_card, textvariable=var, height=34,
                         placeholder_text=ph,
                         fg_color=T["bg_el"], border_color=T["bg_hl"],
                         font=ctk.CTkFont(size=12)).grid(row=2, column=col, padx=8, pady=(0,10), sticky="ew")

        ctk.CTkButton(add_card, text="＋  Enregistrer",
                      fg_color=T["blue"], hover_color=T["blue_dm"],
                      text_color="#fff", height=34, corner_radius=8,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=self._add_mesure).grid(
            row=2, column=3, padx=8, pady=(0,10), sticky="ew")

        # Fréquence + graphique
        ctrl_row = ctk.CTkFrame(parent, fg_color="transparent")
        ctrl_row.grid(row=1, column=0, padx=8, pady=(0,4), sticky="ew")

        ctk.CTkLabel(ctrl_row, text="Affichage :",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).pack(side="left", padx=(0,8))

        self.freq_var = ctk.StringVar(value="tous")
        for key, label in FREQ_OPTS:
            ctk.CTkButton(ctrl_row, text=label, height=28, width=110,
                          fg_color=T["bg_el"], hover_color=T["bg_hl"],
                          corner_radius=6, font=ctk.CTkFont(size=11),
                          command=lambda k=key: self._set_freq(k)).pack(side="left", padx=3)

        # Zone principale : graphique + historique
        main = ctk.CTkFrame(parent, fg_color="transparent")
        main.grid(row=2, column=0, padx=8, pady=0, sticky="nsew")
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        main.grid_rowconfigure(0, weight=1)

        self.chart_frame = ctk.CTkFrame(main, fg_color=T["bg_card"], corner_radius=12)
        self.chart_frame.grid(row=0, column=0, padx=(0,6), sticky="nsew")

        self.hist_frame = ctk.CTkFrame(main, fg_color=T["bg_card"], corner_radius=12)
        self.hist_frame.grid(row=0, column=1, padx=(6,0), sticky="nsew")
        self.hist_frame.grid_columnconfigure(0, weight=1)
        self.hist_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self.hist_frame, text="📋  Historique",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["tx1"]).grid(row=0, column=0, padx=14, pady=(12,6), sticky="w")

        self.hist_scroll = ctk.CTkScrollableFrame(
            self.hist_frame, fg_color="transparent",
            scrollbar_button_color=T["bg_el"])
        self.hist_scroll.grid(row=1, column=0, padx=8, pady=(0,8), sticky="nsew")
        self.hist_scroll.grid_columnconfigure(0, weight=1)

    # ── Onglet Bilan ─────────────────────────────────────────────

    def _build_bilan(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        self.bilan_scroll = ctk.CTkScrollableFrame(
            parent, fg_color="transparent",
            scrollbar_button_color=T["bg_el"])
        self.bilan_scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.bilan_scroll.grid_columnconfigure((0,1), weight=1)

    # ── Onglet Programmes ─────────────────────────────────────────

    def _build_programmes(self, parent):
        """Intègre la gestion des programmes dans le profil."""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # Bouton ajouter
        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.grid(row=0, column=0, padx=8, pady=(8,4), sticky="ew")
        top_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top_bar, text="Gérez vos programmes nutritionnels personnalisés",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(top_bar, text="＋  Nouveau programme",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000", height=34, width=190, corner_radius=8,
                      command=self._open_add_programme).grid(row=0, column=1)

        # Liste programmes
        self.prog_scroll = ctk.CTkScrollableFrame(
            parent, fg_color="transparent",
            scrollbar_button_color=T["bg_el"])
        self.prog_scroll.grid(row=1, column=0, padx=8, pady=(4,8), sticky="nsew")
        for c in range(3):
            self.prog_scroll.grid_columnconfigure(c, weight=1)

        self._refresh_programmes()

    def _on_coeff_change(self, val=None):
        if not hasattr(self, '_coeff_lbl'):
            return
        if val is None:
            val = self._coeff_var.get()
        val = float(val)
        if val < 0.1:
            self._coeff_lbl.configure(text="Auto")
            self._prot_preview.configure(text="calc. auto")
        else:
            v = round(val * 10) / 10
            self._coeff_lbl.configure(text=f"{v:.1f} g/kg")
            user = db.get_current_user()
            poids = float((user or {}).get('poids') or 70)
            prot = round(poids * v)
            self._prot_preview.configure(text=f"≈ {prot} g/j")

    def _refresh_programmes(self):
        if not hasattr(self, 'prog_scroll'):
            return
        for w in self.prog_scroll.winfo_children():
            w.destroy()

        programmes = db.get_programmes()
        if not programmes:
            ctk.CTkLabel(self.prog_scroll,
                         text="Aucun programme\n\nCliquez sur « + Nouveau programme »",
                         text_color=T["tx2"], font=ctk.CTkFont(size=13),
                         justify="center").grid(row=0, column=0, columnspan=3, pady=40)
            return

        OBJECTIFS = {
            "perte_poids": ("🔥", "Perte de poids",  T["err"]),
            "maintien":    ("⚖️",  "Maintien",         T["blue"]),
            "prise_masse": ("💪",  "Prise de masse",   T["ac"]),
        }

        for i, prog in enumerate(programmes):
            is_actif  = bool(prog.get('actif'))
            obj_key   = prog.get('objectif', 'maintien')
            icon, label, color = OBJECTIFS.get(obj_key, ("📋", obj_key, T["tx2"]))
            border    = color if is_actif else T["bg_el"]

            card = ctk.CTkFrame(self.prog_scroll, fg_color=T["bg_card"],
                                corner_radius=12, border_width=2, border_color=border)
            card.grid(row=i//3, column=i%3, padx=5, pady=5, sticky="nsew")
            card.grid_columnconfigure(0, weight=1)

            if is_actif:
                ctk.CTkLabel(card, text="  ✅  ACTIF  ",
                             font=ctk.CTkFont(size=9, weight="bold"),
                             text_color=T["ac"],
                             fg_color=tint_low(T["ac"]),
                             corner_radius=6).grid(
                    row=0, column=0, padx=10, pady=(10,4), sticky="w")
            else:
                ctk.CTkFrame(card, height=6, fg_color="transparent").grid(row=0, column=0)

            ctk.CTkLabel(card, text=f"  {icon}  {label}  ",
                         font=ctk.CTkFont(size=9, weight="bold"),
                         text_color=color, fg_color=tint_low(color),
                         corner_radius=6).grid(row=1, column=0, padx=10, pady=(0,4), sticky="w")

            ctk.CTkLabel(card, text=prog['nom'],
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=T["tx1"], anchor="w",
                         wraplength=180).grid(row=2, column=0, padx=12, pady=(0,4), sticky="w")

            nf = ctk.CTkFrame(card, fg_color=T["bg_el"], corner_radius=8)
            nf.grid(row=3, column=0, padx=10, pady=(0,6), sticky="ew")
            nf.grid_columnconfigure((0,1), weight=1)

            ctk.CTkLabel(nf, text=f"{prog['calories_jour']} kcal/j",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=color).grid(row=0, column=0, padx=8, pady=8)
            ctk.CTkLabel(nf, text=f"{prog['duree_semaines']} sem.",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=T["tx2"]).grid(row=0, column=1, padx=8, pady=8)

            ctk.CTkLabel(nf,
                         text=f"P{prog['proteines_pct']}%  G{prog['glucides_pct']}%  L{prog['lipides_pct']}%",
                         font=ctk.CTkFont(size=9), text_color=T["tx3"]).grid(
                row=1, column=0, columnspan=2, pady=(0,6))

            bf = ctk.CTkFrame(card, fg_color="transparent")
            bf.grid(row=4, column=0, padx=10, pady=(0,10), sticky="ew")
            bf.grid_columnconfigure(0, weight=1)

            if not is_actif:
                ctk.CTkButton(bf, text="▶  Activer",
                              fg_color=tint_low(color), hover_color=tint_low(color),
                              text_color=color, height=28, corner_radius=6,
                              font=ctk.CTkFont(size=11, weight="bold"),
                              command=lambda p=prog: self._activate_prog(p)).grid(
                    row=0, column=0, padx=(0,4), sticky="ew")
            else:
                ctk.CTkButton(bf, text="✓ Actif",
                              fg_color=tint_low(T["ac"]),
                              text_color=T["ac"], height=28, corner_radius=6,
                              state="disabled").grid(row=0, column=0, padx=(0,4), sticky="ew")

            btns = ctk.CTkFrame(bf, fg_color="transparent")
            btns.grid(row=0, column=1)
            ctk.CTkButton(btns, text="✏", width=28, height=28,
                          fg_color=T["bg_el"], hover_color=T["bg_hl"],
                          corner_radius=6,
                          command=lambda p=prog: self._open_edit_programme(p)).pack(side="left", padx=2)
            ctk.CTkButton(btns, text="🗑", width=28, height=28,
                          fg_color=T["bg_el"], hover_color=T["err_bg"],
                          corner_radius=6,
                          command=lambda p=prog: self._confirm_del_prog(p)).pack(side="left", padx=2)

    def _activate_prog(self, prog):
        db.set_programme_actif(prog['id'])
        self._refresh_programmes()

    def _open_add_programme(self):
        from pages.programmes import ProgrammeDialog
        ProgrammeDialog(self, None, self._refresh_programmes)

    def _open_edit_programme(self, prog):
        from pages.programmes import ProgrammeDialog
        ProgrammeDialog(self, prog, self._refresh_programmes)

    def _confirm_del_prog(self, prog):
        from tkinter import messagebox as mb
        if mb.askyesno("Supprimer", f"Supprimer « {prog['nom']} » ?", parent=self):
            db.delete_programme(prog['id'])
            self._refresh_programmes()

    # ── Refresh ───────────────────────────────────────────────────

    def refresh(self):
        user = db.get_current_user()
        if not user:
            return
        self._refresh_header(user)
        self._fill_infos(user)
        self._refresh_suivi()
        self._refresh_bilan()
        self._refresh_programmes()

    def _refresh_header(self, user):
        color = user.get('avatar_color') or T["ac"]
        initials = db.user_initials(user)
        self.avatar_lbl.configure(
            text=initials, text_color=color,
            fg_color=tint_low(color, bg=T["bg_card"]))
        self.user_name_lbl.configure(
            text=f"{user.get('prenom','')} {user.get('nom','')}".strip() or "—")
        obj = db.OBJECTIFS_LABELS.get(user.get('objectif',''), '')
        poids = user.get('poids','—')
        taille = user.get('taille','—')
        imc = db.calc_imc(float(poids or 0), float(taille or 0))
        self.user_sub_lbl.configure(
            text=f"{obj}  ·  {poids} kg  ·  {taille} cm  ·  IMC {imc}")

    def _fill_infos(self, user):
        skip = ("_keys","_display")
        for key, var in self.vars.items():
            if any(key.endswith(s) for s in skip):
                continue
            if key+"_keys" in self.vars:
                # combo → trouver le display actuel
                keys    = self.vars[key+"_keys"]
                display = self.vars[key+"_display"]
                val = user.get(key, '')
                try:
                    idx = keys.index(val)
                    var.set(display[idx])
                except (ValueError, AttributeError):
                    var.set(display[0])
            else:
                v = user.get(key, '')
                var.set(str(v) if v is not None else '')
        # Coefficient protéines
        if hasattr(self, '_coeff_var'):
            coeff = float(user.get('coefficient_proteines') or 0)
            self._coeff_var.set(coeff)
            self._on_coeff_change(coeff)
        # Objectif eau
        if hasattr(self, '_eau_obj_var'):
            self._eau_obj_var.set(str(int(user.get('objectif_eau_ml') or 2000)))
        # FC max
        if hasattr(self, '_fc_max_var'):
            fc = int(user.get('fc_max') or 0)
            self._fc_max_var.set(str(fc) if fc > 0 else "")

    def _refresh_suivi(self):
        freq = self.freq_var.get() if hasattr(self, 'freq_var') else "tous"
        data = db.get_suivi_poids(limit=180, frequence=freq)

        # Graphique
        for w in self.chart_frame.winfo_children():
            w.destroy()
        if MPL_OK and len(data) >= 2:
            self._draw_chart(data)
        elif not data:
            ctk.CTkLabel(self.chart_frame,
                         text="Aucune donnée\nEnregistrez votre première mesure",
                         text_color=T["tx2"], font=ctk.CTkFont(size=13),
                         justify="center").pack(expand=True)
        else:
            ctk.CTkLabel(self.chart_frame,
                         text="Graphique disponible avec\nau moins 2 mesures",
                         text_color=T["tx2"], font=ctk.CTkFont(size=12),
                         justify="center").pack(expand=True)

        # Historique tableau
        for w in self.hist_scroll.winfo_children():
            w.destroy()

        if not data:
            ctk.CTkLabel(self.hist_scroll, text="Aucune mesure",
                         text_color=T["tx2"], font=ctk.CTkFont(size=12)).pack(pady=20)
            return

        # En-tête
        hdr = ctk.CTkFrame(self.hist_scroll, fg_color=T["bg_el"], corner_radius=6)
        hdr.grid(row=0, column=0, pady=(0,4), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        for col, txt, w in [(0,"Date",90),(1,"Poids",60),(2,"Tour",60),(3,"",30)]:
            ctk.CTkLabel(hdr, text=txt, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=T["tx2"], width=w).grid(
                row=0, column=col, padx=4, pady=4, sticky="w")

        for i, entry in enumerate(reversed(data)):
            bg = T["bg_row"] if i % 2 == 0 else "transparent"
            row = ctk.CTkFrame(self.hist_scroll, fg_color=bg, corner_radius=4)
            row.grid(row=i+1, column=0, pady=1, sticky="ew")
            row.grid_columnconfigure(2, weight=1)

            ctk.CTkLabel(row, text=entry['date'][:10],
                         font=ctk.CTkFont(size=10), text_color=T["tx2"],
                         width=90).grid(row=0, column=0, padx=4, pady=4, sticky="w")
            ctk.CTkLabel(row, text=f"{entry['poids']} kg",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=T["blue"], width=60).grid(row=0, column=1, padx=4)

            taille_val = entry.get('tour_de_taille') or 0
            ctk.CTkLabel(row, text=f"{taille_val} cm" if taille_val else "—",
                         font=ctk.CTkFont(size=11), text_color=T["lip"],
                         width=60).grid(row=0, column=2, padx=4)

            if entry.get('id'):
                ctk.CTkButton(row, text="✕", width=22, height=22,
                              fg_color="transparent", hover_color=T["err_bg"],
                              text_color=T["err"],
                              command=lambda eid=entry['id']: self._delete_mesure(eid)).grid(
                    row=0, column=3, padx=4)

    def _draw_chart(self, data):
        from datetime import datetime as _dt
        poids_vals  = [d['poids'] for d in data]
        taille_vals = [d.get('tour_de_taille') or 0 for d in data]
        has_taille  = any(t > 0 for t in taille_vals)

        # Axe X en vraies dates matplotlib
        raw_labels = [d['date'][:10] for d in data]
        try:
            x_hist = [mdates.date2num(_dt.strptime(lb, "%Y-%m-%d")) for lb in raw_labels]
        except ValueError:
            x_hist = list(range(len(raw_labels)))

        plt.rcParams.update({
            'figure.facecolor': T["bg_card"],
            'axes.facecolor':   T["bg_row"],
            'axes.edgecolor':   T["bg_hl"],
            'axes.labelcolor':  T["tx2"],
            'xtick.color':      T["tx2"],
            'ytick.color':      T["tx2"],
            'grid.color':       T["bg_el"],
            'grid.linestyle':   '--',
            'grid.alpha':       0.7,
        })

        if has_taille:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6, 4.5), sharex=True)
            fig.patch.set_facecolor(T["bg_card"])
        else:
            fig, ax1 = plt.subplots(1, 1, figsize=(6, 3.2))
            ax2 = None
            fig.patch.set_facecolor(T["bg_card"])

        # Courbe poids historique
        ax1.plot(x_hist, poids_vals, color=T["blue"], linewidth=2.5,
                 marker="o", markersize=4, markerfacecolor=T["blue_l"])
        ax1.fill_between(x_hist, poids_vals,
                         [min(poids_vals) - 0.5] * len(poids_vals),
                         color=T["blue"], alpha=0.12)

        # Projection
        proj   = db.get_projection_poids()
        target = proj.get("poids_cible", 0.0)

        if proj.get("has_cible") and proj.get("points"):
            pts    = proj["points"]
            x_proj = [mdates.date2num(_dt.strptime(p["date"], "%Y-%m-%d")) for p in pts]
            y_proj = [p["poids"] for p in pts]
            # Relier depuis le dernier point historique
            x_proj = [x_hist[-1]] + x_proj
            y_proj = [poids_vals[-1]] + y_proj

            ax1.plot(x_proj, y_proj, color=T["ac"], linewidth=1.8,
                     linestyle="--", alpha=0.85, label="Projection")
            ax1.fill_between(x_proj,
                             [y - 0.5 for y in y_proj],
                             [y + 0.5 for y in y_proj],
                             color=T["ac"], alpha=0.07)
            ax1.plot(x_proj[-1], y_proj[-1], marker="*", markersize=10,
                     color=T["ac"], zorder=5)
            date_atteinte = proj.get("date_atteinte", "")
            if date_atteinte:
                date_courte = _dt.strptime(date_atteinte, "%Y-%m-%d").strftime("%b %Y")
                ax1.annotate(f"~{date_courte}",
                             xy=(x_proj[-1], y_proj[-1]),
                             xytext=(0, 10), textcoords="offset points",
                             fontsize=8, color=T["ac"], ha="center")

        # Ligne objectif (pointillée fine pour ne pas écraser la projection)
        if target > 0:
            ax1.axhline(y=target, color=T["ac"], linewidth=1.2,
                        linestyle=":", alpha=0.5,
                        label=f"Objectif : {target} kg")

        ax1.legend(fontsize=8, framealpha=0.3, facecolor=T["bg_el"],
                   labelcolor=T["tx1"])
        ax1.set_ylabel("Poids (kg)", fontsize=9, color=T["tx2"])
        ax1.grid(True)
        ax1.set_facecolor(T["bg_row"])

        # Tour de taille
        if ax2 is not None:
            non_zero = [(xi, t) for xi, t in zip(x_hist, taille_vals) if t > 0]
            if non_zero:
                xi_l, ti_l = zip(*non_zero)
                ax2.plot(list(xi_l), list(ti_l), color=T["lip"], linewidth=2,
                         marker="s", markersize=4, markerfacecolor="#fbbf24")
                ax2.fill_between(list(xi_l), list(ti_l),
                                 [min(ti_l) - 0.5] * len(ti_l),
                                 color=T["lip"], alpha=0.10)
            ax2.set_ylabel("Tour de taille (cm)", fontsize=9, color=T["tx2"])
            ax2.grid(True)
            ax2.set_facecolor(T["bg_row"])

        # Axe X en dates réelles
        ax1.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=8))
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        fig.autofmt_xdate(rotation=30)
        for tick in ax1.xaxis.get_major_ticks():
            tick.label1.set_fontsize(8)

        fig.tight_layout(pad=1.2)
        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
        plt.close(fig)

        # Message si pas de poids cible
        if not proj.get("has_cible"):
            ctk.CTkLabel(
                self.chart_frame,
                text="Définissez un poids cible dans Profil > Informations\npour voir la projection",
                font=ctk.CTkFont(size=9),
                text_color=T["tx2"],
                justify="center",
            ).pack(pady=(0, 8))

    def _refresh_bilan(self):
        for w in self.bilan_scroll.winfo_children():
            w.destroy()

        user   = db.get_current_user()
        if not user:
            return
        profil = user
        poids  = float(profil.get('poids') or 0)
        taille = float(profil.get('taille') or 0)
        macros = db.calc_macros_cibles(profil)
        imc    = db.calc_imc(poids, taille)
        imc_label, imc_color = db.imc_category(imc)

        # IMC
        imc_card = _card(self.bilan_scroll, "🏥  IMC & Poids")
        imc_card.grid(row=0, column=0, padx=(8,4), pady=8, sticky="nsew")
        ctk.CTkLabel(imc_card, text=f"{imc}",
                     font=ctk.CTkFont(size=44, weight="bold"),
                     text_color=imc_color).grid(row=1, column=0, padx=20, pady=(8,0))
        ctk.CTkLabel(imc_card, text=imc_label,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=imc_color).grid(row=2, column=0, padx=20, pady=(0,8))

        poids_cible = float(profil.get('poids_cible') or 0)
        if poids_cible and poids:
            diff = round(poids - poids_cible, 1)
            txt  = (f"À perdre : {diff} kg" if diff > 0
                    else f"Objectif atteint ✅" if diff == 0
                    else f"À prendre : {abs(diff)} kg")
            col  = T["ac"] if diff <= 0 else T["lip"]
            ctk.CTkLabel(imc_card, text=txt,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=col).grid(row=3, column=0, padx=20, pady=(0,14))

        # Macros
        mc = _card(self.bilan_scroll, "⚡  Objectifs nutritionnels / jour")
        mc.grid(row=0, column=1, padx=(4,8), pady=8, sticky="nsew")
        mc.grid_columnconfigure(0, weight=1)

        for r, (lbl, val, col) in enumerate([
            ("Énergie",   f"{macros['calories']} kcal", T["cal"]),
            ("Protéines", f"{macros['proteines']} g",   T["ac"]),
            ("Glucides",  f"{macros['glucides']} g",    T["blue"]),
            ("Lipides",   f"{macros['lipides']} g",     T["lip"]),
        ], start=1):
            rf = ctk.CTkFrame(mc, fg_color=T["bg_el"], corner_radius=8)
            rf.grid(row=r, column=0, padx=14, pady=2, sticky="ew")
            rf.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(rf, text=lbl, font=ctk.CTkFont(size=12),
                         text_color=T["tx2"], anchor="w").grid(
                row=0, column=0, padx=10, pady=8, sticky="w")
            ctk.CTkLabel(rf, text=val,
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=col, anchor="e").grid(
                row=0, column=1, padx=10, sticky="e")

        _spacer(mc, 6)

        # Évolution poids
        data = db.get_suivi_poids(limit=10, frequence="tous")
        if len(data) >= 2:
            evo_card = _card(self.bilan_scroll, "📉  Évolution récente")
            evo_card.grid(row=1, column=0, columnspan=2, padx=8, pady=(0,8), sticky="ew")
            premier = data[0]
            dernier = data[-1]
            diff_p = round(dernier['poids'] - premier['poids'], 1)
            col_d  = T["ac"] if diff_p < 0 else T["err"] if diff_p > 0 else T["tx2"]
            signe  = "↓" if diff_p < 0 else "↑" if diff_p > 0 else "="
            ctk.CTkLabel(evo_card,
                         text=f"{signe} {abs(diff_p)} kg   depuis le {premier['date'][:10]}",
                         font=ctk.CTkFont(size=16, weight="bold"),
                         text_color=col_d).grid(row=1, column=0, padx=16, pady=(0,14), sticky="w")

    # ── Actions ──────────────────────────────────────────────────

    def _save_profil(self):
        data = {}
        skip = ("_keys","_display")
        for key, var in self.vars.items():
            if any(key.endswith(s) for s in skip):
                continue
            if key+"_keys" in self.vars:
                display_val = var.get()
                opts_d = self.vars[key+"_display"]
                opts_k = self.vars[key+"_keys"]
                try:
                    data[key] = opts_k[opts_d.index(display_val)]
                except (ValueError, IndexError):
                    data[key] = opts_k[0]
            else:
                data[key] = var.get().strip()

        for k in ('age',):
            try:   data[k] = int(data.get(k) or 0)
            except: data[k] = 0
        for k in ('poids','taille','tour_de_taille','poids_cible'):
            try:   data[k] = float(str(data.get(k) or 0).replace(',','.'))
            except: data[k] = 0.0

        if hasattr(self, '_coeff_var'):
            val = float(self._coeff_var.get())
            data['coefficient_proteines'] = round(val, 2) if val >= 0.1 else 0.0
        else:
            data.setdefault('coefficient_proteines', 0.0)

        if hasattr(self, '_eau_obj_var'):
            try:
                data['objectif_eau_ml'] = max(500, int(float(
                    self._eau_obj_var.get().replace(',', '.') or 2000)))
            except (ValueError, TypeError):
                data['objectif_eau_ml'] = 2000
        else:
            data.setdefault('objectif_eau_ml', 2000)

        if hasattr(self, '_fc_max_var'):
            try:
                fc = int(float(self._fc_max_var.get().replace(',', '.') or 0))
                data['fc_max'] = max(0, fc)
            except (ValueError, TypeError):
                data['fc_max'] = 0
        else:
            data.setdefault('fc_max', 0)

        db.save_profil(data)
        self.refresh()
        messagebox.showinfo("Enregistré ✅", "Profil mis à jour.", parent=self)

    def _add_mesure(self):
        try:
            p = float(self.new_poids_var.get().replace(',','.'))
        except ValueError:
            messagebox.showwarning("Valeur invalide",
                                   "Entrez un poids valide (ex: 72.5)", parent=self)
            return
        try:
            t = float(self.new_taille_var.get().replace(',','.') or 0)
        except ValueError:
            t = 0.0
        db.add_suivi_poids(p, t, self.new_notes_var.get().strip())
        self.new_poids_var.set("")
        self.new_taille_var.set("")
        self.new_notes_var.set("")
        self._refresh_suivi()
        self._refresh_bilan()

    def _delete_mesure(self, eid):
        db.delete_suivi_poids(eid)
        self._refresh_suivi()

    def _set_freq(self, freq: str):
        self.freq_var.set(freq)
        self._refresh_suivi()

    def _export_backup(self):
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Sauvegarder la base de données",
            defaultextension=".db",
            initialfile=f"nutritrack_backup_{date.today().isoformat()}.db",
            filetypes=[("Base SQLite", "*.db"), ("Tous les fichiers", "*.*")])
        if not path:
            return
        if db.export_backup(path):
            messagebox.showinfo("Sauvegarde", f"Base de données sauvegardée :\n{path}", parent=self)
        else:
            messagebox.showerror("Erreur", "La sauvegarde a échoué.", parent=self)

    def _switch_profile(self):
        from login import LoginScreen
        self.winfo_toplevel()._show_login()


# ─────────────────── Helpers ─────────────────────────────────────

def _card(parent, title):
    frame = ctk.CTkFrame(parent, fg_color=T["bg_card"], corner_radius=12)
    frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(frame, text=title,
                 font=ctk.CTkFont(size=14, weight="bold"),
                 text_color=T["tx1"]).grid(
        row=0, column=0, padx=16, pady=(14,10), sticky="w")
    ctk.CTkFrame(frame, height=1, fg_color=T["bg_el"]).grid(
        row=0, column=0, padx=16, sticky="sew")
    return frame

def _spacer(parent, row, h=12):
    ctk.CTkFrame(parent, height=h, fg_color="transparent").grid(row=row, column=0)
