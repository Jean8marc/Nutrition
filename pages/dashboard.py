"""
NutriTrack Pro — Tableau de bord
"""
import customtkinter as ctk
import database as db
from datetime import date
from widgets import MacroRing
from theme import T

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MPL_OK = True
except ImportError:
    MPL_OK = False


class DashboardPage(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=T["bg_app"],
                         scrollbar_button_color=T["bg_el"],
                         scrollbar_button_hover_color=T["bg_hl"])
        self.grid_columnconfigure(0, weight=1)
        self._build_skeleton()
        self.refresh()

    def _build_skeleton(self):
        # ── Titre ──────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=28, pady=(28, 0), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Tableau de bord",
                     font=ctk.CTkFont(family="Helvetica", size=26, weight="bold"),
                     text_color=T["tx1"]).grid(row=0, column=0, sticky="w")

        self.subtitle_lbl = ctk.CTkLabel(header, text="",
                                          font=ctk.CTkFont(size=13), text_color=T["tx2"])
        self.subtitle_lbl.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # ── Cartes stats ───────────────────────────────────────────
        self.stats_row = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_row.grid(row=1, column=0, padx=28, pady=(18, 0), sticky="ew")
        for i in range(4):
            self.stats_row.grid_columnconfigure(i, weight=1)

        # ── Ligne principale ───────────────────────────────────────
        self.main_row = ctk.CTkFrame(self, fg_color="transparent")
        self.main_row.grid(row=2, column=0, padx=28, pady=18, sticky="ew")
        self.main_row.grid_columnconfigure(0, weight=1)
        self.main_row.grid_columnconfigure(1, weight=1)

        # ── Macros suggérées ───────────────────────────────────────
        self.macro_row = ctk.CTkFrame(self, fg_color="transparent")
        self.macro_row.grid(row=3, column=0, padx=28, pady=(0, 14), sticky="ew")
        self.macro_row.grid_columnconfigure(0, weight=1)

        # ── Suivi du jour ──────────────────────────────────────────
        self.jour_row = ctk.CTkFrame(self, fg_color="transparent")
        self.jour_row.grid(row=4, column=0, padx=28, pady=(0, 14), sticky="ew")
        self.jour_row.grid_columnconfigure(0, weight=1)

        # ── Sport du jour ──────────────────────────────────────────
        self.sport_row = ctk.CTkFrame(self, fg_color="transparent")
        self.sport_row.grid(row=5, column=0, padx=28, pady=(0, 14), sticky="ew")
        self.sport_row.grid_columnconfigure(0, weight=1)

        # ── Alertes stock ─────────────────────────────────────────
        self.stock_row = ctk.CTkFrame(self, fg_color="transparent")
        self.stock_row.grid(row=6, column=0, padx=28, pady=(0, 14), sticky="ew")
        self.stock_row.grid_columnconfigure(0, weight=1)

        # ── Graphiques ─────────────────────────────────────────────
        self.charts_row = ctk.CTkFrame(self, fg_color="transparent")
        self.charts_row.grid(row=7, column=0, padx=28, pady=(0, 28), sticky="ew")
        self.charts_row.grid_columnconfigure(0, weight=1)
        self.charts_row.grid_columnconfigure(1, weight=1)

    # ──────────────────────────────────────────────────────────────

    def refresh(self):
        for w in self.stats_row.winfo_children():
            w.destroy()
        for w in self.main_row.winfo_children():
            w.destroy()
        for w in self.macro_row.winfo_children():
            w.destroy()
        for w in self.jour_row.winfo_children():
            w.destroy()
        for w in self.sport_row.winfo_children():
            w.destroy()
        for w in self.stock_row.winfo_children():
            w.destroy()
        for w in self.charts_row.winfo_children():
            w.destroy()

        profil    = db.get_profil()
        stats     = db.get_stats()
        prog      = db.get_programme_actif()
        macros    = db.calc_macros_cibles(profil)
        imc       = db.calc_imc(profil.get('poids', 70), profil.get('taille', 170))
        imc_label, imc_color = db.imc_category(imc)

        prenom = profil.get('prenom', '') or 'Utilisateur'
        self.subtitle_lbl.configure(
            text=f"Bonjour {prenom} 👋   •   {_today_fr()}")

        # ── Cartes stats ───────────────────────────────────────────
        cards = [
            ("🥑", str(stats['nb_aliments']), "Aliments",    T["ac"]),
            ("👨‍🍳", str(stats['nb_recettes']),  "Recettes",    T["blue"]),
            ("📋", str(stats['nb_programmes']),"Programmes",  T["lip"]),
            ("⚡", f"{macros['calories']}",     "kcal / jour", T["cal"]),
        ]
        for i, (icon, val, lbl, color) in enumerate(cards):
            c = self._stat_card(self.stats_row, icon, val, lbl, color)
            c.grid(row=0, column=i, padx=(0 if i == 0 else 10, 0), sticky="ew")

        # ── Card Profil ────────────────────────────────────────────
        pc = _card(self.main_row, "👤  Mon Profil")
        pc.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        nom_complet = (f"{profil.get('prenom','')} {profil.get('nom','')}".strip()
                       or "Non renseigné")
        rows = [
            ("Nom",       nom_complet),
            ("Âge",       f"{profil.get('age', '-')} ans"),
            ("Poids",     f"{profil.get('poids', '-')} kg"),
            ("Taille",    f"{profil.get('taille', '-')} cm"),
            ("IMC",       f"{imc}  —  {imc_label}"),
            ("Objectif",  db.OBJECTIFS_LABELS.get(profil.get('objectif',''), '—')),
            ("Activité",  db.ACTIVITE_LABELS.get(profil.get('activite',''), '—').split('(')[0].strip()),
        ]
        for i, (k, v) in enumerate(rows):
            color = imc_color if k == "IMC" else T["tx1"]
            _kv_row(pc, k, v, i + 1, val_color=color)

        _spacer(pc, len(rows) + 1)

        # ── Card Programme ─────────────────────────────────────────
        pgc = _card(self.main_row, "📋  Programme actif")
        pgc.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        if prog:
            ctk.CTkLabel(pgc, text=prog['nom'],
                         font=ctk.CTkFont(size=15, weight="bold"),
                         text_color=T["ac"], anchor="w",
                         wraplength=260).grid(row=1, column=0, padx=18, pady=(0, 10), sticky="w")
            pg_rows = [
                ("Objectif",     db.OBJECTIFS_LABELS.get(prog['objectif'], '—')),
                ("Durée",        f"{prog['duree_semaines']} semaines"),
                ("Calories/jour",f"{prog['calories_jour']} kcal"),
                ("Protéines",    f"{prog['proteines_pct']} %"),
                ("Glucides",     f"{prog['glucides_pct']} %"),
                ("Lipides",      f"{prog['lipides_pct']} %"),
            ]
            for i, (k, v) in enumerate(pg_rows):
                _kv_row(pgc, k, v, i + 2)

            if prog.get('description'):
                ctk.CTkLabel(pgc, text=prog['description'],
                             font=ctk.CTkFont(size=11), text_color=T["tx2"],
                             wraplength=270, justify="left").grid(
                    row=9, column=0, padx=18, pady=(10, 0), sticky="w")
            _spacer(pgc, 10)
        else:
            ctk.CTkLabel(pgc, text="Aucun programme actif",
                         font=ctk.CTkFont(size=13), text_color=T["tx2"]).grid(
                row=1, column=0, padx=18, pady=8, sticky="w")
            ctk.CTkLabel(pgc, text="Rendez-vous dans la section\nProgrammes pour en activer un.",
                         font=ctk.CTkFont(size=12), text_color=T["tx2"],
                         justify="left").grid(row=2, column=0, padx=18, pady=(4, 18), sticky="w")

        # ── Carte macros cibles ────────────────────────────────────
        mc = _card(self.macro_row, "⚡  Objectifs nutritionnels du jour")
        mc.grid(row=0, column=0, sticky="ew")
        mc.grid_columnconfigure((0, 1, 2, 3), weight=1)

        macro_items = [
            (f"{macros['calories']}",  "kcal",  "Énergie",    T["cal"]),
            (f"{macros['proteines']}g","",       "Protéines",  T["ac"]),
            (f"{macros['glucides']}g", "",       "Glucides",   T["blue"]),
            (f"{macros['lipides']}g",  "",       "Lipides",    T["lip"]),
        ]
        for j, (val, unit, lbl, col) in enumerate(macro_items):
            mf = ctk.CTkFrame(mc, fg_color="transparent")
            mf.grid(row=1, column=j, padx=12, pady=(0, 18))
            ctk.CTkLabel(mf, text=val + unit,
                         font=ctk.CTkFont(size=22, weight="bold"),
                         text_color=col).pack()
            ctk.CTkLabel(mf, text=lbl,
                         font=ctk.CTkFont(size=12),
                         text_color=T["tx2"]).pack()

        # ── Suivi du jour ──────────────────────────────────────────
        today_str = date.today().isoformat()
        nutri_j   = db.get_nutri_jour(today_str)
        repas_j   = db.get_planning_jour(today_str)

        jc = _card(self.jour_row, f"📊  Consommé aujourd'hui — {len(repas_j)} repas planifié(s)")
        jc.grid(row=0, column=0, sticky="ew")
        jc.grid_columnconfigure((0, 1, 2, 3), weight=1)

        items_j = [
            (nutri_j['calories'],  macros['calories'],  "kcal", "Énergie",   T["cal"]),
            (nutri_j['proteines'], macros['proteines'], "g",    "Protéines", T["ac"]),
            (nutri_j['glucides'],  macros['glucides'],  "g",    "Glucides",  T["blue"]),
            (nutri_j['lipides'],   macros['lipides'],   "g",    "Lipides",   T["lip"]),
        ]
        for j, (consomme, cible, unit, lbl, col) in enumerate(items_j):
            ring = MacroRing(jc, label=lbl, value=consomme, cible=cible,
                             unit=unit, color=col, size=100, bg_color=T["bg_card"])
            ring.grid(row=1, column=j, padx=14, pady=(8, 12))

        # ── Eau ─────────────────────────────────────────────────
        total_ml = db.get_total_eau_jour(today_str)
        obj_ml   = db.get_objectif_eau()
        pct_eau  = min(1.0, total_ml / max(1, obj_ml))

        wf = ctk.CTkFrame(jc, fg_color=T["bg_el"], corner_radius=8)
        wf.grid(row=2, column=0, columnspan=4, padx=14, pady=(0, 14), sticky="ew")
        wf.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(wf, text="💧",
                     font=ctk.CTkFont(size=16)).grid(row=0, column=0, padx=(12, 4), pady=8)
        ctk.CTkLabel(wf, text="Hydratation",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).grid(
            row=0, column=1, padx=(0, 10))
        pb_w = ctk.CTkProgressBar(wf, height=8,
                                  progress_color=T["blue"], fg_color=T["bg_hl"])
        pb_w.grid(row=0, column=2, sticky="ew", padx=8)
        pb_w.set(pct_eau)
        ctk.CTkLabel(wf, text=f"{total_ml} / {obj_ml} ml",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=T["blue"], width=110, anchor="e").grid(
            row=0, column=3, padx=(4, 12))

        # ── Sport du jour ──────────────────────────────────────────
        self._draw_sport_card(today_str, macros)

        # ── Alertes stock ─────────────────────────────────────────
        self._draw_stock_alerts_card()

        # ── Graphiques ─────────────────────────────────────────────
        if MPL_OK:
            self._draw_charts()

    def _draw_sport_card(self, today_str: str, macros: dict):
        cal_sport = db.get_calories_sport_jour(today_str)
        seances   = db.get_activites_sport_jour(today_str)

        sc = _card(self.sport_row, "🏃  Sport aujourd'hui")
        sc.grid(row=0, column=0, sticky="ew")
        sc.grid_columnconfigure((0, 1, 2, 3), weight=1)

        if not seances:
            ctk.CTkLabel(sc,
                         text="Aucune séance enregistrée.\nRendez-vous dans la section Sport pour logger une activité.",
                         font=ctk.CTkFont(size=12), text_color=T["tx2"],
                         justify="center").grid(row=1, column=0, columnspan=4, pady=18)
            _spacer(sc, 2)
            return

        cal_cible       = macros['calories']
        budget_ajuste   = cal_cible + int(cal_sport * 0.7)
        total_min       = sum(s['duree_min'] for s in seances)

        cols = [
            (f"{len(seances)}",          "Séances",          T["blue"]),
            (f"{int(cal_sport)} kcal",   "Calories brûlées", T["ac"]),
            (f"{total_min} min",         "Durée totale",     T["vio"]),
            (f"{budget_ajuste} kcal",    "Budget ajusté",    T["cal"]),
        ]
        for i, (val, lbl, col) in enumerate(cols):
            cf = ctk.CTkFrame(sc, fg_color="transparent")
            cf.grid(row=1, column=i, padx=12, pady=(8, 4))
            ctk.CTkLabel(cf, text=val,
                         font=ctk.CTkFont(size=20, weight="bold"),
                         text_color=col).pack()
            ctk.CTkLabel(cf, text=lbl,
                         font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack()

        if cal_sport >= 100:
            tip = "💧 Pensez à boire +500 ml d'eau pour récupérer." if cal_sport < 250 else \
                  "🔥 Effort important — protéines + glucides recommandés pour la récupération."
            ctk.CTkLabel(sc, text=tip,
                         font=ctk.CTkFont(size=11), text_color=T["blue"],
                         justify="left").grid(row=2, column=0, columnspan=4,
                                               padx=18, pady=(0, 4), sticky="w")
        _spacer(sc, 3)

    def _draw_stock_alerts_card(self):
        alerts_dlc = db.get_stock_alerts()
        alerts_seuil = db.get_stock_sous_seuil()
        if not alerts_dlc and not alerts_seuil:
            return

        card = ctk.CTkFrame(self.stock_row, fg_color=T["bg_card"], corner_radius=12)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card,
                     text="Stock - Alertes",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T["cal"]).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 6))

        today = date.today().isoformat()
        row_i = 1

        for item in alerts_dlc[:3]:
            dlc = item.get('date_peremption', '')
            if dlc < today:
                txt = f"[x] {item['nom']} - perime"
                col = T["err"]
            else:
                txt = f"[!] {item['nom']} - expire le {dlc}"
                col = T["cal"]
            ctk.CTkLabel(card, text=txt, text_color=col,
                         font=ctk.CTkFont(size=12)).grid(
                row=row_i, column=0, sticky="w", padx=16, pady=2)
            row_i += 1

        for item in alerts_seuil[:3]:
            txt = f"[~] {item['nom']} : {round(item['quantite'],1)}{item['unite']} (seuil {round(item['quantite_min'],1)}{item['unite']})"
            ctk.CTkLabel(card, text=txt, text_color=T["cal"],
                         font=ctk.CTkFont(size=12)).grid(
                row=row_i, column=0, sticky="w", padx=16, pady=2)
            row_i += 1

        ctk.CTkButton(card, text="Voir le stock",
                      fg_color="transparent", hover_color=T["bg_el"],
                      text_color=T["ac"], anchor="e",
                      font=ctk.CTkFont(size=12),
                      command=lambda: self.winfo_toplevel()._show_page("stock")).grid(
            row=row_i, column=0, sticky="e", padx=16, pady=(4, 12))

    def _draw_charts(self):
        # Paramètres visuels partagés
        plt.rcParams.update({
            'figure.facecolor': T["bg_card"], 'axes.facecolor': T["bg_row"],
            'axes.edgecolor':   T["bg_hl"], 'axes.labelcolor': T["tx2"],
            'xtick.color':      T["tx2"], 'ytick.color': T["tx2"],
            'grid.color':       T["bg_el"], 'grid.linestyle': '--', 'grid.alpha': 0.6,
        })

        # ── Courbe poids 30 jours ────────────────────────────────
        pc = _card(self.charts_row, "⚖️  Poids — 30 derniers jours")
        pc.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        poids_data = db.get_suivi_poids(limit=30, frequence="tous")
        if len(poids_data) >= 2:
            chart_p = ctk.CTkFrame(pc, fg_color="transparent", height=200)
            chart_p.grid(row=1, column=0, padx=8, pady=(0, 12), sticky="ew")
            chart_p.grid_propagate(False)

            fig, ax = plt.subplots(figsize=(5, 2.2))
            fig.patch.set_facecolor(T["bg_card"])
            xs = list(range(len(poids_data)))
            ys = [d['poids'] for d in poids_data]
            ax.plot(xs, ys, color=T["blue"], linewidth=2,
                    marker="o", markersize=3, markerfacecolor=T["blue_l"])
            ax.fill_between(xs, ys, [min(ys)-0.5]*len(ys), color=T["blue"], alpha=0.1)
            user = db.get_current_user()
            target = float(user.get('poids_cible') or 0)
            if target > 0:
                ax.axhline(target, color=T["ac"], linewidth=1.2,
                           linestyle="--", alpha=0.8,
                           label=f"Objectif {target} kg")
                ax.legend(fontsize=7, framealpha=0.3,
                          facecolor=T["bg_el"], labelcolor=T["tx1"])
            step = max(1, len(poids_data) // 6)
            lbls = [d['date'][:10] for d in poids_data]
            ax.set_xticks(xs[::step])
            ax.set_xticklabels(lbls[::step], rotation=30, fontsize=7)
            ax.set_ylabel("kg", fontsize=8)
            ax.grid(True)
            fig.tight_layout(pad=0.8)
            canvas = FigureCanvasTkAgg(fig, master=chart_p)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            plt.close(fig)
        else:
            ctk.CTkLabel(pc, text="Enregistrez votre poids\ndans Mon Profil pour voir la courbe",
                         font=ctk.CTkFont(size=11), text_color=T["tx2"],
                         justify="center").grid(row=1, column=0, pady=30)
        _spacer(pc, 2)

        # ── Courbe calories journal 14 jours ─────────────────────
        cc = _card(self.charts_row, "📓  Calories journal — 14 derniers jours")
        cc.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        cal_data = db.get_calories_14j()
        if len(cal_data) >= 2:
            chart_c = ctk.CTkFrame(cc, fg_color="transparent", height=200)
            chart_c.grid(row=1, column=0, padx=8, pady=(0, 12), sticky="ew")
            chart_c.grid_propagate(False)

            fig2, ax2 = plt.subplots(figsize=(5, 2.2))
            fig2.patch.set_facecolor(T["bg_card"])
            xs2 = list(range(len(cal_data)))
            ys2 = [d['calories'] for d in cal_data]
            ax2.bar(xs2, ys2, color=T["cal"], alpha=0.7, width=0.7)
            profil = db.get_profil()
            prog   = db.get_programme_actif()
            cible  = prog['calories_jour'] if prog else db.calc_calories_cible(profil)
            ax2.axhline(cible, color=T["ac"], linewidth=1.2,
                        linestyle="--", alpha=0.8, label=f"Cible {cible} kcal")
            ax2.legend(fontsize=7, framealpha=0.3,
                       facecolor=T["bg_el"], labelcolor=T["tx1"])
            lbls2 = [d['date'][5:] for d in cal_data]
            step2 = max(1, len(cal_data) // 7)
            ax2.set_xticks(xs2[::step2])
            ax2.set_xticklabels(lbls2[::step2], rotation=30, fontsize=7)
            ax2.set_ylabel("kcal", fontsize=8)
            ax2.grid(True, axis="y")
            fig2.tight_layout(pad=0.8)
            canvas2 = FigureCanvasTkAgg(fig2, master=chart_c)
            canvas2.draw()
            canvas2.get_tk_widget().pack(fill="both", expand=True)
            plt.close(fig2)
        else:
            ctk.CTkLabel(cc, text="Utilisez le Journal pour\nenregistrer vos repas quotidiens",
                         font=ctk.CTkFont(size=11), text_color=T["tx2"],
                         justify="center").grid(row=1, column=0, pady=30)
        _spacer(cc, 2)

    # ─── Helper card ───────────────────────────────────────────────
    def _stat_card(self, parent, icon, val, lbl, color):
        card = ctk.CTkFrame(parent, fg_color=T["bg_card"], corner_radius=14, height=110)
        card.grid_columnconfigure(0, weight=1)
        card.grid_propagate(False)
        ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=20)).grid(
            row=0, column=0, padx=16, pady=(14, 0), sticky="w")
        ctk.CTkLabel(card, text=val,
                     font=ctk.CTkFont(family="Helvetica", size=30, weight="bold"),
                     text_color=color).grid(row=1, column=0, padx=16, pady=(0, 0), sticky="w")
        ctk.CTkLabel(card, text=lbl,
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).grid(
            row=2, column=0, padx=16, pady=(0, 14), sticky="w")
        return card


# ─────────────────── Fonctions utilitaires partagées ───────────────────

def _card(parent, title):
    frame = ctk.CTkFrame(parent, fg_color=T["bg_card"], corner_radius=14)
    frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(frame, text=title,
                 font=ctk.CTkFont(size=14, weight="bold"),
                 text_color=T["tx1"]).grid(
        row=0, column=0, padx=18, pady=(16, 12), sticky="w")
    # séparateur
    sep = ctk.CTkFrame(frame, height=1, fg_color=T["bg_el"])
    sep.grid(row=0, column=0, padx=18, pady=(0, 0), sticky="sew")
    return frame


def _kv_row(parent, key, value, row_idx, val_color=T["tx1"]):
    rf = ctk.CTkFrame(parent, fg_color="transparent")
    rf.grid(row=row_idx, column=0, padx=18, pady=2, sticky="ew")
    rf.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(rf, text=key, font=ctk.CTkFont(size=12),
                 text_color=T["tx2"], width=110, anchor="w").grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(rf, text=value, font=ctk.CTkFont(size=12, weight="bold"),
                 text_color=val_color, anchor="e").grid(row=0, column=1, sticky="e")


def _spacer(parent, row_idx, h=12):
    ctk.CTkFrame(parent, height=h, fg_color="transparent").grid(row=row_idx, column=0)


def _today_fr():
    from datetime import date
    import locale
    d = date.today()
    MOIS = ["janvier","février","mars","avril","mai","juin",
            "juillet","août","septembre","octobre","novembre","décembre"]
    JOURS = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month-1]} {d.year}"
