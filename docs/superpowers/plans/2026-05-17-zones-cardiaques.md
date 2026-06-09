# Zones de fréquence cardiaque — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter les zones cardiaques (FC max + 5 zones) dans le module Sport, avec affichage de la zone cible avant la séance, saisie de la FC observée, badge sur chaque séance, et carte de référence en bas de la page Sport.

**Architecture:** Deux migrations SQLite (`users.fc_max`, `activites_sport.fc_observee`) + 4 fonctions DB → modifications de `pages/sport.py` (SportDialog + SportPage) + ajout du champ FC max dans `pages/profil.py`.

**Tech Stack:** Python 3.9+, CustomTkinter, SQLite (via `database.py`), thème via `T` dict

---

## Fichiers impactés

| Fichier | Action |
|---|---|
| `database.py` | Migrations + 4 fonctions : `get_fc_max`, `get_zones_cardiaques`, `get_zone_for_fc`, `is_fc_alert` + màj `add_activite_sport` |
| `pages/sport.py` | SportDialog : zone cible card + champ fc_observee + alerte ; `_draw_sessions` : badge ; `refresh` : carte référence |
| `pages/profil.py` | Champ FC max dans `_build_infos`, chargement dans `_refresh_infos`, sauvegarde dans `_save_profil` |

---

## Task 1 : Migrations DB + fonctions

**Fichier :** `database.py`

- [ ] **Étape 1 — Ajouter les migrations dans `_migrate()`**

Trouver le bloc des migrations (chercher `"ALTER TABLE activites_sport"`) et ajouter juste après :

```python
try:
    conn.execute("ALTER TABLE users ADD COLUMN fc_max INTEGER DEFAULT 0")
except Exception:
    pass
try:
    conn.execute("ALTER TABLE activites_sport ADD COLUMN fc_observee INTEGER DEFAULT 0")
except Exception:
    pass
```

- [ ] **Étape 2 — Ajouter `get_fc_max()` après les constantes sport**

Ajouter après `INTENSITES_LABELS = ...` :

```python
def get_fc_max() -> int:
    """FC max du profil si renseignée, sinon 220 − âge."""
    user = get_current_user()
    if not user:
        return 160
    fc = int(user.get('fc_max') or 0)
    if fc > 0:
        return fc
    return max(100, 220 - int(user.get('age') or 40))


def get_zones_cardiaques(fc_max: int) -> list:
    """5 zones cardiaques en bpm. color_key = clé dans T[]."""
    zones_def = [
        (1, 'Récupération',      0.50, 0.60, 'ac'),
        (2, 'Endurance de base', 0.60, 0.70, 'blue'),
        (3, 'Aérobie',           0.70, 0.80, 'lip'),
        (4, 'Seuil',             0.80, 0.90, 'cal'),
        (5, 'Maximum',           0.90, 1.00, 'err'),
    ]
    return [
        {
            'num':       num,
            'label':     label,
            'bpm_min':   int(fc_max * pmin),
            'bpm_max':   int(fc_max * pmax),
            'pct_min':   int(pmin * 100),
            'pct_max':   int(pmax * 100),
            'color_key': color_key,
        }
        for num, label, pmin, pmax, color_key in zones_def
    ]


def get_zone_for_fc(fc_obs: int, fc_max: int):
    """Zone correspondant à fc_obs, ou None si fc_obs == 0."""
    if not fc_obs or fc_obs <= 0:
        return None
    zones = get_zones_cardiaques(fc_max)
    for z in reversed(zones):
        if fc_obs >= z['bpm_min']:
            return z
    return zones[0]


def is_fc_alert(fc_obs: int, fc_max: int) -> bool:
    """True si fc_obs dépasse 85 % de fc_max."""
    return fc_obs > 0 and fc_obs > fc_max * 0.85
```

- [ ] **Étape 3 — Mettre à jour `add_activite_sport()` pour inclure `fc_observee`**

Remplacer la fonction existante :

```python
def add_activite_sport(data: dict) -> int:
    conn = get_connection()
    cur  = conn.execute("""INSERT INTO activites_sport
        (user_id, date, heure, type_activite, duree_min,
         vitesse_kmh, intensite, calories_brulees, notes, fc_observee)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (_current_user_id,
         data.get('date', date.today().isoformat()),
         data.get('heure', ''),
         data['type_activite'],
         int(data.get('duree_min', 0)),
         float(data.get('vitesse_kmh', 0)),
         data.get('intensite', 'leger'),
         float(data.get('calories_brulees', 0)),
         data.get('notes', ''),
         int(data.get('fc_observee', 0))))
    conn.commit()
    conn.close()
    return cur.lastrowid
```

- [ ] **Étape 4 — Vérifier**

```bash
python -c "
import sys; sys.path.insert(0,'.')
import database as db
db.init_db()
fc = db.get_fc_max()
print(f'FC max: {fc} bpm')
zones = db.get_zones_cardiaques(fc)
for z in zones: print(f'  Z{z[\"num\"]} {z[\"label\"]}: {z[\"bpm_min\"]}–{z[\"bpm_max\"]} bpm')
z = db.get_zone_for_fc(100, 160)
print(f'FC 100 bpm -> Zone {z[\"num\"]} {z[\"label\"]}' if z else 'Aucune zone')
print(f'Alerte 140/160: {db.is_fc_alert(140, 160)}')
print(f'Alerte 100/160: {db.is_fc_alert(100, 160)}')
"
```

Résultat attendu :
```
FC max: 160 bpm   (ou calculé depuis l'utilisateur courant)
  Z1 Récupération: 80–96 bpm
  Z2 Endurance de base: 96–112 bpm
  Z3 Aérobie: 112–128 bpm
  Z4 Seuil: 128–144 bpm
  Z5 Maximum: 144–160 bpm
FC 100 bpm -> Zone 2 Endurance de base
Alerte 140/160: True
Alerte 100/160: False
```

---

## Task 2 : SportDialog — zone cible + FC observée

**Fichier :** `pages/sport.py`

- [ ] **Étape 1 — Ajouter `_fc_var` et `_zone_card_lbl` dans `__init__`**

Dans `SportDialog.__init__`, après `self._vit_lbl = None` :

```python
self._fc_var         = ctk.StringVar(value='')
self._zone_card_lbl  = None
```

- [ ] **Étape 2 — Insérer la carte "Zone cible" dans `_build()`**

Dans `_build()`, remplacer le séparateur entre le type d'activité et la durée :

```python
        ctk.CTkFrame(self, height=1, fg_color=T["bg_el"]).pack(fill="x", padx=16, pady=(4, 8))
```

par :

```python
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
```

- [ ] **Étape 3 — Insérer le champ "FC observée" dans `_build()`, après le preview card**

Après `self._preview_sub.pack(pady=(0, 10))` :

```python
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
        self._fc_var.trace_add("write", self._on_fc_change)
```

- [ ] **Étape 4 — Augmenter la hauteur du dialogue**

Remplacer `self.geometry("500x660")` par `self.geometry("500x760")`.

- [ ] **Étape 5 — Ajouter `_on_fc_change()` et `_update_zone_display()`**

Ajouter ces deux méthodes dans `SportDialog` (avant `_save`):

```python
    def _update_zone_display(self):
        if self._zone_card_lbl is None:
            return
        fc_max = db.get_fc_max()
        zones  = db.get_zones_cardiaques(fc_max)
        z2     = zones[1]   # Zone 2 — recommandée pour débutants cardiaques
        color  = T.get(z2['color_key'], T["ac"])
        self._zone_card_lbl.configure(
            text=f"🟡 Zone {z2['num']} — {z2['label']} : {z2['bpm_min']}–{z2['bpm_max']} bpm",
            text_color=color)

    def _on_fc_change(self, *_):
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
```

- [ ] **Étape 6 — Appeler `_update_zone_display()` au bon moment**

Dans `_build()`, à la fin (après `self._update_preview()`) :
```python
        self._update_zone_display()
```

Dans `_select_type()`, à la fin :
```python
        self._update_zone_display()
```

- [ ] **Étape 7 — Sauvegarder `fc_observee` dans `_save()`**

Dans `_save()`, avant `db.add_activite_sport(...)`, ajouter :

```python
        try:
            fc_obs = int(self._fc_var.get())
        except (ValueError, TypeError):
            fc_obs = 0
```

Puis dans le dict passé à `add_activite_sport`, ajouter :
```python
            'fc_observee': fc_obs,
```

---

## Task 3 : Badges séances + carte référence

**Fichier :** `pages/sport.py`

- [ ] **Étape 1 — Badge coloré dans `_draw_sessions()`**

Dans la boucle `for i, s in enumerate(seances)`, après le CTkButton "✕" (colonne 3), ajouter :

```python
            if s.get('fc_observee') and int(s['fc_observee']) > 0:
                fc_max = db.get_fc_max()
                zone   = db.get_zone_for_fc(int(s['fc_observee']), fc_max)
                if zone:
                    col = T.get(zone['color_key'], T["tx2"])
                    ctk.CTkLabel(row_w,
                                 text=f"Z{zone['num']} · {int(s['fc_observee'])} bpm",
                                 font=ctk.CTkFont(size=10, weight="bold"),
                                 text_color=col).grid(row=0, column=4, padx=(0, 4))
```

- [ ] **Étape 2 — Ajouter `_draw_zones_card()` dans `SportPage`**

Ajouter cette méthode dans `SportPage` (après `_draw_chart`) :

```python
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
```

- [ ] **Étape 3 — Appeler `_draw_zones_card()` dans `refresh()`**

À la fin de `refresh()`, après l'appel à `_draw_chart()` :

```python
        self._draw_zones_card()
```

---

## Task 4 : Champ FC max dans Profil

**Fichier :** `pages/profil.py`

- [ ] **Étape 1 — Ajouter le champ FC max dans `_build_infos()`**

Dans `_build_infos()`, entre le bloc "Hydratation" (row 22–24) et le bouton Enregistrer (row 26), insérer à row 25 :

```python
        # ── FC max ───────────────────────────────────────────────
        ctk.CTkFrame(scroll, height=1, fg_color=T["bg_el"]).grid(
            row=25, column=0, columnspan=2, padx=8, pady=(8, 0), sticky="ew")
        ctk.CTkLabel(scroll, text="❤️  Fréquence cardiaque maximale",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=T["err"]).grid(
            row=26, column=0, columnspan=2, padx=8, pady=(10, 2), sticky="w")

        fc_row = ctk.CTkFrame(scroll, fg_color="transparent")
        fc_row.grid(row=27, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
        ctk.CTkLabel(fc_row, text="FC max (bpm) :",
                     font=ctk.CTkFont(size=12), text_color=T["tx2"]).pack(side="left")
        self._fc_max_var = ctk.StringVar(value="")
        ctk.CTkEntry(fc_row, textvariable=self._fc_max_var, width=100, height=34,
                     fg_color=T["bg_card"], border_color=T["bg_hl"],
                     font=ctk.CTkFont(size=13),
                     placeholder_text="auto").pack(side="left", padx=8)
        ctk.CTkLabel(fc_row, text="bpm  (laisser vide = 220 − âge)",
                     font=ctk.CTkFont(size=11), text_color=T["tx2"]).pack(side="left")
```

Mettre à jour le bouton "Enregistrer" pour qu'il soit à row 29 (au lieu de row 26). Chercher et remplacer :
```python
                      command=self._save_profil).grid(
            row=26, column=0, columnspan=2, padx=8, pady=(16, 8), sticky="ew")
```
par :
```python
                      command=self._save_profil).grid(
            row=29, column=0, columnspan=2, padx=8, pady=(16, 8), sticky="ew")
```

- [ ] **Étape 2 — Charger `fc_max` dans `_refresh_infos()`**

Dans `_refresh_infos()`, après le bloc `if hasattr(self, '_eau_obj_var')` :

```python
        if hasattr(self, '_fc_max_var'):
            fc = int(user.get('fc_max') or 0)
            self._fc_max_var.set(str(fc) if fc > 0 else "")
```

- [ ] **Étape 3 — Sauvegarder `fc_max` dans `_save_profil()`**

Dans `_save_profil()`, avant `db.save_profil(data)` :

```python
        if hasattr(self, '_fc_max_var'):
            try:
                fc = int(float(self._fc_max_var.get().replace(',', '.') or 0))
                data['fc_max'] = max(0, fc)
            except (ValueError, TypeError):
                data['fc_max'] = 0
        else:
            data.setdefault('fc_max', 0)
```

- [ ] **Étape 4 — Vérification finale**

Lancer l'app et tester :
1. Sport → "+ Ajouter une séance" → la carte "Zone recommandée" affiche "Zone 2 — Endurance de base : 96–112 bpm"
2. Saisir 140 dans "FC observée" → alerte orange apparaît
3. Saisir 100 → "→ Zone 2 — Endurance de base" en bleu
4. Sauvegarder → badge "Z2 · 100 bpm" visible dans la liste des séances
5. Carte référence visible en bas de la page Sport
6. Profil → Informations → champ "FC max" visible avec placeholder "auto"

```bash
python main.py
```
