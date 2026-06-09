"""
NutriTrack Pro — Gestion des programmes
"""
import customtkinter as ctk
from tkinter import messagebox
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import database as db
from colors import tint_low, tint_mid, tint_high
from theme import T

OBJECTIFS = {
    "perte_poids": ("🔥", "Perte de poids",        T["err"]),
    "maintien":    ("⚖️",  "Maintien",               T["blue"]),
    "prise_masse": ("💪",  "Prise de masse",         T["ac"]),
}

OBJECTIF_KEYS   = list(OBJECTIFS.keys())
OBJECTIF_LABELS = [OBJECTIFS[k][1] for k in OBJECTIF_KEYS]


class ProgrammesPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=T["bg_app"], corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build()

    # ── Construction ─────────────────────────────────────────────

    def _build(self):
        # Entête
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=28, pady=(28, 0), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="📋  Programmes",
                     font=ctk.CTkFont(family="Helvetica", size=26, weight="bold"),
                     text_color=T["tx1"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header,
                     text="Créez et activez vos programmes nutritionnels personnalisés",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).grid(
            row=1, column=0, sticky="w", pady=(2, 0))

        ctk.CTkButton(header, text="＋  Nouveau programme",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000000", height=38, width=210, corner_radius=8,
                      command=self._open_add).grid(row=0, column=1, rowspan=2, sticky="e")

        # Légende
        leg = ctk.CTkFrame(self, fg_color="transparent")
        leg.grid(row=1, column=0, padx=28, pady=14, sticky="ew")
        for key, (icon, label, color) in OBJECTIFS.items():
            ctk.CTkLabel(leg,
                         text=f"  {icon}  {label}  ",
                         font=ctk.CTkFont(size=11),
                         text_color=color,
                         fg_color=tint_low(color),
                         corner_radius=6).pack(side="left", padx=(0, 8))

        # Corps scrollable
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                            scrollbar_button_color=T["bg_el"],
                                            scrollbar_button_hover_color=T["bg_hl"])
        self.body.grid(row=2, column=0, padx=28, pady=(0, 28), sticky="nsew")
        for c in range(3):
            self.body.grid_columnconfigure(c, weight=1)

        self.refresh()

    # ── Rafraîchissement ─────────────────────────────────────────

    def refresh(self):
        for w in self.body.winfo_children():
            w.destroy()

        programmes = db.get_programmes()
        if not programmes:
            ctk.CTkLabel(self.body,
                         text="Aucun programme\n\nCliquez sur « + Nouveau programme » pour commencer",
                         text_color=T["tx2"], font=ctk.CTkFont(size=14),
                         justify="center").grid(row=0, column=0, columnspan=3, pady=60)
            return

        for i, prog in enumerate(programmes):
            self._make_card(prog, i // 3, i % 3)

    # ── Carte programme ───────────────────────────────────────────

    def _make_card(self, prog, row, col):
        is_actif = bool(prog.get('actif'))
        obj_key  = prog.get('objectif', 'maintien')
        icon, label, color = OBJECTIFS.get(obj_key, ("📋", obj_key, T["tx2"]))

        border = color if is_actif else T["bg_el"]
        card   = ctk.CTkFrame(self.body, fg_color=T["bg_card"], corner_radius=14,
                               border_width=2, border_color=border)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        # Badge actif
        if is_actif:
            ctk.CTkLabel(card,
                         text="  ✅  PROGRAMME ACTIF  ",
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=T["ac"],
                         fg_color=tint_low(T["ac"]),
                         corner_radius=6).grid(
                row=0, column=0, padx=12, pady=(12, 4), sticky="w")
        else:
            ctk.CTkFrame(card, height=6, fg_color="transparent").grid(row=0, column=0)

        # Objectif badge
        ctk.CTkLabel(card,
                     text=f"  {icon}  {label}  ",
                     font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=color,
                     fg_color=tint_low(color),
                     corner_radius=6).grid(
            row=1, column=0, padx=12, pady=(0, 6), sticky="w")

        # Titre
        ctk.CTkLabel(card, text=prog['nom'],
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T["tx1"], anchor="w", wraplength=230).grid(
            row=2, column=0, padx=14, pady=(0, 4), sticky="w")

        # Description
        if prog.get('description'):
            ctk.CTkLabel(card, text=prog['description'],
                         font=ctk.CTkFont(size=11), text_color=T["tx2"],
                         anchor="w", wraplength=230, justify="left").grid(
                row=3, column=0, padx=14, pady=(0, 8), sticky="w")

        # Stats nutritionnelles
        nf = ctk.CTkFrame(card, fg_color=T["bg_el"], corner_radius=10)
        nf.grid(row=4, column=0, padx=12, pady=(0, 8), sticky="ew")
        for j in range(3):
            nf.grid_columnconfigure(j, weight=1)

        # Calories / j
        self._stat_block(nf, f"{prog['calories_jour']}", "kcal/jour", color, 0)

        # Durée
        self._stat_block(nf, f"{prog['duree_semaines']}", "semaines",  T["blue"], 1)

        # Répartition macros
        macros_frame = ctk.CTkFrame(nf, fg_color="transparent")
        macros_frame.grid(row=0, column=2, padx=8, pady=8)
        ctk.CTkLabel(macros_frame,
                     text=f"P {prog['proteines_pct']}%  G {prog['glucides_pct']}%  L {prog['lipides_pct']}%",
                     font=ctk.CTkFont(size=10), text_color=T["tx2"]).pack()
        ctk.CTkLabel(macros_frame, text="Macros",
                     font=ctk.CTkFont(size=10), text_color=T["tx3"]).pack()

        # Boutons
        bf = ctk.CTkFrame(card, fg_color="transparent")
        bf.grid(row=5, column=0, padx=12, pady=(4, 12), sticky="ew")
        bf.grid_columnconfigure(0, weight=1)

        if not is_actif:
            ctk.CTkButton(bf, text="▶  Activer",
                          fg_color=tint_mid(color), hover_color=tint_high(color),
                          text_color=color,
                          height=30, corner_radius=6,
                          font=ctk.CTkFont(size=12, weight="bold"),
                          command=lambda p=prog: self._activate(p)).grid(
                row=0, column=0, padx=(0, 6), sticky="ew")
        else:
            active_row = ctk.CTkFrame(bf, fg_color="transparent")
            active_row.grid(row=0, column=0, padx=(0, 6), sticky="ew")
            active_row.grid_columnconfigure(0, weight=1)
            ctk.CTkButton(active_row, text="✓  Actif",
                          fg_color=tint_low(T["ac"]), hover_color=tint_mid(T["ac"]),
                          text_color=T["ac"],
                          height=30, corner_radius=6,
                          font=ctk.CTkFont(size=12),
                          state="disabled").grid(
                row=0, column=0, padx=(0, 4), sticky="ew")
            ctk.CTkButton(active_row, text="🔄",
                          fg_color=T["bg_el"], hover_color=T["bg_hl"],
                          text_color=T["blue"],
                          width=34, height=30, corner_radius=6,
                          font=ctk.CTkFont(size=13),
                          command=self._open_reequilibrage).grid(row=0, column=1)

        edit_del = ctk.CTkFrame(bf, fg_color="transparent")
        edit_del.grid(row=0, column=1)
        ctk.CTkButton(edit_del, text="✏", width=30, height=30,
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      font=ctk.CTkFont(size=12), corner_radius=6,
                      command=lambda p=prog: self._open_edit(p)).pack(side="left", padx=(0, 4))
        ctk.CTkButton(edit_del, text="🗑", width=30, height=30,
                      fg_color=T["bg_el"], hover_color=T["err_bg"],
                      font=ctk.CTkFont(size=12), corner_radius=6,
                      command=lambda p=prog: self._confirm_delete(p)).pack(side="left")

    def _stat_block(self, parent, val, label, color, col):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, padx=8, pady=8)
        ctk.CTkLabel(f, text=val,
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=color).pack()
        ctk.CTkLabel(f, text=label,
                     font=ctk.CTkFont(size=10),
                     text_color=T["tx2"]).pack()

    # ── Actions ──────────────────────────────────────────────────

    def _activate(self, prog):
        db.set_programme_actif(prog['id'])
        self.refresh()

    def _open_add(self):
        ProgrammeDialog(self, None, self.refresh)

    def _open_edit(self, prog):
        ProgrammeDialog(self, prog, self.refresh)

    def _confirm_delete(self, prog):
        if messagebox.askyesno("Supprimer",
                               f"Supprimer « {prog['nom']} » ?\nCette action est irréversible.",
                               parent=self):
            db.delete_programme(prog['id'])
            self.refresh()

    def _open_reequilibrage(self):
        ReequilibrageDialog(self, self.refresh)


# ─────────────────────── Dialogue Programme ──────────────────────────────────


class ProgrammeDialog(ctk.CTkToplevel):
    def __init__(self, parent, prog, callback):
        super().__init__(parent)
        self.prog     = prog
        self.callback = callback
        self.title("Modifier le programme" if prog else "Nouveau programme")
        self.geometry("500x680")
        self.resizable(False, False)
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()
        self._build()
        if prog:
            self._populate()

    def _build(self):
        ctk.CTkLabel(self,
                     text="Modifier le programme" if self.prog else "Nouveau programme",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=T["tx1"]).pack(padx=24, pady=(22, 16), anchor="w")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                         scrollbar_button_color=T["bg_el"])
        scroll.pack(fill="both", expand=True, padx=24, pady=4)
        scroll.grid_columnconfigure((0, 1), weight=1)

        self.vars = {}

        def row_entry(label, key, r, col=0, span=2):
            ctk.CTkLabel(scroll, text=label,
                         font=ctk.CTkFont(size=12), text_color=T["tx2"]).grid(
                row=r * 2, column=col, columnspan=span, padx=6, pady=(10, 2), sticky="w")
            var = ctk.StringVar()
            ctk.CTkEntry(scroll, textvariable=var, height=36,
                         fg_color=T["bg_el"], border_color=T["bg_hl"],
                         font=ctk.CTkFont(size=13)).grid(
                row=r * 2 + 1, column=col, columnspan=span, padx=6, sticky="ew")
            self.vars[key] = var

        def row_combo(label, key, r, col, opts, val_map=None):
            ctk.CTkLabel(scroll, text=label,
                         font=ctk.CTkFont(size=12), text_color=T["tx2"]).grid(
                row=r * 2, column=col, padx=6, pady=(10, 2), sticky="w")
            var = ctk.StringVar(value=opts[0])
            ctk.CTkOptionMenu(scroll, variable=var, values=opts,
                              fg_color=T["bg_el"], button_color=T["bg_hl"],
                              height=36, font=ctk.CTkFont(size=12)).grid(
                row=r * 2 + 1, column=col, padx=6, sticky="ew")
            self.vars[key] = var

        row_entry("Nom du programme *",        "nom",            0)
        row_combo("Objectif",                   "objectif",       1, 0, OBJECTIF_LABELS)
        row_entry("Durée (semaines)",           "duree_semaines", 1, 1, 1)
        row_entry("Calories par jour (kcal)",   "calories_jour",  2)

        # Séparateur macros
        ctk.CTkLabel(scroll, text="Répartition des macronutriments (%)",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["tx1"]).grid(
            row=6, column=0, columnspan=2, padx=6, pady=(18, 6), sticky="w")
        ctk.CTkLabel(scroll, text="Les 3 valeurs doivent totaliser 100 %",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).grid(
            row=7, column=0, columnspan=2, padx=6, pady=(0, 4), sticky="w")

        for label, key, col in [("Protéines (%)", "proteines_pct", 0),
                                  ("Glucides (%)",  "glucides_pct",  1)]:
            ctk.CTkLabel(scroll, text=label,
                         font=ctk.CTkFont(size=12), text_color=T["tx2"]).grid(
                row=8, column=col, padx=6, pady=(4, 2), sticky="w")
            var = ctk.StringVar()
            ctk.CTkEntry(scroll, textvariable=var, height=36,
                         fg_color=T["bg_el"], border_color=T["bg_hl"],
                         font=ctk.CTkFont(size=13)).grid(
                row=9, column=col, padx=6, sticky="ew")
            self.vars[key] = var

        ctk.CTkLabel(scroll, text="Lipides (%)",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).grid(
            row=10, column=0, padx=6, pady=(10, 2), sticky="w")
        var = ctk.StringVar()
        ctk.CTkEntry(scroll, textvariable=var, height=36,
                     fg_color=T["bg_el"], border_color=T["bg_hl"],
                     font=ctk.CTkFont(size=13)).grid(
            row=11, column=0, padx=6, sticky="ew")
        self.vars["lipides_pct"] = var

        row_entry("Description / notes",        "description",   6, 0, 2)

        # Boutons
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(padx=24, pady=(6, 20), fill="x")
        ctk.CTkButton(bf, text="Annuler",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=38, width=120, corner_radius=8,
                      command=self.destroy).pack(side="left")
        ctk.CTkButton(bf, text="✔  Enregistrer",
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000000", height=38, width=160,
                      corner_radius=8, command=self._save).pack(side="right")

    def _populate(self):
        obj_label = OBJECTIFS.get(self.prog.get('objectif', 'maintien'), ('', 'Maintien', ''))[1]
        self.vars['objectif'].set(obj_label)
        for key in ('nom', 'duree_semaines', 'calories_jour',
                    'proteines_pct', 'glucides_pct', 'lipides_pct', 'description'):
            v = self.prog.get(key, '')
            self.vars[key].set('' if v is None else str(v))

    def _save(self):
        data = {k: v.get().strip() for k, v in self.vars.items()}
        if not data.get("nom"):
            messagebox.showwarning("Champ requis", "Le nom est obligatoire.", parent=self)
            return

        # Convertir objectif label → clé
        for k, (icon, lbl, col) in OBJECTIFS.items():
            if lbl == data['objectif']:
                data['objectif'] = k
                break
        else:
            data['objectif'] = 'maintien'

        for key in ('duree_semaines', 'calories_jour',
                    'proteines_pct', 'glucides_pct', 'lipides_pct'):
            try:
                data[key] = int(data[key]) if data[key] else 0
            except ValueError:
                data[key] = 0

        total = data['proteines_pct'] + data['glucides_pct'] + data['lipides_pct']
        if total != 100 and total != 0:
            if not messagebox.askyesno("Vérification",
                                       f"Les macros totalisent {total} % (≠ 100 %).\nContinuer quand même ?",
                                       parent=self):
                return

        if self.prog:
            db.update_programme(self.prog['id'], data)
        else:
            db.add_programme(data)

        self.callback()
        self.destroy()


# ─────────────────────── Dialogue Rééquilibrage ──────────────────────────────

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _MPL_OK = True
except ImportError:
    _MPL_OK = False


class ReequilibrageDialog(ctk.CTkToplevel):
    """Mode rééquilibrage progressif — analyse poids réel vs projeté."""

    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback   = callback
        self._fig_ref   = None
        self.title("Rééquilibrage progressif")
        self.geometry("640x720")
        self.resizable(False, True)
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="🔄  Rééquilibrage progressif",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=T["tx1"]).pack(padx=24, pady=(22, 4), anchor="w")
        ctk.CTkLabel(self,
                     text="Ajustement automatique des calories selon votre évolution de poids",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(padx=24, anchor="w")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                         scrollbar_button_color=T["bg_el"])
        scroll.pack(fill="both", expand=True, padx=24, pady=(14, 0))
        scroll.grid_columnconfigure(0, weight=1)
        self._scroll = scroll

        data = db.get_reequilibrage_data()
        if not data:
            ctk.CTkLabel(scroll,
                         text="Aucun programme actif ou profil incomplet.",
                         font=ctk.CTkFont(size=13), text_color=T["tx2"]).pack(pady=40)
            self._add_close_button()
            return

        self._render_data(data)
        self._add_action_buttons(data)

    def _render_data(self, data: dict):
        scroll = self._scroll
        obj    = data.get('objectif', 'maintien')
        icon, lbl, color = OBJECTIFS.get(obj, ("📋", obj, T["tx2"]))

        # ── Résumé programme ─────────────────────────────────────
        summary = ctk.CTkFrame(scroll, fg_color=T["bg_el"], corner_radius=12)
        summary.pack(fill="x", pady=(0, 14))
        summary.grid_columnconfigure((0, 1, 2), weight=1)

        def stat(col, val, label, c):
            f = ctk.CTkFrame(summary, fg_color="transparent")
            f.grid(row=0, column=col, padx=10, pady=12)
            ctk.CTkLabel(f, text=val,
                         font=ctk.CTkFont(size=18, weight="bold"),
                         text_color=c).pack()
            ctk.CTkLabel(f, text=label,
                         font=ctk.CTkFont(size=10), text_color=T["tx2"]).pack()

        stat(0, f"{data['cal_cible']} kcal", "Objectif actuel", color)
        stat(1, f"{data['cal_tdee']} kcal", "TDEE estimé",      T["blue"])
        kg = data['kg_par_semaine']
        kg_str = f"{'+'if kg>0 else ''}{kg} kg/sem."
        stat(2, kg_str, "Progression projetée",
             T["ac"] if kg < 0 else (T["lip"] if kg == 0 else T["blue"]))

        # ── Graphique poids ──────────────────────────────────────
        semaines = data.get('semaines', [])
        if _MPL_OK and len(semaines) >= 2:
            chart_frame = ctk.CTkFrame(scroll, fg_color=T["bg_app"], corner_radius=12)
            chart_frame.pack(fill="x", pady=(0, 14))
            ctk.CTkLabel(chart_frame,
                         text="Poids réel vs projeté (par semaine)",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=T["tx1"]).pack(padx=16, pady=(12, 0), anchor="w")

            labels     = [s['semaine'] for s in semaines]
            reels      = [s['poids_reel'] for s in semaines]
            projetes   = [s['poids_proj'] for s in semaines]

            fig, ax = plt.subplots(figsize=(5.6, 2.8), facecolor=T["bg_app"])
            ax.set_facecolor(T["bg_app"])
            ax.plot(range(len(labels)), reels,    color=T["ac"], linewidth=2,
                    marker="o", markersize=5, label="Réel")
            ax.plot(range(len(labels)), projetes, color=T["blue"], linewidth=1.5,
                    linestyle="--", marker="s", markersize=4, label="Projeté")
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8, color=T["tx2"])
            ax.tick_params(axis="y", colors=T["tx2"], labelsize=8)
            ax.spines[:].set_color(T["bg_el"])
            ax.legend(fontsize=9, frameon=False, labelcolor=T["tx1"],
                      facecolor=T["bg_app"], loc="best")
            fig.tight_layout(pad=0.8)

            canvas = FigureCanvasTkAgg(fig, master=chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(padx=12, pady=(4, 14))
            self._fig_ref = fig
        elif semaines:
            # Tableau texte si matplotlib absent ou données insuffisantes
            tbl_frame = ctk.CTkFrame(scroll, fg_color=T["bg_el"], corner_radius=12)
            tbl_frame.pack(fill="x", pady=(0, 14))
            ctk.CTkLabel(tbl_frame, text="Données hebdomadaires",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=T["tx1"]).pack(padx=16, pady=(12, 6), anchor="w")
            header_row = ctk.CTkFrame(tbl_frame, fg_color="transparent")
            header_row.pack(fill="x", padx=16)
            for txt, w in [("Semaine", 120), ("Réel", 90), ("Projeté", 90), ("Écart", 80)]:
                ctk.CTkLabel(header_row, text=txt, width=w,
                             font=ctk.CTkFont(size=11, weight="bold"),
                             text_color=T["tx2"], anchor="w").pack(side="left")
            for s in semaines:
                delta = s['delta']
                c = T["ac"] if abs(delta) <= 0.5 else (T["lip"] if abs(delta) <= 1 else T["err"])
                r = ctk.CTkFrame(tbl_frame, fg_color="transparent")
                r.pack(fill="x", padx=16)
                sign = "+" if delta >= 0 else ""
                for txt, w in [(s['semaine'], 120),
                               (f"{s['poids_reel']:.1f} kg", 90),
                               (f"{s['poids_proj']:.1f} kg", 90),
                               (f"{sign}{delta:.1f} kg", 80)]:
                    ctk.CTkLabel(r, text=txt, width=w,
                                 font=ctk.CTkFont(size=11),
                                 text_color=c if "kg" in txt and "Projeté" not in txt else T["tx1"],
                                 anchor="w").pack(side="left")
            ctk.CTkFrame(tbl_frame, height=12, fg_color="transparent").pack()
        else:
            ctk.CTkLabel(scroll,
                         text="Pas encore de données de poids enregistrées.\n"
                              "Ajoutez votre poids dans Mon Profil pour activer le rééquilibrage.",
                         font=ctk.CTkFont(size=12), text_color=T["tx2"],
                         justify="center").pack(pady=20)

        # ── Suggestion ───────────────────────────────────────────
        adj     = data.get('adjustment', 0)
        new_cal = data.get('cal_ajustees', data.get('cal_cible', 1800))
        delta_m = data.get('delta_moyen', 0)

        suggest = ctk.CTkFrame(scroll, fg_color=T["bg_el"], corner_radius=12)
        suggest.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(suggest, text="Suggestion de rééquilibrage",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["tx1"]).pack(padx=16, pady=(14, 6), anchor="w")

        if len(semaines) < 2:
            ctk.CTkLabel(suggest,
                         text="Minimum 2 semaines de données requises pour une suggestion.",
                         font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(
                padx=16, pady=(0, 14), anchor="w")
        elif adj == 0:
            ctk.CTkLabel(suggest,
                         text=f"✅  Programme bien calibré — écart moyen {delta_m:+.2f} kg/semaine.",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=T["ac"]).pack(padx=16, pady=(0, 14), anchor="w")
        else:
            direction = "Augmenter" if adj > 0 else "Réduire"
            reason    = ("progression trop rapide" if adj > 0 and obj == "perte_poids"
                         else "progression trop lente" if adj < 0 and obj == "perte_poids"
                         else "prise trop lente" if adj > 0
                         else "prise trop rapide")
            adj_color = T["ac"] if adj > 0 else T["lip"]

            info = ctk.CTkFrame(suggest, fg_color=tint_low(adj_color), corner_radius=8)
            info.pack(fill="x", padx=16, pady=(0, 8))
            ctk.CTkLabel(info,
                         text=f"  {direction} de {abs(adj)} kcal/jour  ({reason})",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=adj_color).pack(padx=12, pady=8, anchor="w")

            ctk.CTkLabel(suggest,
                         text=f"{data['cal_cible']} kcal/jour  →  {new_cal} kcal/jour",
                         font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=T["tx1"]).pack(padx=16, pady=(0, 4), anchor="w")
            ctk.CTkLabel(suggest,
                         text=f"Écart moyen sur {min(4, len(semaines))} semaines : {delta_m:+.2f} kg/sem.",
                         font=ctk.CTkFont(size=10), text_color=T["tx2"]).pack(
                padx=16, pady=(0, 14), anchor="w")

        self._new_cal = new_cal
        self._adj     = adj

    def _add_action_buttons(self, data: dict):
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(padx=24, pady=(8, 20), fill="x")
        ctk.CTkButton(bf, text="Fermer",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=38, width=120, corner_radius=8,
                      command=self._close).pack(side="left")

        adj = data.get('adjustment', 0)
        if adj != 0 and len(data.get('semaines', [])) >= 2:
            ctk.CTkButton(bf,
                          text=f"✔  Appliquer {self._new_cal} kcal/jour",
                          fg_color=T["ac"], hover_color=T["ac_d"],
                          text_color="#000000", height=38, corner_radius=8,
                          font=ctk.CTkFont(size=13, weight="bold"),
                          command=self._apply).pack(side="right")

    def _add_close_button(self):
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(padx=24, pady=(8, 20), fill="x")
        ctk.CTkButton(bf, text="Fermer",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=38, width=120, corner_radius=8,
                      command=self._close).pack(side="left")

    def _apply(self):
        db.apply_reequilibrage(self._new_cal)
        self.callback()
        messagebox.showinfo("Rééquilibrage appliqué",
                            f"Objectif calorique mis à jour : {self._new_cal} kcal/jour.",
                            parent=self)
        self._close()

    def _close(self):
        if self._fig_ref is not None:
            try:
                plt.close(self._fig_ref)
            except Exception:
                pass
        self.destroy()
