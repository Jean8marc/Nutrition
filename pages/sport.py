"""
NutriTrack Pro — Sport & Activité
Suivi des séances sportives avec impact nutritionnel.
"""
import os, sys
from datetime import date, datetime, timedelta
import customtkinter as ctk
from tkinter import messagebox
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import database as db
from theme import T

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MPL_OK = True
except ImportError:
    MPL_OK = False

ACCENT = T["ac"]


def _tint(color: str) -> str:
    try:
        from colors import tint_low
        return tint_low(color, bg=T["bg_card"])
    except Exception:
        return T["bg_el"]


class SportPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=T["bg_app"], corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._date = date.today()
        self._canvas_refs = []
        self._build()

    # ── Construction ─────────────────────────────────────────────

    def _build(self):
        nav = ctk.CTkFrame(self, fg_color=T["bg_card"], corner_radius=0, height=60)
        nav.grid(row=0, column=0, sticky="ew")
        nav.grid_columnconfigure(1, weight=1)
        nav.grid_propagate(False)

        ctk.CTkLabel(nav, text="🏃  Sport & Activité",
                     font=ctk.CTkFont(family="Helvetica", size=20, weight="bold"),
                     text_color=T["tx1"]).grid(row=0, column=0, padx=20, sticky="w")

        nav_mid = ctk.CTkFrame(nav, fg_color="transparent")
        nav_mid.grid(row=0, column=1)

        ctk.CTkButton(nav_mid, text="◀", width=32, height=32,
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      command=self._prev_day).pack(side="left", padx=4)

        self._date_lbl = ctk.CTkLabel(nav_mid, text="",
                                       font=ctk.CTkFont(size=13, weight="bold"),
                                       text_color=T["tx1"], width=200)
        self._date_lbl.pack(side="left", padx=8)

        ctk.CTkButton(nav_mid, text="▶", width=32, height=32,
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      command=self._next_day).pack(side="left", padx=4)

        ctk.CTkButton(nav_mid, text="Aujourd'hui", width=100, height=32,
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      font=ctk.CTkFont(size=12),
                      command=self._goto_today).pack(side="left", padx=8)

        ctk.CTkButton(nav, text="+ Ajouter une séance",
                      fg_color=ACCENT, hover_color=T["ac_d"],
                      text_color=T["bg_app"],
                      font=ctk.CTkFont(size=13, weight="bold"),
                      height=36, corner_radius=8,
                      command=self._open_add_dialog).grid(
            row=0, column=2, padx=20, sticky="e")

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                            scrollbar_button_color=T["bg_el"],
                                            scrollbar_button_hover_color=T["bg_hl"])
        self.body.grid(row=1, column=0, padx=28, pady=(14, 28), sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)

    # ── Navigation date ──────────────────────────────────────────

    def _prev_day(self):
        self._date -= timedelta(days=1)
        self.refresh()

    def _next_day(self):
        self._date += timedelta(days=1)
        self.refresh()

    def _goto_today(self):
        self._date = date.today()
        self.refresh()

    def _fmt_date(self) -> str:
        jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        mois  = ["", "janvier", "février", "mars", "avril", "mai", "juin",
                 "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        d = self._date
        return f"{jours[d.weekday()]} {d.day} {mois[d.month]} {d.year}"

    # ── Rafraîchissement ─────────────────────────────────────────

    def refresh(self):
        self._date_lbl.configure(text=self._fmt_date())
        for w in self.body.winfo_children():
            w.destroy()
        for fig in self._canvas_refs:
            try:
                plt.close(fig)
            except Exception:
                pass
        self._canvas_refs = []

        if not db.get_current_user_id():
            ctk.CTkLabel(self.body,
                         text="Connectez-vous pour voir vos activités sportives.",
                         font=ctk.CTkFont(size=14), text_color=T["tx2"]).grid(
                row=0, column=0, pady=60)
            return

        self._draw_summary()
        self._draw_impact_banner()
        self._draw_sessions()
        if MPL_OK:
            self._draw_chart()
        self._draw_zones_card()

    # ── Résumé du jour ───────────────────────────────────────────

    def _draw_summary(self):
        date_str  = self._date.isoformat()
        stats_sem = db.get_stats_sport_semaine()
        cal_jour  = db.get_calories_sport_jour(date_str)
        seances   = db.get_activites_sport_jour(date_str)
        cette_sem = stats_sem['cette_semaine']
        prec_sem  = stats_sem['semaine_precedente']

        if prec_sem['minutes'] > 0:
            delta = int((cette_sem['minutes'] - prec_sem['minutes']) / prec_sem['minutes'] * 100)
            prog_txt = f"+{delta} %" if delta >= 0 else f"{delta} %"
            prog_col = ACCENT if delta >= 0 else T["err"]
        else:
            prog_txt = "1ère semaine !"
            prog_col = T["blue"]

        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.grid(row=0, column=0, pady=(0, 16), sticky="ew")
        for i in range(4):
            row.grid_columnconfigure(i, weight=1)

        def kpi(col, val, label, color, sub=None):
            card = ctk.CTkFrame(row, fg_color=T["bg_card"], corner_radius=14)
            card.grid(row=0, column=col, padx=6, sticky="nsew")
            ctk.CTkLabel(card, text=val,
                         font=ctk.CTkFont(size=26, weight="bold"),
                         text_color=color).pack(padx=20, pady=(18, 2))
            ctk.CTkLabel(card, text=label,
                         font=ctk.CTkFont(size=12), text_color=T["tx1"]).pack()
            ctk.CTkLabel(card, text=sub or "",
                         font=ctk.CTkFont(size=10),
                         text_color=T["tx2"]).pack(pady=(2, 14))

        kpi(0, str(len(seances)),           "Séances aujourd'hui", T["blue"],  "séances enregistrées")
        kpi(1, f"{int(cal_jour)} kcal",     "Calories brûlées",    ACCENT,     "aujourd'hui")
        kpi(2, f"{cette_sem['minutes']} mn", "Minutes / semaine",   T["vio"],   f"{cette_sem['seances']} séances")
        kpi(3, prog_txt,                    "Progression",          prog_col,   "vs semaine précédente")

    # ── Bannière impact nutritionnel ─────────────────────────────

    def _draw_impact_banner(self):
        date_str  = self._date.isoformat()
        cal_sport = db.get_calories_sport_jour(date_str)

        if cal_sport < 50:
            return

        prog      = db.get_programme_actif()
        cal_cible = int(prog.get('calories_jour', 2000)) if prog else 2000

        if cal_sport < 100:
            msg   = f"🏃 {int(cal_sport)} kcal brûlées — belle activité ! Pensez à bien vous hydrater."
            color = T["blue"]
            bg    = _tint(T["blue"])
        elif cal_sport < 250:
            extra = int(cal_sport * 0.5)
            msg   = (f"💧 {int(cal_sport)} kcal brûlées — ajoutez une collation de ~{extra} kcal "
                     f"et +500 ml d'eau pour bien récupérer.")
            color = T["vio"]
            bg    = _tint(T["vio"])
        else:
            budget = cal_cible + int(cal_sport * 0.7)
            msg    = (f"🔥 {int(cal_sport)} kcal brûlées — effort important ! "
                      f"Budget calorique ajusté : {budget} kcal. "
                      f"Privilégiez protéines + glucides complexes pour la récupération.")
            color = ACCENT
            bg    = _tint(ACCENT)

        banner = ctk.CTkFrame(self.body, fg_color=bg, corner_radius=12)
        banner.grid(row=1, column=0, pady=(0, 16), sticky="ew")
        ctk.CTkLabel(banner, text=msg,
                     font=ctk.CTkFont(size=12),
                     text_color=color,
                     wraplength=900,
                     justify="left").pack(padx=20, pady=12, anchor="w")

    # ── Liste des séances du jour ────────────────────────────────

    def _draw_sessions(self):
        date_str = self._date.isoformat()
        seances  = db.get_activites_sport_jour(date_str)

        section = ctk.CTkFrame(self.body, fg_color=T["bg_card"], corner_radius=14)
        section.grid(row=2, column=0, pady=(0, 16), sticky="ew")
        section.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(section, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="ew")
        ctk.CTkLabel(hdr, text="Séances du jour",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T["tx1"]).pack(side="left")

        if not seances:
            ctk.CTkLabel(section,
                         text="Aucune séance enregistrée.\nCliquez sur « + Ajouter une séance » pour commencer.",
                         font=ctk.CTkFont(size=12), text_color=T["tx2"],
                         justify="center").grid(row=1, column=0, pady=24)
            return

        for i, s in enumerate(seances):
            info  = db.ACTIVITES_SPORT.get(s['type_activite'], {})
            icon  = info.get('icon', '🏋️')
            label = info.get('label', s['type_activite'])
            param = info.get('param', 'none')

            if param == 'vitesse' and s['vitesse_kmh']:
                param_txt = f"@ {s['vitesse_kmh']} km/h"
            elif param == 'intensite':
                param_txt = f"— {db.INTENSITES_LABELS.get(s['intensite'], s['intensite'])}"
            else:
                param_txt = ""

            heure_txt = f"  {s['heure']}" if s.get('heure') else ""

            row_w = ctk.CTkFrame(section,
                                  fg_color=T["bg_row"] if i % 2 else "transparent",
                                  corner_radius=8)
            row_w.grid(row=i + 1, column=0, padx=12, pady=2, sticky="ew")
            row_w.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row_w, text=icon, font=ctk.CTkFont(size=20),
                         width=40).grid(row=0, column=0, padx=(8, 4), pady=10)

            ctk.CTkLabel(row_w,
                         text=f"{label} {param_txt}{heure_txt}",
                         font=ctk.CTkFont(size=13),
                         text_color=T["tx1"], anchor="w").grid(row=0, column=1, sticky="w")

            ctk.CTkLabel(row_w,
                         text=f"{int(s['duree_min'])} min  •  {int(s['calories_brulees'])} kcal",
                         font=ctk.CTkFont(size=12),
                         text_color=ACCENT).grid(row=0, column=2, padx=16)

            if s.get('notes'):
                ctk.CTkLabel(row_w, text=s['notes'],
                             font=ctk.CTkFont(size=10),
                             text_color=T["tx2"]).grid(row=1, column=1, columnspan=2,
                                                        padx=4, pady=(0, 6), sticky="w")

            ctk.CTkButton(row_w, text="✕", width=28, height=28,
                          fg_color="transparent", text_color=T["tx3"],
                          hover_color=T["err_bg"],
                          command=lambda aid=s['id']: self._delete_session(aid)).grid(
                row=0, column=3, padx=(0, 8))

            if s.get('fc_observee') and int(s['fc_observee']) > 0:
                fc_max = db.get_fc_max()
                zone   = db.get_zone_for_fc(int(s['fc_observee']), fc_max)
                if zone:
                    col = T.get(zone['color_key'], T["tx2"])
                    ctk.CTkLabel(row_w,
                                 text=f"Z{zone['num']} · {int(s['fc_observee'])} bpm",
                                 font=ctk.CTkFont(size=10, weight="bold"),
                                 text_color=col).grid(row=0, column=4, padx=(0, 4))

    # ── Graphique 7 jours ────────────────────────────────────────

    def _draw_chart(self):
        prog_data = db.get_progression_sport(7)

        chart_card = ctk.CTkFrame(self.body, fg_color=T["bg_card"], corner_radius=14)
        chart_card.grid(row=3, column=0, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(chart_card, text="Progression sur 7 jours",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T["tx1"]).pack(padx=16, pady=(14, 2), anchor="w")
        ctk.CTkLabel(chart_card, text="Calories brûlées par jour",
                     font=ctk.CTkFont(size=10), text_color=T["tx2"]).pack(padx=16, anchor="w")

        dates    = [r['date'] for r in prog_data]
        calories = [r['calories'] for r in prog_data]

        labels = [f"{d[8:]}/{d[5:7]}" for d in dates]
        max_cal = max(calories) if calories else 1

        fig, ax = plt.subplots(figsize=(8, 2.6), facecolor=T["bg_card"])
        ax.set_facecolor(T["bg_card"])
        fig.tight_layout(pad=1.4)

        x    = list(range(len(dates)))
        bars = ax.bar(x, calories, color=ACCENT, alpha=0.85, width=0.55, zorder=3)

        for bar, cal in zip(bars, calories):
            if cal > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + max(max_cal * 0.03, 2),
                        f"{int(cal)}",
                        ha='center', va='bottom',
                        color=T["tx1"], fontsize=8)

        ax.set_xticks(x)
        ax.set_xticklabels(labels, color=T["tx2"], fontsize=9)
        ax.tick_params(axis='y', colors=T["tx2"], labelsize=8)
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.spines['bottom'].set_color(T["bg_el"])
        ax.yaxis.set_tick_params(length=0)
        ax.set_ylim(0, max(max_cal * 1.3, 50))
        ax.grid(axis='y', color=T["bg_el"], linewidth=0.6, zorder=0)

        canvas = FigureCanvasTkAgg(fig, master=chart_card)
        canvas.draw()
        canvas.get_tk_widget().pack(padx=16, pady=(4, 14), fill="x")
        self._canvas_refs.append(fig)

    def _draw_zones_card(self):
        fc_max = db.get_fc_max()
        zones  = db.get_zones_cardiaques(fc_max)
        user   = db.get_current_user()
        fc_src = "personnalisé" if user and int(user.get('fc_max') or 0) > 0 else "calculé"

        card = ctk.CTkFrame(self.body, fg_color=T["bg_card"], corner_radius=14)
        card.grid(row=4, column=0, pady=(0, 8), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card,
                     text=f"❤️  Vos zones cardiaques — FC max : {fc_max} bpm ({fc_src})",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T["tx1"]).grid(
            row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        for i, z in enumerate(zones):
            color = T.get(z['color_key'], T["tx2"])
            row_w = ctk.CTkFrame(card,
                                  fg_color=T["bg_row"] if i % 2 else "transparent",
                                  corner_radius=6)
            row_w.grid(row=i + 1, column=0, padx=12, pady=1, sticky="ew")
            row_w.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row_w, text=f"Zone {z['num']}",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=color, width=58).grid(row=0, column=0, padx=8, pady=7)
            ctk.CTkLabel(row_w, text=z['label'],
                         font=ctk.CTkFont(size=12), text_color=T["tx1"]).grid(
                row=0, column=1, sticky="w")
            ctk.CTkLabel(row_w,
                         text=f"{z['bpm_min']}–{z['bpm_max']} bpm",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=color).grid(row=0, column=2, padx=8)
            ctk.CTkLabel(row_w, text=f"{z['pct_min']}–{z['pct_max']} %",
                         font=ctk.CTkFont(size=11), text_color=T["tx2"]).grid(
                row=0, column=3, padx=(0, 12))
            if z['num'] >= 4:
                ctk.CTkLabel(row_w, text="⚠️ Demandez l'avis de votre médecin",
                             font=ctk.CTkFont(size=9), text_color=T["err"]).grid(
                    row=1, column=1, columnspan=3, padx=6, pady=(0, 4), sticky="w")

        ctk.CTkFrame(card, height=10, fg_color="transparent").grid(row=6, column=0)

    # ── Actions ──────────────────────────────────────────────────

    def _open_add_dialog(self):
        SportDialog(self, self._date.isoformat(), self.refresh)

    def _delete_session(self, aid: int):
        if messagebox.askyesno("Supprimer", "Supprimer cette séance ?", parent=self):
            db.delete_activite_sport(aid)
            self.refresh()


# ── Dialogue ajout de séance ─────────────────────────────────────────────

class SportDialog(ctk.CTkToplevel):
    def __init__(self, parent, date_str: str, on_save_cb):
        super().__init__(parent)
        self.title("Ajouter une séance")
        self.geometry("500x760")
        self.resizable(False, True)
        self.grab_set()
        self.configure(fg_color=T["bg_card"])
        self._date_str = date_str
        self._on_save  = on_save_cb
        self._type_var = ctk.StringVar(value='tapis_marche')
        self._duree_var = ctk.IntVar(value=30)
        self._vit_var   = ctk.DoubleVar(value=2.2)
        self._int_var   = ctk.StringVar(value='leger')
        self._notes_var = ctk.StringVar(value='')
        self._int_btns  = {}
        self._vit_lbl   = None
        self._fc_var         = ctk.StringVar(value='')
        self._zone_card_lbl  = None
        self._fc_alert_lbl   = None

        user = db.get_current_user()
        self._poids = float(user.get('poids', 75)) if user else 75.0

        self._build()
        self._update_preview()
        self._update_zone_display()

    def _build(self):
        ctk.CTkLabel(self, text="Nouvelle séance sportive",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=T["tx1"]).pack(padx=20, pady=(14, 2), anchor="w")
        ctk.CTkLabel(self, text=f"Date : {self._date_str}",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(padx=20, anchor="w")

        ctk.CTkFrame(self, height=1, fg_color=T["bg_el"]).pack(fill="x", padx=16, pady=(8, 10))

        # ── Type d'activité ──────────────────────────────────────
        ctk.CTkLabel(self, text="Type d'activité",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=T["tx1"]).pack(padx=20, anchor="w")

        type_row = ctk.CTkFrame(self, fg_color="transparent")
        type_row.pack(padx=16, pady=(6, 10), fill="x")

        self._type_btns = {}
        acts = list(db.ACTIVITES_SPORT.items())
        ncols = 3
        for i, (key, info) in enumerate(acts):
            r, c = divmod(i, ncols)
            btn = ctk.CTkButton(
                type_row,
                text=f"{info['icon']} {info['label']}",
                font=ctk.CTkFont(size=11),
                height=36, corner_radius=8,
                fg_color=T["ac_bg"] if key == self._type_var.get() else T["bg_el"],
                text_color=ACCENT   if key == self._type_var.get() else T["tx2"],
                hover_color=T["ac_bg"],
                command=lambda k=key: self._select_type(k))
            btn.grid(row=r, column=c, padx=3, pady=3, sticky="ew")
            type_row.grid_columnconfigure(c, weight=1)
            self._type_btns[key] = btn

        ctk.CTkFrame(self, height=1, fg_color=T["bg_el"]).pack(fill="x", padx=16, pady=(4, 8))

        # ── Zone cible ────────────────────────────────────────────
        zone_card = ctk.CTkFrame(self, fg_color=T["ac_bg"], corner_radius=8)
        zone_card.pack(padx=20, pady=(0, 8), fill="x")
        ctk.CTkLabel(zone_card, text="Zone recommandée",
                     font=ctk.CTkFont(size=10), text_color=T["tx2"]).pack(
            padx=14, pady=(8, 2), anchor="w")
        self._zone_card_lbl = ctk.CTkLabel(zone_card, text="",
                                            font=ctk.CTkFont(size=12, weight="bold"),
                                            text_color=T["ac"])
        self._zone_card_lbl.pack(padx=14, pady=(0, 8), anchor="w")

        # ── Durée ────────────────────────────────────────────────
        ctk.CTkLabel(self, text="Durée",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=T["tx1"]).pack(padx=20, anchor="w")

        duree_row = ctk.CTkFrame(self, fg_color="transparent")
        duree_row.pack(padx=16, pady=(4, 2), fill="x")

        ctk.CTkSlider(duree_row, from_=5, to=120, number_of_steps=23,
                       variable=self._duree_var,
                       button_color=ACCENT, button_hover_color=T["ac_d"],
                       progress_color=T["ac_bg"],
                       command=lambda v: self._on_slider_change()).pack(
            side="left", expand=True, fill="x", padx=(0, 10))

        self._duree_lbl = ctk.CTkLabel(duree_row, text="30 min",
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        text_color=ACCENT, width=70)
        self._duree_lbl.pack(side="left")

        ctk.CTkFrame(self, height=1, fg_color=T["bg_el"]).pack(fill="x", padx=16, pady=(8, 8))

        # ── Paramètre vitesse / intensité ─────────────────────────
        self._param_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._param_frame.pack(padx=16, pady=(0, 2), fill="x")
        self._render_param()

        ctk.CTkFrame(self, height=1, fg_color=T["bg_el"]).pack(fill="x", padx=16, pady=(8, 8))

        # ── Aperçu calories ───────────────────────────────────────
        prev_card = ctk.CTkFrame(self, fg_color=T["ac_bg"], corner_radius=10)
        prev_card.pack(padx=20, pady=(0, 8), fill="x")

        self._preview_lbl = ctk.CTkLabel(prev_card, text="",
                                          font=ctk.CTkFont(size=20, weight="bold"),
                                          text_color=ACCENT)
        self._preview_lbl.pack(pady=(10, 2))
        self._preview_sub = ctk.CTkLabel(prev_card, text="",
                                          font=ctk.CTkFont(size=11),
                                          text_color=T["tx2"])
        self._preview_sub.pack(pady=(0, 10))

        ctk.CTkFrame(self, height=1, fg_color=T["bg_el"]).pack(fill="x", padx=16, pady=(8, 8))

        fc_row = ctk.CTkFrame(self, fg_color="transparent")
        fc_row.pack(padx=16, pady=(0, 2), fill="x")
        ctk.CTkLabel(fc_row, text="FC observée (bpm) :",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(side="left")
        ctk.CTkEntry(fc_row, textvariable=self._fc_var,
                     width=90, height=30,
                     fg_color=T["bg_el"], border_color=T["bg_el"],
                     text_color=T["tx1"],
                     placeholder_text="optionnel").pack(side="left", padx=(8, 0))
        ctk.CTkLabel(fc_row, text="bpm",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(side="left", padx=(4, 0))

        self._fc_alert_lbl = ctk.CTkLabel(self, text="",
                                           font=ctk.CTkFont(size=11),
                                           text_color=T["lip"],
                                           wraplength=440)
        self._fc_alert_lbl.pack(padx=20, anchor="w")
        self._trace_id = self._fc_var.trace_add("write", self._on_fc_change)
        self.bind("<Destroy>", self._cleanup_trace)

        # ── Notes ────────────────────────────────────────────────
        notes_row = ctk.CTkFrame(self, fg_color="transparent")
        notes_row.pack(padx=16, pady=(0, 6), fill="x")
        ctk.CTkLabel(notes_row, text="Notes :",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(side="left")
        ctk.CTkEntry(notes_row, textvariable=self._notes_var,
                     fg_color=T["bg_el"], border_color=T["bg_el"],
                     text_color=T["tx1"], height=30,
                     placeholder_text="sensations, programme, …").pack(
            side="left", expand=True, fill="x", padx=(8, 0))

        # ── Sauvegarder ───────────────────────────────────────────
        ctk.CTkButton(self, text="✔  Enregistrer la séance",
                      fg_color=ACCENT, hover_color=T["ac_d"],
                      text_color=T["bg_app"],
                      font=ctk.CTkFont(size=13, weight="bold"),
                      height=40, corner_radius=8,
                      command=self._save).pack(padx=20, pady=(8, 16), fill="x")

    # ── Paramètre dynamique ──────────────────────────────────────

    def _render_param(self):
        for w in self._param_frame.winfo_children():
            w.destroy()
        self._vit_lbl = None
        self._int_btns = {}

        act_type = self._type_var.get()
        param    = db.ACTIVITES_SPORT.get(act_type, {}).get('param', 'none')

        if param == 'vitesse':
            ctk.CTkLabel(self._param_frame, text="Vitesse",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=T["tx1"]).pack(anchor="w")
            row = ctk.CTkFrame(self._param_frame, fg_color="transparent")
            row.pack(fill="x", pady=(6, 0))

            ctk.CTkSlider(row, from_=1.5, to=8.0, number_of_steps=26,
                           variable=self._vit_var,
                           button_color=T["blue"], button_hover_color=T["blue_dm"],
                           progress_color=T["blue_l"],
                           command=lambda v: self._on_slider_change()).pack(
                side="left", expand=True, fill="x", padx=(0, 10))

            self._vit_lbl = ctk.CTkLabel(row,
                                          text=f"{self._vit_var.get():.1f} km/h",
                                          font=ctk.CTkFont(size=13, weight="bold"),
                                          text_color=T["blue"], width=80)
            self._vit_lbl.pack(side="left")

        elif param == 'intensite':
            ctk.CTkLabel(self._param_frame, text="Intensité",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=T["tx1"]).pack(anchor="w")
            btn_row = ctk.CTkFrame(self._param_frame, fg_color="transparent")
            btn_row.pack(pady=(6, 0))

            for key, label in db.INTENSITES_LABELS.items():
                active = key == self._int_var.get()
                b = ctk.CTkButton(btn_row, text=label,
                                   width=110, height=34, corner_radius=8,
                                   font=ctk.CTkFont(size=12),
                                   fg_color=T["vio"]    if active else T["bg_el"],
                                   text_color=T["bg_app"] if active else T["tx2"],
                                   hover_color=T["vio_d"],
                                   command=lambda k=key: self._select_intensite(k))
                b.pack(side="left", padx=4)
                self._int_btns[key] = b

        else:
            ctk.CTkLabel(self._param_frame,
                         text="Activité à intensité constante — aucun paramètre requis.",
                         font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(anchor="w")

    # ── Sélection / mise à jour ──────────────────────────────────

    def _select_type(self, key: str):
        self._type_var.set(key)
        for k, b in self._type_btns.items():
            active = k == key
            b.configure(fg_color=T["ac_bg"] if active else T["bg_el"],
                        text_color=ACCENT   if active else T["tx2"])
        self._render_param()
        self._update_preview()
        self._update_zone_display()

    def _select_intensite(self, key: str):
        self._int_var.set(key)
        for k, b in self._int_btns.items():
            active = k == key
            b.configure(fg_color=T["vio"]    if active else T["bg_el"],
                        text_color=T["bg_app"] if active else T["tx2"])
        self._update_preview()

    def _on_slider_change(self):
        self._duree_lbl.configure(text=f"{int(self._duree_var.get())} min")
        if self._vit_lbl:
            self._vit_lbl.configure(text=f"{self._vit_var.get():.1f} km/h")
        self._update_preview()

    def _update_preview(self):
        cal = db.calc_calories_sport(
            type_activite=self._type_var.get(),
            duree_min=int(self._duree_var.get()),
            vitesse_kmh=self._vit_var.get(),
            intensite=self._int_var.get(),
            poids_kg=self._poids,
        )
        self._preview_lbl.configure(text=f"~{int(cal)} kcal brûlées")
        self._preview_sub.configure(
            text=f"{int(self._duree_var.get())} min · {self._poids:.1f} kg")

    def _cleanup_trace(self, _event=None):
        try:
            self._fc_var.trace_remove("write", self._trace_id)
        except Exception:
            pass

    def _update_zone_display(self):
        if self._zone_card_lbl is None:
            return
        fc_max = db.get_fc_max()
        zones  = db.get_zones_cardiaques(fc_max)
        z2     = next((z for z in zones if z['num'] == 2), zones[1])
        color  = T.get(z2['color_key'], T["ac"])
        self._zone_card_lbl.configure(
            text=f"🟡 Zone {z2['num']} — {z2['label']} : {z2['bpm_min']}–{z2['bpm_max']} bpm",
            text_color=color)

    def _on_fc_change(self, *_):
        if self._fc_alert_lbl is None:
            return
        try:
            fc = int(self._fc_var.get())
        except (ValueError, TypeError):
            self._fc_alert_lbl.configure(text="")
            return
        fc_max = db.get_fc_max()
        if db.is_fc_alert(fc, fc_max):
            self._fc_alert_lbl.configure(
                text="⚠️ FC élevée — consultez votre cardiologue avant d'augmenter l'intensité",
                text_color=T["lip"])
        else:
            zone = db.get_zone_for_fc(fc, fc_max)
            if zone:
                self._fc_alert_lbl.configure(
                    text=f"→ Zone {zone['num']} — {zone['label']}",
                    text_color=T.get(zone['color_key'], T["tx2"]))
            else:
                self._fc_alert_lbl.configure(text="")

    def _save(self):
        type_act = self._type_var.get()
        duree    = int(self._duree_var.get())
        vit      = round(self._vit_var.get(), 1)
        int_val  = self._int_var.get()
        cal      = db.calc_calories_sport(type_act, duree, vit, int_val, self._poids)
        heure    = datetime.now().strftime("%H:%M") if self._date_str == date.today().isoformat() else ""

        try:
            fc_obs = int(self._fc_var.get())
        except (ValueError, TypeError):
            fc_obs = 0

        db.add_activite_sport({
            'date':            self._date_str,
            'heure':           heure,
            'type_activite':   type_act,
            'duree_min':       duree,
            'vitesse_kmh':     vit,
            'intensite':       int_val,
            'calories_brulees': cal,
            'notes':           self._notes_var.get(),
            'fc_observee':     fc_obs,
        })
        self._on_save()
        self.destroy()
