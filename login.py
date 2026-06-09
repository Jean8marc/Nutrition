"""
NutriTrack Pro — Écran de connexion / sélection utilisateur
"""
import customtkinter as ctk
from tkinter import messagebox
import database as db
from colors import tint_low
from theme import T

ACCENT = T["ac"]


class LoginScreen(ctk.CTkToplevel):
    """
    Écran affiché au démarrage pour choisir ou créer un profil.
    Appelle on_login(user_id) quand un utilisateur est sélectionné.
    """

    def __init__(self, parent, on_login):
        super().__init__(parent)
        self.on_login = on_login
        self.title("NutriTrack Pro — Choisir un profil")
        self.geometry("560x520")
        self.resizable(False, False)
        self.configure(fg_color=T["bg_app"])
        self.protocol("WM_DELETE_WINDOW", parent.destroy)
        self.lift()
        self.grab_set()
        self._build()

    def _build(self):
        # Logo + titre
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(pady=(36, 0))
        ctk.CTkLabel(top, text="🥗", font=ctk.CTkFont(size=42)).pack()
        ctk.CTkLabel(top, text="NutriTrack Pro",
                     font=ctk.CTkFont(family="Helvetica", size=26, weight="bold"),
                     text_color=T["tx1"]).pack()
        ctk.CTkLabel(top, text="Choisissez votre profil pour continuer",
                     font=ctk.CTkFont(size=13), text_color=T["tx2"]).pack(pady=(4, 0))

        # Liste des profils
        self.profiles_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=T["bg_el"],
            height=260)
        self.profiles_frame.pack(padx=40, pady=20, fill="x")
        self.profiles_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self._refresh_profiles()

        # Bouton nouveau profil
        ctk.CTkButton(self, text="＋  Créer un nouveau profil",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color=ACCENT, hover_color=T["ac_d"],
                      text_color="#000", height=44, width=280,
                      corner_radius=10,
                      command=self._open_create).pack(pady=(0, 20))

    def _refresh_profiles(self):
        for w in self.profiles_frame.winfo_children():
            w.destroy()

        users = db.get_users()

        if not users:
            ctk.CTkLabel(self.profiles_frame,
                         text="Aucun profil — créez le vôtre !",
                         font=ctk.CTkFont(size=13), text_color=T["tx2"]).grid(
                row=0, column=0, columnspan=3, pady=30)
            return

        for i, user in enumerate(users):
            card = self._make_user_card(user)
            card.grid(row=i // 3, column=i % 3, padx=6, pady=6, sticky="nsew")

    def _make_user_card(self, user):
        color  = user.get('avatar_color') or ACCENT
        initials = db.user_initials(user)
        card = ctk.CTkFrame(self.profiles_frame, fg_color=T["bg_card"],
                             corner_radius=12, cursor="hand2")
        card.grid_columnconfigure(0, weight=1)

        # Avatar
        avatar = ctk.CTkLabel(card, text=initials,
                               font=ctk.CTkFont(size=22, weight="bold"),
                               text_color=color,
                               fg_color=tint_low(color, bg=T["bg_card"]),
                               width=64, height=64, corner_radius=32)
        avatar.grid(row=0, column=0, pady=(16, 6))

        ctk.CTkLabel(card, text=user['prenom'],
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["tx1"]).grid(row=1, column=0)

        if user.get('nom'):
            ctk.CTkLabel(card, text=user['nom'],
                         font=ctk.CTkFont(size=11), text_color=T["tx2"]).grid(row=2, column=0)

        obj = db.OBJECTIFS_LABELS.get(user.get('objectif', ''), '')
        ctk.CTkLabel(card, text=obj,
                     font=ctk.CTkFont(size=10), text_color=color).grid(
            row=3, column=0, pady=(2, 4))

        ctk.CTkLabel(card, text=f"{user.get('poids', '—')} kg",
                     font=ctk.CTkFont(size=10), text_color=T["tx2"]).grid(
            row=4, column=0, pady=(0, 12))

        # Clic sur la carte
        for widget in [card, avatar]:
            widget.bind("<Button-1>", lambda e, uid=user['id']: self._select(uid))
            widget.bind("<Enter>",    lambda e, c=card: c.configure(fg_color=T["bg_row"]))
            widget.bind("<Leave>",    lambda e, c=card: c.configure(fg_color=T["bg_card"]))

        # Bouton supprimer discret
        ctk.CTkButton(card, text="✕", width=22, height=22,
                      fg_color="transparent", hover_color=T["err_bg"],
                      text_color=T["tx3"], font=ctk.CTkFont(size=10),
                      command=lambda uid=user['id'], n=user['prenom']: self._delete_user(uid, n)).grid(
            row=0, column=0, padx=(0, 4), pady=(4, 0), sticky="ne")

        return card

    def _select(self, user_id: int):
        db.set_current_user(user_id)
        self.destroy()
        self.on_login(user_id)

    def _delete_user(self, user_id: int, prenom: str):
        if messagebox.askyesno("Supprimer le profil",
                               f"Supprimer le profil de « {prenom} » ?\n"
                               f"Tout l'historique sera perdu.",
                               parent=self):
            db.delete_user(user_id)
            self._refresh_profiles()

    def _open_create(self):
        CreateUserDialog(self, self._refresh_profiles)


class CreateUserDialog(ctk.CTkToplevel):
    """Dialogue de création de nouveau profil."""

    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.title("Nouveau profil")
        self.geometry("420x480")
        self.resizable(False, False)
        self.configure(fg_color=T["bg_card"])
        self.grab_set()
        self.lift()
        self._selected_color = db.AVATAR_COLORS[0]
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Créer un profil",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=T["tx1"]).pack(padx=24, pady=(22, 4), anchor="w")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                         scrollbar_button_color=T["bg_el"])
        scroll.pack(fill="both", expand=True, padx=24, pady=8)
        scroll.grid_columnconfigure((0, 1), weight=1)

        self.vars = {}

        def entry(label, key, row, col=0, span=2, ph=""):
            ctk.CTkLabel(scroll, text=label, font=ctk.CTkFont(size=12),
                         text_color=T["tx2"]).grid(
                row=row*2, column=col, columnspan=span, padx=6, pady=(10,2), sticky="w")
            var = ctk.StringVar()
            ctk.CTkEntry(scroll, textvariable=var, height=36,
                         placeholder_text=ph,
                         fg_color=T["bg_el"], border_color=T["bg_hl"],
                         font=ctk.CTkFont(size=13)).grid(
                row=row*2+1, column=col, columnspan=span, padx=6, sticky="ew")
            self.vars[key] = var

        entry("Prénom *",          "prenom", 0, ph="Marie")
        entry("Nom",               "nom",    1, ph="Dupont")
        entry("Poids actuel (kg)", "poids",  2, 0, 1, ph="70")
        entry("Taille (cm)",       "taille", 2, 1, 1, ph="170")

        # Couleur avatar
        ctk.CTkLabel(scroll, text="Couleur de l'avatar",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).grid(
            row=6, column=0, columnspan=2, padx=6, pady=(10,2), sticky="w")

        colors_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        colors_frame.grid(row=7, column=0, columnspan=2, padx=6, sticky="w")

        self._color_btns = []
        for i, color in enumerate(db.AVATAR_COLORS):
            btn = ctk.CTkButton(colors_frame, text="", width=34, height=34,
                                fg_color=color, hover_color=color,
                                corner_radius=17,
                                command=lambda c=color: self._pick_color(c))
            btn.pack(side="left", padx=3)
            self._color_btns.append((btn, color))

        # Boutons
        bf = ctk.CTkFrame(self, fg_color="transparent")
        bf.pack(padx=24, pady=(4, 20), fill="x")
        ctk.CTkButton(bf, text="Annuler",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=38, width=110, corner_radius=8,
                      command=self.destroy).pack(side="left")
        ctk.CTkButton(bf, text="✔  Créer le profil",
                      fg_color=ACCENT, hover_color=T["ac_d"],
                      text_color="#000", height=38, width=160,
                      corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._create).pack(side="right")

    def _pick_color(self, color: str):
        self._selected_color = color
        for btn, c in self._color_btns:
            btn.configure(border_width=3 if c == color else 0,
                          border_color="#ffffff")

    def _create(self):
        prenom = self.vars['prenom'].get().strip()
        if not prenom:
            messagebox.showwarning("Champ requis", "Le prénom est obligatoire.", parent=self)
            return
        try:
            poids  = float(self.vars['poids'].get().replace(',','.') or 70)
            taille = float(self.vars['taille'].get().replace(',','.') or 170)
        except ValueError:
            poids, taille = 70.0, 170.0

        db.create_user(prenom=prenom,
                       nom=self.vars['nom'].get().strip(),
                       poids=poids, taille=taille,
                       avatar_color=self._selected_color)
        self.callback()
        self.destroy()
