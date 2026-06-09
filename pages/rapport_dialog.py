# -*- coding: utf-8 -*-
"""NutriTrack Pro — Dialogue de génération du rapport hebdomadaire."""
import os, sys, webbrowser
from datetime import date, timedelta
import customtkinter as ctk
from tkinter import messagebox
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import database as db
import rapport as rp
from theme import T

_MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin",
          "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def _lundi_de(d: date) -> date:
    return d - timedelta(days=d.weekday())


class RapportDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Rapport hebdomadaire")
        self.geometry("460x190")
        self.resizable(False, False)
        self.grab_set()
        self.configure(fg_color=T["bg_card"])
        self._lundi = _lundi_de(date.today())
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="📄  Rapport hebdomadaire",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=T["tx1"]).pack(padx=20, pady=(16, 4), anchor="w")
        ctk.CTkLabel(self, text="Sélectionnez la semaine à exporter",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(padx=20, anchor="w")

        ctk.CTkFrame(self, height=1, fg_color=T["bg_el"]).pack(fill="x", padx=16, pady=(10, 12))

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(padx=20, fill="x")

        ctk.CTkButton(nav, text="◀", width=32, height=32,
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      command=self._prev_week).pack(side="left", padx=(0, 6))

        self._lbl = ctk.CTkLabel(nav, text="",
                                  font=ctk.CTkFont(size=13, weight="bold"),
                                  text_color=T["tx1"])
        self._lbl.pack(side="left", expand=True)

        ctk.CTkButton(nav, text="▶", width=32, height=32,
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      command=self._next_week).pack(side="left", padx=(6, 0))

        self._refresh_label()

        ctk.CTkButton(self, text="📄  Générer & ouvrir dans le navigateur",
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color=T["bg_app"],
                      font=ctk.CTkFont(size=13, weight="bold"),
                      height=40, corner_radius=8,
                      command=self._generate).pack(padx=20, pady=(16, 20), fill="x")

    def _prev_week(self):
        self._lundi -= timedelta(days=7)
        self._refresh_label()

    def _next_week(self):
        self._lundi += timedelta(days=7)
        self._refresh_label()

    def _refresh_label(self):
        dim = self._lundi + timedelta(days=6)
        self._lbl.configure(
            text=f"Semaine du {self._lundi.day} au {dim.day} {_MOIS[dim.month]} {dim.year}")

    def _generate(self):
        data = db.get_rapport_semaine(self._lundi.isoformat())
        if not any(j['enregistre'] for j in data['jours']):
            messagebox.showinfo(
                "Aucune donnée",
                "Aucune entrée dans le journal pour cette semaine.\n"
                "Enregistrez des repas dans le Journal pour générer un rapport.",
                parent=self)
            return
        path = rp.generer_rapport_html(data)
        webbrowser.open(f"file:///{path.replace(os.sep, '/')}")
        self.destroy()
