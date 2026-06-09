"""
NutriTrack Pro — Statistiques nutritionnelles avancées
"""
import customtkinter as ctk
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import database as db
from colors import tint_low, tint_mid
from theme import T

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MPL_OK = True
except ImportError:
    MPL_OK = False

ACCENT  = T["ac"]
PERIODS = [("7 jours", 7), ("30 jours", 30), ("90 jours", 90)]

MACRO_COLORS = {
    "Protéines": T["ac"],
    "Glucides":  T["blue"],
    "Lipides":   T["lip"],
}


class StatsPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=T["bg_app"], corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._period = 30
        self._canvas_refs = []
        self._build()

    # ── Construction ─────────────────────────────────────────────

    def _build(self):
        # Entête + sélecteur de période
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=28, pady=(28, 0), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="📊  Statistiques nutritionnelles",
                     font=ctk.CTkFont(family="Helvetica", size=26, weight="bold"),
                     text_color=T["tx1"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="Analyse de votre journal alimentaire",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).grid(
            row=1, column=0, sticky="w", pady=(2, 0))

        period_row = ctk.CTkFrame(header, fg_color="transparent")
        period_row.grid(row=0, column=1, rowspan=2, sticky="e")
        ctk.CTkLabel(period_row, text="Période :",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).pack(side="left", padx=(0, 8))
        self._period_btns = {}
        for label, days in PERIODS:
            b = ctk.CTkButton(period_row, text=label, width=80, height=32,
                              corner_radius=8,
                              font=ctk.CTkFont(size=12),
                              fg_color=T["ac_bg"] if days == self._period else T["bg_card"],
                              text_color=ACCENT if days == self._period else T["tx2"],
                              hover_color=T["ac_bg"],
                              command=lambda d=days: self._set_period(d))
            b.pack(side="left", padx=3)
            self._period_btns[days] = b

        # Séparateur visuel
        ctk.CTkFrame(period_row, width=1, fg_color=T["bg_el"]).pack(side="left", padx=8, fill="y")
        ctk.CTkButton(period_row, text="📄 Rapport",
                      width=90, height=32, corner_radius=8,
                      font=ctk.CTkFont(size=12),
                      fg_color=T["bg_card"], text_color=T["tx2"],
                      hover_color=T["ac_bg"],
                      command=self._open_rapport).pack(side="left", padx=3)

        # Corps scrollable
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                            scrollbar_button_color=T["bg_el"],
                                            scrollbar_button_hover_color=T["bg_hl"])
        self.body.grid(row=1, column=0, padx=28, pady=(14, 28), sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)

    def _open_rapport(self):
        from pages.rapport_dialog import RapportDialog
        RapportDialog(self)

    # ── Période ──────────────────────────────────────────────────

    def _set_period(self, days: int):
        self._period = days
        for d, btn in self._period_btns.items():
            active = d == days
            btn.configure(
                fg_color=T["ac_bg"] if active else T["bg_card"],
                text_color=ACCENT if active else T["tx2"])
        self._render()

    # ── Rafraîchissement ─────────────────────────────────────────

    def refresh(self):
        self._render()

    def _render(self):
        for w in self.body.winfo_children():
            w.destroy()
        for fig in self._canvas_refs:
            try:
                plt.close(fig)
            except Exception:
                pass
        self._canvas_refs = []

        stats = db.get_adherence_stats(self._period)
        data  = db.get_stats_nutrition(self._period)

        if not db.get_current_user_id():
            ctk.CTkLabel(self.body, text="Connectez-vous pour voir vos statistiques.",
                         font=ctk.CTkFont(size=14), text_color=T["tx2"]).grid(
                row=0, column=0, pady=60)
            return

        if stats.get('jours', 0) == 0:
            ctk.CTkLabel(self.body,
                         text="Aucune donnée dans le journal pour cette période.\n"
                              "Ajoutez des repas dans le Journal pour voir vos statistiques.",
                         font=ctk.CTkFont(size=14), text_color=T["tx2"],
                         justify="center").grid(row=0, column=0, pady=60)
            return

        self._draw_kpis(stats)
        if MPL_OK and data:
            self._draw_charts(data, stats)
        self._draw_weeks(stats)

    # ── KPI cards ────────────────────────────────────────────────

    def _draw_kpis(self, stats: dict):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.grid(row=0, column=0, pady=(0, 18), sticky="ew")
        for i in range(4):
            row.grid_columnconfigure(i, weight=1)

        cible = stats.get('cible_cal', 2000)

        def kpi(col, val, label, color, sub=None):
            card = ctk.CTkFrame(row, fg_color=T["bg_card"], corner_radius=14)
            card.grid(row=0, column=col, padx=6, sticky="nsew")
            ctk.CTkLabel(card, text=val,
                         font=ctk.CTkFont(size=26, weight="bold"),
                         text_color=color).pack(padx=20, pady=(18, 2))
            ctk.CTkLabel(card, text=label,
                         font=ctk.CTkFont(size=12), text_color=T["tx1"]).pack()
            if sub:
                ctk.CTkLabel(card, text=sub,
                             font=ctk.CTkFont(size=10), text_color=T["tx2"]).pack(pady=(2, 14))
            else:
                ctk.CTkFrame(card, height=14, fg_color="transparent").pack()

        avg_cal  = int(stats.get('avg_cal',  0))
        avg_prot = int(stats.get('avg_prot', 0))
        pct_cal  = stats.get('pct_cal_ok',  0)
        pct_prot = stats.get('pct_prot_ok', 0)
        jours    = stats.get('jours', 0)

        diff = avg_cal - cible
        diff_str = f"{'+'if diff>0 else ''}{diff:.0f} vs cible"
        cal_color = ACCENT if abs(diff) <= cible * 0.1 else (T["lip"] if abs(diff) <= cible * 0.2 else T["err"])

        kpi(0, f"{avg_cal}", "Calories moy./jour", cal_color, diff_str)
        kpi(1, f"{pct_cal} %", "Jours à l'objectif",
            ACCENT if pct_cal >= 70 else (T["lip"] if pct_cal >= 40 else T["err"]),
            f"±10 % de {cible:.0f} kcal")
        kpi(2, f"{avg_prot} g", "Protéines moy./jour",
            ACCENT if pct_prot >= 70 else T["lip"],
            f"{pct_prot} % jours ok")
        kpi(3, f"{jours}", "Jours enregistrés",
            T["blue"], f"sur {self._period} jours")

    # ── Graphiques ────────────────────────────────────────────────

    def _draw_charts(self, data: list, stats: dict):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.grid(row=1, column=0, pady=(0, 18), sticky="ew")
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=2)

        # ── Camembert macros ─────────────────────────────────────
        pie_frame = ctk.CTkFrame(row, fg_color=T["bg_card"], corner_radius=14)
        pie_frame.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        ctk.CTkLabel(pie_frame, text="Répartition des macros",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["tx1"]).pack(padx=16, pady=(14, 0), anchor="w")
        ctk.CTkLabel(pie_frame, text="(en kcal, moyenne sur la période)",
                     font=ctk.CTkFont(size=10), text_color=T["tx2"]).pack(padx=16, anchor="w")

        macro_dist = stats.get('macro_dist', {})
        labels = list(macro_dist.keys())
        sizes  = [macro_dist[k] for k in labels]
        colors = [MACRO_COLORS.get(k, T["tx2"]) for k in labels]

        fig, ax = plt.subplots(figsize=(3.6, 3.0), facecolor=T["bg_card"])
        wedges, texts, autotexts = ax.pie(
            sizes, labels=None, colors=colors,
            autopct="%1.0f%%", startangle=90,
            wedgeprops=dict(width=0.6),
            pctdistance=0.75)
        for t in autotexts:
            t.set_color(T["tx1"])
            t.set_fontsize(10)
        ax.set_facecolor(T["bg_card"])
        legend_patches = [mpatches.Patch(color=c, label=l) for c, l in zip(colors, labels)]
        ax.legend(handles=legend_patches, loc="lower center",
                  bbox_to_anchor=(0.5, -0.08), ncol=3,
                  fontsize=9, frameon=False,
                  labelcolor=T["tx1"], facecolor=T["bg_card"])
        fig.tight_layout(pad=0.4)

        canvas = FigureCanvasTkAgg(fig, master=pie_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(padx=12, pady=(4, 16))
        self._canvas_refs.append(fig)

        # ── Barres calories ──────────────────────────────────────
        bar_frame = ctk.CTkFrame(row, fg_color=T["bg_card"], corner_radius=14)
        bar_frame.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
        ctk.CTkLabel(bar_frame, text="Calories journalières",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["tx1"]).pack(padx=16, pady=(14, 0), anchor="w")
        ctk.CTkLabel(bar_frame, text="Journal alimentaire — trait rouge = cible",
                     font=ctk.CTkFont(size=10), text_color=T["tx2"]).pack(padx=16, anchor="w")

        dates  = [r['date'][-5:] for r in data]   # MM-DD
        cals   = [float(r['calories'] or 0) for r in data]
        cible  = stats.get('cible_cal', 2000)
        bar_colors = [ACCENT if abs(c - cible) <= cible * 0.1
                      else (T["lip"] if abs(c - cible) <= cible * 0.2
                            else T["err"]) for c in cals]

        width  = max(5.5, min(9.0, len(dates) * 0.22))
        fig2, ax2 = plt.subplots(figsize=(width, 3.0), facecolor=T["bg_card"])
        ax2.set_facecolor(T["bg_card"])
        ax2.bar(range(len(dates)), cals, color=bar_colors, width=0.65)
        ax2.axhline(cible, color=T["err"], linewidth=1.2, linestyle="--")
        step = max(1, len(dates) // 10)
        ax2.set_xticks(range(0, len(dates), step))
        ax2.set_xticklabels(dates[::step], rotation=45, ha="right",
                            fontsize=8, color=T["tx2"])
        ax2.tick_params(axis="y", colors=T["tx2"], labelsize=8)
        ax2.spines[:].set_color(T["bg_el"])
        ax2.yaxis.label.set_color(T["tx2"])
        fig2.tight_layout(pad=0.8)

        canvas2 = FigureCanvasTkAgg(fig2, master=bar_frame)
        canvas2.draw()
        canvas2.get_tk_widget().pack(padx=12, pady=(4, 16), fill="x", expand=True)
        self._canvas_refs.append(fig2)

    # ── Semaines ──────────────────────────────────────────────────

    def _draw_weeks(self, stats: dict):
        week_avgs  = stats.get('week_avgs', {})
        best_week  = stats.get('best_week',  '—')
        worst_week = stats.get('worst_week', '—')
        cible      = stats.get('cible_cal',  2000)

        card = ctk.CTkFrame(self.body, fg_color=T["bg_card"], corner_radius=14)
        card.grid(row=2, column=0, pady=(0, 18), sticky="ew")
        card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(card, text="Analyse hebdomadaire",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["tx1"]).grid(
            row=0, column=0, columnspan=2, padx=18, pady=(14, 8), sticky="w")

        if not week_avgs:
            ctk.CTkLabel(card, text="Pas assez de données (minimum 7 jours).",
                         font=ctk.CTkFont(size=12), text_color=T["tx2"]).grid(
                row=1, column=0, columnspan=2, padx=18, pady=(0, 14))
            return

        def week_block(col, label, week_key, color):
            f = ctk.CTkFrame(card, fg_color=T["bg_el"], corner_radius=10)
            f.grid(row=1, column=col, padx=12, pady=(0, 16), sticky="ew")
            ctk.CTkLabel(f, text=label,
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=color).pack(padx=16, pady=(12, 2), anchor="w")
            ctk.CTkLabel(f, text=week_key,
                         font=ctk.CTkFont(size=18, weight="bold"),
                         text_color=T["tx1"]).pack(padx=16, anchor="w")
            avg = week_avgs.get(week_key)
            if avg is not None:
                diff = int(avg - cible)
                diff_str = f"Moy. {avg:.0f} kcal  ({'+'if diff>0 else ''}{diff} vs cible)"
                ctk.CTkLabel(f, text=diff_str,
                             font=ctk.CTkFont(size=10), text_color=T["tx2"]).pack(
                    padx=16, pady=(2, 12))

        week_block(0, "✅  Meilleure semaine", best_week,  ACCENT)
        week_block(1, "⚠️   Semaine la plus difficile", worst_week, T["lip"])

        # Tableau de toutes les semaines
        if len(week_avgs) > 1:
            sep = ctk.CTkFrame(card, height=1, fg_color=T["bg_el"])
            sep.grid(row=2, column=0, columnspan=2, padx=18, pady=(0, 8), sticky="ew")
            ctk.CTkLabel(card, text="Toutes les semaines",
                         font=ctk.CTkFont(size=11), text_color=T["tx2"]).grid(
                row=3, column=0, columnspan=2, padx=18, pady=(0, 6), sticky="w")
            tbl = ctk.CTkFrame(card, fg_color="transparent")
            tbl.grid(row=4, column=0, columnspan=2, padx=18, pady=(0, 16), sticky="ew")
            for i, (week, avg) in enumerate(sorted(week_avgs.items())):
                diff  = int(avg - cible)
                color = ACCENT if abs(diff) <= cible * 0.1 else (T["lip"] if abs(diff) <= cible * 0.2 else T["err"])
                ctk.CTkLabel(tbl, text=week,
                             font=ctk.CTkFont(size=11), text_color=T["tx2"],
                             width=100, anchor="w").grid(row=i, column=0, padx=(0, 8))
                ctk.CTkLabel(tbl, text=f"{avg:.0f} kcal",
                             font=ctk.CTkFont(size=11, weight="bold"),
                             text_color=color, width=100, anchor="w").grid(row=i, column=1, padx=(0, 8))
                sign = "+" if diff >= 0 else ""
                ctk.CTkLabel(tbl, text=f"{sign}{diff}",
                             font=ctk.CTkFont(size=11),
                             text_color=color, width=70, anchor="w").grid(row=i, column=2)
