"""NutriTrack Pro — Gestion de stock des aliments."""
import sys, os
import customtkinter as ctk
from tkinter import messagebox
from datetime import date, timedelta, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import database as db
from theme import T
from logger import get_logger
try:
    from barcode_scanner import BarcodeScannerDialog, ProductFoundDialog, MANUAL_OK
except ImportError:
    BarcodeScannerDialog = None
    ProductFoundDialog = None
    MANUAL_OK = False

log = get_logger(__name__)

UNITES_STOCK = ['g', 'ml', 'kg', 'L', 'unité']


def _dlc_status(dlc: str):
    """Retourne (texte, couleur) selon la date de péremption ISO."""
    if not dlc:
        return '—', T['tx3']
    today = date.today().isoformat()
    cutoff = (date.today() + timedelta(days=3)).isoformat()
    if dlc < today:
        return 'Périmé', T['err']
    if dlc <= cutoff:
        return 'Bientôt', T['cal']
    return 'OK', T['ac']


def show_stock_alert_toast(parent, items_sous_seuil: list):
    """Affiche un toast non-bloquant (4s) pour les items sous seuil."""
    if not items_sous_seuil:
        return
    toast = ctk.CTkToplevel(parent)
    toast.overrideredirect(True)
    toast.configure(fg_color=T['bg_card'])
    toast.attributes('-topmost', True)

    frame = ctk.CTkFrame(toast, fg_color=T['bg_card'],
                          border_width=1, border_color=T['cal'],
                          corner_radius=8)
    frame.pack(padx=2, pady=2)

    ctk.CTkLabel(frame, text='Stock faible',
                 font=ctk.CTkFont(size=12, weight='bold'),
                 text_color=T['cal']).pack(padx=12, pady=(8, 4), anchor='w')

    for item in items_sous_seuil[:3]:
        txt = f"  {item['nom']} : {round(item['quantite'], 1)}{item['unite']} (seuil : {round(item['quantite_min'], 1)}{item['unite']})"
        ctk.CTkLabel(frame, text=txt,
                     font=ctk.CTkFont(size=11), text_color=T['tx1']).pack(
            padx=12, anchor='w')

    def _nav_stock():
        toast.destroy()
        try:
            parent.winfo_toplevel()._show_page('stock')
        except Exception:
            pass

    ctk.CTkButton(frame, text='Voir le stock',
                  fg_color='transparent', hover_color=T['bg_el'],
                  text_color=T['ac'], font=ctk.CTkFont(size=11),
                  command=_nav_stock).pack(padx=8, pady=(4, 8), anchor='e')

    parent.update_idletasks()
    sw = parent.winfo_screenwidth()
    sh = parent.winfo_screenheight()
    toast.update_idletasks()
    w = toast.winfo_reqwidth()
    h = toast.winfo_reqheight()
    toast.geometry(f"+{sw - w - 20}+{sh - h - 60}")
    toast.after(4000, lambda: toast.destroy() if toast.winfo_exists() else None)


class StockPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=T['bg_app'], corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._stock = []
        self._alerts = []
        self._search_var = ctk.StringVar()
        self._cat_var = ctk.StringVar(value='Toutes')
        self._build()

    def _build(self):
        # ── En-tête ─────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color='transparent')
        hdr.grid(row=0, column=0, padx=28, pady=(28, 0), sticky='ew')
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text='📦  Mon Stock',
                     font=ctk.CTkFont(family='Helvetica', size=26, weight='bold'),
                     text_color=T['tx1']).grid(row=0, column=0, sticky='w')
        ctk.CTkLabel(hdr,
                     text="Gérez vos stocks d'aliments et découvrez quelles recettes vous pouvez cuisiner",
                     font=ctk.CTkFont(size=12), text_color=T['tx2']).grid(
            row=1, column=0, sticky='w', pady=(2, 0))

        btn_hdr = ctk.CTkFrame(hdr, fg_color='transparent')
        btn_hdr.grid(row=0, column=1, rowspan=2, sticky='e')

        self._search_var.trace_add('write', lambda *_: self._refresh_list())
        ctk.CTkEntry(btn_hdr, textvariable=self._search_var,
                     placeholder_text='Rechercher…',
                     width=180, height=36,
                     fg_color=T['bg_card'], border_color=T['bg_hl'],
                     font=ctk.CTkFont(size=13)).grid(row=0, column=0, padx=(0, 10))

        ctk.CTkButton(btn_hdr, text='＋  Ajouter',
                      font=ctk.CTkFont(size=13, weight='bold'),
                      fg_color=T['ac'], hover_color=T['ac_d'],
                      text_color='#000', height=36, width=130, corner_radius=8,
                      command=self._open_add).grid(row=0, column=1)

        # ── Zone alertes (cachée si vide) ────────────────────────
        self._alert_frame = ctk.CTkFrame(self, fg_color=T['bg_card'],
                                          corner_radius=10)

        # ── Filtre catégorie ─────────────────────────────────────
        fbar = ctk.CTkFrame(self, fg_color='transparent')
        fbar.grid(row=2, column=0, padx=28, pady=10, sticky='ew')

        ctk.CTkLabel(fbar, text='Catégorie :',
                     text_color=T['tx2']).pack(side='left', padx=(0, 8))
        self._cat_var.trace_add('write', lambda *_: self._refresh_list())
        self._cat_menu = ctk.CTkOptionMenu(fbar, variable=self._cat_var,
                                            values=['Toutes'],
                                            fg_color=T['bg_el'],
                                            button_color=T['bg_hl'],
                                            width=180)
        self._cat_menu.pack(side='left')

        self._count_lbl = ctk.CTkLabel(fbar, text='',
                                        font=ctk.CTkFont(size=12),
                                        text_color=T['tx2'])
        self._count_lbl.pack(side='right')

        # ── Liste scrollable ─────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(self, fg_color='transparent',
                                               scrollbar_button_color=T['bg_el'],
                                               scrollbar_button_hover_color=T['bg_hl'])
        self._scroll.grid(row=3, column=0, padx=28, pady=(0, 28), sticky='nsew')
        self._scroll.grid_columnconfigure(0, weight=1)

        # ── Liste de courses ─────────────────────────────────────
        self._courses_frame = ctk.CTkFrame(self, fg_color=T['bg_card'],
                                            corner_radius=10)
        self._courses_frame.grid(row=4, column=0, padx=28, pady=(0, 28), sticky='ew')
        self._courses_frame.grid_columnconfigure(0, weight=1)
        self._courses_visible = False

        courses_hdr = ctk.CTkFrame(self._courses_frame, fg_color='transparent')
        courses_hdr.grid(row=0, column=0, sticky='ew', padx=14, pady=10)
        courses_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(courses_hdr, text='Liste de courses',
                     font=ctk.CTkFont(size=14, weight='bold'),
                     text_color=T['tx1']).grid(row=0, column=0, sticky='w')
        self._courses_toggle_btn = ctk.CTkButton(
            courses_hdr, text='Afficher', width=90, height=28,
            fg_color=T['bg_el'], hover_color=T['bg_hl'],
            text_color=T['tx2'], font=ctk.CTkFont(size=11),
            command=self._toggle_courses)
        self._courses_toggle_btn.grid(row=0, column=1, sticky='e')

        self._courses_content = ctk.CTkFrame(self._courses_frame, fg_color='transparent')
        self._courses_content.grid_columnconfigure(0, weight=1)

    # ── Refresh ─────────────────────────────────────────────────

    def refresh(self):
        if not db.get_current_user_id():
            return
        self._stock = db.get_stock()
        self._alerts = db.get_stock_alerts()
        self._update_alerts()
        self._update_cat_menu()
        self._refresh_list()

    def _update_alerts(self):
        self._alert_frame.grid_forget()
        for w in self._alert_frame.winfo_children():
            w.destroy()

        dlc_alerts = self._alerts
        sous_seuil = db.get_stock_sous_seuil()
        if not dlc_alerts and not sous_seuil:
            return

        ctk.CTkLabel(self._alert_frame, text='Alertes stock',
                     font=ctk.CTkFont(size=13, weight='bold'),
                     text_color=T['cal']).grid(
            row=0, column=0, sticky='w', padx=14, pady=(10, 4))

        today = date.today().isoformat()
        row_i = 1
        for item in dlc_alerts:
            dlc = item.get('date_peremption', '')
            if dlc < today:
                txt = f"[x]  {item['nom']} - perime (DLC : {dlc})"
                color = T['err']
            else:
                txt = f"[!]  {item['nom']} - expire le {dlc}"
                color = T['cal']
            ctk.CTkLabel(self._alert_frame, text=txt, text_color=color,
                         font=ctk.CTkFont(size=12)).grid(
                row=row_i, column=0, sticky='w', padx=14, pady=2)
            row_i += 1

        for item in sous_seuil:
            txt = f"[~]  {item['nom']} - {round(item['quantite'],1)}{item['unite']} restants (seuil : {round(item['quantite_min'],1)}{item['unite']})"
            ctk.CTkLabel(self._alert_frame, text=txt, text_color=T['cal'],
                         font=ctk.CTkFont(size=12)).grid(
                row=row_i, column=0, sticky='w', padx=14, pady=2)
            row_i += 1

        self._alert_frame.grid(row=1, column=0, padx=28, pady=(10, 0), sticky='ew')

    def _update_cat_menu(self):
        cats = sorted({s['categorie'] for s in self._stock if s.get('categorie')})
        self._cat_menu.configure(values=['Toutes'] + cats)

    def _refresh_list(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        search = self._search_var.get().strip().lower()
        cat = self._cat_var.get()
        items = [s for s in self._stock
                 if (not search or search in s['nom'].lower())
                 and (cat == 'Toutes' or s.get('categorie') == cat)]

        self._count_lbl.configure(text=f'{len(items)} aliment(s)')

        if not items:
            ctk.CTkLabel(self._scroll,
                         text='Aucun aliment en stock.\nCliquez sur « ＋ Ajouter » pour commencer.',
                         text_color=T['tx3'], font=ctk.CTkFont(size=13),
                         justify='center').grid(row=0, column=0, pady=40)
            return

        # En-tête tableau
        cols = [('Aliment', 220), ('Catégorie', 150), ('Qté', 70),
                ('Unité', 65), ('DLC', 95), ('Statut', 80), ('', 76)]
        hdr_row = ctk.CTkFrame(self._scroll, fg_color=T['bg_el'], corner_radius=6)
        hdr_row.grid(row=0, column=0, sticky='ew', pady=(0, 4))
        for j, (h, w) in enumerate(cols):
            ctk.CTkLabel(hdr_row, text=h, width=w,
                         font=ctk.CTkFont(size=11, weight='bold'),
                         text_color=T['tx2']).grid(
                row=0, column=j, padx=6, pady=6, sticky='w')

        for i, item in enumerate(items):
            bg = T['bg_card'] if i % 2 == 0 else T['bg_el']
            row = ctk.CTkFrame(self._scroll, fg_color=bg, corner_radius=4)
            row.grid(row=i + 1, column=0, sticky='ew', pady=1)

            dlc = item.get('date_peremption') or ''
            status_txt, status_col = _dlc_status(dlc)

            vals = [item['nom'], item.get('categorie', ''),
                    str(round(item['quantite'], 1)), item.get('unite', 'g'),
                    dlc or '—', status_txt]
            colors = [T['tx1'], T['tx2'], T['tx1'], T['tx2'], T['tx2'], status_col]
            widths = [w for _, w in cols]

            for j, (v, c, w) in enumerate(zip(vals, colors, widths)):
                ctk.CTkLabel(row, text=v, width=w, text_color=c,
                             font=ctk.CTkFont(size=12), anchor='w').grid(
                    row=0, column=j, padx=6, pady=8, sticky='w')

            bf = ctk.CTkFrame(row, fg_color='transparent')
            bf.grid(row=0, column=6, padx=4, pady=4)
            ctk.CTkButton(bf, text='✏️', width=34, height=28,
                          fg_color=T['bg_hl'], hover_color=T['bg_el'],
                          font=ctk.CTkFont(size=12), corner_radius=6,
                          command=lambda it=item: self._open_edit(it)).grid(
                row=0, column=0, padx=2)
            ctk.CTkButton(bf, text='🗑', width=34, height=28,
                          fg_color=T['bg_hl'], hover_color=T['err_bg'],
                          font=ctk.CTkFont(size=12), corner_radius=6,
                          command=lambda it=item: self._delete_item(it)).grid(
                row=0, column=1, padx=2)

    # ── Actions ─────────────────────────────────────────────────

    def _open_add(self):
        StockDialog(self, on_save=self.refresh)

    def _open_edit(self, item):
        StockDialog(self, item=item, on_save=self.refresh)

    def _delete_item(self, item):
        if messagebox.askyesno('Supprimer',
                               f"Retirer « {item['nom']} » du stock ?",
                               parent=self):
            db.delete_stock(item['id'])
            self.refresh()

    # ── Liste de courses ─────────────────────────────────────────

    def _toggle_courses(self):
        self._courses_visible = not self._courses_visible
        if self._courses_visible:
            self._courses_toggle_btn.configure(text='Masquer')
            self._draw_courses()
            self._courses_content.grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 14))
        else:
            self._courses_toggle_btn.configure(text='Afficher')
            self._courses_content.grid_forget()

    def _draw_courses(self):
        for w in self._courses_content.winfo_children():
            w.destroy()

        data = db.get_liste_courses_stock()
        row_i = 0

        def add_section(title, items, render_fn):
            nonlocal row_i
            if not items:
                return
            ctk.CTkLabel(self._courses_content, text=title,
                         font=ctk.CTkFont(size=12, weight='bold'),
                         text_color=T['tx2']).grid(
                row=row_i, column=0, sticky='w', pady=(10, 2))
            row_i += 1
            for item in items:
                render_fn(item)
                row_i += 1

        def render_staple(item):
            ctk.CTkLabel(self._courses_content,
                         text=f"  - {item['nom']}  manque {item['manque']}{item['unite']}  (cible {item['quantite_cible']}{item['unite']})",
                         font=ctk.CTkFont(size=12), text_color=T['tx1']).grid(
                row=row_i, column=0, sticky='w', padx=8)

        def render_recette(item):
            ctk.CTkLabel(self._courses_content,
                         text=f"  - {item['nom']}  {item['manque_g']}g  -> {item['nom_recette']} ({item['date_repas']})",
                         font=ctk.CTkFont(size=12), text_color=T['tx1']).grid(
                row=row_i, column=0, sticky='w', padx=8)

        def render_suggestion(item):
            f = ctk.CTkFrame(self._courses_content, fg_color='transparent')
            f.grid(row=row_i, column=0, sticky='ew', padx=8)
            ctk.CTkLabel(f, text=f"  - {item['nom']}  (utilise {item['nb_utilisations']}x)",
                         font=ctk.CTkFont(size=12), text_color=T['tx2']).pack(side='left')
            ctk.CTkButton(f, text='+ Staple', width=70, height=22,
                          fg_color=T['bg_el'], hover_color=T['bg_hl'],
                          text_color=T['ac'], font=ctk.CTkFont(size=10),
                          command=lambda aid=item['aliment_id']: self._mark_staple(aid)).pack(
                side='right', padx=4)

        add_section('STAPLES A REAPPROVISIONNER', data['staples'], render_staple)
        add_section('RECETTES PLANIFIEES - MANQUANTS', data['recettes'], render_recette)
        add_section('SUGGESTIONS - frequemment utilises', data['suggestions'], render_suggestion)

        if not any([data['staples'], data['recettes'], data['suggestions']]):
            ctk.CTkLabel(self._courses_content,
                         text='Aucun article a acheter pour le moment.',
                         text_color=T['tx3'], font=ctk.CTkFont(size=12)).grid(
                row=0, column=0, pady=16)
            return

        row_i += 1
        ctk.CTkButton(self._courses_content, text='Copier la liste',
                      fg_color=T['bg_el'], hover_color=T['bg_hl'],
                      text_color=T['tx1'], width=120,
                      command=lambda: self._copy_courses(data)).grid(
            row=row_i, column=0, pady=10, sticky='w', padx=8)

    def _mark_staple(self, aliment_id: int):
        stock = db.get_stock()
        item = next((s for s in stock if s['aliment_id'] == aliment_id), None)
        if item:
            conn = db.get_connection()
            conn.execute("UPDATE stock SET est_staple=1 WHERE id=?", (item['id'],))
            conn.commit()
            conn.close()
            self._draw_courses()

    def _copy_courses(self, data: dict):
        lines = []
        if data['staples']:
            lines.append('STAPLES A REAPPROVISIONNER')
            for s in data['staples']:
                lines.append(f"  - {s['nom']} : manque {s['manque']}{s['unite']}")
        if data['recettes']:
            lines.append('RECETTES PLANIFIEES - MANQUANTS')
            for r in data['recettes']:
                lines.append(f"  - {r['nom']} : {r['manque_g']}g ({r['nom_recette']})")
        try:
            self.clipboard_clear()
            self.clipboard_append('\n'.join(lines))
        except Exception:
            pass


class StockDialog(ctk.CTkToplevel):
    def __init__(self, parent, item: dict = None, on_save=None):
        super().__init__(parent)
        self._item = item
        self._on_save = on_save
        self._aliment_id = item['aliment_id'] if item else None

        self.title('Modifier le stock' if item else 'Ajouter au stock')
        self.geometry('440x580')
        self.resizable(False, False)
        self.configure(fg_color=T['bg_app'])
        self.grab_set()
        self._build()
        if item:
            self._prefill(item)

    def _build(self):
        pad = {'padx': 20, 'pady': 5}

        ctk.CTkLabel(self, text='Aliment *', text_color=T['tx2'],
                     font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky='w', **pad)

        search_row = ctk.CTkFrame(self, fg_color='transparent')
        search_row.grid(row=1, column=0, sticky='w', **pad)

        self._search_var = ctk.StringVar()
        self._search_var.trace_add('write', self._on_search)
        ctk.CTkEntry(search_row, textvariable=self._search_var,
                     placeholder_text='Rechercher un aliment…',
                     width=290, fg_color=T['bg_el'],
                     border_color=T['bg_hl']).grid(row=0, column=0)

        scan_lbl = 'Scanner' if MANUAL_OK else 'Code-barres'
        scan_col = T['blue'] if MANUAL_OK else T['bg_hl']
        ctk.CTkButton(search_row, text=scan_lbl, width=90, height=32,
                      fg_color=scan_col, hover_color=T['blue_d'],
                      font=ctk.CTkFont(size=11),
                      command=self._open_scan).grid(row=0, column=1, padx=(8, 0))

        self._results_frame = ctk.CTkFrame(self, fg_color=T['bg_el'],
                                            corner_radius=6)

        self._selected_lbl = ctk.CTkLabel(self, text='',
                                           text_color=T['ac'],
                                           font=ctk.CTkFont(size=12))
        self._selected_lbl.grid(row=3, column=0, sticky='w', padx=20)

        row_qu = ctk.CTkFrame(self, fg_color='transparent')
        row_qu.grid(row=4, column=0, sticky='w', **pad)

        ctk.CTkLabel(row_qu, text='Quantité *', text_color=T['tx2'],
                     width=90).grid(row=0, column=0, sticky='w')
        ctk.CTkLabel(row_qu, text='Unité', text_color=T['tx2'],
                     width=80).grid(row=0, column=1, sticky='w', padx=(20, 0))

        self._qty_var = ctk.StringVar()
        ctk.CTkEntry(row_qu, textvariable=self._qty_var, width=100,
                     fg_color=T['bg_el'], border_color=T['bg_hl']).grid(row=1, column=0)

        self._unite_var = ctk.StringVar(value='g')
        ctk.CTkOptionMenu(row_qu, variable=self._unite_var,
                          values=UNITES_STOCK, width=90,
                          fg_color=T['bg_el'],
                          button_color=T['bg_hl']).grid(row=1, column=1, padx=(20, 0))

        ctk.CTkLabel(self, text='Date péremption JJ/MM/AAAA — optionnel',
                     text_color=T['tx2'], font=ctk.CTkFont(size=11)).grid(
            row=5, column=0, sticky='w', **pad)
        self._dlc_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self._dlc_var, width=180,
                     placeholder_text='ex: 10/06/2026',
                     fg_color=T['bg_el'], border_color=T['bg_hl']).grid(
            row=6, column=0, sticky='w', padx=20)

        ctk.CTkLabel(self, text='Notes — optionnel',
                     text_color=T['tx2'], font=ctk.CTkFont(size=11)).grid(
            row=7, column=0, sticky='w', **pad)
        self._notes_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self._notes_var, width=380,
                     fg_color=T['bg_el'], border_color=T['bg_hl']).grid(
            row=8, column=0, padx=20)

        ctk.CTkFrame(self, height=1, fg_color=T['bg_el']).grid(
            row=9, column=0, sticky='ew', padx=20, pady=8)

        row_min = ctk.CTkFrame(self, fg_color='transparent')
        row_min.grid(row=10, column=0, sticky='w', padx=20, pady=4)
        ctk.CTkLabel(row_min, text='Seuil alerte (0 = desactive) :',
                     text_color=T['tx2'], font=ctk.CTkFont(size=11),
                     width=200).grid(row=0, column=0, sticky='w')
        self._qmin_var = ctk.StringVar(value='0')
        ctk.CTkEntry(row_min, textvariable=self._qmin_var, width=80,
                     fg_color=T['bg_el'], border_color=T['bg_hl']).grid(
            row=0, column=1, padx=8)

        self._staple_var2 = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text='Produit de premiere necessite (staple)',
                        variable=self._staple_var2,
                        fg_color=T['ac'], hover_color=T['ac_d'],
                        text_color=T['tx1'],
                        command=self._toggle_staple_fields).grid(
            row=11, column=0, sticky='w', padx=20, pady=4)

        self._staple_fields2 = ctk.CTkFrame(self, fg_color='transparent')
        ctk.CTkLabel(self._staple_fields2, text='Quantite cible :',
                     text_color=T['tx2'], font=ctk.CTkFont(size=11)).pack(side='left')
        self._cible_var2 = ctk.StringVar(value='0')
        ctk.CTkEntry(self._staple_fields2, textvariable=self._cible_var2, width=80,
                     fg_color=T['bg_el'], border_color=T['bg_hl']).pack(side='left', padx=8)

        self._eau_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text="Source d'eau (lier au tracker hydratation)",
                        variable=self._eau_var,
                        fg_color=T['blue'], hover_color=T['blue_d'],
                        text_color=T['tx1']).grid(
            row=13, column=0, sticky='w', padx=20, pady=4)

        bf = ctk.CTkFrame(self, fg_color='transparent')
        bf.grid(row=14, column=0, pady=16)
        ctk.CTkButton(bf, text='Enregistrer',
                      fg_color=T['ac'], hover_color=T['ac_d'],
                      text_color='#000', width=130, height=36,
                      command=self._save).grid(row=0, column=0, padx=8)
        ctk.CTkButton(bf, text='Annuler',
                      fg_color=T['bg_el'], hover_color=T['bg_hl'],
                      width=110, height=36,
                      command=self.destroy).grid(row=0, column=1, padx=8)

    def _toggle_staple_fields(self):
        if self._staple_var2.get():
            self._staple_fields2.grid(row=12, column=0, sticky='w', padx=32, pady=2)
        else:
            self._staple_fields2.grid_forget()

    def _open_scan(self):
        if not MANUAL_OK or BarcodeScannerDialog is None:
            messagebox.showinfo('Module manquant',
                                'pip install requests', parent=self)
            return
        BarcodeScannerDialog(self, self._on_scan_found)

    def _on_scan_found(self, data: dict):
        """Produit identifié par scan : vérifie s'il est en BDD, sinon propose de l'ajouter."""
        # Chercher dans aliments par nom
        alims = db.get_aliments(search=data.get('nom', ''))
        exact = next((a for a in alims
                      if a['nom'].strip().lower() == data.get('nom', '').strip().lower()), None)
        if exact:
            self._select_aliment(exact)
        elif ProductFoundDialog:
            ProductFoundDialog(self, data, self._on_scan_confirmed)

    def _on_scan_confirmed(self, data: dict):
        """Aliment scanné confirmé et ajouté à la BDD : le sélectionner."""
        db.add_aliment(data)
        alims = db.get_aliments(search=data.get('nom', ''))
        alim = next((a for a in alims
                     if a['nom'].strip().lower() == data.get('nom', '').strip().lower()), None)
        if alim:
            self._select_aliment(alim)

    def _on_search(self, *_):
        for w in self._results_frame.winfo_children():
            w.destroy()
        q = self._search_var.get().strip()
        if len(q) < 2:
            self._results_frame.grid_forget()
            return
        aliments = db.get_aliments(search=q)[:8]
        if not aliments:
            self._results_frame.grid_forget()
            return
        for i, a in enumerate(aliments):
            ctk.CTkButton(
                self._results_frame,
                text=f"{a['nom']}  ({a['categorie']})",
                fg_color='transparent', hover_color=T['ac_bg'],
                text_color=T['tx1'], anchor='w',
                font=ctk.CTkFont(size=12),
                command=lambda al=a: self._select_aliment(al)
            ).grid(row=i, column=0, sticky='ew', padx=4, pady=1)
        self._results_frame.grid(row=2, column=0, sticky='ew', padx=20)

    def _select_aliment(self, aliment):
        self._aliment_id = aliment['id']
        self._search_var.set('')
        self._results_frame.grid_forget()
        self._selected_lbl.configure(text=f"✅  {aliment['nom']}")
        if not self._item:
            self._unite_var.set(aliment.get('unite', 'g')
                                if aliment.get('unite') in UNITES_STOCK else 'g')

    def _prefill(self, item):
        self._selected_lbl.configure(text=f"✅  {item['nom']}")
        self._qty_var.set(str(round(item['quantite'], 2)))
        self._unite_var.set(item.get('unite', 'g'))
        dlc = item.get('date_peremption') or ''
        if dlc:
            try:
                self._dlc_var.set(
                    datetime.fromisoformat(dlc).strftime('%d/%m/%Y'))
            except Exception:
                self._dlc_var.set(dlc)
        self._notes_var.set(item.get('notes', ''))
        self._qmin_var.set(str(round(float(item.get('quantite_min') or 0), 1)))
        self._staple_var2.set(bool(item.get('est_staple', 0)))
        self._cible_var2.set(str(round(float(item.get('quantite_cible') or 0), 1)))
        self._eau_var.set(bool(item.get('est_eau', 0)))
        if self._staple_var2.get():
            self._toggle_staple_fields()

    def _save(self):
        if not self._aliment_id:
            messagebox.showwarning('Champ requis',
                                   'Sélectionnez un aliment.', parent=self)
            return
        try:
            qty = float(self._qty_var.get().replace(',', '.'))
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning('Quantité invalide',
                                   'Entrez une quantité positive.', parent=self)
            return

        dlc_str = self._dlc_var.get().strip()
        dlc_iso = None
        if dlc_str:
            try:
                dlc_iso = datetime.strptime(dlc_str, '%d/%m/%Y').date().isoformat()
            except ValueError:
                messagebox.showwarning('Date invalide',
                                       'Format attendu : JJ/MM/AAAA', parent=self)
                return

        db.upsert_stock(self._aliment_id, qty,
                        self._unite_var.get(), dlc_iso,
                        self._notes_var.get().strip())

        stock = db.get_stock()
        item_s = next((s for s in stock if s['aliment_id'] == self._aliment_id), None)
        if item_s:
            try:
                qmin = float(self._qmin_var.get().replace(',', '.') or 0)
            except ValueError:
                qmin = 0.0
            try:
                cible = float(self._cible_var2.get().replace(',', '.') or 0)
            except ValueError:
                cible = 0.0
            conn = db.get_connection()
            conn.execute("""UPDATE stock SET quantite_min=?, est_staple=?,
                            quantite_cible=? WHERE id=?""",
                         (qmin, 1 if self._staple_var2.get() else 0,
                          cible, item_s['id']))
            conn.commit()
            conn.close()
            if self._eau_var.get():
                db.set_stock_eau(item_s['id'])

        if self._on_save:
            self._on_save()
        self.destroy()


class AddToStockDialog(ctk.CTkToplevel):
    """
    Dialog rapide pour ajouter un aliment au stock depuis un contexte externe
    (page Aliments, scanner, journal). L'aliment est pré-rempli, pas de recherche.
    """
    def __init__(self, parent, aliment: dict, on_save=None):
        super().__init__(parent)
        self._aliment = aliment
        self._on_save = on_save
        self._stock_qty_entry = None
        self.title('Ajouter au stock')
        self.geometry('380x340')
        self.resizable(False, False)
        self.configure(fg_color=T['bg_app'])
        self.grab_set()
        self._build()

    def _build(self):
        pad = {'padx': 20, 'pady': 6}
        ctk.CTkLabel(self, text=f"  {self._aliment['nom']}",
                     font=ctk.CTkFont(size=14, weight='bold'),
                     text_color=T['tx1']).grid(row=0, column=0, sticky='w', **pad)
        ctk.CTkLabel(self, text=self._aliment.get('categorie', ''),
                     font=ctk.CTkFont(size=11), text_color=T['tx2']).grid(
            row=1, column=0, sticky='w', padx=20, pady=(0, 8))

        row_qu = ctk.CTkFrame(self, fg_color='transparent')
        row_qu.grid(row=2, column=0, sticky='w', **pad)
        ctk.CTkLabel(row_qu, text='Quantite achetee *',
                     text_color=T['tx2'], width=140).grid(row=0, column=0, sticky='w')
        ctk.CTkLabel(row_qu, text='Unite',
                     text_color=T['tx2'], width=60).grid(row=0, column=1, sticky='w', padx=(16, 0))

        self._qty_var = ctk.StringVar()
        ctk.CTkEntry(row_qu, textvariable=self._qty_var, width=110,
                     fg_color=T['bg_el'], border_color=T['bg_hl']).grid(row=1, column=0)

        default_unite = self._aliment.get('unite', 'g')
        if default_unite not in UNITES_STOCK:
            default_unite = 'g'
        self._unite_var = ctk.StringVar(value=default_unite)
        ctk.CTkOptionMenu(row_qu, variable=self._unite_var,
                          values=UNITES_STOCK, width=80,
                          fg_color=T['bg_el'], button_color=T['bg_hl']).grid(
            row=1, column=1, padx=(16, 0))

        ctk.CTkLabel(self, text='DLC JJ/MM/AAAA - optionnel',
                     text_color=T['tx2'], font=ctk.CTkFont(size=11)).grid(
            row=3, column=0, sticky='w', **pad)
        self._dlc_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self._dlc_var, width=160,
                     placeholder_text='ex: 10/06/2026',
                     fg_color=T['bg_el'], border_color=T['bg_hl']).grid(
            row=4, column=0, sticky='w', padx=20)

        self._staple_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text='Produit de premiere necessite (staple)',
                        variable=self._staple_var,
                        fg_color=T['ac'], hover_color=T['ac_d'],
                        text_color=T['tx1'],
                        command=self._toggle_staple).grid(
            row=5, column=0, sticky='w', padx=20, pady=(10, 4))

        self._cible_frame = ctk.CTkFrame(self, fg_color='transparent')
        ctk.CTkLabel(self._cible_frame, text='Quantite cible :',
                     text_color=T['tx2'], font=ctk.CTkFont(size=11)).pack(side='left')
        self._cible_var = ctk.StringVar()
        ctk.CTkEntry(self._cible_frame, textvariable=self._cible_var, width=80,
                     fg_color=T['bg_el'], border_color=T['bg_hl']).pack(side='left', padx=8)

        bf = ctk.CTkFrame(self, fg_color='transparent')
        bf.grid(row=7, column=0, pady=14)
        ctk.CTkButton(bf, text='Ajouter au stock',
                      fg_color=T['ac'], hover_color=T['ac_d'],
                      text_color='#000', width=150, height=36,
                      command=self._save).grid(row=0, column=0, padx=8)
        ctk.CTkButton(bf, text='Annuler',
                      fg_color=T['bg_el'], hover_color=T['bg_hl'],
                      width=100, height=36,
                      command=self.destroy).grid(row=0, column=1, padx=8)

    def _toggle_staple(self):
        if self._staple_var.get():
            self._cible_frame.grid(row=6, column=0, sticky='w', padx=20, pady=2)
        else:
            self._cible_frame.grid_forget()

    def _save(self):
        try:
            qty = float(self._qty_var.get().replace(',', '.'))
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning('Quantite invalide',
                                   'Entrez une quantite positive.', parent=self)
            return
        dlc_str = self._dlc_var.get().strip()
        dlc_iso = None
        if dlc_str:
            try:
                dlc_iso = datetime.strptime(dlc_str, '%d/%m/%Y').date().isoformat()
            except ValueError:
                messagebox.showwarning('Date invalide',
                                       'Format attendu : JJ/MM/AAAA', parent=self)
                return

        db.add_to_stock_from_aliment(self._aliment['id'], qty, self._unite_var.get())

        if dlc_iso or self._staple_var.get():
            stock = db.get_stock()
            item = next((s for s in stock if s['aliment_id'] == self._aliment['id']), None)
            if item:
                try:
                    cible = float(self._cible_var.get().replace(',', '.') or 0)
                except ValueError:
                    cible = 0.0
                conn = db.get_connection()
                conn.execute("""UPDATE stock SET date_peremption=?,
                                est_staple=?, quantite_cible=? WHERE id=?""",
                             (dlc_iso, 1 if self._staple_var.get() else 0,
                              cible, item['id']))
                conn.commit()
                conn.close()

        if self._on_save:
            self._on_save()
        self.destroy()
