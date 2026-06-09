# Gestion de stock des aliments — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un garde-manger intelligent (stock per-user) qui indique quelles recettes sont faisables avec les ingrédients disponibles et propose une déduction semi-auto après cuisson.

**Architecture:** Table `stock` per-user référençant `aliments`. Page dédiée `📦 Stock` dans la sidebar. Badges de faisabilité sur les cartes recettes + tri dans le planning. Carte d'alertes péremption conditionnelle sur le dashboard.

**Tech Stack:** Python 3.9+, CustomTkinter, SQLite (database.py), même pattern que les pages existantes (pages/*.py).

---

## File Map

| Fichier | Action | Rôle |
|---|---|---|
| `database.py` | Modifier | Table stock + 6 fonctions métier |
| `pages/stock.py` | Créer | Page Stock + StockDialog |
| `main.py` | Modifier | Import + nav item + instanciation |
| `pages/recettes.py` | Modifier | Badges faisabilité + filtre |
| `pages/planning.py` | Modifier | Tri faisable + DeductionStockDialog |
| `pages/dashboard.py` | Modifier | Carte alertes péremption |

---

## Task 1 — DB : table stock + CRUD

**Files:**
- Modify: `database.py` (ligne 218, dans `_migrate()` et section STOCK nouvelle)

### Étape 1.1 — Ajouter l'import `timedelta` en haut du fichier

La ligne 7 de `database.py` est :
```python
from datetime import datetime, date
```
Remplacer par :
```python
from datetime import datetime, date, timedelta
```

- [ ] Modifier `database.py` ligne 7 pour ajouter `timedelta`

### Étape 1.2 — Ajouter la table `stock` dans `_migrate()`

Insérer le bloc suivant dans `_migrate()`, juste avant `conn.commit()` (ligne 218) :

```python
    # ── stock ─────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS stock (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id          INTEGER NOT NULL,
        aliment_id       INTEGER REFERENCES aliments(id),
        quantite         REAL    DEFAULT 0,
        unite            TEXT    DEFAULT 'g',
        date_peremption  TEXT    NULL,
        notes            TEXT    DEFAULT '',
        updated_at       TEXT    DEFAULT ''
    )""")
```

- [ ] Insérer le bloc `CREATE TABLE IF NOT EXISTS stock` avant `conn.commit()` dans `_migrate()`

### Étape 1.3 — Ajouter les fonctions CRUD stock dans `database.py`

Insérer un nouveau bloc après la section `# ─── RECETTES ───` (après la fonction `delete_recette`), avant `# ─── PROGRAMMES ───`. Voici le code exact :

```python
# ─────────────────────────── STOCK ───────────────────────────────────────────

def get_stock(user_id: int) -> list:
    """Retourne tout le stock de l'utilisateur avec nom et catégorie de l'aliment."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.*, a.nom, a.categorie, a.unite as unite_aliment
        FROM stock s
        JOIN aliments a ON s.aliment_id = a.id
        WHERE s.user_id = ?
        ORDER BY a.categorie, a.nom
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_stock(user_id: int, aliment_id: int, quantite: float,
                 unite: str = 'g', date_peremption: str = None,
                 notes: str = '') -> None:
    """Insert ou update l'entrée stock pour cet aliment/utilisateur."""
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM stock WHERE user_id=? AND aliment_id=?",
        (user_id, aliment_id)
    ).fetchone()
    now = datetime.now().isoformat()
    if existing:
        conn.execute("""UPDATE stock SET quantite=?, unite=?, date_peremption=?,
                        notes=?, updated_at=? WHERE id=?""",
                     (quantite, unite, date_peremption, notes, now, existing[0]))
    else:
        conn.execute("""INSERT INTO stock
            (user_id, aliment_id, quantite, unite, date_peremption, notes, updated_at)
            VALUES (?,?,?,?,?,?,?)""",
                     (user_id, aliment_id, quantite, unite, date_peremption, notes, now))
    conn.commit()
    conn.close()


def delete_stock(user_id: int, stock_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM stock WHERE id=? AND user_id=?", (stock_id, user_id))
    conn.commit()
    conn.close()
```

- [ ] Insérer le bloc `# ── STOCK ──` avec `get_stock`, `upsert_stock`, `delete_stock` dans `database.py`

### Étape 1.4 — Vérification manuelle

```bash
python -c "import database; database.init_db(); print('OK stock table'); conn = database.get_connection(); print(conn.execute('PRAGMA table_info(stock)').fetchall()); conn.close()"
```

Résultat attendu : liste des colonnes de la table `stock` (id, user_id, aliment_id, quantite, unite, date_peremption, notes, updated_at).

- [ ] Vérifier que la table `stock` est créée sans erreur

### Étape 1.5 — Commit

```
git add database.py
git commit -m "feat(stock): add stock table + CRUD functions (get/upsert/delete)"
```

- [ ] Commit Task 1

---

## Task 2 — DB : fonctions métier stock

**Files:**
- Modify: `database.py` (ajouter 3 fonctions dans le bloc `# ── STOCK ──`)

### Étape 2.1 — Ajouter `deduct_stock`

Ajouter après `delete_stock` dans le bloc STOCK :

```python
def deduct_stock(user_id: int, ingredients: list) -> None:
    """
    Déduit du stock une liste [{aliment_id, quantite_g}].
    Plancher à 0 ; supprime les entrées arrivant à 0.
    """
    conn = get_connection()
    for ing in ingredients:
        aid = ing['aliment_id']
        qte_deduire_g = float(ing.get('quantite_g', 0))
        row = conn.execute(
            "SELECT id, quantite, unite FROM stock WHERE user_id=? AND aliment_id=?",
            (user_id, aid)
        ).fetchone()
        if not row:
            continue
        alim = conn.execute("SELECT * FROM aliments WHERE id=?", (aid,)).fetchone()
        alim_dict = dict(alim) if alim else {}
        stock_g = quantite_en_grammes(row['quantite'], row['unite'], alim_dict)
        new_g = max(0.0, stock_g - qte_deduire_g)
        if new_g == 0:
            conn.execute("DELETE FROM stock WHERE id=?", (row['id'],))
        else:
            coeff = UNITS_CONVERSION.get(row['unite'])
            if coeff and coeff > 0:
                new_qty = new_g / coeff
            else:
                poids = float(alim_dict.get('poids_unite_g') or 0)
                new_qty = (new_g / poids) if poids > 0 else new_g
            conn.execute("UPDATE stock SET quantite=?, updated_at=? WHERE id=?",
                         (round(new_qty, 2), datetime.now().isoformat(), row['id']))
    conn.commit()
    conn.close()
```

- [ ] Ajouter `deduct_stock` dans le bloc STOCK de `database.py`

### Étape 2.2 — Ajouter `get_stock_alerts`

```python
def get_stock_alerts(user_id: int, jours: int = 3) -> list:
    """Items périmés ou expirant dans <= jours jours."""
    cutoff = (date.today() + timedelta(days=jours)).isoformat()
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.*, a.nom, a.categorie
        FROM stock s
        JOIN aliments a ON s.aliment_id = a.id
        WHERE s.user_id = ?
          AND s.date_peremption IS NOT NULL
          AND s.date_peremption != ''
          AND s.date_peremption <= ?
        ORDER BY s.date_peremption
    """, (user_id, cutoff)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

- [ ] Ajouter `get_stock_alerts` dans le bloc STOCK de `database.py`

### Étape 2.3 — Ajouter `check_recette_faisable`

```python
def check_recette_faisable(recette_id: int, user_id: int) -> dict:
    """
    Retourne {faisable: bool, manquants: [{nom, qte_requise, qte_stock, unite}]}
    Ignore les ingrédients non comparables (poids_unite_g=0 pour unité).
    """
    ings = get_recette_ingredients(recette_id)
    if not ings:
        return {'faisable': True, 'manquants': []}

    conn = get_connection()
    stock_rows = conn.execute(
        "SELECT aliment_id, quantite, unite FROM stock WHERE user_id=?",
        (user_id,)
    ).fetchall()
    conn.close()
    stock_by_alim = {r['aliment_id']: dict(r) for r in stock_rows}

    manquants = []
    for ing in ings:
        alim_id = ing['aliment_id']
        alim = get_aliment_by_id(alim_id) or {}
        qte_requise_g = quantite_en_grammes(
            ing['quantite'], ing.get('unite_recette', 'g'), alim)

        if alim_id in stock_by_alim:
            s = stock_by_alim[alim_id]
            coeff = UNITS_CONVERSION.get(s['unite'])
            if coeff is not None:
                stock_g = s['quantite'] * coeff
            else:
                poids = float(alim.get('poids_unite_g') or 0)
                if poids == 0:
                    continue  # unité incomparable → ignorée
                stock_g = s['quantite'] * poids

            if stock_g < qte_requise_g - 0.5:  # tolérance 0.5g
                manquants.append({
                    'nom':          ing.get('nom', alim.get('nom', '?')),
                    'qte_requise':  round(qte_requise_g, 0),
                    'qte_stock':    round(stock_g, 0),
                    'unite':        'g',
                })
        else:
            manquants.append({
                'nom':          ing.get('nom', alim.get('nom', '?')),
                'qte_requise':  round(qte_requise_g, 0),
                'qte_stock':    0,
                'unite':        'g',
            })

    return {'faisable': len(manquants) == 0, 'manquants': manquants}
```

- [ ] Ajouter `check_recette_faisable` dans le bloc STOCK de `database.py`

### Étape 2.4 — Vérification manuelle

```python
python -c "
import database
database.init_db()
uid = 1
# Test upsert
database.upsert_stock(uid, 1, 500, 'g', None, 'test')
stock = database.get_stock(uid)
print('Stock items:', len(stock), stock[0]['nom'] if stock else 'empty')
# Test alerts (aucune alerte car pas de DLC)
alerts = database.get_stock_alerts(uid)
print('Alerts:', len(alerts))
# Test faisabilite recette 1
result = database.check_recette_faisable(1, uid)
print('Faisable recette 1:', result['faisable'], 'manquants:', len(result['manquants']))
# Cleanup
if stock: database.delete_stock(uid, stock[0]['id'])
print('DONE')
"
```

Résultat attendu : `Stock items: 1`, `Alerts: 0`, les manquants correspondent aux ingrédients de la recette 1 absents du stock.

- [ ] Vérifier les 3 nouvelles fonctions DB

### Étape 2.5 — Commit

```
git add database.py
git commit -m "feat(stock): add deduct_stock, get_stock_alerts, check_recette_faisable"
```

- [ ] Commit Task 2

---

## Task 3 — Page Stock (pages/stock.py)

**Files:**
- Create: `pages/stock.py`

### Étape 3.1 — Créer `pages/stock.py`

Créer le fichier complet :

```python
"""NutriTrack Pro — Gestion de stock des aliments."""
import sys, os
import customtkinter as ctk
from tkinter import messagebox
from datetime import date, timedelta, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import database as db
from theme import T
from logger import get_logger

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


class StockPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=T['bg_app'], corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._uid = None
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
                     text='Gérez vos stocks d\'aliments et découvrez quelles recettes vous pouvez cuisiner',
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
        # Affichée dynamiquement dans refresh()

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

    # ── Refresh ─────────────────────────────────────────────────

    def refresh(self):
        self._uid = db.get_current_user_id()
        if not self._uid:
            return
        self._stock = db.get_stock(self._uid)
        self._alerts = db.get_stock_alerts(self._uid)
        self._update_alerts()
        self._update_cat_menu()
        self._refresh_list()

    def _update_alerts(self):
        self._alert_frame.grid_forget()
        for w in self._alert_frame.winfo_children():
            w.destroy()
        if not self._alerts:
            return

        ctk.CTkLabel(self._alert_frame,
                     text='⚠️  Alertes péremption',
                     font=ctk.CTkFont(size=13, weight='bold'),
                     text_color=T['cal']).grid(
            row=0, column=0, sticky='w', padx=14, pady=(10, 4))

        today = date.today().isoformat()
        for i, item in enumerate(self._alerts, start=1):
            dlc = item.get('date_peremption', '')
            if dlc < today:
                txt = f"🔴  {item['nom']} — périmé (DLC : {dlc})"
                color = T['err']
            else:
                txt = f"🟡  {item['nom']} — expire le {dlc}"
                color = T['cal']
            ctk.CTkLabel(self._alert_frame, text=txt,
                         text_color=color,
                         font=ctk.CTkFont(size=12)).grid(
                row=i, column=0, sticky='w', padx=14, pady=2)

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

        today = date.today().isoformat()
        cutoff = (date.today() + timedelta(days=3)).isoformat()
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

            # Boutons action
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
        StockDialog(self, uid=self._uid, on_save=self.refresh)

    def _open_edit(self, item):
        StockDialog(self, uid=self._uid, item=item, on_save=self.refresh)

    def _delete_item(self, item):
        if messagebox.askyesno('Supprimer',
                               f"Retirer « {item['nom']} » du stock ?", parent=self):
            db.delete_stock(self._uid, item['id'])
            self.refresh()


# ── Dialog ajout / édition ──────────────────────────────────────

class StockDialog(ctk.CTkToplevel):
    def __init__(self, parent, uid: int, item: dict = None, on_save=None):
        super().__init__(parent)
        self._uid = uid
        self._item = item
        self._on_save = on_save
        self._aliment_id = item['aliment_id'] if item else None
        self._alim_btns = []

        self.title('Modifier le stock' if item else 'Ajouter au stock')
        self.geometry('440x400')
        self.resizable(False, False)
        self.configure(fg_color=T['bg_app'])
        self.grab_set()
        self._build()
        if item:
            self._prefill(item)

    def _build(self):
        pad = {'padx': 20, 'pady': 5}

        # Aliment
        ctk.CTkLabel(self, text='Aliment *', text_color=T['tx2'],
                     font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, sticky='w', **pad)

        self._search_var = ctk.StringVar()
        self._search_var.trace_add('write', self._on_search)
        ctk.CTkEntry(self, textvariable=self._search_var,
                     placeholder_text='Rechercher un aliment…',
                     width=380, fg_color=T['bg_el'],
                     border_color=T['bg_hl']).grid(row=1, column=0, **pad)

        self._results_frame = ctk.CTkFrame(self, fg_color=T['bg_el'],
                                            corner_radius=6)
        # shown dynamically at row 2

        self._selected_lbl = ctk.CTkLabel(self, text='',
                                           text_color=T['ac'],
                                           font=ctk.CTkFont(size=12))
        self._selected_lbl.grid(row=3, column=0, sticky='w', padx=20)

        # Quantité + Unité
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

        # DLC
        ctk.CTkLabel(self, text='Date péremption JJ/MM/AAAA — optionnel',
                     text_color=T['tx2'], font=ctk.CTkFont(size=11)).grid(
            row=5, column=0, sticky='w', **pad)
        self._dlc_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self._dlc_var, width=180,
                     placeholder_text='ex: 10/06/2026',
                     fg_color=T['bg_el'], border_color=T['bg_hl']).grid(
            row=6, column=0, sticky='w', padx=20)

        # Notes
        ctk.CTkLabel(self, text='Notes — optionnel',
                     text_color=T['tx2'], font=ctk.CTkFont(size=11)).grid(
            row=7, column=0, sticky='w', **pad)
        self._notes_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self._notes_var, width=380,
                     fg_color=T['bg_el'], border_color=T['bg_hl']).grid(
            row=8, column=0, padx=20)

        # Boutons
        bf = ctk.CTkFrame(self, fg_color='transparent')
        bf.grid(row=9, column=0, pady=16)
        ctk.CTkButton(bf, text='Enregistrer',
                      fg_color=T['ac'], hover_color=T['ac_d'],
                      text_color='#000', width=130, height=36,
                      command=self._save).grid(row=0, column=0, padx=8)
        ctk.CTkButton(bf, text='Annuler',
                      fg_color=T['bg_el'], hover_color=T['bg_hl'],
                      width=110, height=36,
                      command=self.destroy).grid(row=0, column=1, padx=8)

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

        db.upsert_stock(self._uid, self._aliment_id, qty,
                        self._unite_var.get(), dlc_iso,
                        self._notes_var.get().strip())
        if self._on_save:
            self._on_save()
        self.destroy()
```

- [ ] Créer `pages/stock.py` avec le contenu ci-dessus

### Étape 3.2 — Commit

```
git add pages/stock.py
git commit -m "feat(stock): add StockPage and StockDialog"
```

- [ ] Commit Task 3

---

## Task 4 — Intégration sidebar (main.py)

**Files:**
- Modify: `main.py`

### Étape 4.1 — Ajouter l'import

En haut de `main.py`, après la ligne `from pages.aliments import AlimentsPage`, ajouter :

```python
from pages.stock     import StockPage
```

- [ ] Ajouter `from pages.stock import StockPage` dans les imports de `main.py`

### Étape 4.2 — Ajouter l'entrée nav

Dans `NAV_ITEMS` (autour de la ligne 27), insérer `("stock", "📦", "Stock")` entre `aliments` et `recettes` :

```python
NAV_ITEMS = [
    ("dashboard",   "🏠",  "Tableau de bord"),
    ("journal",     "📓",  "Journal"),
    ("stats",       "📊",  "Statistiques"),
    ("profil",      "👤",  "Mon Profil"),
    ("aliments",    "🥑",  "Aliments"),
    ("stock",       "📦",  "Stock"),
    ("recettes",    "👨‍🍳", "Recettes"),
    ("planning",    "📅",  "Planning repas"),
    ("programmes",  "📋",  "Programmes"),
    ("sport",       "🏃",  "Sport"),
]
```

- [ ] Insérer `("stock", "📦", "Stock")` dans `NAV_ITEMS`

### Étape 4.3 — Instancier la page

Dans la méthode `__init__` de `NutriTrackApp`, là où les pages sont créées (autour des lignes 165-173), ajouter après `self._pages["aliments"]` :

```python
        self._pages["stock"]      = StockPage(self.content)
```

- [ ] Ajouter `self._pages["stock"] = StockPage(self.content)` dans `__init__`

### Étape 4.4 — Vérification manuelle

Lancer l'app : `python main.py`  
Vérifier que :
- L'entrée `📦 Stock` apparaît dans la sidebar entre Aliments et Recettes
- Le clic ouvre une page vide avec le bouton `＋ Ajouter`
- `StockDialog` s'ouvre, la recherche d'aliment fonctionne, l'enregistrement ajoute une ligne

- [ ] Lancer l'app et vérifier la page Stock

### Étape 4.5 — Commit

```
git add main.py
git commit -m "feat(stock): add stock page to sidebar navigation"
```

- [ ] Commit Task 4

---

## Task 5 — Badges faisabilité dans Recettes (pages/recettes.py)

**Files:**
- Modify: `pages/recettes.py`

### Étape 5.1 — Ajouter le filtre "Faisables" dans `_build()`

Dans `_build()`, après le bouton `self._fav_btn` (environ ligne 78), ajouter un bouton toggle Faisables :

```python
        self._faisable_only = False
        self._faisable_btn = ctk.CTkButton(
            fbar, text="✅  Faisables",
            font=ctk.CTkFont(size=12),
            fg_color=T["bg_el"], hover_color=T["bg_hl"],
            text_color=T["ac"], height=36, width=120, corner_radius=8,
            command=self._toggle_faisable_filter)
        self._faisable_btn.pack(side="left", padx=(0, 10))
```

Et ajouter la méthode `_toggle_faisable_filter` après `_toggle_favori_filter` :

```python
    def _toggle_faisable_filter(self):
        self._faisable_only = not self._faisable_only
        if self._faisable_only:
            self._faisable_btn.configure(fg_color=T["ac_bg"],
                                          text_color=T["ac"])
        else:
            self._faisable_btn.configure(fg_color=T["bg_el"],
                                          text_color=T["ac"])
        self.refresh()
```

- [ ] Ajouter attribut `_faisable_only`, bouton toggle et méthode dans `pages/recettes.py`

### Étape 5.2 — Modifier `refresh()` pour filtrer les faisables

Dans `refresh()` (ligne 103), après `recettes = db.get_recettes(...)` :

```python
    def refresh(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        recettes = db.get_recettes(self.search_var.get(), favori_only=self._favori_only)

        # Calcul faisabilité si stock non vide
        uid = db.get_current_user_id()
        stock = db.get_stock(uid) if uid else []
        if stock:
            for r in recettes:
                r['_stock_result'] = db.check_recette_faisable(r['id'], uid)
        else:
            for r in recettes:
                r['_stock_result'] = None  # stock non géré

        if self._faisable_only and stock:
            recettes = [r for r in recettes if r['_stock_result'] and r['_stock_result']['faisable']]

        self.count_lbl.configure(text=f"{len(recettes)} recette(s)")
        if not recettes:
            ctk.CTkLabel(self.grid_frame,
                         text="Aucune recette\n\nCliquez sur « + Nouvelle recette » pour commencer",
                         text_color=T["tx2"], font=ctk.CTkFont(size=14),
                         justify="center").grid(row=0, column=0, columnspan=3, pady=60)
            return
        for i, r in enumerate(recettes):
            self._make_card(r, i//3, i%3)
```

- [ ] Remplacer le corps de `refresh()` par la version ci-dessus

### Étape 5.3 — Ajouter le badge dans `_make_card()`

Dans `_make_card()`, entre la section `meta` (row=5) et la section boutons `bf` (row=6), ajouter le badge stock (qui devient row=6, les boutons deviennent row=7) :

Remplacer le bloc `bf` existant :
```python
        # Boutons
        bf = ctk.CTkFrame(card, fg_color="transparent")
        bf.grid(row=6, column=0, padx=12, pady=(4,12), sticky="ew")
```

Par :
```python
        # Badge stock
        stock_result = r.get('_stock_result')
        if stock_result is None:
            badge_txt  = '— Stock non géré'
            badge_col  = T['tx3']
            badge_bg   = T['bg_el']
        elif stock_result['faisable']:
            badge_txt  = '✅  Faisable'
            badge_col  = T['ac']
            badge_bg   = T['ac_bg']
        else:
            n = len(stock_result['manquants'])
            badge_txt  = f"⚠️  {n} ingrédient(s) manquant(s)"
            badge_col  = T['cal']
            badge_bg   = T['bg_el']

        stock_badge = ctk.CTkLabel(card, text=badge_txt,
                                    font=ctk.CTkFont(size=11),
                                    text_color=badge_col,
                                    fg_color=badge_bg,
                                    corner_radius=6)
        stock_badge.grid(row=6, column=0, padx=14, pady=(2, 4), sticky='w')

        if stock_result and not stock_result['faisable']:
            manquants_txt = '\n'.join(
                f"  • {m['nom']} : {m['qte_stock']}g dispo / {m['qte_requise']}g requis"
                for m in stock_result['manquants']
            )
            stock_badge.bind('<Enter>', lambda e, t=manquants_txt: self._show_tooltip(e, t))
            stock_badge.bind('<Leave>', lambda e: self._hide_tooltip())

        # Boutons
        bf = ctk.CTkFrame(card, fg_color="transparent")
        bf.grid(row=7, column=0, padx=12, pady=(4,12), sticky="ew")
```

- [ ] Insérer le badge stock entre meta (row=5) et boutons (row=6→7) dans `_make_card()`

### Étape 5.4 — Ajouter les méthodes tooltip dans `RecettesPage`

Ajouter après `_confirm_delete` (vers la fin de la classe) :

```python
    def _show_tooltip(self, event, text: str):
        self._tooltip = ctk.CTkToplevel(self)
        self._tooltip.overrideredirect(True)
        self._tooltip.configure(fg_color=T['bg_card'])
        ctk.CTkLabel(self._tooltip, text=text,
                     font=ctk.CTkFont(size=11),
                     text_color=T['tx1'],
                     justify='left').pack(padx=10, pady=8)
        x = event.widget.winfo_rootx() + 10
        y = event.widget.winfo_rooty() + 24
        self._tooltip.geometry(f"+{x}+{y}")

    def _hide_tooltip(self):
        if hasattr(self, '_tooltip') and self._tooltip.winfo_exists():
            self._tooltip.destroy()
```

- [ ] Ajouter `_show_tooltip` et `_hide_tooltip` dans `RecettesPage`

### Étape 5.5 — Vérification manuelle

Lancer l'app. Aller dans Recettes.  
- Si stock vide : toutes les cartes affichent `— Stock non géré`
- Ajouter un aliment en stock, revenir sur Recettes : les cartes montrent ✅ ou ⚠️
- Hover sur ⚠️ : tooltip listant les manquants
- Toggle Faisables : masque les recettes avec manquants

- [ ] Vérifier badges + filtre + tooltip dans Recettes

### Étape 5.6 — Commit

```
git add pages/recettes.py
git commit -m "feat(stock): add feasibility badges and filter to Recettes page"
```

- [ ] Commit Task 5

---

## Task 6 — Intégration Planning (pages/planning.py)

**Files:**
- Modify: `pages/planning.py`

### Étape 6.1 — Tri par faisabilité dans `_load_recettes()`

Dans `AddRepasDialog._load_recettes()` (environ ligne 636), après `recettes = db.get_recettes(search)` et avant le tri, ajouter la faisabilité :

Remplacer le bloc tri existant :
```python
        # Trier : favoris en premier, puis catégories recommandées, puis nom
        hints = db.REPAS_CAT_HINTS.get(self.type_repas, [])
        recettes.sort(key=lambda r: (
            0 if r.get('favori') else 1,
            0 if r.get('categorie') in hints else 1,
            r['nom']))
```

Par :
```python
        # Faisabilité stock
        uid = db.get_current_user_id()
        stock = db.get_stock(uid) if uid else []
        if stock:
            for r in recettes:
                r['_faisable'] = db.check_recette_faisable(r['id'], uid)['faisable']
        else:
            for r in recettes:
                r['_faisable'] = None  # stock non géré

        # Trier : faisables > favoris > hints > nom
        hints = db.REPAS_CAT_HINTS.get(self.type_repas, [])
        recettes.sort(key=lambda r: (
            0 if r.get('_faisable') else 1,
            0 if r.get('favori') else 1,
            0 if r.get('categorie') in hints else 1,
            r['nom']))
```

- [ ] Remplacer le bloc tri dans `_load_recettes()` par la version avec faisabilité

### Étape 6.2 — Afficher le badge faisable dans la liste

Dans `_load_recettes()`, remplacer le `prefix` existant :
```python
            prefix = "⭐ " if is_fav else ("💡 " if is_hint else "")
```

Par :
```python
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
```

- [ ] Remplacer le `prefix` dans `_load_recettes()` par la version avec badges stock

### Étape 6.3 — Ajouter le bouton "Cuisiner" sur les slots avec recette

Dans la méthode qui rend les slots de repas (autour de la ligne 401, bloc `if repas:`), après le bouton `✕`, ajouter le bouton Cuisiner si le repas a un `recette_id` :

Remplacer le bloc `if repas:` (lignes 383-405) par :

```python
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

                btn_col = 1
                ctk.CTkButton(info, text="✕", width=24, height=24,
                              fg_color="transparent", hover_color=T["err_bg"],
                              text_color=T["err"],
                              command=lambda pid=repas['id']: self._suppr_repas(pid, jour_str)).grid(
                    row=0, column=btn_col, rowspan=2, padx=4)

                if repas.get('recette_id'):
                    ctk.CTkButton(info, text="🍳", width=24, height=24,
                                  fg_color="transparent", hover_color=T["ac_bg"],
                                  text_color=T["ac"],
                                  command=lambda r=repas: self._open_deduction(r)).grid(
                        row=0, column=btn_col + 1, rowspan=2, padx=2)
```

- [ ] Ajouter bouton `🍳` sur les slots avec `recette_id` dans la grille Planning

### Étape 6.4 — Ajouter `_open_deduction` dans la page Planning

Dans `PlanningPage` (pas dans `AddRepasDialog`), ajouter la méthode :

```python
    def _open_deduction(self, repas: dict):
        uid = db.get_current_user_id()
        if not uid:
            return
        DeductionStockDialog(self, uid=uid, repas=repas,
                             on_done=self.refresh)
```

- [ ] Ajouter `_open_deduction` dans `PlanningPage`

### Étape 6.5 — Créer `DeductionStockDialog` dans `pages/planning.py`

Ajouter la classe en bas du fichier, avant la fin :

```python
class DeductionStockDialog(ctk.CTkToplevel):
    """Dialog semi-auto : confirme la déduction du stock après cuisson d'une recette."""

    def __init__(self, parent, uid: int, repas: dict, on_done=None):
        super().__init__(parent)
        self._uid = uid
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

        ctk.CTkLabel(self, text="🍳  Recette cuisinée — déduire du stock ?",
                     font=ctk.CTkFont(size=15, weight='bold'),
                     text_color=T['tx1']).pack(pady=(20, 4), padx=20, anchor='w')
        ctk.CTkLabel(self, text=f"{nom}  ×{portions} portion(s)",
                     font=ctk.CTkFont(size=12), text_color=T['tx2']).pack(
            padx=20, anchor='w', pady=(0, 10))

        # Liste ingrédients avec statut stock
        scroll = ctk.CTkScrollableFrame(self, fg_color=T['bg_card'],
                                         corner_radius=8, height=260)
        scroll.pack(fill='both', expand=True, padx=20, pady=(0, 10))
        scroll.grid_columnconfigure(0, weight=1)

        ings = db.get_recette_ingredients(recette_id) if recette_id else []
        stock_rows = db.get_stock(self._uid)
        stock_by_alim = {s['aliment_id']: s for s in stock_rows}

        self._deductions = []  # [{aliment_id, quantite_g}]

        for i, ing in enumerate(ings):
            alim = db.get_aliment_by_id(ing['aliment_id']) or {}
            qte_g = db.quantite_en_grammes(
                ing['quantite'] * portions, ing.get('unite_recette', 'g'), alim)

            s = stock_by_alim.get(ing['aliment_id'])
            if s:
                coeff = db.UNITS_CONVERSION.get(s['unite'])
                if coeff is not None:
                    stock_g = s['quantite'] * coeff
                else:
                    poids = float(alim.get('poids_unite_g') or 0)
                    stock_g = s['quantite'] * poids if poids > 0 else 0
                reste_g = max(0.0, stock_g - qte_g)
                icon = "✅"
                detail = f"{stock_g:.0f}g → reste {reste_g:.0f}g"
                color = T['ac']
                self._deductions.append({'aliment_id': ing['aliment_id'],
                                          'quantite_g': qte_g})
            else:
                icon = "—"
                detail = "non géré dans le stock"
                color = T['tx3']

            row = ctk.CTkFrame(scroll, fg_color='transparent')
            row.grid(row=i, column=0, sticky='ew', pady=2)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=icon, width=24,
                         text_color=color).grid(row=0, column=0, padx=(8, 4))
            ctk.CTkLabel(row, text=ing.get('nom', alim.get('nom', '?')),
                         font=ctk.CTkFont(size=12), text_color=T['tx1'],
                         anchor='w').grid(row=0, column=1, sticky='w')
            ctk.CTkLabel(row, text=detail,
                         font=ctk.CTkFont(size=10), text_color=color,
                         anchor='e').grid(row=0, column=2, padx=8)

        # Boutons
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
        if self._deductions:
            db.deduct_stock(self._uid, self._deductions)
        if self._on_done:
            self._on_done()
        self.destroy()
```

- [ ] Ajouter `DeductionStockDialog` en bas de `pages/planning.py`

### Étape 6.6 — Vérification manuelle

Lancer l'app. Aller dans Planning.  
- Ajouter une recette (ex. Phở) à un jour de la semaine
- Vérifier que le bouton 🍳 apparaît sur le slot de repas
- Clic 🍳 : dialog de déduction s'ouvre avec la liste des ingrédients
- Clic "Déduire" : vérifier dans Stock que les quantités sont bien réduites

- [ ] Vérifier le bouton Cuisiner et le dialog de déduction

### Étape 6.7 — Commit

```
git add pages/planning.py
git commit -m "feat(stock): add feasibility sort and DeductionStockDialog to Planning"
```

- [ ] Commit Task 6

---

## Task 7 — Carte alertes péremption Dashboard (pages/dashboard.py)

**Files:**
- Modify: `pages/dashboard.py`

### Étape 7.1 — Ajouter `stock_row` dans `_build()`

Dans `_build()`, après le bloc `self.sport_row` (row=5) et avant `self.charts_row`, ajouter :

```python
        # ── Alertes stock ─────────────────────────────────────────
        self.stock_row = ctk.CTkFrame(self, fg_color="transparent")
        self.stock_row.grid(row=6, column=0, padx=28, pady=(0, 14), sticky="ew")
        self.stock_row.grid_columnconfigure(0, weight=1)
```

Et changer `self.charts_row` de `row=6` à `row=7` :

```python
        # ── Graphiques ─────────────────────────────────────────────
        self.charts_row = ctk.CTkFrame(self, fg_color="transparent")
        self.charts_row.grid(row=7, column=0, padx=28, pady=(0, 28), sticky="ew")
```

- [ ] Ajouter `self.stock_row` à `row=6` et déplacer `self.charts_row` à `row=7` dans `_build()`

### Étape 7.2 — Vider `stock_row` dans `refresh()`

Dans `refresh()`, dans le bloc de destruction des enfants (autour des lignes 79-90), ajouter :

```python
        for w in self.stock_row.winfo_children():
            w.destroy()
```

- [ ] Ajouter `for w in self.stock_row.winfo_children(): w.destroy()` dans `refresh()`

### Étape 7.3 — Appeler `_draw_stock_alerts_card` dans `refresh()`

À la fin de `refresh()`, après l'appel `self._draw_sport_card(...)`, ajouter :

```python
        self._draw_stock_alerts_card()
```

- [ ] Ajouter l'appel `self._draw_stock_alerts_card()` à la fin de `refresh()`

### Étape 7.4 — Implémenter `_draw_stock_alerts_card()`

Ajouter la méthode dans `DashboardPage`, après `_draw_sport_card` :

```python
    def _draw_stock_alerts_card(self):
        uid = db.get_current_user_id()
        if not uid:
            return
        alerts = db.get_stock_alerts(uid, jours=3)
        if not alerts:
            return

        card = ctk.CTkFrame(self.stock_row, fg_color=T["bg_card"], corner_radius=12)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card,
                     text="📦  Stock — Alertes péremption",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T["cal"]).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 6))

        today = date.today().isoformat()
        for i, item in enumerate(alerts[:5]):
            dlc = item.get('date_peremption', '')
            if dlc < today:
                txt = f"🔴  {item['nom']} — périmé"
                col = T["err"]
            else:
                txt = f"🟡  {item['nom']} — expire le {dlc}"
                col = T["cal"]
            ctk.CTkLabel(card, text=txt, text_color=col,
                         font=ctk.CTkFont(size=12)).grid(
                row=i + 1, column=0, sticky="w", padx=16, pady=2)

        ctk.CTkButton(card, text="Voir le stock →",
                      fg_color="transparent", hover_color=T["bg_el"],
                      text_color=T["ac"], anchor="e",
                      font=ctk.CTkFont(size=12),
                      command=lambda: self.winfo_toplevel()._show_page("stock")).grid(
            row=len(alerts[:5]) + 1, column=0, sticky="e", padx=16, pady=(4, 12))
```

- [ ] Ajouter `_draw_stock_alerts_card` dans `DashboardPage`

### Étape 7.5 — Ajouter l'import `date` dans `pages/dashboard.py`

Vérifier que `from datetime import date` est présent. Si non, l'ajouter dans les imports du fichier.

- [ ] Vérifier/ajouter `from datetime import date` dans `pages/dashboard.py`

### Étape 7.6 — Vérification manuelle

Lancer l'app.  
- Dashboard sans alertes stock : carte absente (pas de bruit)
- Ajouter un aliment en stock avec DLC = date d'aujourd'hui ou demain
- Revenir sur le Dashboard : carte alertes doit apparaître avec 🟡 ou 🔴
- Clic "Voir le stock →" : navigation vers la page Stock

- [ ] Vérifier la carte alertes péremption sur le Dashboard

### Étape 7.7 — Commit

```
git add pages/dashboard.py
git commit -m "feat(stock): add stock alerts card to dashboard"
```

- [ ] Commit Task 7

---

## Vérification finale

- [ ] Lancer `python main.py` sans erreur
- [ ] Parcourir le flux complet : Stock → ajouter aliments → Recettes (badges) → Planning (tri + cuisiner) → Dashboard (alertes)
- [ ] Vérifier que `python launch.py` passe la vérification des dépendances sans erreur
