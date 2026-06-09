# Stock v2 — Cycle complet garde-manger — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connecter le stock à tous les points de saisie de l'app (scan, aliments, journal, hydratation), ajouter seuils d'alerte, gestion des staples et liste de courses intégrée.

**Architecture:** Extension de la table `stock` existante (5 colonnes), modification de `deduct_stock()` pour retourner les items sous seuil, nouveau widget `AddToStockDialog` partagé entre 3 points d'entrée, helper toast non-bloquant. Toutes les fonctions DB restent scopées sur `_current_user_id`.

**Tech Stack:** Python 3.9+, CustomTkinter, SQLite, même patterns que stock v1 (pages/*.py, database.py).

---

## File Map

| Fichier | Action | Rôle |
|---|---|---|
| `database.py` | Modifier | 5 colonnes, 8 nouvelles fonctions, modifier deduct_stock |
| `pages/stock.py` | Modifier | AddToStockDialog, toast, StockDialog champs, shopping list, alertes étendues |
| `pages/aliments.py` | Modifier | Bouton 📦 par ligne |
| `barcode_scanner.py` | Modifier | Bouton stock post-scan dans ProductFoundDialog |
| `pages/journal.py` | Modifier | Checkbox déduction + section add-to-stock + hydration |
| `pages/planning.py` | Modifier | Toast après déduction dans DeductionStockDialog |
| `pages/dashboard.py` | Modifier | Alertes stock faible dans _draw_stock_alerts_card |

---

## Task 1 — DB : colonnes + fonctions

**Files:** Modify `database.py`

### Étape 1.1 — 5 colonnes dans `_migrate()`

Après le bloc `try: conn.execute("ALTER TABLE activites_sport ADD COLUMN fc_observee...")` (vers ligne 177), ajouter :

```python
    # ── stock v2 : seuils, staples, fréquence, eau ────────────────
    for col, typedef in [
        ("quantite_min",    "REAL DEFAULT 0"),
        ("est_staple",      "INTEGER DEFAULT 0"),
        ("quantite_cible",  "REAL DEFAULT 0"),
        ("nb_utilisations", "INTEGER DEFAULT 0"),
        ("est_eau",         "INTEGER DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE stock ADD COLUMN {col} {typedef}")
        except Exception:
            pass
```

- [ ] Insérer le bloc 5 colonnes dans `_migrate()`

### Étape 1.2 — Modifier `deduct_stock()` pour retourner les items sous seuil

Remplacer la fonction existante `deduct_stock` (dans le bloc `# ── STOCK ──`) par :

```python
def deduct_stock(ingredients: list) -> list:
    """
    Déduit du stock courant une liste [{aliment_id, quantite_g}].
    Plancher à 0 ; supprime les entrées à 0.
    Retourne la liste des items passés sous quantite_min :
    [{nom, quantite, quantite_min, unite}]
    """
    sous_seuil = []
    conn = get_connection()
    for ing in ingredients:
        aid = ing['aliment_id']
        qte_deduire_g = float(ing.get('quantite_g', 0))
        row = conn.execute(
            "SELECT * FROM stock WHERE user_id=? AND aliment_id=?",
            (_current_user_id, aid)
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
            new_qty = round(new_qty, 2)
            conn.execute("UPDATE stock SET quantite=?, updated_at=? WHERE id=?",
                         (new_qty, datetime.now().isoformat(), row['id']))
            # Vérifier seuil minimum
            qmin = float(row['quantite_min'] or 0)
            if qmin > 0 and new_qty < qmin:
                sous_seuil.append({
                    'nom':          alim_dict.get('nom', '?'),
                    'quantite':     new_qty,
                    'quantite_min': qmin,
                    'unite':        row['unite'],
                })
    conn.commit()
    conn.close()
    return sous_seuil
```

- [ ] Remplacer `deduct_stock` par la version qui retourne `list`

### Étape 1.3 — Ajouter `add_to_stock_from_aliment()`

Après `delete_stock`, ajouter :

```python
def add_to_stock_from_aliment(aliment_id: int, quantite: float,
                               unite: str = None) -> None:
    """
    Ajoute (additionne) une quantité au stock de l'aliment courant.
    Applique smart defaults (quantite_min) si c'est un nouvel item.
    Incrémente nb_utilisations.
    """
    alim = get_aliment_by_id(aliment_id) or {}
    if unite is None:
        unite = alim.get('unite', 'g')
        if unite not in ('g', 'ml', 'kg', 'L', 'unité'):
            unite = 'g'
    conn = get_connection()
    existing = conn.execute(
        "SELECT id, quantite FROM stock WHERE user_id=? AND aliment_id=?",
        (_current_user_id, aliment_id)
    ).fetchone()
    now = datetime.now().isoformat()
    if existing:
        conn.execute("""UPDATE stock SET quantite=quantite+?, nb_utilisations=nb_utilisations+1,
                        updated_at=? WHERE id=?""",
                     (quantite, now, existing[0]))
    else:
        # Smart defaults pour nouvel item
        cat = alim.get('categorie', '').lower()
        if unite == 'unité':
            qmin = 1.0
        elif any(k in cat for k in ('epices', 'épices', 'herbes')):
            qmin = round(quantite * 0.10, 1)
        else:
            qmin = 0.0
        conn.execute("""INSERT INTO stock
            (user_id, aliment_id, quantite, unite, quantite_min, nb_utilisations, updated_at)
            VALUES (?,?,?,?,?,1,?)""",
                     (_current_user_id, aliment_id, quantite, unite, qmin, now))
    conn.commit()
    conn.close()
```

- [ ] Ajouter `add_to_stock_from_aliment` dans le bloc STOCK

### Étape 1.4 — Ajouter `get_stock_sous_seuil()`

```python
def get_stock_sous_seuil() -> list:
    """Items où quantite < quantite_min (et quantite_min > 0)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.*, a.nom, a.categorie
        FROM stock s JOIN aliments a ON s.aliment_id = a.id
        WHERE s.user_id=? AND s.quantite_min > 0 AND s.quantite < s.quantite_min
        ORDER BY (s.quantite_min - s.quantite) DESC
    """, (_current_user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

- [ ] Ajouter `get_stock_sous_seuil`

### Étape 1.5 — Ajouter `get_staples_a_reapprovisionner()`

```python
def get_staples_a_reapprovisionner() -> list:
    """Staples dont la quantite < quantite_cible."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.*, a.nom, a.categorie
        FROM stock s JOIN aliments a ON s.aliment_id = a.id
        WHERE s.user_id=? AND s.est_staple=1 AND s.quantite_cible > 0
          AND s.quantite < s.quantite_cible
        ORDER BY a.categorie, a.nom
    """, (_current_user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

- [ ] Ajouter `get_staples_a_reapprovisionner`

### Étape 1.6 — Ajouter `get_liste_courses_stock()`

```python
def get_liste_courses_stock(nb_jours: int = 7) -> dict:
    """
    Retourne {staples, recettes, suggestions} pour la liste de courses.
    - staples  : [{nom, manque, quantite_cible, unite}]
    - recettes : [{nom, manque_g, nom_recette, date_repas}]
    - suggestions : [{nom, nb_utilisations, aliment_id}]
    """
    end_date = (date.today() + timedelta(days=nb_jours)).isoformat()
    today_str = date.today().isoformat()

    # Staples
    staples_raw = get_staples_a_reapprovisionner()
    staples = [{'nom': s['nom'],
                'manque': round(s['quantite_cible'] - s['quantite'], 1),
                'quantite_cible': s['quantite_cible'],
                'unite': s['unite']}
               for s in staples_raw]

    # Recettes planifiées manquantes
    conn = get_connection()
    planning = conn.execute("""
        SELECT pr.recette_id, pr.date, r.nom as recette_nom, pr.portions
        FROM planning_repas pr
        JOIN recettes r ON pr.recette_id = r.id
        WHERE pr.user_id=? AND pr.date >= ? AND pr.date <= ?
          AND pr.recette_id IS NOT NULL
        ORDER BY pr.date
    """, (_current_user_id, today_str, end_date)).fetchall()
    conn.close()

    recettes = []
    seen = set()
    for repas in planning:
        result = check_recette_faisable(repas['recette_id'])
        for m in result['manquants']:
            key = (m['nom'], repas['recette_id'])
            if key not in seen:
                seen.add(key)
                recettes.append({
                    'nom':         m['nom'],
                    'manque_g':    round(m['qte_requise'] - m['qte_stock'], 0),
                    'nom_recette': repas['recette_nom'],
                    'date_repas':  repas['date'],
                })

    # Suggestions (fréquemment utilisés, non staples)
    conn = get_connection()
    sugg_rows = conn.execute("""
        SELECT s.aliment_id, a.nom, s.nb_utilisations
        FROM stock s JOIN aliments a ON s.aliment_id = a.id
        WHERE s.user_id=? AND s.est_staple=0 AND s.nb_utilisations >= 3
        ORDER BY s.nb_utilisations DESC
        LIMIT 5
    """, (_current_user_id,)).fetchall()
    conn.close()
    suggestions = [dict(r) for r in sugg_rows]

    return {'staples': staples, 'recettes': recettes, 'suggestions': suggestions}
```

- [ ] Ajouter `get_liste_courses_stock`

### Étape 1.7 — Ajouter `get_stock_eau_aliment_id()` et `set_stock_eau()`

```python
def get_stock_eau_aliment_id() -> int | None:
    """Retourne l'aliment_id de l'item stock marqué est_eau=1, ou None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT aliment_id FROM stock WHERE user_id=? AND est_eau=1 LIMIT 1",
        (_current_user_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def set_stock_eau(stock_id: int) -> None:
    """Marque cet item comme source d'eau, remet à 0 les autres."""
    conn = get_connection()
    conn.execute("UPDATE stock SET est_eau=0 WHERE user_id=?", (_current_user_id,))
    conn.execute("UPDATE stock SET est_eau=1 WHERE id=? AND user_id=?",
                 (stock_id, _current_user_id))
    conn.commit()
    conn.close()
```

- [ ] Ajouter `get_stock_eau_aliment_id` et `set_stock_eau`

### Étape 1.8 — Ajouter `increment_stock_usage()`

```python
def increment_stock_usage(aliment_id: int) -> None:
    """Incrémente nb_utilisations pour l'aliment dans le stock du user courant."""
    conn = get_connection()
    conn.execute("""UPDATE stock SET nb_utilisations=nb_utilisations+1
                    WHERE user_id=? AND aliment_id=?""",
                 (_current_user_id, aliment_id))
    conn.commit()
    conn.close()
```

- [ ] Ajouter `increment_stock_usage`

### Étape 1.9 — Vérification

```
cd D:\DEV\Python\proteines\nutrition_app_v7 && python -c "
import database, inspect
database.init_db()
conn = database.get_connection()
cols = [r[1] for r in conn.execute('PRAGMA table_info(stock)').fetchall()]
conn.close()
print('cols:', cols)
fns = ['add_to_stock_from_aliment','get_stock_sous_seuil','get_staples_a_reapprovisionner',
       'get_liste_courses_stock','get_stock_eau_aliment_id','set_stock_eau','increment_stock_usage']
for f in fns: print(f, inspect.signature(getattr(database, f)))
sig = inspect.signature(database.deduct_stock)
print('deduct_stock returns list:', 'list' in str(inspect.signature(database.deduct_stock)))
"
```

Résultat attendu : 13 colonnes dans stock (dont quantite_min, est_staple, quantite_cible, nb_utilisations, est_eau), toutes les fonctions listées.

- [ ] Vérifier Task 1

---

## Task 2 — pages/stock.py : AddToStockDialog + toast + StockDialog champs + shopping list

**Files:** Modify `pages/stock.py`

### Étape 2.1 — Ajouter `AddToStockDialog` (utilisé par aliments, scanner, journal)

C'est un dialog léger : l'aliment est fourni (pas de recherche). Ajouter après `StockDialog` dans `pages/stock.py` :

```python
class AddToStockDialog(ctk.CTkToplevel):
    """
    Dialog rapide pour ajouter un aliment au stock depuis un contexte externe
    (page Aliments, scanner, journal). L'aliment est pré-rempli.
    """
    def __init__(self, parent, aliment: dict, on_save=None):
        super().__init__(parent)
        self._aliment = aliment
        self._on_save = on_save
        self.title('Ajouter au stock')
        self.geometry('380x320')
        self.resizable(False, False)
        self.configure(fg_color=T['bg_app'])
        self.grab_set()
        self._build()

    def _build(self):
        pad = {'padx': 20, 'pady': 6}
        ctk.CTkLabel(self, text=f"📦  {self._aliment['nom']}",
                     font=ctk.CTkFont(size=14, weight='bold'),
                     text_color=T['tx1']).grid(row=0, column=0, sticky='w', **pad)
        ctk.CTkLabel(self, text=self._aliment.get('categorie', ''),
                     font=ctk.CTkFont(size=11), text_color=T['tx2']).grid(
            row=1, column=0, sticky='w', padx=20, pady=(0, 8))

        row_qu = ctk.CTkFrame(self, fg_color='transparent')
        row_qu.grid(row=2, column=0, sticky='w', **pad)
        ctk.CTkLabel(row_qu, text='Quantité achetée *',
                     text_color=T['tx2'], width=130).grid(row=0, column=0, sticky='w')
        ctk.CTkLabel(row_qu, text='Unité',
                     text_color=T['tx2'], width=70).grid(row=0, column=1, sticky='w', padx=(16, 0))

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

        ctk.CTkLabel(self, text='DLC JJ/MM/AAAA — optionnel',
                     text_color=T['tx2'], font=ctk.CTkFont(size=11)).grid(
            row=3, column=0, sticky='w', **pad)
        self._dlc_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self._dlc_var, width=160,
                     placeholder_text='ex: 10/06/2026',
                     fg_color=T['bg_el'], border_color=T['bg_hl']).grid(
            row=4, column=0, sticky='w', padx=20)

        self._staple_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text='Produit de première nécessité (staple)',
                        variable=self._staple_var,
                        fg_color=T['ac'], hover_color=T['ac_d'],
                        text_color=T['tx1'],
                        command=self._toggle_staple).grid(
            row=5, column=0, sticky='w', padx=20, pady=(10, 4))

        self._cible_frame = ctk.CTkFrame(self, fg_color='transparent')
        ctk.CTkLabel(self._cible_frame, text='Quantité cible :',
                     text_color=T['tx2'], font=ctk.CTkFont(size=11)).pack(side='left')
        self._cible_var = ctk.StringVar()
        ctk.CTkEntry(self._cible_frame, textvariable=self._cible_var, width=80,
                     fg_color=T['bg_el'], border_color=T['bg_hl']).pack(side='left', padx=8)
        # cible_frame hidden until staple checked

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

        db.add_to_stock_from_aliment(self._aliment['id'], qty, self._unite_var.get())

        # DLC et staple : update après l'upsert
        if dlc_iso or self._staple_var.get():
            stock = db.get_stock()
            item = next((s for s in stock if s['aliment_id'] == self._aliment['id']), None)
            if item:
                cible = 0.0
                if self._staple_var.get():
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
```

- [ ] Ajouter `AddToStockDialog` dans `pages/stock.py`

### Étape 2.2 — Ajouter `show_stock_alert_toast()`

Ajouter comme fonction module-level dans `pages/stock.py`, avant les classes :

```python
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

    ctk.CTkLabel(frame, text='⚠️  Stock faible',
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

    ctk.CTkButton(frame, text='Voir le stock →',
                  fg_color='transparent', hover_color=T['bg_el'],
                  text_color=T['ac'], font=ctk.CTkFont(size=11),
                  command=_nav_stock).pack(padx=8, pady=(4, 8), anchor='e')

    # Positionner en bas à droite
    parent.update_idletasks()
    sw = parent.winfo_screenwidth()
    sh = parent.winfo_screenheight()
    toast.update_idletasks()
    w = toast.winfo_reqwidth()
    h = toast.winfo_reqheight()
    toast.geometry(f"+{sw - w - 20}+{sh - h - 60}")

    # Auto-fermeture 4 secondes
    toast.after(4000, lambda: toast.destroy() if toast.winfo_exists() else None)
```

- [ ] Ajouter `show_stock_alert_toast` dans `pages/stock.py`

### Étape 2.3 — Étendre `StockDialog` avec 4 nouveaux champs

Dans `StockDialog._build()`, après le champ Notes (row=8) et avant les boutons (row=9), insérer :

```python
        # Séparateur
        ctk.CTkFrame(self, height=1, fg_color=T['bg_el']).grid(
            row=9, column=0, sticky='ew', padx=20, pady=8)

        # Seuil minimum
        row_min = ctk.CTkFrame(self, fg_color='transparent')
        row_min.grid(row=10, column=0, sticky='w', padx=20, pady=4)
        ctk.CTkLabel(row_min, text='Seuil alerte (0 = désactivé) :',
                     text_color=T['tx2'], font=ctk.CTkFont(size=11),
                     width=200).grid(row=0, column=0, sticky='w')
        self._qmin_var = ctk.StringVar(value='0')
        ctk.CTkEntry(row_min, textvariable=self._qmin_var, width=80,
                     fg_color=T['bg_el'], border_color=T['bg_hl']).grid(
            row=0, column=1, padx=8)

        # Staple
        self._staple_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text='Produit de première nécessité (staple)',
                        variable=self._staple_var,
                        fg_color=T['ac'], hover_color=T['ac_d'],
                        text_color=T['tx1'],
                        command=self._toggle_staple_fields).grid(
            row=11, column=0, sticky='w', padx=20, pady=4)

        self._staple_fields = ctk.CTkFrame(self, fg_color='transparent')
        ctk.CTkLabel(self._staple_fields, text='Quantité cible :',
                     text_color=T['tx2'], font=ctk.CTkFont(size=11)).pack(side='left')
        self._cible_var = ctk.StringVar(value='0')
        ctk.CTkEntry(self._staple_fields, textvariable=self._cible_var, width=80,
                     fg_color=T['bg_el'], border_color=T['bg_hl']).pack(side='left', padx=8)

        # Source eau
        self._eau_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text='Source d\'eau (lier au tracker hydratation)',
                        variable=self._eau_var,
                        fg_color=T['blue'], hover_color=T['blue_d'],
                        text_color=T['tx1']).grid(
            row=13, column=0, sticky='w', padx=20, pady=4)
```

Et déplacer les boutons de row=9 à row=14.

Ajouter la méthode `_toggle_staple_fields` :
```python
    def _toggle_staple_fields(self):
        if self._staple_var.get():
            self._staple_fields.grid(row=12, column=0, sticky='w', padx=32, pady=2)
        else:
            self._staple_fields.grid_forget()
```

Modifier `_prefill` pour charger ces champs :
```python
        # Après les champs existants dans _prefill :
        self._qmin_var.set(str(round(item.get('quantite_min', 0) or 0, 1)))
        self._staple_var.set(bool(item.get('est_staple', 0)))
        self._cible_var.set(str(round(item.get('quantite_cible', 0) or 0, 1)))
        self._eau_var.set(bool(item.get('est_eau', 0)))
        if self._staple_var.get():
            self._toggle_staple_fields()
```

Modifier `_save` pour persister ces champs (après `db.upsert_stock(...)`) :
```python
        # Récupérer l'item créé/modifié et mettre à jour les champs v2
        stock = db.get_stock()
        item = next((s for s in stock if s['aliment_id'] == self._aliment_id), None)
        if item:
            try:
                qmin = float(self._qmin_var.get().replace(',', '.') or 0)
            except ValueError:
                qmin = 0.0
            try:
                cible = float(self._cible_var.get().replace(',', '.') or 0)
            except ValueError:
                cible = 0.0
            conn = db.get_connection()
            conn.execute("""UPDATE stock SET quantite_min=?, est_staple=?,
                            quantite_cible=? WHERE id=?""",
                         (qmin, 1 if self._staple_var.get() else 0, cible, item['id']))
            conn.commit()
            conn.close()
            if self._eau_var.get():
                db.set_stock_eau(item['id'])
```

Agrandir la fenêtre de StockDialog : `self.geometry('440x560')`

- [ ] Étendre `StockDialog` avec les 4 champs et `_toggle_staple_fields`

### Étape 2.4 — Section alertes étendue dans `StockPage._update_alerts()`

Modifier `_update_alerts()` pour afficher aussi les items sous seuil. Remplacer par :

```python
    def _update_alerts(self):
        self._alert_frame.grid_forget()
        for w in self._alert_frame.winfo_children():
            w.destroy()

        dlc_alerts = self._alerts  # déjà calculé dans refresh()
        sous_seuil = db.get_stock_sous_seuil()
        if not dlc_alerts and not sous_seuil:
            return

        ctk.CTkLabel(self._alert_frame, text='⚠️  Alertes stock',
                     font=ctk.CTkFont(size=13, weight='bold'),
                     text_color=T['cal']).grid(
            row=0, column=0, sticky='w', padx=14, pady=(10, 4))

        today = date.today().isoformat()
        row_i = 1
        for item in dlc_alerts:
            dlc = item.get('date_peremption', '')
            if dlc < today:
                txt = f"🔴  {item['nom']} — périmé (DLC : {dlc})"
                color = T['err']
            else:
                txt = f"🟡  {item['nom']} — expire le {dlc}"
                color = T['cal']
            ctk.CTkLabel(self._alert_frame, text=txt, text_color=color,
                         font=ctk.CTkFont(size=12)).grid(
                row=row_i, column=0, sticky='w', padx=14, pady=2)
            row_i += 1

        for item in sous_seuil:
            txt = f"🟠  {item['nom']} — {round(item['quantite'],1)}{item['unite']} restants (seuil : {round(item['quantite_min'],1)}{item['unite']})"
            ctk.CTkLabel(self._alert_frame, text=txt, text_color=T['cal'],
                         font=ctk.CTkFont(size=12)).grid(
                row=row_i, column=0, sticky='w', padx=14, pady=2)
            row_i += 1

        self._alert_frame.grid(row=1, column=0, padx=28, pady=(10, 0), sticky='ew')
```

- [ ] Remplacer `_update_alerts()` par la version étendue

### Étape 2.5 — Section liste de courses dans `StockPage`

Dans `_build()`, après la liste scrollable (row=3), ajouter un frame pour la liste de courses :

```python
        # ── Liste de courses ─────────────────────────────────────
        self._courses_frame = ctk.CTkFrame(self, fg_color=T['bg_card'],
                                            corner_radius=10)
        self._courses_frame.grid(row=4, column=0, padx=28, pady=(0, 28), sticky='ew')
        self._courses_frame.grid_columnconfigure(0, weight=1)
        self._courses_visible = False

        courses_hdr = ctk.CTkFrame(self._courses_frame, fg_color='transparent')
        courses_hdr.grid(row=0, column=0, sticky='ew', padx=14, pady=10)
        courses_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(courses_hdr, text='🛒  Liste de courses',
                     font=ctk.CTkFont(size=14, weight='bold'),
                     text_color=T['tx1']).grid(row=0, column=0, sticky='w')
        self._courses_toggle_btn = ctk.CTkButton(
            courses_hdr, text='Afficher ▼', width=100, height=28,
            fg_color=T['bg_el'], hover_color=T['bg_hl'],
            text_color=T['tx2'], font=ctk.CTkFont(size=11),
            command=self._toggle_courses)
        self._courses_toggle_btn.grid(row=0, column=1, sticky='e')

        self._courses_content = ctk.CTkFrame(self._courses_frame,
                                              fg_color='transparent')
        # affiché/caché par _toggle_courses
```

Ajouter les méthodes dans `StockPage` :

```python
    def _toggle_courses(self):
        self._courses_visible = not self._courses_visible
        if self._courses_visible:
            self._courses_toggle_btn.configure(text='Masquer ▲')
            self._draw_courses()
            self._courses_content.grid(row=1, column=0, sticky='ew',
                                        padx=14, pady=(0, 14))
        else:
            self._courses_toggle_btn.configure(text='Afficher ▼')
            self._courses_content.grid_forget()

    def _draw_courses(self):
        for w in self._courses_content.winfo_children():
            w.destroy()
        self._courses_content.grid_columnconfigure(0, weight=1)

        data = db.get_liste_courses_stock()
        row_i = 0

        def section(title, items, render_fn):
            nonlocal row_i
            if not items:
                return
            ctk.CTkLabel(self._courses_content,
                         text=title,
                         font=ctk.CTkFont(size=12, weight='bold'),
                         text_color=T['tx2']).grid(
                row=row_i, column=0, sticky='w', pady=(10, 2))
            row_i += 1
            for item in items:
                render_fn(item, row_i)
                row_i += 1

        def render_staple(item, r):
            ctk.CTkLabel(self._courses_content,
                         text=f"  • {item['nom']}  —  manque {item['manque']}{item['unite']}  (cible {item['quantite_cible']}{item['unite']})",
                         font=ctk.CTkFont(size=12), text_color=T['tx1']).grid(
                row=r, column=0, sticky='w', padx=8)

        def render_recette(item, r):
            ctk.CTkLabel(self._courses_content,
                         text=f"  • {item['nom']}  —  {item['manque_g']}g  → {item['nom_recette']} ({item['date_repas']})",
                         font=ctk.CTkFont(size=12), text_color=T['tx1']).grid(
                row=r, column=0, sticky='w', padx=8)

        def render_suggestion(item, r):
            f = ctk.CTkFrame(self._courses_content, fg_color='transparent')
            f.grid(row=r, column=0, sticky='ew', padx=8)
            ctk.CTkLabel(f, text=f"  • {item['nom']}  (utilisé {item['nb_utilisations']}×)",
                         font=ctk.CTkFont(size=12), text_color=T['tx2']).pack(side='left')
            ctk.CTkButton(f, text='+ Staple', width=70, height=22,
                          fg_color=T['bg_el'], hover_color=T['bg_hl'],
                          text_color=T['ac'], font=ctk.CTkFont(size=10),
                          command=lambda aid=item['aliment_id']: self._mark_staple(aid)).pack(
                side='right', padx=4)

        section('STAPLES À RÉAPPROVISIONNER', data['staples'], render_staple)
        section('RECETTES PLANIFIÉES — MANQUANTS', data['recettes'], render_recette)
        section('SUGGESTIONS — fréquemment utilisés', data['suggestions'], render_suggestion)

        if not any([data['staples'], data['recettes'], data['suggestions']]):
            ctk.CTkLabel(self._courses_content,
                         text='Aucun article à acheter pour le moment.',
                         text_color=T['tx3'], font=ctk.CTkFont(size=12)).grid(
                row=0, column=0, pady=16)
            return

        # Boutons export
        row_i += 1
        export_row = ctk.CTkFrame(self._courses_content, fg_color='transparent')
        export_row.grid(row=row_i, column=0, pady=10)
        ctk.CTkButton(export_row, text='📋 Copier',
                      fg_color=T['bg_el'], hover_color=T['bg_hl'],
                      text_color=T['tx1'], width=100,
                      command=lambda: self._copy_courses(data)).grid(
            row=0, column=0, padx=8)

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
```

- [ ] Ajouter section liste de courses dans `StockPage`

### Étape 2.6 — Vérification

```
cd D:\DEV\Python\proteines\nutrition_app_v7 && python -c "
from pages.stock import StockPage, StockDialog, AddToStockDialog, show_stock_alert_toast
print('Imports OK')
import inspect
print('AddToStockDialog._save:', 'add_to_stock_from_aliment' in inspect.getsource(AddToStockDialog._save))
print('show_stock_alert_toast exists:', callable(show_stock_alert_toast))
"
```

- [ ] Vérifier Task 2

---

## Task 3 — pages/aliments.py : bouton 📦 par ligne

**Files:** Modify `pages/aliments.py`

### Étape 3.1 — Import AddToStockDialog

En haut de `pages/aliments.py`, après `from theme import T`, ajouter :
```python
from pages.stock import AddToStockDialog
```

- [ ] Ajouter import `AddToStockDialog` dans `pages/aliments.py`

### Étape 3.2 — Bouton 📦 dans `_refresh_table()`

Dans `_refresh_table()`, trouver le bloc des boutons action (vers ligne 224-233) :
```python
            bf = ctk.CTkFrame(row, fg_color="transparent")
            bf.place(x=x, rely=0.5, anchor="w")
            ctk.CTkButton(bf, text="✏", ...)
            ctk.CTkButton(bf, text="🗑", ...)
```

Ajouter un bouton `📦` **avant** `✏` :
```python
            bf = ctk.CTkFrame(row, fg_color="transparent")
            bf.place(x=x, rely=0.5, anchor="w")
            ctk.CTkButton(bf, text="📦", width=30, height=26,
                          fg_color=T["bg_el"], hover_color=T["ac_bg"],
                          font=ctk.CTkFont(size=12), corner_radius=6,
                          command=lambda a=alim: AddToStockDialog(self, a, self.refresh)).pack(
                side="left", padx=2)
            ctk.CTkButton(bf, text="✏", width=30, height=26, ...)
            ctk.CTkButton(bf, text="🗑", width=30, height=26, ...)
```

- [ ] Ajouter bouton `📦` dans `_refresh_table()`

### Étape 3.3 — Vérification

```
cd D:\DEV\Python\proteines\nutrition_app_v7 && python -c "
from pages.aliments import AlimentsPage
import inspect
src = inspect.getsource(AlimentsPage._refresh_table)
print('AddToStockDialog in src:', 'AddToStockDialog' in src)
"
```

- [ ] Vérifier Task 3

---

## Task 4 — barcode_scanner.py : bouton stock post-scan

**Files:** Modify `barcode_scanner.py`

### Étape 4.1 — Import AddToStockDialog dans barcode_scanner.py

En haut du fichier, dans les imports, ajouter :
```python
from pages.stock import AddToStockDialog
```
Note : cet import est conditionnel (le scanner fonctionne sans l'UI). L'entourer d'un try/except :
```python
try:
    from pages.stock import AddToStockDialog as _AddToStockDialog
except ImportError:
    _AddToStockDialog = None
```

- [ ] Ajouter import conditionnel `AddToStockDialog` dans `barcode_scanner.py`

### Étape 4.2 — Bouton "📦 Ajouter au stock" dans `ProductFoundDialog`

Dans `ProductFoundDialog._confirm()`, après `self.on_confirm(data)`, le produit est maintenant en BDD. Modifier `_confirm` pour passer l'aliment_id au callback, et ajouter un bouton "📦 Ajouter au stock + aliments" :

Dans `_build()`, trouver le bouton `"➕  Ajouter à mes aliments"` et le remplacer par deux boutons :

```python
        ctk.CTkButton(bf, text="Annuler",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=38, width=120, corner_radius=8,
                      command=self.destroy).pack(side="left")

        ctk.CTkButton(bf, text="➕  Aliments seulement",
                      fg_color=T["bg_el"], hover_color=T["bg_hl"],
                      height=38, width=180, corner_radius=8,
                      command=self._confirm).pack(side="left", padx=8)

        ctk.CTkButton(bf, text="📦  Aliments + Stock",
                      fg_color=T["ac"], hover_color=T["ac_d"],
                      text_color="#000000",
                      height=38, width=180, corner_radius=8,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._confirm_and_stock).pack(side="right")
```

Ajouter la méthode `_confirm_and_stock` :
```python
    def _confirm_and_stock(self):
        """Ajoute à la BDD aliments puis ouvre AddToStockDialog."""
        data = {k: v.get().strip() for k, v in self.vars.items()}
        if not data.get("nom"):
            messagebox.showwarning("Champ requis", "Le nom est obligatoire.", parent=self)
            return
        for key in ("calories", "proteines", "glucides", "lipides", "fibres"):
            try:
                data[key] = float(data[key]) if data[key] else 0.0
            except ValueError:
                data[key] = 0.0
        try:
            data["ig"] = int(data["ig"]) if data["ig"] else 0
        except ValueError:
            data["ig"] = 0
        data.setdefault("unite", "g")
        self.on_confirm(data)
        # Récupérer l'aliment nouvellement créé
        import database as db
        alim = db.get_aliments(search=data.get("nom", ""))
        if alim and _AddToStockDialog:
            parent = self.master
            self.destroy()
            _AddToStockDialog(parent, alim[0])
        else:
            self.destroy()
```

- [ ] Ajouter boutons stock + méthode `_confirm_and_stock` dans `ProductFoundDialog`

### Étape 4.3 — Vérification

```
cd D:\DEV\Python\proteines\nutrition_app_v7 && python -c "
from barcode_scanner import ProductFoundDialog
import inspect
src = inspect.getsource(ProductFoundDialog._confirm_and_stock)
print('_confirm_and_stock exists, len:', len(src))
"
```

- [ ] Vérifier Task 4

---

## Task 5 — pages/journal.py : déduction + add-to-stock + hydratation

**Files:** Modify `pages/journal.py`

### Étape 5.1 — Import AddToStockDialog et show_stock_alert_toast

En haut de `pages/journal.py`, après `from theme import T` :
```python
from pages.stock import AddToStockDialog, show_stock_alert_toast
```

- [ ] Ajouter imports stock dans `pages/journal.py`

### Étape 5.2 — Checkbox déduction dans `AddJournalDialog`

Dans `AddJournalDialog`, ajouter un attribut `_deduct_var` et `_add_stock_var`, et un frame `_stock_row` qui s'affiche dynamiquement.

Dans `_build()`, dans l'onglet "🥑 Depuis la base" (t1), après le champ quantité (l'entrée `_qte_var`), ajouter le widget dynamique stock. La méthode `_select_alim` devra mettre à jour ce widget.

Ajouter dans `__init__` après `self._selected_alim = None` :
```python
        self._deduct_var = ctk.BooleanVar(value=False)
        self._add_stock_var = ctk.BooleanVar(value=False)
```

Ajouter dans `_build()`, dans t1, après la section quantité (chercher `self._qte_var`) :
```python
        # Zone stock dynamique (affichée selon l'aliment sélectionné)
        self._stock_zone = ctk.CTkFrame(t1, fg_color='transparent')
        self._stock_zone.grid(row=4, column=0, sticky='ew', pady=(4, 0))
```

Modifier `_select_alim()` pour mettre à jour la zone stock :
```python
    def _select_alim(self, alim, row_widget):
        self._selected_alim = alim
        for w in self._alim_list.winfo_children():
            w.configure(fg_color="transparent")
        if row_widget is not None:
            row_widget.configure(fg_color=T["ac_sel"], border_width=1, border_color=T["ac"])
        self._alim_info.configure(
            text=f"Sélectionné : {alim['nom']}  —  {alim['calories']} kcal / 100g")
        self._update_stock_zone(alim)

    def _update_stock_zone(self, alim):
        for w in self._stock_zone.winfo_children():
            w.destroy()
        if not alim:
            return
        stock = db.get_stock()
        item = next((s for s in stock if s['aliment_id'] == alim['id']), None)

        if item:
            # Aliment en stock → proposer déduction
            stock_qty = round(item['quantite'], 1)
            self._deduct_var.set(True)
            f = ctk.CTkFrame(self._stock_zone, fg_color=T['bg_el'], corner_radius=6)
            f.pack(fill='x', pady=2)
            ctk.CTkCheckBox(f, text=f"Déduire du stock  (stock : {stock_qty} {item['unite']})",
                            variable=self._deduct_var,
                            fg_color=T['ac'], hover_color=T['ac_d'],
                            text_color=T['tx1'],
                            font=ctk.CTkFont(size=11)).pack(
                side='left', padx=8, pady=6)
        else:
            # Aliment pas en stock → proposer ajout
            self._add_stock_var.set(False)
            f = ctk.CTkFrame(self._stock_zone, fg_color=T['bg_el'], corner_radius=6)
            f.pack(fill='x', pady=2)
            ctk.CTkCheckBox(f, text='Ajouter aussi au stock',
                            variable=self._add_stock_var,
                            fg_color=T['blue'], hover_color=T['blue_d'],
                            text_color=T['tx2'],
                            font=ctk.CTkFont(size=11),
                            command=lambda: self._toggle_add_stock_qty(f)).pack(
                side='left', padx=8, pady=6)
            self._stock_qty_entry = None

    def _toggle_add_stock_qty(self, parent_frame):
        # Supprimer ancien champ si présent
        for w in parent_frame.winfo_children():
            if hasattr(w, '_is_stock_qty'):
                w.destroy()
        if self._add_stock_var.get():
            entry = ctk.CTkEntry(parent_frame, width=80, placeholder_text='qté achetée',
                                  fg_color=T['bg_card'], border_color=T['bg_hl'],
                                  font=ctk.CTkFont(size=11))
            entry._is_stock_qty = True
            entry.pack(side='left', padx=4, pady=6)
            self._stock_qty_entry = entry
        else:
            self._stock_qty_entry = None
```

- [ ] Ajouter `_stock_zone` + `_update_stock_zone` + `_toggle_add_stock_qty` dans `AddJournalDialog`

### Étape 5.3 — Modifier `_save()` pour appliquer déduction ou ajout

Dans `_save()`, dans le bloc `if "base" in tab.lower():`, après `db.add_journal_entry(...)` (juste avant `self._callback()`), ajouter :

```python
            # Gestion stock
            if self._deduct_var.get() and self._selected_alim:
                sous_seuil = db.deduct_stock([{
                    'aliment_id': a['id'],
                    'quantite_g': qte
                }])
                db.increment_stock_usage(a['id'])
                if sous_seuil:
                    show_stock_alert_toast(self, sous_seuil)
            elif self._add_stock_var.get() and self._selected_alim:
                qty_str = ''
                if self._stock_qty_entry and self._stock_qty_entry.winfo_exists():
                    qty_str = self._stock_qty_entry.get().strip()
                try:
                    qty_achat = float(qty_str.replace(',', '.'))
                except (ValueError, AttributeError):
                    qty_achat = qte  # fallback : même quantité que consommée
                db.add_to_stock_from_aliment(a['id'], qty_achat)
```

- [ ] Modifier `_save()` pour la gestion stock

### Étape 5.4 — Modifier `_add_eau()` pour déduire du stock eau

Remplacer dans `JournalPage` :
```python
    def _add_eau(self, ml: int):
        db.add_eau(ml, self._date.isoformat())
        self._refresh_bilan()
```

Par :
```python
    def _add_eau(self, ml: int):
        db.add_eau(ml, self._date.isoformat())
        # Déduire du stock eau si configuré
        eau_aid = db.get_stock_eau_aliment_id()
        if eau_aid:
            sous_seuil = db.deduct_stock([{'aliment_id': eau_aid, 'quantite_g': ml}])
            if sous_seuil:
                show_stock_alert_toast(self, sous_seuil)
        self._refresh_bilan()
```

- [ ] Modifier `_add_eau()` pour déduction hydratation

### Étape 5.5 — Vérification

```
cd D:\DEV\Python\proteines\nutrition_app_v7 && python -c "
from pages.journal import JournalPage, AddJournalDialog
import inspect
src_eau = inspect.getsource(JournalPage._add_eau)
print('eau deduction:', 'deduct_stock' in src_eau)
src_save = inspect.getsource(AddJournalDialog._save)
print('deduct in save:', 'deduct_stock' in src_save)
print('add_to_stock in save:', 'add_to_stock_from_aliment' in src_save)
"
```

- [ ] Vérifier Task 5

---

## Task 6 — pages/planning.py : toast dans DeductionStockDialog

**Files:** Modify `pages/planning.py`

### Étape 6.1 — Import show_stock_alert_toast

En haut de `pages/planning.py`, ajouter :
```python
from pages.stock import show_stock_alert_toast
```

- [ ] Ajouter import `show_stock_alert_toast` dans `pages/planning.py`

### Étape 6.2 — Modifier `DeductionStockDialog._deduct()`

Trouver `DeductionStockDialog._deduct()` (à la fin du fichier) :
```python
    def _deduct(self):
        if self._deductions:
            db.deduct_stock(self._deductions)
        if self._on_done:
            self._on_done()
        self.destroy()
```

Remplacer par :
```python
    def _deduct(self):
        sous_seuil = []
        if self._deductions:
            sous_seuil = db.deduct_stock(self._deductions)
        if self._on_done:
            self._on_done()
        self.destroy()
        if sous_seuil:
            # Le parent est PlanningPage — on cherche la toplevel pour le toast
            try:
                show_stock_alert_toast(self.master, sous_seuil)
            except Exception:
                pass
```

- [ ] Remplacer `_deduct()` avec gestion toast

### Étape 6.3 — Vérification

```
cd D:\DEV\Python\proteines\nutrition_app_v7 && python -c "
from pages.planning import DeductionStockDialog
import inspect
src = inspect.getsource(DeductionStockDialog._deduct)
print('sous_seuil in _deduct:', 'sous_seuil' in src)
print('show_stock_alert_toast:', 'show_stock_alert_toast' in src)
"
```

- [ ] Vérifier Task 6

---

## Task 7 — pages/dashboard.py : alertes stock faible

**Files:** Modify `pages/dashboard.py`

### Étape 7.1 — Étendre `_draw_stock_alerts_card()`

Trouver la méthode `_draw_stock_alerts_card()`. La remplacer par :

```python
    def _draw_stock_alerts_card(self):
        alerts_dlc = db.get_stock_alerts()
        alerts_seuil = db.get_stock_sous_seuil()
        if not alerts_dlc and not alerts_seuil:
            return

        card = ctk.CTkFrame(self.stock_row, fg_color=T["bg_card"], corner_radius=12)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card,
                     text="Stock — Alertes",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=T["cal"]).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 6))

        today = date.today().isoformat()
        row_i = 1

        for item in alerts_dlc[:3]:
            dlc = item.get('date_peremption', '')
            if dlc < today:
                txt = f"[x] {item['nom']} — perime"
                col = T["err"]
            else:
                txt = f"[!] {item['nom']} — expire le {dlc}"
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
```

- [ ] Remplacer `_draw_stock_alerts_card()` par la version étendue

### Étape 7.2 — Vérification finale complète

```
cd D:\DEV\Python\proteines\nutrition_app_v7 && python -c "
import database
from pages.stock import StockPage, AddToStockDialog, show_stock_alert_toast
from pages.aliments import AlimentsPage
from pages.journal import JournalPage, AddJournalDialog
from pages.planning import DeductionStockDialog
from pages.dashboard import DashboardPage
from barcode_scanner import ProductFoundDialog
print('ALL IMPORTS OK')

database.init_db()
conn = database.get_connection()
cols = [r[1] for r in conn.execute('PRAGMA table_info(stock)').fetchall()]
conn.close()
assert 'quantite_min' in cols and 'est_staple' in cols and 'est_eau' in cols, 'Missing columns!'
print('DB columns OK:', [c for c in cols if c not in ['id','user_id','aliment_id','updated_at']])

# Test end-to-end
u = database.get_connection().execute('SELECT id FROM users LIMIT 1').fetchone()
if u:
    database.set_current_user(u[0])
    database.add_to_stock_from_aliment(1, 500, 'g')
    stock = database.get_stock()
    print('Stock count:', len(stock))
    sous_seuil = database.deduct_stock([{'aliment_id': 1, 'quantite_g': 400}])
    print('deduct returns list:', isinstance(sous_seuil, list))
    courses = database.get_liste_courses_stock()
    print('courses keys:', list(courses.keys()))
    for s in database.get_stock(): database.delete_stock(s['id'])
print('ALL OK')
"
```

- [ ] Vérification finale Task 7
