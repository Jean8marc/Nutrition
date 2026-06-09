"""
NutriTrack Pro — Application principale avec multi-utilisateurs
"""
import customtkinter as ctk
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import database as db
from pages.dashboard  import DashboardPage
from pages.aliments   import AlimentsPage
from pages.stock      import StockPage
from pages.recettes   import RecettesPage
from pages.planning   import PlanningPage
from pages.profil     import ProfilPage
from pages.journal    import JournalPage
from pages.stats      import StatsPage
from pages.programmes import ProgrammesPage
from pages.sport      import SportPage
from login            import LoginScreen
from colors           import tint_low
import theme as _theme
from theme import T

ctk.set_appearance_mode(T["ctk_mode"])
ctk.set_default_color_theme("blue")

ACCENT = T["ac"]
NAV_ITEMS = [
    ("dashboard",   "🏠",  "Tableau de bord"),
    ("journal",     "📓",  "Journal"),
    ("stats",       "📊",  "Statistiques"),
    ("profil",      "👤",  "Mon Profil"),
    ("aliments",    "🥑",  "Aliments"),
    ("stock",       "📦",  "Stock"),
    ("recettes",    "👨\u200d🍳", "Recettes"),
    ("planning",    "📅",  "Planning repas"),
    ("programmes",  "📋",  "Programmes"),
    ("sport",       "🏃",  "Sport"),
]


class NutriTrackApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NutriTrack Pro")
        self.geometry("1280x820")
        self.minsize(1060, 680)
        self.configure(fg_color=T["bg_app"])

        db.init_db()

        self._active_page = "dashboard"
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._nav_btns: dict[str, ctk.CTkButton] = {}

        self._build_layout()
        self._load_all_pages()

        # Afficher l'écran de login au démarrage
        self.after(100, self._show_login)

    # ── Layout ───────────────────────────────────────────────────

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar ───────────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self, fg_color=T["bg_card"],
                                    width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(20, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        # Logo
        logo = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo.grid(row=0, column=0, padx=16, pady=(22, 6), sticky="ew")
        ctk.CTkLabel(logo, text="🥗",
                     font=ctk.CTkFont(size=28)).pack(side="left", padx=(4, 0))
        titles = ctk.CTkFrame(logo, fg_color="transparent")
        titles.pack(side="left", padx=8)
        ctk.CTkLabel(titles, text="NutriTrack",
                     font=ctk.CTkFont(family="Helvetica", size=17, weight="bold"),
                     text_color=T["tx1"]).pack(anchor="w")
        ctk.CTkLabel(titles, text="Pro",
                     font=ctk.CTkFont(size=11), text_color=ACCENT).pack(anchor="w")

        # Séparateur
        ctk.CTkFrame(self.sidebar, height=1, fg_color=T["bg_el"]).grid(
            row=1, column=0, padx=16, pady=(8, 12), sticky="ew")

        ctk.CTkLabel(self.sidebar, text="NAVIGATION",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=T["tx3"]).grid(
            row=2, column=0, padx=20, pady=(0, 6), sticky="w")

        # Boutons nav
        for i, (key, icon, label) in enumerate(NAV_ITEMS):
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"  {icon}   {label}",
                font=ctk.CTkFont(size=13),
                height=42, anchor="w",
                fg_color="transparent",
                text_color=T["tx2"],
                hover_color=T["bg_el"],
                corner_radius=8,
                command=lambda k=key: self._show_page(k))
            btn.grid(row=3+i, column=0, padx=10, pady=2, sticky="ew")
            self._nav_btns[key] = btn

        # ── Switcher de thème ─────────────────────────────────────
        theme_row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        theme_row.grid(row=21, column=0, padx=10, pady=(4, 0), sticky="ew")
        ctk.CTkLabel(theme_row, text="Thème",
                     font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=T["tx3"]).pack(side="left", padx=(6, 6))
        for tname, tdata in _theme.THEMES.items():
            is_active = (tname == _theme.get_theme_name())
            btn = ctk.CTkButton(
                theme_row, text=tdata["name"],
                width=58, height=24, corner_radius=6,
                font=ctk.CTkFont(size=10),
                fg_color=T["ac_bg"] if is_active else T["bg_el"],
                text_color=T["ac"] if is_active else T["tx2"],
                hover_color=T["ac_bg"],
                command=lambda n=tname: self._switch_theme(n))
            btn.pack(side="left", padx=2)

        # ── Avatar utilisateur bas de sidebar ─────────────────────
        ctk.CTkFrame(self.sidebar, height=1, fg_color=T["bg_el"]).grid(
            row=22, column=0, padx=16, pady=8, sticky="ew")

        self.user_sidebar = ctk.CTkFrame(self.sidebar, fg_color="transparent",
                                          cursor="hand2")
        self.user_sidebar.grid(row=23, column=0, padx=12, pady=(0, 12), sticky="ew")
        self.user_sidebar.grid_columnconfigure(1, weight=1)
        self.user_sidebar.bind("<Button-1>", lambda e: self._show_login())

        self.sidebar_avatar = ctk.CTkLabel(self.user_sidebar, text="?",
                                            font=ctk.CTkFont(size=14, weight="bold"),
                                            width=38, height=38, corner_radius=19,
                                            fg_color=T["bg_el"], text_color=T["tx2"])
        self.sidebar_avatar.grid(row=0, column=0, padx=(0, 8))
        self.sidebar_avatar.bind("<Button-1>", lambda e: self._show_login())

        self.sidebar_name = ctk.CTkLabel(self.user_sidebar, text="",
                                          font=ctk.CTkFont(size=12),
                                          text_color=T["tx1"], anchor="w")
        self.sidebar_name.grid(row=0, column=1, sticky="w")
        self.sidebar_name.bind("<Button-1>", lambda e: self._show_login())

        ctk.CTkLabel(self.sidebar, text="v1.0.0",
                     font=ctk.CTkFont(size=9), text_color=T["tx3"]).grid(
            row=24, column=0, padx=16, pady=(0, 16), sticky="w")

        # ── Zone contenu ──────────────────────────────────────────
        self.content = ctk.CTkFrame(self, fg_color=T["bg_app"], corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

    # ── Pages ────────────────────────────────────────────────────

    def _load_all_pages(self):
        self._pages["dashboard"]  = DashboardPage(self.content)
        self._pages["journal"]    = JournalPage(self.content)
        self._pages["stats"]      = StatsPage(self.content)
        self._pages["profil"]     = ProfilPage(self.content)
        self._pages["aliments"]   = AlimentsPage(self.content)
        self._pages["stock"]      = StockPage(self.content)
        self._pages["recettes"]   = RecettesPage(self.content)
        self._pages["planning"]   = PlanningPage(self.content)
        self._pages["programmes"] = ProgrammesPage(self.content)
        self._pages["sport"]      = SportPage(self.content)

        for page in self._pages.values():
            page.grid(row=0, column=0, sticky="nsew")
            page.grid_remove()

    def _show_page(self, key: str):
        if self._active_page in self._pages:
            self._pages[self._active_page].grid_remove()
        if self._active_page in self._nav_btns:
            self._nav_btns[self._active_page].configure(
                fg_color="transparent", text_color=T["tx2"])

        self._active_page = key
        self._pages[key].grid()
        self._nav_btns[key].configure(
            fg_color=T["ac_bg"], text_color=T["ac"])

        if hasattr(self._pages[key], "refresh"):
            self._pages[key].refresh()

    # ── Login ────────────────────────────────────────────────────

    def _show_login(self):
        LoginScreen(self, self._on_login)

    def _on_login(self, user_id: int):
        """Appelé après sélection d'un utilisateur."""
        self._update_sidebar_user()
        self._show_page("dashboard")

    def _update_sidebar_user(self):
        user = db.get_current_user()
        if not user:
            return
        color    = user.get('avatar_color') or ACCENT
        initials = db.user_initials(user)
        prenom   = user.get('prenom', '')
        self.sidebar_avatar.configure(
            text=initials, text_color=color,
            fg_color=tint_low(color, bg=T["bg_card"]))
        self.sidebar_name.configure(
            text=prenom)

    # ── Thème ────────────────────────────────────────────────────

    def _switch_theme(self, theme_name: str):
        if theme_name == _theme.get_theme_name():
            return
        from tkinter import messagebox
        ok = messagebox.askyesno(
            "Changer de thème",
            f"Appliquer le thème « {_theme.THEMES[theme_name]['name']} » ?\n"
            "L'application va redémarrer.",
            parent=self)
        if not ok:
            return
        _theme.save_theme(theme_name)
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv)
        self.destroy()

    # ── API publique pour ProfilPage ──────────────────────────────

    def _show_login_from_profil(self):
        self._show_login()


def main():
    app = NutriTrackApp()
    app.mainloop()


if __name__ == "__main__":
    main()
