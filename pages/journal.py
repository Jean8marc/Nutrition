"""
NutriTrack Pro — Journal alimentaire quotidien
Saisie rapide : aliment de la base ou entrée libre, avec totaux en temps réel.
"""
import os, sys
from datetime import date, datetime
import customtkinter as ctk
from tkinter import messagebox
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import database as db
from widgets import MacroRing
from theme import T
from pages.stock import show_stock_alert_toast

MOIS_FR = ["","janvier","février","mars","avril","mai","juin",
           "juillet","août","septembre","octobre","novembre","décembre"]
JOURS_FR = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]


class JournalPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=T["bg_app"], corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._date = date.today()
        self._build()

    # ── Construction ─────────────────────────────────────────────

    def _build(self):
        # ── Entête ───────────────────────────────────────────────
        nav = ctk.CTkFrame(self, fg_color=T["bg_card"], corner_radius=0, height=60)
        nav.grid(row=0, column=0, sticky="ew")
        nav.grid_columnconfigure(1, weight=1)
        nav.grid_propagate(False)

        ctk.CTkLabel(nav, text="📓  Journal alimentaire",
                     font=ctk.CTkFont(family="Helvetica", size=20, weight="bold"),
                     text_color=T["tx1"]).grid(row=0, column=0, padx=20, sticky="w")

        # Navigation date
        nav_mid = ctk.CTkFrame(nav, fg_color="transparent")
        nav_mid.grid(row=0, column=1)

        ctk.CTkButton(nav_mid, text="◀", width=32, height=32,
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      command=self._prev_day).pack(side="left", padx=4)

        self._date_lbl = ctk.CTkLabel(nav_mid, text="",
                                       font=ctk.CTkFont(size=13, weight="bold"),
                                       text_color=T["tx1"], width=260)
        self._date_lbl.pack(side="left", padx=8)

        ctk.CTkButton(nav_mid, text="▶", width=32, height=32,
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      command=self._next_day).pack(side="left", padx=4)

        ctk.CTkButton(nav_mid, text="Aujourd'hui", width=100, height=32,
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      font=ctk.CTkFont(size=12),
                      command=self._goto_today).pack(side="left", padx=8)

        ctk.CTkButton(nav, text="＋  Ajouter un repas",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000", height=34, width=160, corner_radius=8,
                      command=self._open_add).grid(row=0, column=2, padx=16)

        # ── Corps : liste + bilan ─────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0)
        body.grid_rowconfigure(0, weight=1)

        # Liste des entrées
        self._list_frame = ctk.CTkScrollableFrame(
            body, fg_color="transparent",
            scrollbar_button_color=T["bg_el"])
        self._list_frame.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=12)
        self._list_frame.grid_columnconfigure(0, weight=1)

        # Panneau bilan
        self._bilan_frame = ctk.CTkFrame(body, fg_color=T["bg_card"],
                                          corner_radius=14, width=240)
        self._bilan_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 16), pady=12)
        self._bilan_frame.grid_propagate(False)
        self._bilan_frame.grid_columnconfigure(0, weight=1)

        self.refresh()

    # ── Refresh ───────────────────────────────────────────────────

    def refresh(self):
        d = self._date
        self._date_lbl.configure(
            text=f"{JOURS_FR[d.weekday()]} {d.day} {MOIS_FR[d.month]} {d.year}")
        self._refresh_list()
        self._refresh_bilan()

    def _refresh_list(self):
        for w in self._list_frame.winfo_children():
            w.destroy()

        entries = db.get_journal_jour(self._date.isoformat())
        if not entries:
            ctk.CTkLabel(self._list_frame,
                         text="Aucune entrée pour ce jour\n\nCliquez sur « + Ajouter un repas »",
                         font=ctk.CTkFont(size=13), text_color=T["tx2"],
                         justify="center").grid(row=0, column=0, pady=60)
            return

        # En-tête
        hdr = ctk.CTkFrame(self._list_frame, fg_color=T["bg_el"], corner_radius=8)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        hdr.grid_columnconfigure(1, weight=1)
        for ci, (txt, w) in enumerate([("Heure",60),("Aliment",0),
                                        ("Qté",55),("kcal",55),
                                        ("Prot.",50),("Gluc.",50),("Lip.",50),("",36)]):
            ctk.CTkLabel(hdr, text=txt,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=T["tx2"],
                         width=w if w else 0).grid(
                row=0, column=ci, padx=6, pady=6, sticky="w")

        for i, e in enumerate(entries):
            bg = T["bg_row"] if i % 2 == 0 else "transparent"
            row = ctk.CTkFrame(self._list_frame, fg_color=bg, corner_radius=6)
            row.grid(row=i+1, column=0, sticky="ew", pady=1)
            row.grid_columnconfigure(1, weight=1)

            vals = [
                (e.get('heure','') or '--:--', 60, T["tx2"]),
                (e.get('nom','')[:30], 0, T["tx1"]),
                (f"{int(e.get('quantite_g',0))} g", 55, T["tx2"]),
                (str(int(e.get('calories',0))), 55, T["cal"]),
                (f"{e.get('proteines',0):.1f}", 50, T["ac"]),
                (f"{e.get('glucides',0):.1f}", 50, T["blue"]),
                (f"{e.get('lipides',0):.1f}", 50, T["lip"]),
            ]
            for ci, (txt, w, col) in enumerate(vals):
                ctk.CTkLabel(row, text=txt,
                             font=ctk.CTkFont(size=11),
                             text_color=col,
                             width=w if w else 0,
                             anchor="w").grid(row=0, column=ci, padx=6, pady=5, sticky="w")

            ctk.CTkButton(row, text="✕", width=28, height=28,
                          fg_color="transparent", hover_color=T["err_bg"],
                          text_color=T["err"], corner_radius=6,
                          command=lambda eid=e['id']: self._delete(eid)).grid(
                row=0, column=7, padx=4, sticky="e")

    def _refresh_bilan(self):
        for w in self._bilan_frame.winfo_children():
            w.destroy()

        ctk.CTkLabel(self._bilan_frame,
                     text="📊  Bilan du jour",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["tx1"]).grid(row=0, column=0, padx=16, pady=(16,4), sticky="w")

        totaux  = db.get_nutri_journal_jour(self._date.isoformat())
        profil  = db.get_profil()
        prog    = db.get_programme_actif()
        macros  = db.calc_macros_cibles(profil)
        if prog:
            macros['calories']  = prog['calories_jour']
            macros['proteines'] = round(prog['calories_jour'] * prog['proteines_pct'] / 100 / 4)
            macros['glucides']  = round(prog['calories_jour'] * prog['glucides_pct']  / 100 / 4)
            macros['lipides']   = round(prog['calories_jour'] * prog['lipides_pct']   / 100 / 9)

        items = [
            ("Énergie",   totaux['calories'],  macros['calories'],  "kcal", T["cal"]),
            ("Protéines", totaux['proteines'], macros['proteines'], "g",    T["ac"]),
            ("Glucides",  totaux['glucides'],  macros['glucides'],  "g",    T["blue"]),
            ("Lipides",   totaux['lipides'],   macros['lipides'],   "g",    T["lip"]),
            ("Fibres",    totaux['fibres'],    25,                  "g",    T["fib"]),
        ]

        # Grille 2 colonnes de MacroRing
        rings_frame = ctk.CTkFrame(self._bilan_frame, fg_color="transparent")
        rings_frame.grid(row=1, column=0, padx=4, pady=(4, 0), sticky="ew")
        rings_frame.grid_columnconfigure(0, weight=1)
        rings_frame.grid_columnconfigure(1, weight=1)

        for i, (lbl, val, cible, unit, col) in enumerate(items):
            r, c = divmod(i, 2)
            if i == 4:
                # Fibres seule sur la dernière ligne : centrer sur 2 colonnes
                wrapper = ctk.CTkFrame(rings_frame, fg_color="transparent")
                wrapper.grid(row=r, column=0, columnspan=2, pady=4)
                MacroRing(wrapper, label=lbl, value=val, cible=cible,
                          unit=unit, color=col, size=88, bg_color=T["bg_card"]).pack()
            else:
                MacroRing(rings_frame, label=lbl, value=val, cible=cible,
                          unit=unit, color=col, size=88, bg_color=T["bg_card"]
                          ).grid(row=r, column=c, padx=4, pady=4)

        # Entrées
        entries = db.get_journal_jour(self._date.isoformat())
        ctk.CTkLabel(self._bilan_frame,
                     text=f"{len(entries)} entrée(s) enregistrée(s)",
                     font=ctk.CTkFont(size=10), text_color=T["tx3"]).grid(
            row=2, column=0, padx=16, pady=(4, 4), sticky="w")

        # ── Eau ──────────────────────────────────────────────────
        ctk.CTkFrame(self._bilan_frame, height=1, fg_color=T["bg_el"]).grid(
            row=3, column=0, padx=16, pady=(0, 0), sticky="ew")
        ctk.CTkLabel(self._bilan_frame, text="💧  Hydratation",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=T["blue"]).grid(
            row=4, column=0, padx=16, pady=(8, 2), sticky="w")

        total_ml   = db.get_total_eau_jour(self._date.isoformat())
        obj_ml     = db.get_objectif_eau()
        pct_eau    = min(1.0, total_ml / max(1, obj_ml))

        eau_lbl_f = ctk.CTkFrame(self._bilan_frame, fg_color="transparent")
        eau_lbl_f.grid(row=5, column=0, padx=16, pady=(0, 0), sticky="ew")
        eau_lbl_f.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(eau_lbl_f, text=f"{total_ml} ml",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T["blue"], anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(eau_lbl_f, text=f"/ {obj_ml} ml",
                     font=ctk.CTkFont(size=10), text_color=T["tx2"],
                     anchor="e").grid(row=0, column=1, sticky="e")

        pb_eau = ctk.CTkProgressBar(self._bilan_frame, height=6,
                                    progress_color=T["blue"], fg_color=T["bg_el"])
        pb_eau.grid(row=6, column=0, padx=16, pady=(2, 6), sticky="ew")
        pb_eau.set(pct_eau)

        btns_eau = ctk.CTkFrame(self._bilan_frame, fg_color="transparent")
        btns_eau.grid(row=7, column=0, padx=16, pady=(0, 12), sticky="ew")
        for txt, ml in [("🥃 150ml", 150), ("🥤 250ml", 250), ("🍶 500ml", 500)]:
            ctk.CTkButton(btns_eau, text=txt, height=26,
                          fg_color=T["blue_d"], hover_color=T["blue_dm"],
                          text_color=T["blue_l"], corner_radius=6,
                          font=ctk.CTkFont(size=10),
                          command=lambda m=ml: self._add_eau(m)).pack(
                side="left", padx=2, expand=True, fill="x")

    # ── Navigation ────────────────────────────────────────────────

    def _prev_day(self):
        from datetime import timedelta
        self._date -= timedelta(days=1)
        self.refresh()

    def _next_day(self):
        from datetime import timedelta
        self._date += timedelta(days=1)
        self.refresh()

    def _goto_today(self):
        self._date = date.today()
        self.refresh()

    # ── Actions ──────────────────────────────────────────────────

    def _open_add(self):
        AddJournalDialog(self, self._date.isoformat(), self.refresh)

    def _delete(self, eid: int):
        db.delete_journal_entry(eid)
        self.refresh()

    def _add_eau(self, ml: int):
        db.add_eau(ml, self._date.isoformat())
        eau_aid = db.get_stock_eau_aliment_id()
        if eau_aid:
            sous_seuil = db.deduct_stock([{'aliment_id': eau_aid, 'quantite_g': ml}])
            if sous_seuil:
                show_stock_alert_toast(self, sous_seuil)
        self._refresh_bilan()


# ─────────────────────────── Dialogue ajout ──────────────────────────────────

class AddJournalDialog(ctk.CTkToplevel):
    def __init__(self, parent, date_str: str, callback):
        super().__init__(parent)
        self._date_str = date_str
        self._callback = callback
        self._selected_alim = None
        self._deduct_var = ctk.BooleanVar(value=False)
        self._add_stock_var = ctk.BooleanVar(value=False)
        self._stock_qty_entry = None

        self.title("＋  Ajouter au journal")
        self.geometry("520x580")
        self.resizable(False, False)
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="＋  Ajouter un aliment / repas",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T["tx1"]).pack(padx=20, pady=(16,4), anchor="w")
        ctk.CTkLabel(self, text=f"Journal du {self._date_str}",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(padx=20, anchor="w")

        tabs = ctk.CTkTabview(self, fg_color=T["bg_card"],
                               segmented_button_fg_color=T["bg_el"],
                               segmented_button_selected_color=T["ac"],
                               text_color=T["tx1"])
        tabs.pack(fill="both", expand=True, padx=16, pady=8)
        t1 = tabs.add("🥑  Depuis la base")
        t2 = tabs.add("✏️  Saisie libre")
        self._tabs = tabs

        # ── Onglet base aliments ──────────────────────────────────
        t1.grid_columnconfigure(0, weight=1)
        t1.grid_rowconfigure(1, weight=1)

        self._search_var = ctk.StringVar()
        se = ctk.CTkEntry(t1, textvariable=self._search_var,
                          placeholder_text="🔍  Rechercher un aliment…",
                          height=34, fg_color=T["bg_el"], border_color=T["bg_hl"],
                          font=ctk.CTkFont(size=12))
        se.grid(row=0, column=0, padx=4, pady=(4,6), sticky="ew")
        se.bind("<KeyRelease>", lambda e: self._search_aliments())

        self._alim_list = ctk.CTkScrollableFrame(t1, fg_color="transparent",
                                                  scrollbar_button_color=T["bg_el"],
                                                  height=180)
        self._alim_list.grid(row=1, column=0, padx=4, sticky="nsew")
        self._alim_list.grid_columnconfigure(0, weight=1)

        qf = ctk.CTkFrame(t1, fg_color="transparent")
        qf.grid(row=2, column=0, padx=4, pady=(8,4), sticky="ew")
        ctk.CTkLabel(qf, text="Quantité (g) :",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).pack(side="left")
        self._qte_var = ctk.StringVar(value="100")
        ctk.CTkEntry(qf, textvariable=self._qte_var, width=80, height=32,
                     fg_color=T["bg_el"], border_color=T["bg_hl"],
                     font=ctk.CTkFont(size=13)).pack(side="left", padx=8)

        self._alim_info = ctk.CTkLabel(t1, text="",
                                        font=ctk.CTkFont(size=10), text_color=T["tx2"],
                                        wraplength=460)
        self._alim_info.grid(row=3, column=0, padx=4, sticky="w")

        # Zone stock dynamique
        self._stock_zone = ctk.CTkFrame(t1, fg_color='transparent')
        self._stock_zone.grid(row=4, column=0, sticky='ew', pady=(4, 0))

        self._search_aliments()

        # ── Onglet saisie libre ───────────────────────────────────
        t2.grid_columnconfigure((0,1), weight=1)

        def lbl(text, r, c, span=1):
            ctk.CTkLabel(t2, text=text, font=ctk.CTkFont(size=11),
                         text_color=T["tx2"]).grid(
                row=r*2, column=c, columnspan=span, padx=8, pady=(8,2), sticky="w")

        def entry(key, r, c, ph="", span=1):
            var = ctk.StringVar()
            ctk.CTkEntry(t2, textvariable=var, height=34, placeholder_text=ph,
                         fg_color=T["bg_el"], border_color=T["bg_hl"],
                         font=ctk.CTkFont(size=12)).grid(
                row=r*2+1, column=c, columnspan=span, padx=8, sticky="ew")
            self._libre_vars[key] = var

        self._libre_vars = {}
        lbl("Nom", 0, 0, span=2);    entry("nom",      0, 0, "Ex : Salade composée", span=2)
        lbl("Calories (kcal)", 1, 0); entry("calories",  1, 0, "0")
        lbl("Protéines (g)", 1, 1);   entry("proteines", 1, 1, "0")
        lbl("Glucides (g)", 2, 0);    entry("glucides",  2, 0, "0")
        lbl("Lipides (g)", 2, 1);     entry("lipides",   2, 1, "0")
        lbl("Fibres (g)", 3, 0);      entry("fibres",    3, 0, "0")

        # ── Heure (commune) ──────────────────────────────────────
        hf = ctk.CTkFrame(self, fg_color="transparent")
        hf.pack(padx=20, pady=(0,8), fill="x")
        ctk.CTkLabel(hf, text="Heure :",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).pack(side="left")
        self._heure_var = ctk.StringVar(
            value=datetime.now().strftime("%H:%M"))
        ctk.CTkEntry(hf, textvariable=self._heure_var, width=70, height=32,
                     fg_color=T["bg_el"], border_color=T["bg_hl"],
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=8)

        # ── Boutons ───────────────────────────────────────────────
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(padx=20, pady=(0,16), fill="x")
        ctk.CTkButton(bf, text="Annuler",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=38, width=110,
                      command=self.destroy).pack(side="left")
        ctk.CTkButton(bf, text="＋  Enregistrer",
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000", height=38, width=160,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._save).pack(side="right")

    # ── Recherche aliments ────────────────────────────────────────

    def _search_aliments(self):
        for w in self._alim_list.winfo_children():
            w.destroy()
        search = self._search_var.get().strip()
        grid_row = 0

        # Section récents (uniquement quand la recherche est vide)
        if not search:
            recents = db.get_journal_frequents(limit=6)
            if recents:
                ctk.CTkLabel(self._alim_list,
                             text="⚡  Récemment utilisés",
                             font=ctk.CTkFont(size=10, weight="bold"),
                             text_color=T["lip"]).grid(
                    row=grid_row, column=0, padx=8, pady=(4, 2), sticky="w")
                grid_row += 1
                for r in recents:
                    self._make_recent_row(r, grid_row)
                    grid_row += 1
                ctk.CTkFrame(self._alim_list, height=1,
                             fg_color=T["bg_el"]).grid(
                    row=grid_row, column=0, padx=8, pady=(4, 2), sticky="ew")
                grid_row += 1
                ctk.CTkLabel(self._alim_list, text="📋  Tous les aliments",
                             font=ctk.CTkFont(size=10, weight="bold"),
                             text_color=T["tx2"]).grid(
                    row=grid_row, column=0, padx=8, pady=(2, 4), sticky="w")
                grid_row += 1

        aliments = db.get_aliments(search=search)[:40]
        for i, a in enumerate(aliments):
            bg = T["bg_row"] if i % 2 == 0 else "transparent"
            row = ctk.CTkFrame(self._alim_list, fg_color=bg, corner_radius=6, height=38)
            row.grid(row=grid_row + i, column=0, pady=1, sticky="ew")
            row.grid_columnconfigure(0, weight=1)
            row.grid_propagate(False)

            ctk.CTkLabel(row, text=a['nom'],
                         font=ctk.CTkFont(size=11), text_color=T["tx1"],
                         anchor="w").grid(row=0, column=0, padx=8, pady=4, sticky="w")
            ctk.CTkLabel(row,
                         text=f"{a['calories']} kcal  •  P{a['proteines']}  G{a['glucides']}  L{a['lipides']} / 100g",
                         font=ctk.CTkFont(size=9), text_color=T["tx2"]).grid(
                row=0, column=1, padx=8, sticky="e")

            row.bind("<Button-1>", lambda e, al=a, rw=row: self._select_alim(al, rw))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda e, al=a, rw=row: self._select_alim(al, rw))

    def _make_recent_row(self, recent: dict, grid_row: int):
        qty  = int(recent.get('quantite_g', 100) or 100)
        cal  = int(recent.get('calories', 0) or 0)
        nb   = int(recent.get('nb_fois', 1) or 1)

        row = ctk.CTkFrame(self._alim_list, fg_color=T["bg_row"], corner_radius=6, height=36)
        row.grid(row=grid_row, column=0, pady=1, sticky="ew")
        row.grid_columnconfigure(1, weight=1)
        row.grid_propagate(False)

        ctk.CTkLabel(row, text="⚡",
                     font=ctk.CTkFont(size=11), text_color=T["lip"],
                     width=18).grid(row=0, column=0, padx=(6, 2))
        ctk.CTkLabel(row, text=recent['nom'][:28],
                     font=ctk.CTkFont(size=11), text_color=T["tx1"],
                     anchor="w").grid(row=0, column=1, padx=4, sticky="w")
        ctk.CTkLabel(row, text=f"{qty} g • {cal} kcal • ×{nb}",
                     font=ctk.CTkFont(size=9), text_color=T["tx2"]).grid(
            row=0, column=2, padx=6, sticky="e")
        ctk.CTkButton(row, text="＋", width=26, height=26,
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000", corner_radius=6,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=lambda r=recent: self._quick_add_recent(r)).grid(
            row=0, column=3, padx=(0, 6))

        # Clic sur la ligne → sélectionner avec quantité pré-remplie
        for w in [row] + [c for c in row.winfo_children()
                          if not isinstance(c, ctk.CTkButton)]:
            w.bind("<Button-1>", lambda e, r=recent: self._select_recent(r))

    def _select_recent(self, recent: dict):
        alim_id = recent.get('aliment_id')
        if alim_id:
            alim = db.get_aliment_by_id(int(alim_id))
            if alim:
                # Trouver le widget de ligne pour le mettre en surbrillance
                self._select_alim(alim, None)
                self._qte_var.set(str(int(recent.get('quantite_g', 100) or 100)))

    def _quick_add_recent(self, recent: dict):
        heure = self._heure_var.get().strip()
        qty   = float(recent.get('quantite_g', 100) or 100)
        alim_id = recent.get('aliment_id')

        if alim_id:
            alim = db.get_aliment_by_id(int(alim_id))
            if alim:
                ratio = qty / 100.0
                db.add_journal_entry(
                    date_str=self._date_str, heure=heure,
                    aliment_id=int(alim_id), nom=alim['nom'],
                    quantite_g=qty,
                    calories=round(alim['calories']        * ratio, 1),
                    proteines=round(alim['proteines']      * ratio, 1),
                    glucides=round(alim['glucides']        * ratio, 1),
                    lipides=round(alim['lipides']          * ratio, 1),
                    fibres=round(alim.get('fibres', 0)     * ratio, 1))
        else:
            db.add_journal_entry(
                date_str=self._date_str, heure=heure,
                nom=recent['nom'], quantite_g=qty,
                calories=float(recent.get('calories', 0)  or 0),
                proteines=float(recent.get('proteines', 0) or 0),
                glucides=float(recent.get('glucides', 0)   or 0),
                lipides=float(recent.get('lipides', 0)     or 0),
                fibres=float(recent.get('fibres', 0)       or 0))

        self._callback()
        self.destroy()

    def _select_alim(self, alim, row_widget):
        self._selected_alim = alim
        for w in self._alim_list.winfo_children():
            w.configure(fg_color="transparent")
        if row_widget is not None:
            row_widget.configure(fg_color=T["ac_sel"], border_width=1, border_color=T["ac"])
        self._alim_info.configure(
            text=f"Selectionne : {alim['nom']}  -  {alim['calories']} kcal / 100g")
        self._update_stock_zone(alim)

    def _update_stock_zone(self, alim):
        for w in self._stock_zone.winfo_children():
            w.destroy()
        if not alim:
            return
        stock = db.get_stock()
        item = next((s for s in stock if s['aliment_id'] == alim['id']), None)
        if item:
            stock_qty = round(item['quantite'], 1)
            self._deduct_var.set(True)
            f = ctk.CTkFrame(self._stock_zone, fg_color=T['bg_el'], corner_radius=6)
            f.pack(fill='x', pady=2)
            ctk.CTkCheckBox(f,
                            text=f"Deduire du stock  (stock : {stock_qty} {item['unite']})",
                            variable=self._deduct_var,
                            fg_color=T['ac'], hover_color=T['ac_d'],
                            text_color=T['tx1'],
                            font=ctk.CTkFont(size=11)).pack(side='left', padx=8, pady=6)
        else:
            self._add_stock_var.set(False)
            self._stock_qty_entry = None
            f = ctk.CTkFrame(self._stock_zone, fg_color=T['bg_el'], corner_radius=6)
            f.pack(fill='x', pady=2)
            ctk.CTkCheckBox(f, text='Ajouter aussi au stock',
                            variable=self._add_stock_var,
                            fg_color=T['blue'], hover_color=T['blue_d'],
                            text_color=T['tx2'],
                            font=ctk.CTkFont(size=11),
                            command=lambda fr=f: self._toggle_add_stock_qty(fr)).pack(
                side='left', padx=8, pady=6)

    def _toggle_add_stock_qty(self, parent_frame):
        for w in parent_frame.winfo_children():
            if getattr(w, '_is_stock_qty', False):
                w.destroy()
        if self._add_stock_var.get():
            entry = ctk.CTkEntry(parent_frame, width=80,
                                  placeholder_text='qte achetee',
                                  fg_color=T['bg_el'], border_color=T['bg_hl'],
                                  font=ctk.CTkFont(size=11))
            entry._is_stock_qty = True
            entry.pack(side='left', padx=4, pady=6)
            self._stock_qty_entry = entry
        else:
            self._stock_qty_entry = None

    # ── Sauvegarde ────────────────────────────────────────────────

    def _save(self):
        tab = self._tabs.get()
        heure = self._heure_var.get().strip()

        if "base" in tab.lower():
            if not self._selected_alim:
                messagebox.showwarning("Sélection requise",
                                       "Choisissez un aliment.", parent=self)
                return
            try:
                qte = float(self._qte_var.get().replace(",",".") or 100)
            except ValueError:
                qte = 100.0
            a = self._selected_alim
            ratio = qte / 100.0
            db.add_journal_entry(
                date_str=self._date_str, heure=heure,
                aliment_id=a['id'], nom=a['nom'],
                quantite_g=qte,
                calories=round(a['calories']  * ratio, 1),
                proteines=round(a['proteines'] * ratio, 1),
                glucides=round(a['glucides']   * ratio, 1),
                lipides=round(a['lipides']     * ratio, 1),
                fibres=round(a.get('fibres',0) * ratio, 1))
            # Gestion stock
            if self._deduct_var.get() and self._selected_alim:
                sous_seuil = db.deduct_stock([{
                    'aliment_id': a['id'],
                    'quantite_g': qte
                }])
                db.increment_stock_usage(a['id'])
                if sous_seuil:
                    show_stock_alert_toast(self, sous_seuil)
            elif self._add_stock_var.get() and self._selected_alim:
                qty_str = ''
                if self._stock_qty_entry and self._stock_qty_entry.winfo_exists():
                    qty_str = self._stock_qty_entry.get().strip()
                try:
                    qty_achat = float(qty_str.replace(',', '.'))
                except (ValueError, AttributeError):
                    qty_achat = qte
                db.add_to_stock_from_aliment(a['id'], qty_achat)
        else:
            nom = self._libre_vars['nom'].get().strip()
            if not nom:
                messagebox.showwarning("Champ requis",
                                       "Le nom est obligatoire.", parent=self)
                return
            def _f(key):
                try:
                    return float(self._libre_vars[key].get().replace(",",".") or 0)
                except ValueError:
                    return 0.0
            db.add_journal_entry(
                date_str=self._date_str, heure=heure,
                nom=nom, quantite_g=_f('calories'),  # stocke kcal en quantite_g pour libre
                calories=_f('calories'), proteines=_f('proteines'),
                glucides=_f('glucides'), lipides=_f('lipides'),
                fibres=_f('fibres'))

        self._callback()
        self.destroy()
