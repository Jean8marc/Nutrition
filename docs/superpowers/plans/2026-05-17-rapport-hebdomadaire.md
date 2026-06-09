# Rapport hebdomadaire — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Générer un rapport HTML hebdomadaire (nutrition + sport + adhérence) depuis les pages Stats et Planning, avec bouton d'impression natif.

**Architecture:** `database.get_rapport_semaine()` agrège les données → `rapport.py` génère le HTML → `pages/rapport_dialog.py` fournit le dialogue de sélection de semaine → boutons ajoutés dans Stats et Planning.

**Tech Stack:** Python 3.9+, CustomTkinter, SQLite, `webbrowser` (stdlib), `tempfile` (stdlib), HTML/CSS pur (aucune dépendance externe)

---

## Fichiers impactés

| Fichier | Action |
|---|---|
| `database.py` | Nouvelle fonction `get_rapport_semaine(date_lundi_iso)` |
| `rapport.py` | Nouveau — génération HTML complète |
| `pages/rapport_dialog.py` | Nouveau — `RapportDialog` CTkToplevel |
| `pages/stats.py` | Ajout bouton "📄 Rapport semaine" + méthode `_open_rapport` |
| `pages/planning.py` | Ajout bouton "📄 Rapport semaine" + méthode `_open_rapport` |

---

## Task 1 : `get_rapport_semaine()` dans `database.py`

**Fichier :** `database.py`

- [ ] **Étape 1 — Ajouter la fonction à la fin du fichier** (avant la ligne `if __name__ == '__main__'` s'il y en a une, sinon en fin de fichier)

```python
def get_rapport_semaine(date_lundi_iso: str) -> dict:
    """Agrège les données journal + eau + sport pour la semaine commençant date_lundi_iso."""
    from datetime import date as _date, timedelta

    lundi    = _date.fromisoformat(date_lundi_iso)
    dimanche = lundi + timedelta(days=6)

    user   = get_current_user()
    profil = get_profil()
    prog   = get_programme_actif()
    cible_cal = prog['calories_jour'] if prog else calc_calories_cible(profil)
    macros    = calc_macros_cibles(profil)

    _JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    _MOIS  = ["", "janvier", "février", "mars", "avril", "mai", "juin",
               "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

    jours = []
    for i in range(7):
        d        = lundi + timedelta(days=i)
        date_str = d.isoformat()
        label    = f"{_JOURS[d.weekday()]} {d.day} {_MOIS[d.month]}"
        nutri    = get_nutri_journal_jour(date_str)
        eau      = get_total_eau_jour(date_str)

        conn = get_connection()
        nb   = conn.execute(
            "SELECT COUNT(*) FROM journal_repas WHERE user_id=? AND date=?",
            (_current_user_id, date_str)).fetchone()[0]
        conn.close()

        enregistre = nb > 0
        a_objectif = (enregistre and
                      abs(nutri['calories'] - cible_cal) <= cible_cal * 0.10)

        jours.append({
            'date':        date_str,
            'label':       label,
            'calories':    nutri['calories'],
            'proteines':   nutri['proteines'],
            'glucides':    nutri['glucides'],
            'lipides':     nutri['lipides'],
            'fibres':      nutri['fibres'],
            'eau_ml':      eau,
            'a_objectif':  a_objectif,
            'enregistre':  enregistre,
        })

    jours_enr = [j for j in jours if j['enregistre']]
    nb_enr    = len(jours_enr)
    moyennes  = {
        k: round(sum(j[k] for j in jours_enr) / max(1, nb_enr), 1)
        for k in ('calories', 'proteines', 'glucides', 'lipides')
    }
    moyennes['eau_ml'] = round(sum(j['eau_ml'] for j in jours_enr) / max(1, nb_enr))

    # Sport
    conn       = get_connection()
    sport_rows = conn.execute(
        """SELECT type_activite, date, duree_min, calories_brulees
           FROM activites_sport
           WHERE user_id=? AND date>=? AND date<=?
           ORDER BY date, heure""",
        (_current_user_id, date_lundi_iso, dimanche.isoformat())).fetchall()
    conn.close()

    seances_sport = [
        {
            'label':           f"{ACTIVITES_SPORT.get(r['type_activite'],{}).get('icon','🏋️')} "
                               f"{ACTIVITES_SPORT.get(r['type_activite'],{}).get('label', r['type_activite'])}",
            'date':            r['date'],
            'duree_min':       r['duree_min'],
            'calories_brulees': round(float(r['calories_brulees']), 1),
        }
        for r in sport_rows
    ]

    jours_ok = sum(1 for j in jours if j['a_objectif'])

    semaine_label = (f"Semaine du {lundi.day} au {dimanche.day} "
                     f"{_MOIS[dimanche.month]} {dimanche.year}")

    return {
        'semaine_label': semaine_label,
        'date_lundi':    date_lundi_iso,
        'user': {
            'prenom':   user.get('prenom', '') if user else '',
            'nom':      user.get('nom', '') if user else '',
            'objectif': OBJECTIFS_LABELS.get(profil.get('objectif', ''), '—'),
        },
        'cible': {
            'calories':  int(cible_cal),
            'proteines': macros['proteines'],
            'glucides':  macros['glucides'],
            'lipides':   macros['lipides'],
        },
        'jours':    jours,
        'moyennes': moyennes,
        'sport': {
            'seances':    seances_sport,
            'total_cal':  round(sum(s['calories_brulees'] for s in seances_sport), 1),
            'total_min':  sum(s['duree_min'] for s in seances_sport),
            'nb_seances': len(seances_sport),
        },
        'adherence': {
            'jours_ok':         jours_ok,
            'jours_enregistres': nb_enr,
            'pct':              int(jours_ok / 7 * 100),
        },
    }
```

- [ ] **Étape 2 — Vérifier**

```bash
python -c "
import sys; sys.path.insert(0,'.')
import database as db
db.init_db()
from datetime import date, timedelta
lundi = date.today() - __import__('datetime').timedelta(days=date.today().weekday())
data = db.get_rapport_semaine(lundi.isoformat())
print('Semaine:', data['semaine_label'])
print('Jours:', len(data['jours']))
print('Sport séances:', data['sport']['nb_seances'])
print('Adhérence:', data['adherence']['pct'], '%')
"
```

Résultat attendu : pas d'exception, 7 jours retournés, valeurs cohérentes.

---

## Task 2 : `rapport.py` — Génération HTML

**Fichier :** `rapport.py` (nouveau, à la racine du projet)

- [ ] **Étape 1 — Créer `rapport.py`**

```python
# -*- coding: utf-8 -*-
"""NutriTrack Pro — Génération du rapport hebdomadaire HTML."""
import os
import tempfile
from datetime import date as _date

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, Arial, sans-serif; background: #f5f5f5; color: #1a1a1a; padding: 20px; }
.page { max-width: 920px; margin: 0 auto; background: white; border-radius: 12px;
        overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,.1); }
header { background: #0d1117; color: white; padding: 20px 28px;
         display: flex; justify-content: space-between; align-items: center; }
header h1 { font-size: 20px; }
header p  { font-size: 12px; opacity: .7; margin-top: 4px; }
.btn-print { background: #22c55e; color: #000; border: none; padding: 8px 18px;
             border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 13px; }
.kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
           padding: 20px 28px; background: #f8f9fa; }
.kpi { text-align: center; }
.kpi .val { font-size: 26px; font-weight: bold; color: #22c55e; }
.kpi .lbl { font-size: 11px; color: #666; margin-top: 3px; }
section { padding: 20px 28px; border-top: 1px solid #eee; }
section h2 { font-size: 15px; font-weight: bold; color: #333;
             border-left: 3px solid #22c55e; padding-left: 10px; margin-bottom: 14px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #0d1117; color: white; padding: 8px 10px; text-align: right;
     font-weight: 500; font-size: 12px; }
th:first-child { text-align: left; }
td { padding: 7px 10px; text-align: right; border-bottom: 1px solid #f0f0f0; }
td:first-child { text-align: left; font-weight: 500; }
tr.ok  td { background: #f0fdf4; }
tr.nok td { background: #fff5f5; }
tr.empty td { color: #bbb; font-style: italic; }
.badge { display: inline-block; padding: 1px 7px; border-radius: 10px;
         font-size: 10px; font-weight: bold; margin-left: 6px; }
.badge-ok  { background: #dcfce7; color: #16a34a; }
.badge-nok { background: #fee2e2; color: #dc2626; }
.sport-item { display: flex; justify-content: space-between; padding: 6px 0;
              border-bottom: 1px solid #f0f0f0; font-size: 13px; }
.sport-item:last-child { border-bottom: none; }
.progress-bar  { background: #eee; border-radius: 8px; height: 14px;
                 overflow: hidden; margin: 8px 0; }
.progress-fill { background: #22c55e; height: 100%; border-radius: 8px; }
footer { padding: 12px 28px; font-size: 11px; color: #aaa; text-align: center;
         border-top: 1px solid #eee; }
@media print {
  body { background: white; padding: 0; }
  .page { box-shadow: none; border-radius: 0; }
  .no-print { display: none !important; }
}
"""


def generer_rapport_html(data: dict) -> str:
    """Génère le HTML et retourne le chemin du fichier temporaire."""
    html = _build_html(data)
    fd, path = tempfile.mkstemp(suffix='.html', prefix='nutritrack_rapport_')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(html)
    return path


def _build_html(data: dict) -> str:
    user = data['user']
    nom  = f"{user.get('prenom','')} {user.get('nom','')}".strip() or "Utilisateur"

    moy   = data['moyennes']
    sport = data['sport']
    cible = data['cible']
    adh   = data['adherence']

    # ── KPI row ──────────────────────────────────────────────────
    eau_l   = round(moy.get('eau_ml', 0) / 1000, 1)
    kpis    = f"""
    <div class="kpi-row">
      <div class="kpi"><div class="val">{int(moy['calories'])}</div><div class="lbl">Calories moy./jour</div></div>
      <div class="kpi"><div class="val">{int(moy['proteines'])} g</div><div class="lbl">Protéines moy./jour</div></div>
      <div class="kpi"><div class="val">{eau_l} L</div><div class="lbl">Eau moy./jour</div></div>
      <div class="kpi"><div class="val">{sport['nb_seances']}</div><div class="lbl">Séances sport</div></div>
    </div>"""

    # ── Tableau journalier ────────────────────────────────────────
    rows_html = ""
    for j in data['jours']:
        if not j['enregistre']:
            css, badge = 'empty', ''
            vals = '<td>—</td>' * 6
        elif j['a_objectif']:
            css   = 'ok'
            badge = '<span class="badge badge-ok">✓ Objectif</span>'
            vals  = (f'<td>{int(j["calories"])}</td><td>{int(j["proteines"])} g</td>'
                     f'<td>{int(j["glucides"])} g</td><td>{int(j["lipides"])} g</td>'
                     f'<td>{int(j["fibres"])} g</td><td>{int(j["eau_ml"])} ml</td>')
        else:
            css   = 'nok'
            badge = '<span class="badge badge-nok">✗</span>'
            vals  = (f'<td>{int(j["calories"])}</td><td>{int(j["proteines"])} g</td>'
                     f'<td>{int(j["glucides"])} g</td><td>{int(j["lipides"])} g</td>'
                     f'<td>{int(j["fibres"])} g</td><td>{int(j["eau_ml"])} ml</td>')
        rows_html += f'<tr class="{css}"><td>{j["label"]}{badge}</td>{vals}</tr>'

    table_html = f"""
    <section>
      <h2>📅 Détail journalier</h2>
      <table>
        <thead><tr>
          <th>Jour</th>
          <th>Calories<br><small>cible {cible['calories']} kcal</small></th>
          <th>Protéines</th><th>Glucides</th><th>Lipides</th><th>Fibres</th><th>Eau</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </section>"""

    # ── Sport ─────────────────────────────────────────────────────
    if sport['seances']:
        items = "".join(
            f'<div class="sport-item">'
            f'<span>{s["label"]}</span>'
            f'<span>{s["date"][8:]}/{s["date"][5:7]} · {s["duree_min"]} min · {int(s["calories_brulees"])} kcal</span>'
            f'</div>'
            for s in sport['seances'])
        sport_html = f"""
    <section>
      <h2>🏃 Sport</h2>
      {items}
      <p style="margin-top:10px;font-size:12px;color:#666;">
        Total : {sport['nb_seances']} séance(s) · {sport['total_min']} min · {int(sport['total_cal'])} kcal brûlées
      </p>
    </section>"""
    else:
        sport_html = """
    <section>
      <h2>🏃 Sport</h2>
      <p style="color:#bbb;font-size:13px;">Aucune séance enregistrée cette semaine.</p>
    </section>"""

    # ── Adhérence ─────────────────────────────────────────────────
    pct        = adh['pct']
    pct_color  = '#16a34a' if pct >= 70 else ('#f59e0b' if pct >= 40 else '#dc2626')
    adh_html   = f"""
    <section>
      <h2>🎯 Adhérence à l'objectif calorique (±10 %)</h2>
      <p style="font-size:13px;color:#555;">
        {adh['jours_ok']} / {adh['jours_enregistres']} jours enregistrés dans l'objectif
      </p>
      <div class="progress-bar">
        <div class="progress-fill" style="width:{pct}%"></div>
      </div>
      <p style="font-size:14px;font-weight:bold;color:{pct_color};">{pct} %</p>
    </section>"""

    today = _date.today().strftime("%d/%m/%Y")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Bilan semaine — NutriTrack Pro</title>
<style>{_CSS}</style>
</head>
<body>
<div class="page">
  <header>
    <div>
      <h1>🥗 NutriTrack Pro — Bilan nutritionnel hebdomadaire</h1>
      <p>{nom} · {user.get('objectif','—')} · {data['semaine_label']}</p>
    </div>
    <button class="btn-print no-print" onclick="window.print()">🖨️ Imprimer</button>
  </header>
  {kpis}
  {table_html}
  {sport_html}
  {adh_html}
  <footer>Généré le {today} par NutriTrack Pro</footer>
</div>
</body>
</html>"""
```

- [ ] **Étape 2 — Vérifier la génération**

```bash
python -c "
import sys; sys.path.insert(0,'.')
import database as db, rapport as rp
db.init_db()
from datetime import date, timedelta
lundi = date.today() - timedelta(days=date.today().weekday())
data  = db.get_rapport_semaine(lundi.isoformat())
path  = rp.generer_rapport_html(data)
print('Rapport généré:', path)
import os; print('Taille:', os.path.getsize(path), 'octets')
"
```

Résultat attendu : chemin vers un fichier `.html` de quelques Ko, pas d'exception.

---

## Task 3 : `RapportDialog`

**Fichier :** `pages/rapport_dialog.py` (nouveau)

- [ ] **Étape 1 — Créer `pages/rapport_dialog.py`**

```python
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
```

---

## Task 4 : Bouton dans Stats

**Fichier :** `pages/stats.py`

- [ ] **Étape 1 — Ajouter le bouton dans `_build()`**

Dans `_build()`, dans le bloc `period_row`, après la boucle qui crée les boutons 7j/30j/90j :

```python
        # Séparateur visuel
        ctk.CTkFrame(period_row, width=1, fg_color=T["bg_el"]).pack(side="left", padx=8, fill="y")
        ctk.CTkButton(period_row, text="📄 Rapport",
                      width=90, height=32, corner_radius=8,
                      font=ctk.CTkFont(size=12),
                      fg_color=T["bg_card"], text_color=T["tx2"],
                      hover_color=T["ac_bg"],
                      command=self._open_rapport).pack(side="left", padx=3)
```

- [ ] **Étape 2 — Ajouter la méthode `_open_rapport()` dans `StatsPage`**

```python
    def _open_rapport(self):
        from pages.rapport_dialog import RapportDialog
        RapportDialog(self)
```

---

## Task 5 : Bouton dans Planning

**Fichier :** `pages/planning.py`

- [ ] **Étape 1 — Ajouter le bouton dans `_build()`**

Dans `_build()`, dans le bloc `right_btns`, après le bouton "📄 Exporter HTML" (et avant "🗑 Vider semaine") :

```python
        ctk.CTkButton(right_btns, text="📄  Rapport semaine",
                      font=ctk.CTkFont(size=12),
                      fg_color=T["bg_el"], hover_color=T["ac_bg"],
                      text_color=T["tx2"], height=34, width=150, corner_radius=8,
                      command=self._open_rapport).pack(side="left", padx=(0, 8))
```

- [ ] **Étape 2 — Ajouter la méthode `_open_rapport()` dans `PlanningPage`**

```python
    def _open_rapport(self):
        from pages.rapport_dialog import RapportDialog
        RapportDialog(self)
```

---

## Task 6 : Vérification finale

- [ ] **Lancer l'app et tester le flux complet**

```bash
python main.py
```

1. Stats → bouton "📄 Rapport" visible dans la barre de période
2. Cliquer → dialog s'ouvre, semaine courante affichée
3. Naviguer ◀/▶ → le label de semaine change
4. "Générer & ouvrir" → le navigateur s'ouvre avec le rapport HTML
5. Vérifier : KPIs, tableau 7 jours (vert/rouge/gris), section sport, barre d'adhérence
6. Cliquer "🖨️ Imprimer" → dialog d'impression du navigateur s'ouvre
7. Planning → même bouton visible et fonctionnel
