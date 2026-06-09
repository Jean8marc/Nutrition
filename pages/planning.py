"""
NutriTrack Pro — Planning repas
Calendrier hebdomadaire avec récapitulatif nutritionnel et génération de menus.
"""
import os, sys, webbrowser
from datetime import datetime, date, timedelta
import customtkinter as ctk
from tkinter import messagebox, filedialog
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import database as db
from colors import tint_low
from theme import T
from pages.stock import show_stock_alert_toast

JOURS_FR = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
MOIS_FR  = ["","janvier","février","mars","avril","mai","juin",
             "juillet","août","septembre","octobre","novembre","décembre"]

REPAS_ICONS = {
    "petit_dejeuner":  "🌅",
    "collation_matin": "☕",
    "dejeuner":        "☀️",
    "collation_soir":  "🍎",
    "diner":           "🌙",
}


def _lundi_de(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _format_semaine(lundi: date) -> str:
    dim = lundi + timedelta(days=6)
    return f"Semaine du {lundi.day} au {dim.day} {MOIS_FR[dim.month]} {dim.year}"


class PlanningPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=T["bg_app"], corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._semaine = _lundi_de(date.today())
        self._selected_day = date.today().strftime("%Y-%m-%d")
        self._build()

    # ── Construction ─────────────────────────────────────────────

    def _build(self):
        # ── Barre de navigation ───────────────────────────────────
        nav = ctk.CTkFrame(self, fg_color=T["bg_card"], corner_radius=0, height=60)
        nav.grid(row=0, column=0, sticky="ew")
        nav.grid_columnconfigure(1, weight=1)
        nav.grid_propagate(False)

        ctk.CTkLabel(nav, text="📅  Planning repas",
                     font=ctk.CTkFont(family="Helvetica", size=20, weight="bold"),
                     text_color=T["tx1"]).grid(row=0, column=0, padx=20, pady=0, sticky="w")

        # Nav semaine
        nav_mid = ctk.CTkFrame(nav, fg_color="transparent")
        nav_mid.grid(row=0, column=1)

        ctk.CTkButton(nav_mid, text="◀", width=32, height=32,
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      command=self._prev_week).pack(side="left", padx=4)

        self.semaine_lbl = ctk.CTkLabel(nav_mid, text="",
                                         font=ctk.CTkFont(size=13, weight="bold"),
                                         text_color=T["tx1"], width=280)
        self.semaine_lbl.pack(side="left", padx=8)

        ctk.CTkButton(nav_mid, text="▶", width=32, height=32,
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      command=self._next_week).pack(side="left", padx=4)

        ctk.CTkButton(nav_mid, text="Aujourd'hui", width=100, height=32,
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      font=ctk.CTkFont(size=12),
                      command=self._goto_today).pack(side="left", padx=8)

        # Boutons droite
        right_btns = ctk.CTkFrame(nav, fg_color="transparent")
        right_btns.grid(row=0, column=2, padx=16)

        ctk.CTkButton(right_btns, text="🛒  Liste de courses",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color="#0d9488", hover_color="#0f766e",
                      text_color="#fff", height=34, width=160, corner_radius=8,
                      command=self._open_liste_courses).pack(side="left", padx=(0,8))

        ctk.CTkButton(right_btns, text="🎲  Générer la semaine",
                      font=ctk.CTkFont(size=12, weight="bold"),
                      fg_color=T["vio"], hover_color=T["vio_d"],
                      text_color="#fff", height=34, width=180, corner_radius=8,
                      command=self._generer_semaine).pack(side="left", padx=(0,8))

        ctk.CTkButton(right_btns, text="📄  Exporter HTML",
                      font=ctk.CTkFont(size=12),
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=34, width=140, corner_radius=8,
                      command=self._export_html).pack(side="left", padx=(0, 8))

        ctk.CTkButton(right_btns, text="📄  Rapport semaine",
                      font=ctk.CTkFont(size=12),
                      fg_color=T["bg_el"], hover_color=T["ac_bg"],
                      text_color=T["tx2"], height=34, width=150, corner_radius=8,
                      command=self._open_rapport).pack(side="left", padx=(0, 8))

        ctk.CTkButton(right_btns, text="🗑  Vider semaine",
                      font=ctk.CTkFont(size=12),
                      fg_color=T["bg_el"], hover_color=T["err_bg"],
                      text_color=T["err"], height=34, width=130, corner_radius=8,
                      command=self._vider_semaine).pack(side="left")

        # ── Corps principal : vue semaine + détail jour ───────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0)
        body.grid_rowconfigure(0, weight=1)

        # Vue semaine (7 colonnes)
        self.week_frame = ctk.CTkScrollableFrame(
            body, fg_color="transparent",
            scrollbar_button_color=T["bg_el"],
            orientation="horizontal")
        self.week_frame.grid(row=0, column=0, sticky="nsew", padx=(12,0), pady=12)

        # Panneau détail du jour sélectionné
        self.detail_frame = ctk.CTkFrame(body, fg_color=T["bg_card"],
                                          corner_radius=14, width=320)
        self.detail_frame.grid(row=0, column=1, sticky="nsew",
                                padx=(8,12), pady=12)
        self.detail_frame.grid_propagate(False)
        self.detail_frame.grid_columnconfigure(0, weight=1)
        self.detail_frame.grid_rowconfigure(2, weight=1)

        self.refresh()

    # ── Refresh ──────────────────────────────────────────────────

    def refresh(self):
        self.semaine_lbl.configure(text=_format_semaine(self._semaine))
        self._build_week_grid()
        self._build_day_detail(self._selected_day)

    # ── Vue semaine ──────────────────────────────────────────────

    def _build_week_grid(self):
        for w in self.week_frame.winfo_children():
            w.destroy()

        today_str = date.today().strftime("%Y-%m-%d")
        prog      = db.get_programme_actif()
        profil    = db.get_profil()
        cal_cible = (prog['calories_jour'] if prog
                     else db.calc_calories_cible(profil))

        for i in range(7):
            jour_d   = self._semaine + timedelta(days=i)
            jour_str = jour_d.strftime("%Y-%m-%d")
            is_today = jour_str == today_str
            is_sel   = jour_str == self._selected_day

            # Couleur de la colonne
            col_bg = T["bg_row"] if is_sel else T["bg_row"] if is_today else T["bg_card"]
            border = T["ac"] if is_sel else T["blue"] if is_today else T["bg_el"]

            col = ctk.CTkFrame(self.week_frame, fg_color=col_bg,
                               corner_radius=12, width=155,
                               border_width=2, border_color=border)
            col.pack(side="left", padx=4, fill="y")
            col.grid_columnconfigure(0, weight=1)

            # En-tête jour
            hdr_bg = T["ac"] if is_sel else T["bg_el"]
            hdr = ctk.CTkFrame(col, fg_color=hdr_bg, corner_radius=8, height=52)
            hdr.grid(row=0, column=0, padx=4, pady=(4,2), sticky="ew")
            hdr.grid_propagate(False)
            hdr.grid_columnconfigure(0, weight=1)
            hdr.bind("<Button-1>", lambda e, j=jour_str: self._select_day(j))

            hdr_text_color = "#000" if is_sel else T["tx1"]
            ctk.CTkLabel(hdr, text=JOURS_FR[i],
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=hdr_text_color).grid(row=0, column=0, pady=(6,0))
            ctk.CTkLabel(hdr, text=f"{jour_d.day}/{jour_d.month}",
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=hdr_text_color).grid(row=1, column=0, pady=(0,6))

            # Repas du jour
            repas_jour = db.get_planning_jour(jour_str)
            repas_by_type = {r['type_repas']: r for r in repas_jour}

            for row_i, (type_rep, label, _) in enumerate(db.TYPES_REPAS):
                repas = repas_by_type.get(type_rep)
                slot = ctk.CTkFrame(col, fg_color=T["bg_el"] if repas else "transparent",
                                    corner_radius=6, height=54, cursor="hand2")
                slot.grid(row=row_i+1, column=0, padx=4, pady=2, sticky="ew")
                slot.grid_propagate(False)
                slot.grid_columnconfigure(0, weight=1)

                icon = REPAS_ICONS.get(type_rep, "🍽️")

                if repas:
                    nom = (repas.get('recette_nom') or repas.get('nom_custom') or '')[:16]
                    cal = int(repas.get('calories_custom') or 0)
                    ctk.CTkLabel(slot, text=f"{icon} {nom}",
                                 font=ctk.CTkFont(size=9, weight="bold"),
                                 text_color=T["tx1"],
                                 wraplength=130, anchor="w").grid(
                        row=0, column=0, padx=6, pady=(4,0), sticky="w")
                    ctk.CTkLabel(slot, text=f"{cal} kcal",
                                 font=ctk.CTkFont(size=9),
                                 text_color=T["ac"]).grid(
                        row=1, column=0, padx=6, pady=(0,4), sticky="w")
                else:
                    ctk.CTkLabel(slot, text=f"{icon}  +",
                                 font=ctk.CTkFont(size=11), text_color=T["tx3"]).grid(
                        row=0, column=0, rowspan=2, padx=6, pady=8, sticky="w")

                slot.bind("<Button-1>",
                          lambda e, j=jour_str, t=type_rep: self._on_slot_click(j, t))
                for child in slot.winfo_children():
                    child.bind("<Button-1>",
                               lambda e, j=jour_str, t=type_rep: self._on_slot_click(j, t))

            # Résumé nutritionnel journalier
            nutri = db.calc_planning_jour_nutrition(jour_str)
            cal_jour = int(nutri['calories'])
            pct      = min(1.0, cal_jour / max(1, cal_cible))

            # Barre de progression calories
            bar_frame = ctk.CTkFrame(col, fg_color="transparent")
            bar_frame.grid(row=len(db.TYPES_REPAS)+1, column=0, padx=4, pady=(4,6), sticky="ew")

            bar_color = (T["ac"] if 0.85 <= pct <= 1.15
                         else T["lip"] if 0.6 <= pct <= 1.35
                         else T["err"] if cal_jour > 0
                         else T["bg_el"])

            ctk.CTkProgressBar(bar_frame, progress_color=bar_color,
                               fg_color=T["bg_el"], height=6).pack(fill="x", padx=4, pady=(0,2))
            bar_frame.winfo_children()[0].set(pct)

            emoji = "✅" if 0.85 <= pct <= 1.15 else "⚠️" if cal_jour > 0 else ""
            ctk.CTkLabel(bar_frame, text=f"{emoji} {cal_jour}/{cal_cible} kcal",
                         font=ctk.CTkFont(size=9), text_color=T["tx2"]).pack()

    # ── Détail du jour ───────────────────────────────────────────

    def _build_day_detail(self, jour_str: str):
        for w in self.detail_frame.winfo_children():
            w.destroy()

        jour_d   = datetime.strptime(jour_str, "%Y-%m-%d").date()
        today    = date.today()
        is_today = jour_d == today

        # En-tête
        hdr = ctk.CTkFrame(self.detail_frame, fg_color=T["bg_el"], corner_radius=10)
        hdr.grid(row=0, column=0, padx=12, pady=(12,8), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr,
                     text=f"{'Aujourd\'hui — ' if is_today else ''}"
                          f"{JOURS_FR[jour_d.weekday()]} {jour_d.day} {MOIS_FR[jour_d.month]}",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["tx1"]).grid(row=0, column=0, padx=12, pady=(8,2), sticky="w")

        # Bilan nutritionnel du jour
        nutri    = db.calc_planning_jour_nutrition(jour_str)
        prog     = db.get_programme_actif()
        profil   = db.get_profil()
        macros_c = db.calc_macros_cibles(profil)
        if prog:
            cal_c  = prog['calories_jour']
            prot_c = round(cal_c * prog.get('proteines_pct', 30) / 100 / 4)
            gluc_c = round(cal_c * prog.get('glucides_pct', 40)  / 100 / 4)
            lip_c  = round(cal_c * prog.get('lipides_pct',  30)  / 100 / 9)
        else:
            cal_c  = macros_c['calories']
            prot_c = macros_c['proteines']
            gluc_c = macros_c['glucides']
            lip_c  = macros_c['lipides']

        if prog:
            ctk.CTkLabel(hdr, text=f"Programme : {prog['nom']}",
                         font=ctk.CTkFont(size=10), text_color=T["ac"]).grid(
                row=1, column=0, padx=12, pady=(0,8), sticky="w")

        # Barres de macros
        bilan = ctk.CTkFrame(self.detail_frame, fg_color=T["bg_el"], corner_radius=10)
        bilan.grid(row=1, column=0, padx=12, pady=(0,8), sticky="ew")
        bilan.grid_columnconfigure(0, weight=1)

        macros_display = [
            ("⚡ Calories",   nutri['calories'],  cal_c,  T["cal"], "kcal"),
            ("🥩 Protéines",  nutri['proteines'], prot_c, T["ac"], "g"),
            ("🍞 Glucides",   nutri['glucides'],  gluc_c, T["blue"], "g"),
            ("🫒 Lipides",    nutri['lipides'],   lip_c,  T["lip"], "g"),
        ]
        for mi, (label, val, cible, color, unit) in enumerate(macros_display):
            pct = min(1.0, val / max(1, cible))
            ok  = 0.85 <= pct <= 1.15
            bar_color = color if ok else T["lip"] if pct < 0.85 else T["err"]

            mf = ctk.CTkFrame(bilan, fg_color="transparent")
            mf.grid(row=mi, column=0, padx=10, pady=(6 if mi==0 else 2, 0), sticky="ew")
            mf.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(mf, text=label, font=ctk.CTkFont(size=11),
                         text_color=T["tx2"], width=90, anchor="w").grid(
                row=0, column=0, sticky="w")
            ctk.CTkLabel(mf, text=f"{val} / {cible} {unit}",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=bar_color, anchor="e").grid(row=0, column=1, sticky="e")
            pb = ctk.CTkProgressBar(bilan, progress_color=bar_color,
                                    fg_color=T["bg_card"], height=5)
            pb.grid(row=mi*2+1, column=0, padx=10, pady=(2, 4 if mi==3 else 0), sticky="ew")
            pb.set(pct)

        # Verdict
        verdict_cal = nutri['calories']
        if verdict_cal == 0:
            verdict_txt = "Aucun repas planifié"
            verdict_col = T["tx2"]
        elif 0.85 * cal_c <= verdict_cal <= 1.15 * cal_c:
            verdict_txt = "✅ Dans les objectifs du programme"
            verdict_col = T["ac"]
        elif verdict_cal < 0.7 * cal_c:
            verdict_txt = "⚠️ Apports trop faibles"
            verdict_col = T["lip"]
        elif verdict_cal < cal_c:
            verdict_txt = "📉 Légèrement en dessous"
            verdict_col = T["lip"]
        else:
            verdict_txt = "📈 Dépassement calorique"
            verdict_col = T["err"]

        ctk.CTkLabel(bilan, text=verdict_txt,
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=verdict_col).grid(
            row=8, column=0, padx=10, pady=(4,8))

        # Bouton générer ce jour
        ctk.CTkButton(self.detail_frame, text="🎲  Générer ce jour",
                      fg_color=T["vio"], hover_color=T["vio_d"],
                      text_color="#fff", height=32, corner_radius=8,
                      font=ctk.CTkFont(size=12, weight="bold"),
                      command=lambda j=jour_str: self._generer_jour(j)).grid(
            row=2, column=0, padx=12, pady=(0,6), sticky="ew")

        # Liste repas du jour
        repas_scroll = ctk.CTkScrollableFrame(
            self.detail_frame, fg_color="transparent",
            scrollbar_button_color=T["bg_el"])
        repas_scroll.grid(row=3, column=0, padx=8, pady=(0,8), sticky="nsew")
        repas_scroll.grid_columnconfigure(0, weight=1)
        self.detail_frame.grid_rowconfigure(3, weight=1)

        repas_jour   = db.get_planning_jour(jour_str)
        repas_by_type = {r['type_repas']: r for r in repas_jour}

        for ri, (type_rep, label, part_pct) in enumerate(db.TYPES_REPAS):
            repas = repas_by_type.get(type_rep)
            icon  = REPAS_ICONS.get(type_rep, "🍽️")

            slot = ctk.CTkFrame(repas_scroll, fg_color=T["bg_el"], corner_radius=8)
            slot.grid(row=ri, column=0, pady=3, sticky="ew")
            slot.grid_columnconfigure(1, weight=1)

            # Label type repas
            ctk.CTkLabel(slot, text=f"{icon} {label.split(' ',1)[-1]}",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=T["tx1"], width=110, anchor="w").grid(
                row=0, column=0, padx=8, pady=(6,2), sticky="w")

            cible_slot = round(cal_c * part_pct)
            ctk.CTkLabel(slot, text=f"~{cible_slot} kcal recommandés",
                         font=ctk.CTkFont(size=9), text_color=T["tx3"]).grid(
                row=1, column=0, padx=8, pady=(0,6), sticky="w")

            if repas:
                nom = repas.get('recette_nom') or repas.get('nom_custom') or '—'
                cal = int(repas.get('calories_custom') or 0)
                prot = round(repas.get('proteines_custom') or 0, 1)
                portions = repas.get('portions', 1)

                info = ctk.CTkFrame(slot, fg_color="transparent")
                info.grid(row=0, column=1, rowspan=2, padx=4, pady=4, sticky="ew")
                info.grid_columnconfigure(0, weight=1)

                ctk.CTkLabel(info, text=nom,
                             font=ctk.CTkFont(size=11), text_color=T["tx1"],
                             anchor="w", wraplength=130).grid(row=0, column=0, sticky="w")
                ctk.CTkLabel(info,
                             text=f"{cal} kcal  •  {prot}g prot.  •  ×{portions} port.",
                             font=ctk.CTkFont(size=9), text_color=T["tx2"]).grid(
                    row=1, column=0, sticky="w")

                ctk.CTkButton(info, text="✕", width=24, height=24,
                              fg_color="transparent", hover_color=T["err_bg"],
                              text_color=T["err"],
                              command=lambda pid=repas['id']: self._suppr_repas(pid, jour_str)).grid(
                    row=0, column=1, rowspan=2, padx=4)
                if repas.get('recette_id'):
                    ctk.CTkButton(info, text="🍳", width=24, height=24,
                                  fg_color="transparent", hover_color=T["ac_bg"],
                                  text_color=T["ac"],
                                  command=lambda r=repas: self._open_deduction(r)).grid(
                        row=0, column=2, rowspan=2, padx=2)
            else:
                ctk.CTkButton(slot, text="＋ Ajouter",
                              fg_color=T["bg_hl"], hover_color=T["bg_hl"],
                              text_color=T["tx2"], height=28, width=90,
                              font=ctk.CTkFont(size=11), corner_radius=6,
                              command=lambda j=jour_str, t=type_rep: self._open_add_repas(j, t)).grid(
                    row=0, column=1, rowspan=2, padx=8, pady=6)

    # ── Actions ──────────────────────────────────────────────────

    def _select_day(self, jour_str: str):
        self._selected_day = jour_str
        self.refresh()

    def _on_slot_click(self, jour_str: str, type_repas: str):
        self._selected_day = jour_str
        repas = {r['type_repas']: r
                 for r in db.get_planning_jour(jour_str)}
        if type_repas in repas:
            # Déjà rempli → ne rien faire (le bouton ✕ sert à supprimer)
            self._build_day_detail(jour_str)
            self._build_week_grid()
        else:
            self._open_add_repas(jour_str, type_repas)

    def _open_add_repas(self, jour_str: str, type_repas: str):
        AddRepasDialog(self, jour_str, type_repas,
                       callback=lambda: self.refresh())

    def _suppr_repas(self, pid: int, jour_str: str):
        db.delete_planning_repas(pid)
        self._selected_day = jour_str
        self.refresh()

    def _open_deduction(self, repas: dict):
        uid = db.get_current_user_id()
        if not uid:
            return
        DeductionStockDialog(self, repas=repas, on_done=self.refresh)

    def _generer_jour(self, jour_str: str):
        suggestions = db.generer_menu_jour(jour_str)
        if not suggestions:
            messagebox.showinfo("Génération", "Aucune recette disponible.\nAjoutez des recettes d'abord.", parent=self)
            return
        SuggestionsDialog(self, jour_str, suggestions,
                          callback=lambda: self.refresh())

    def _generer_semaine(self):
        if not messagebox.askyesno("Générer la semaine",
                                   "Générer un menu automatique pour toute la semaine ?\n"
                                   "Les repas déjà planifiés seront remplacés.", parent=self):
            return
        for i in range(7):
            jour = (self._semaine + timedelta(days=i)).strftime("%Y-%m-%d")
            suggestions = db.generer_menu_jour(jour)
            if suggestions:
                db.appliquer_menu_jour(jour, suggestions)
        self.refresh()

    def _open_liste_courses(self):
        d_debut = self._semaine.strftime("%Y-%m-%d")
        d_fin   = (self._semaine + timedelta(days=6)).strftime("%Y-%m-%d")
        ListeCoursesDialog(self, d_debut, d_fin)

    def _export_html(self):
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Exporter le planning",
            defaultextension=".html",
            initialfile=f"planning_{self._semaine.isoformat()}.html",
            filetypes=[("Page HTML", "*.html"), ("Tous les fichiers", "*.*")])
        if not path:
            return
        html = _build_planning_html(self._semaine)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html)
            webbrowser.open(f"file://{os.path.abspath(path)}")
        except OSError as e:
            messagebox.showerror("Erreur export", str(e), parent=self)

    def _vider_semaine(self):
        if not messagebox.askyesno("Vider la semaine",
                                   "Supprimer tous les repas planifiés de cette semaine ?", parent=self):
            return
        uid = db.get_current_user_id()
        if not uid:
            return
        conn = db.get_connection()
        for i in range(7):
            jour = (self._semaine + timedelta(days=i)).strftime("%Y-%m-%d")
            conn.execute("DELETE FROM planning_repas WHERE user_id=? AND date=?", (uid, jour))
        conn.commit()
        conn.close()
        self.refresh()

    def _open_rapport(self):
        from pages.rapport_dialog import RapportDialog
        RapportDialog(self)

    def _prev_week(self):
        self._semaine -= timedelta(weeks=1)
        self.refresh()

    def _next_week(self):
        self._semaine += timedelta(weeks=1)
        self.refresh()

    def _goto_today(self):
        self._semaine      = _lundi_de(date.today())
        self._selected_day = date.today().strftime("%Y-%m-%d")
        self.refresh()


# ─────────────────── Dialogue ajout de repas ─────────────────────────────────

class AddRepasDialog(ctk.CTkToplevel):
    def __init__(self, parent, jour_str, type_repas, callback):
        super().__init__(parent)
        self.jour_str  = jour_str
        self.type_repas = type_repas
        self.callback  = callback
        label = db.TYPES_REPAS_LABELS.get(type_repas, type_repas)
        jour_d = datetime.strptime(jour_str, "%Y-%m-%d").date()
        self.title(f"{label} — {JOURS_FR[jour_d.weekday()]} {jour_d.day}")
        self.geometry("540x560")
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()
        self._build()

    def _build(self):
        icon = REPAS_ICONS.get(self.type_repas, "🍽️")
        label = db.TYPES_REPAS_LABELS.get(self.type_repas, "")
        ctk.CTkLabel(self, text=f"{icon}  Ajouter — {label}",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=T["tx1"]).pack(padx=20, pady=(18,4), anchor="w")

        # Cible calorique pour ce repas
        prog    = db.get_programme_actif()
        profil  = db.get_profil()
        cal_c   = prog['calories_jour'] if prog else db.calc_calories_cible(profil)
        part    = db.TYPES_REPAS_PARTS.get(self.type_repas, 0.25)
        cible   = round(cal_c * part)
        ctk.CTkLabel(self, text=f"Objectif pour ce repas : ≈ {cible} kcal",
                     font=ctk.CTkFont(size=11), text_color=T["ac"]).pack(padx=20, anchor="w")

        # Onglets : Recette / Libre
        tabs = ctk.CTkTabview(self, fg_color=T["bg_card"],
                               segmented_button_fg_color=T["bg_el"],
                               segmented_button_selected_color=T["ac"],
                               segmented_button_selected_hover_color=T["ac_d"],
                               text_color=T["tx1"])
        tabs.pack(fill="both", expand=True, padx=16, pady=8)
        t1 = tabs.add("🍽️  Choisir une recette")
        t2 = tabs.add("✏️  Saisie libre")

        # Onglet recette
        t1.grid_columnconfigure(0, weight=1)
        t1.grid_rowconfigure(1, weight=1)

        # Filtre par catégorie
        self.recette_search_var = ctk.StringVar()
        search = ctk.CTkEntry(t1, textvariable=self.recette_search_var,
                              placeholder_text="🔍 Rechercher une recette...",
                              height=34, fg_color=T["bg_el"], border_color=T["bg_hl"],
                              font=ctk.CTkFont(size=12))
        search.grid(row=0, column=0, padx=4, pady=(4,6), sticky="ew")
        search.bind("<KeyRelease>", lambda e: self._filter_recettes())

        self.recettes_list = ctk.CTkScrollableFrame(t1, fg_color="transparent",
                                                     scrollbar_button_color=T["bg_el"])
        self.recettes_list.grid(row=1, column=0, padx=4, sticky="nsew")
        self.recettes_list.grid_columnconfigure(0, weight=1)

        self.portions_var = ctk.StringVar(value="1")
        pf = ctk.CTkFrame(t1, fg_color="transparent")
        pf.grid(row=2, column=0, padx=4, pady=(6,4), sticky="ew")
        ctk.CTkLabel(pf, text="Nombre de portions :",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).pack(side="left")
        ctk.CTkEntry(pf, textvariable=self.portions_var, width=60, height=30,
                     fg_color=T["bg_el"], border_color=T["bg_hl"],
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=8)

        self._selected_recette = None
        self._recette_btns = []
        self._load_recettes()

        # Onglet saisie libre
        t2.grid_columnconfigure((0,1), weight=1)

        self._libre_vars = {}
        for r, (lbl, key, ph) in enumerate([
            ("Nom du repas", "nom", "ex: Salade maison"),
            ("Calories (kcal)", "calories", "ex: 450"),
            ("Protéines (g)", "proteines", "ex: 30"),
            ("Glucides (g)", "glucides", "ex: 40"),
            ("Lipides (g)", "lipides", "ex: 15"),
        ]):
            col = r % 2
            gr  = (r // 2) * 2
            if r == 0:
                ctk.CTkLabel(t2, text=lbl, font=ctk.CTkFont(size=12),
                             text_color=T["tx2"]).grid(row=gr, column=0, columnspan=2,
                                                        padx=6, pady=(10,2), sticky="w")
                var = ctk.StringVar()
                ctk.CTkEntry(t2, textvariable=var, height=34,
                             placeholder_text=ph,
                             fg_color=T["bg_el"], border_color=T["bg_hl"]).grid(
                    row=gr+1, column=0, columnspan=2, padx=6, sticky="ew")
            else:
                ctk.CTkLabel(t2, text=lbl, font=ctk.CTkFont(size=12),
                             text_color=T["tx2"]).grid(row=gr, column=col,
                                                        padx=6, pady=(10,2), sticky="w")
                var = ctk.StringVar()
                ctk.CTkEntry(t2, textvariable=var, height=34,
                             placeholder_text=ph,
                             fg_color=T["bg_el"], border_color=T["bg_hl"]).grid(
                    row=gr+1, column=col, padx=6, sticky="ew")
            self._libre_vars[key] = var

        self._tabs = tabs

        # Boutons bas
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(padx=16, pady=(4,16), fill="x")
        ctk.CTkButton(bf, text="Annuler", fg_color=T["bg_el"],
                      hover_color=T["bg_hl"], height=38, width=110,
                      command=self.destroy).pack(side="left")
        ctk.CTkButton(bf, text="✔  Ajouter au planning",
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000", height=38, width=200,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._save).pack(side="right")

    def _load_recettes(self):
        for w in self.recettes_list.winfo_children():
            w.destroy()
        self._recette_btns = []

        search = self.recette_search_var.get().strip().lower()
        recettes = db.get_recettes(search)

        # Faisabilité stock
        uid = db.get_current_user_id()
        stock = db.get_stock() if uid else []
        if stock:
            for r in recettes:
                r['_faisable'] = db.check_recette_faisable(r['id'])['faisable']
        else:
            for r in recettes:
                r['_faisable'] = None

        # Trier : faisables > favoris > hints > nom
        hints = db.REPAS_CAT_HINTS.get(self.type_repas, [])
        recettes.sort(key=lambda r: (
            0 if r.get('_faisable') else 1,
            0 if r.get('favori') else 1,
            0 if r.get('categorie') in hints else 1,
            r['nom']))

        for i, rec in enumerate(recettes):
            nutri = db.calc_recette_nutrition(rec['id'])
            pp    = nutri['par_portion']
            cat   = rec.get('categorie', '')
            is_fav  = bool(rec.get('favori'))
            is_hint = cat in hints

            bg = T["bg_row"] if i % 2 == 0 else "transparent"
            row = ctk.CTkFrame(self.recettes_list, fg_color=bg,
                               corner_radius=6, height=46)
            row.grid(row=i, column=0, pady=1, sticky="ew")
            row.grid_columnconfigure(0, weight=1)
            row.grid_propagate(False)

            faisable = rec.get('_faisable')
            if faisable is True:
                prefix = "✅ "
            elif faisable is False:
                prefix = "⚠️ "
            elif is_fav:
                prefix = "⭐ "
            elif is_hint:
                prefix = "💡 "
            else:
                prefix = ""
            ctk.CTkLabel(row, text=f"{prefix}{rec['nom']}",
                         font=ctk.CTkFont(size=11),
                         text_color=T["lip"] if is_fav else T["tx1"],
                         anchor="w").grid(row=0, column=0, padx=8, pady=(4,0), sticky="w")
            ctk.CTkLabel(row,
                         text=f"{pp['calories']} kcal  •  {pp['proteines']}g P  •  {cat}",
                         font=ctk.CTkFont(size=9), text_color=T["tx2"]).grid(
                row=1, column=0, padx=8, pady=(0,4), sticky="w")

            row.bind("<Button-1>", lambda e, r=rec, rw=row: self._select_recette(r, rw))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda e, r=rec, rw=row: self._select_recette(r, rw))
            self._recette_btns.append((rec, row))

    def _filter_recettes(self):
        self._load_recettes()

    def _select_recette(self, rec, row_widget):
        self._selected_recette = rec
        # Highlight
        for _, rw in self._recette_btns:
            rw.configure(fg_color=T["bg_el"] if rw == row_widget else "transparent")
        row_widget.configure(fg_color=T["ac_sel"], border_width=1, border_color=T["ac"])

    def _save(self):
        tab = self._tabs.get()
        if "recette" in tab.lower():
            if not self._selected_recette:
                messagebox.showwarning("Sélection requise",
                                       "Choisissez une recette.", parent=self)
                return
            try:
                portions = float(self.portions_var.get().replace(',','.') or 1)
            except:
                portions = 1.0
            # Alerte allergènes
            allergenes = (self._selected_recette.get('allergenes') or '').strip()
            if allergenes:
                ok = messagebox.askokcancel(
                    "⚠️  Allergènes détectés",
                    f"Cette recette contient :\n\n  {allergenes}\n\nAjouter quand même au planning ?",
                    parent=self)
                if not ok:
                    return
            db.add_planning_repas(self.jour_str, self.type_repas,
                                   recette_id=self._selected_recette['id'],
                                   portions=portions)
        else:
            nom = self._libre_vars['nom'].get().strip()
            if not nom:
                messagebox.showwarning("Champ requis", "Le nom est obligatoire.", parent=self)
                return
            uid = db.get_current_user_id()
            if not uid:
                return
            try:
                cal  = float(self._libre_vars['calories'].get() or 0)
                prot = float(self._libre_vars['proteines'].get() or 0)
                gluc = float(self._libre_vars['glucides'].get() or 0)
                lip  = float(self._libre_vars['lipides'].get() or 0)
            except:
                cal = prot = gluc = lip = 0.0
            conn = db.get_connection()
            conn.execute("""INSERT INTO planning_repas
                (user_id,date,type_repas,nom_custom,
                 calories_custom,proteines_custom,glucides_custom,lipides_custom,portions)
                VALUES (?,?,?,?,?,?,?,?,1)""",
                (uid, self.jour_str, self.type_repas, nom, cal, prot, gluc, lip))
            conn.commit()
            conn.close()

        self.callback()
        self.destroy()


# ─────────────────── Dialogue suggestions de menu ────────────────────────────

class SuggestionsDialog(ctk.CTkToplevel):
    def __init__(self, parent, jour_str, suggestions, callback):
        super().__init__(parent)
        self.jour_str    = jour_str
        self.suggestions = suggestions
        self.callback    = callback
        jour_d = datetime.strptime(jour_str, "%Y-%m-%d").date()
        self.title(f"Menu suggéré — {JOURS_FR[jour_d.weekday()]} {jour_d.day}")
        self.geometry("480x520")
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="🎲  Menu suggéré",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=T["tx1"]).pack(padx=20, pady=(18,4), anchor="w")
        ctk.CTkLabel(self, text="Basé sur votre programme actif et vos objectifs caloriques",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(padx=20, anchor="w")

        total_cal = sum(s['calories'] for s in self.suggestions)
        ctk.CTkLabel(self, text=f"Total estimé : {int(total_cal)} kcal",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["ac"]).pack(padx=20, pady=(8,4), anchor="w")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                         scrollbar_button_color=T["bg_el"])
        scroll.pack(fill="both", expand=True, padx=16, pady=8)
        scroll.grid_columnconfigure(0, weight=1)

        for i, s in enumerate(self.suggestions):
            icon = REPAS_ICONS.get(s['type_repas'], "🍽️")
            label = db.TYPES_REPAS_LABELS.get(s['type_repas'], '')

            card = ctk.CTkFrame(scroll, fg_color=T["bg_el"], corner_radius=10)
            card.grid(row=i, column=0, pady=4, sticky="ew")
            card.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=18), width=40).grid(
                row=0, column=0, rowspan=2, padx=8, pady=10)
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=10),
                         text_color=T["tx2"]).grid(row=0, column=1, padx=4, pady=(8,0), sticky="w")
            ctk.CTkLabel(card, text=s['recette_nom'],
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=T["tx1"]).grid(row=1, column=1, padx=4, pady=(0,4), sticky="w")
            ctk.CTkLabel(card,
                         text=f"×{s['portions']} portion(s)  •  {int(s['calories'])} kcal",
                         font=ctk.CTkFont(size=10), text_color=T["ac"]).grid(
                row=1, column=2, padx=12, pady=(0,4))

        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(padx=16, pady=(4,16), fill="x")
        ctk.CTkButton(bf, text="Annuler", fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=38, width=110, command=self.destroy).pack(side="left")
        ctk.CTkButton(bf, text="✔  Appliquer ce menu",
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000", height=38, width=200,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._apply).pack(side="right")

    def _apply(self):
        db.appliquer_menu_jour(self.jour_str, self.suggestions)
        self.callback()
        self.destroy()


# ─────────────────────── Liste de courses ────────────────────────────────────

class ListeCoursesDialog(ctk.CTkToplevel):
    """Affiche la liste agrégée des ingrédients pour la semaine visible."""

    def __init__(self, parent, date_debut: str, date_fin: str):
        super().__init__(parent)
        self._debut = date_debut
        self._fin   = date_fin
        self.title("🛒  Liste de courses")
        self.geometry("480x580")
        self.resizable(False, False)
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="🛒  Liste de courses",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=T["tx1"]).pack(padx=20, pady=(16, 2), anchor="w")
        ctk.CTkLabel(self,
                     text=f"Semaine du {self._debut} au {self._fin}  •  ingrédients agrégés",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(padx=20, anchor="w")

        items = db.get_liste_courses(self._debut, self._fin)

        if not items:
            ctk.CTkLabel(self, text="Aucun repas planifié avec des recettes cette semaine.",
                         font=ctk.CTkFont(size=12), text_color=T["tx2"]).pack(pady=40)
        else:
            scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                             scrollbar_button_color=T["bg_el"])
            scroll.pack(padx=12, pady=12, fill="both", expand=True)
            scroll.grid_columnconfigure(0, weight=1)

            # Grouper par catégorie
            by_cat: dict[str, list] = {}
            for item in items:
                cat = item['categorie'] or 'Autre'
                by_cat.setdefault(cat, []).append(item)

            row = 0
            for cat, cat_items in sorted(by_cat.items()):
                ctk.CTkLabel(scroll, text=f"  {cat}",
                             font=ctk.CTkFont(size=11, weight="bold"),
                             text_color=T["tx2"], anchor="w",
                             fg_color=T["bg_el"], corner_radius=4).grid(
                    row=row, column=0, sticky="ew", pady=(8, 2), padx=4)
                row += 1
                for item in cat_items:
                    fr = ctk.CTkFrame(scroll, fg_color=T["bg_app"], corner_radius=6)
                    fr.grid(row=row, column=0, sticky="ew", pady=1, padx=4)
                    fr.grid_columnconfigure(0, weight=1)
                    ctk.CTkLabel(fr, text=f"  {item['nom']}",
                                 font=ctk.CTkFont(size=12), text_color=T["tx1"],
                                 anchor="w").grid(row=0, column=0, padx=8, pady=5, sticky="w")
                    ctk.CTkLabel(fr, text=f"{int(item['total_g'])} g  ",
                                 font=ctk.CTkFont(size=12, weight="bold"),
                                 text_color=T["ac"]).grid(row=0, column=1, padx=8, sticky="e")
                    row += 1

        ctk.CTkButton(self, text="Fermer", fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=38, width=120, command=self.destroy).pack(pady=(4, 16))


# ─────────────────────── Export HTML ─────────────────────────────────────────

def _build_planning_html(lundi: date) -> str:
    REPAS_ORDER = ["petit_dejeuner", "collation_matin", "dejeuner",
                   "collation_soir", "diner"]
    REPAS_LABELS = {"petit_dejeuner":"Petit-déjeuner","collation_matin":"Collation matin",
                    "dejeuner":"Déjeuner","collation_soir":"Collation soir","diner":"Dîner"}
    JOURS = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    MOIS  = ["","janvier","février","mars","avril","mai","juin",
             "juillet","août","septembre","octobre","novembre","décembre"]
    dim = lundi + timedelta(days=6)
    titre = f"Planning du {lundi.day} au {dim.day} {MOIS[dim.month]} {dim.year}"

    rows_html = ""
    for i in range(7):
        jour = lundi + timedelta(days=i)
        jour_str = jour.strftime("%Y-%m-%d")
        repas_jour = db.get_planning_jour(jour_str)
        by_type: dict = {r['type_repas']: r for r in repas_jour}
        rows_html += f"<tr><th>{JOURS[i]}<br><small>{jour.day}/{jour.month}</small></th>"
        for t in REPAS_ORDER:
            r = by_type.get(t)
            if r:
                nom = r.get('recette_nom') or r.get('nom_custom') or '—'
                kcal = int(r.get('calories_custom') or 0)
                rows_html += f"<td><strong>{nom}</strong><br><small>{kcal} kcal</small></td>"
            else:
                rows_html += "<td>—</td>"
        rows_html += "</tr>\n"

    headers = "".join(f"<th>{REPAS_LABELS[t]}</th>" for t in REPAS_ORDER)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8">
<title>{titre}</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; }}
  h1   {{ color: #16a34a; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 8px 10px; text-align: left; vertical-align: top; }}
  th {{ background: #f0fdf4; color: #15803d; }}
  tr:nth-child(even) td {{ background: #fafafa; }}
  small {{ color: #888; }}
  @media print {{ body {{ margin: 8px; }} }}
</style>
</head>
<body>
<h1>🥗 NutriTrack Pro</h1>
<h2>{titre}</h2>
<table>
<thead><tr><th>Jour</th>{headers}</tr></thead>
<tbody>{rows_html}</tbody>
</table>
<p style="color:#aaa;font-size:11px;margin-top:20px">
  Généré par NutriTrack Pro — imprimez cette page pour l'exporter en PDF (Fichier → Imprimer → Enregistrer en PDF)
</p>
</body></html>"""


class DeductionStockDialog(ctk.CTkToplevel):
    """Dialog semi-auto : confirme la déduction du stock après cuisson d'une recette."""

    def __init__(self, parent, repas: dict, on_done=None):
        super().__init__(parent)
        self._repas = repas
        self._on_done = on_done
        self.title("Déduire du stock")
        self.geometry("480x480")
        self.resizable(False, False)
        self.configure(fg_color=T['bg_app'])
        self.grab_set()
        self._build()

    def _build(self):
        recette_id = self._repas.get('recette_id')
        nom = self._repas.get('recette_nom', 'Recette inconnue')
        portions = float(self._repas.get('portions') or 1)

        ctk.CTkLabel(self, text="Recette cuisinée — déduire du stock ?",
                     font=ctk.CTkFont(size=15, weight='bold'),
                     text_color=T['tx1']).pack(pady=(20, 4), padx=20, anchor='w')
        ctk.CTkLabel(self, text=f"{nom}  x{portions} portion(s)",
                     font=ctk.CTkFont(size=12), text_color=T['tx2']).pack(
            padx=20, anchor='w', pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(self, fg_color=T['bg_card'],
                                         corner_radius=8, height=260)
        scroll.pack(fill='both', expand=True, padx=20, pady=(0, 10))
        scroll.grid_columnconfigure(0, weight=1)

        ings = db.get_recette_ingredients(recette_id) if recette_id else []
        stock_rows = db.get_stock()
        stock_by_alim = {s['aliment_id']: s for s in stock_rows}

        self._deductions = []

        for i, ing in enumerate(ings):
            alim = db.get_aliment_by_id(ing['aliment_id']) or {}
            qte_g = db.quantite_en_grammes(
                ing['quantite'] * portions,
                ing.get('unite_recette', 'g'),
                alim)

            s = stock_by_alim.get(ing['aliment_id'])
            if s:
                coeff = db.UNITS_CONVERSION.get(s['unite'])
                if coeff is not None:
                    stock_g = s['quantite'] * coeff
                else:
                    poids = float(alim.get('poids_unite_g') or 0)
                    stock_g = s['quantite'] * poids if poids > 0 else 0
                reste_g = max(0.0, stock_g - qte_g)
                icon = "OK"
                detail = f"{stock_g:.0f}g -> reste {reste_g:.0f}g"
                color = T['ac']
                self._deductions.append({'aliment_id': ing['aliment_id'],
                                          'quantite_g': qte_g})
            else:
                icon = "-"
                detail = "non géré dans le stock"
                color = T['tx3']

            row_frame = ctk.CTkFrame(scroll, fg_color='transparent')
            row_frame.grid(row=i, column=0, sticky='ew', pady=2)
            row_frame.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row_frame, text=icon, width=30,
                         text_color=color).grid(row=0, column=0, padx=(8, 4))
            ctk.CTkLabel(row_frame, text=ing.get('nom', alim.get('nom', '?')),
                         font=ctk.CTkFont(size=12), text_color=T['tx1'],
                         anchor='w').grid(row=0, column=1, sticky='w')
            ctk.CTkLabel(row_frame, text=detail,
                         font=ctk.CTkFont(size=10), text_color=color,
                         anchor='e').grid(row=0, column=2, padx=8)

        bf = ctk.CTkFrame(self, fg_color='transparent')
        bf.pack(pady=10)
        ctk.CTkButton(bf, text="Déduire le disponible",
                      fg_color=T['ac'], hover_color=T['ac_d'],
                      text_color='#000', width=180, height=36,
                      command=self._deduct).grid(row=0, column=0, padx=8)
        ctk.CTkButton(bf, text="Ignorer",
                      fg_color=T['bg_el'], hover_color=T['bg_hl'],
                      width=100, height=36,
                      command=self.destroy).grid(row=0, column=1, padx=8)

    def _deduct(self):
        sous_seuil = []
        if self._deductions:
            sous_seuil = db.deduct_stock(self._deductions)
        if self._on_done:
            self._on_done()
        self.destroy()
        if sous_seuil:
            try:
                show_stock_alert_toast(self.master, sous_seuil)
            except Exception:
                pass
