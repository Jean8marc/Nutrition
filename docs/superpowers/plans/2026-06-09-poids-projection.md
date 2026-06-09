# Feature #16 — Graphique poids × objectif long terme — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Afficher une courbe projetée jusqu'au poids cible (avec date estimée) dans le graphique Profil et dans une carte Dashboard, basée sur le déficit calorique moyen réel du journal ou sur le programme actif en fallback.

**Architecture:** Nouvelle fonction `get_projection_poids()` dans `database.py` centralise tout le calcul (déficit, taux hebdo, série de points, date d'atteinte). `profil.py._draw_chart()` est réécrit pour utiliser un axe X en vraies dates et afficher la courbe projetée. `dashboard.py._draw_charts()` remplace la carte "Poids 30j" existante par la carte projection enrichie.

**Tech Stack:** Python 3.9+, matplotlib (déjà importé), CustomTkinter, SQLite via `database.py`

---

## Fichiers modifiés

| Fichier | Nature |
|---|---|
| `database.py` | Nouvelle fonction `get_projection_poids()` après `get_reequilibrage_data()` (~2290) |
| `pages/profil.py` | Remplacement complet de `_draw_chart()` (~607) |
| `pages/dashboard.py` | Remplacement du bloc poids dans `_draw_charts()` (~348-388) |

---

## Task 1 — `get_projection_poids()` dans `database.py`

**Files:**
- Modify: `database.py` (après la ligne 2283, fin de `apply_reequilibrage`)

- [ ] **Step 1 : Ajouter la fonction dans `database.py`**

Insérer après la ligne 2283 (après `apply_reequilibrage`) :

```python
def get_projection_poids() -> dict:
    """
    Projette la courbe de poids jusqu'au poids cible.
    Déficit basé sur le journal réel (si >= 7 jours de données) ou le programme actif.
    Retourne une série de points hebdomadaires depuis aujourd'hui.
    """
    _empty = {
        "has_cible": False, "poids_actuel": 0.0, "poids_cible": 0.0,
        "deficit_jour": 0.0, "kg_par_semaine": 0.0, "source": "none",
        "date_atteinte": None, "jours_restants": None, "points": [],
    }

    profil = get_current_user()
    if not profil:
        return _empty

    poids_cible = float(profil.get("poids_cible") or 0)
    has_cible   = poids_cible > 0

    # Poids de départ : dernier suivi_poids ou valeur du profil
    recents      = get_suivi_poids(limit=1, frequence="tous")
    poids_actuel = float(recents[0]["poids"]) if recents else float(profil.get("poids") or 70)

    if not has_cible:
        return {**_empty, "poids_actuel": round(poids_actuel, 1)}

    # TDEE en mode maintien
    tdee = calc_calories_cible({**dict(profil), "objectif": "maintien"})

    # Source du déficit : journal réel si >= 7 jours, sinon programme
    adherence = get_adherence_stats(90)
    if adherence.get("jours", 0) >= 7:
        deficit_jour = float(adherence["avg_cal"]) - tdee
        source       = "journal"
    else:
        prog = get_programme_actif()
        if prog:
            deficit_jour = int(prog["calories_jour"]) - tdee
            source       = "programme"
        else:
            deficit_jour = 0.0
            source       = "none"

    kg_par_semaine = deficit_jour * 7 / 7700

    # Direction correcte ?
    en_perte    = poids_cible < poids_actuel
    en_prise    = poids_cible > poids_actuel
    bonne_dir   = (en_perte and kg_par_semaine < 0) or (en_prise and kg_par_semaine > 0)

    base = {
        "has_cible":      True,
        "poids_actuel":   round(poids_actuel, 1),
        "poids_cible":    poids_cible,
        "deficit_jour":   round(deficit_jour, 0),
        "kg_par_semaine": round(kg_par_semaine, 3),
        "source":         source,
    }

    if kg_par_semaine == 0 or not bonne_dir:
        return {**base, "date_atteinte": None, "jours_restants": None, "points": []}

    # Objectif déjà atteint
    if (en_perte and poids_actuel <= poids_cible) or (en_prise and poids_actuel >= poids_cible):
        today_str = date.today().isoformat()
        return {**base, "date_atteinte": today_str, "jours_restants": 0,
                "points": [{"date": today_str, "poids": round(poids_actuel, 1)}]}

    # Projection semaine par semaine (max 52 semaines)
    today  = date.today()
    points = []
    for i in range(1, 53):
        poids_proj = round(poids_actuel + kg_par_semaine * i, 2)
        pt_date    = today + timedelta(weeks=i)
        points.append({"date": pt_date.isoformat(), "poids": poids_proj})
        if (en_perte and poids_proj <= poids_cible) or (en_prise and poids_proj >= poids_cible):
            break

    date_atteinte = points[-1]["date"] if points else None
    jours_restants = (date.fromisoformat(date_atteinte) - today).days if date_atteinte else None

    return {**base, "date_atteinte": date_atteinte, "jours_restants": jours_restants,
            "points": points}
```

- [ ] **Step 2 : Vérifier la fonction avec un script rapide**

Créer `verify_projection.py` à la racine du projet :

```python
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import database as db

# Simuler un utilisateur connecté (adapter l'ID si besoin)
users = db.get_connection().execute("SELECT id, prenom FROM users LIMIT 3").fetchall()
for u in users:
    db.set_current_user(u["id"])
    r = db.get_projection_poids()
    print(f"\n=== {u['prenom']} (id={u['id']}) ===")
    print(f"  poids_actuel   : {r['poids_actuel']} kg")
    print(f"  poids_cible    : {r['poids_cible']} kg  (has_cible={r['has_cible']})")
    print(f"  deficit_jour   : {r['deficit_jour']} kcal  source={r['source']}")
    print(f"  kg_par_semaine : {r['kg_par_semaine']}")
    print(f"  date_atteinte  : {r['date_atteinte']}  ({r['jours_restants']} jours)")
    print(f"  points         : {len(r['points'])} semaines")
    if r['points']:
        print(f"    premier: {r['points'][0]}")
        print(f"    dernier: {r['points'][-1]}")
```

Lancer :
```
python verify_projection.py
```

Résultat attendu : pour chaque utilisateur avec `poids_cible > 0`, une série de `points` avec des dates futures hebdomadaires et un `poids` décroissant (ou croissant) vers `poids_cible`. Pour les utilisateurs sans cible, `has_cible=False` et `points=[]`.

- [ ] **Step 3 : Supprimer `verify_projection.py` puis committer**

```bash
del verify_projection.py
git add database.py
git commit -m "feat: add get_projection_poids() — weight projection DB function"
```

---

## Task 2 — Extension de `_draw_chart()` dans `pages/profil.py`

**Files:**
- Modify: `pages/profil.py` — remplacer la méthode `_draw_chart` (lignes ~607-681)

La méthode `_draw_chart` se trouve dans la classe `SuiviPoidsSection` (ou similaire) de `profil.py`. Elle prend `data` (liste de dicts `suivi_poids`).

- [ ] **Step 1 : Remplacer `_draw_chart` dans `pages/profil.py`**

Localiser la méthode (ligne ~607) et la remplacer **intégralement** par :

```python
def _draw_chart(self, data):
    from datetime import datetime as _dt
    poids_vals  = [d['poids'] for d in data]
    taille_vals = [d.get('tour_de_taille') or 0 for d in data]
    has_taille  = any(t > 0 for t in taille_vals)

    # Axe X en vraies dates matplotlib
    raw_labels = [d['date'][:10] for d in data]
    try:
        x_hist = [mdates.date2num(_dt.strptime(lb, "%Y-%m-%d")) for lb in raw_labels]
    except ValueError:
        x_hist = list(range(len(raw_labels)))

    plt.rcParams.update({
        'figure.facecolor': T["bg_card"],
        'axes.facecolor':   T["bg_row"],
        'axes.edgecolor':   T["bg_hl"],
        'axes.labelcolor':  T["tx2"],
        'xtick.color':      T["tx2"],
        'ytick.color':      T["tx2"],
        'grid.color':       T["bg_el"],
        'grid.linestyle':   '--',
        'grid.alpha':       0.7,
    })

    if has_taille:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6, 4.5), sharex=True)
        fig.patch.set_facecolor(T["bg_card"])
    else:
        fig, ax1 = plt.subplots(1, 1, figsize=(6, 3.2))
        ax2 = None
        fig.patch.set_facecolor(T["bg_card"])

    # Courbe poids historique
    ax1.plot(x_hist, poids_vals, color=T["blue"], linewidth=2.5,
             marker="o", markersize=4, markerfacecolor=T["blue_l"])
    ax1.fill_between(x_hist, poids_vals,
                     [min(poids_vals) - 0.5] * len(poids_vals),
                     color=T["blue"], alpha=0.12)

    # Projection
    proj   = db.get_projection_poids()
    target = proj.get("poids_cible", 0.0)

    if proj.get("has_cible") and proj.get("points"):
        pts    = proj["points"]
        x_proj = [mdates.date2num(_dt.strptime(p["date"], "%Y-%m-%d")) for p in pts]
        y_proj = [p["poids"] for p in pts]
        # Relier depuis le dernier point historique
        x_proj = [x_hist[-1]] + x_proj
        y_proj = [poids_vals[-1]] + y_proj

        ax1.plot(x_proj, y_proj, color=T["ac"], linewidth=1.8,
                 linestyle="--", alpha=0.85, label="Projection")
        ax1.fill_between(x_proj,
                         [y - 0.5 for y in y_proj],
                         [y + 0.5 for y in y_proj],
                         color=T["ac"], alpha=0.07)
        ax1.plot(x_proj[-1], y_proj[-1], marker="*", markersize=10,
                 color=T["ac"], zorder=5)
        date_atteinte = proj.get("date_atteinte", "")
        if date_atteinte:
            date_courte = _dt.strptime(date_atteinte, "%Y-%m-%d").strftime("%b %Y")
            ax1.annotate(f"~{date_courte}",
                         xy=(x_proj[-1], y_proj[-1]),
                         xytext=(0, 10), textcoords="offset points",
                         fontsize=8, color=T["ac"], ha="center")

    # Ligne objectif (pointillée fine pour ne pas écraser la projection)
    if target > 0:
        ax1.axhline(y=target, color=T["ac"], linewidth=1.2,
                    linestyle=":", alpha=0.5,
                    label=f"Objectif : {target} kg")

    ax1.legend(fontsize=8, framealpha=0.3, facecolor=T["bg_el"],
               labelcolor=T["tx1"])
    ax1.set_ylabel("Poids (kg)", fontsize=9, color=T["tx2"])
    ax1.grid(True)
    ax1.set_facecolor(T["bg_row"])

    # Tour de taille
    if ax2 is not None:
        non_zero = [(xi, t) for xi, t in zip(x_hist, taille_vals) if t > 0]
        if non_zero:
            xi_l, ti_l = zip(*non_zero)
            ax2.plot(list(xi_l), list(ti_l), color=T["lip"], linewidth=2,
                     marker="s", markersize=4, markerfacecolor="#fbbf24")
            ax2.fill_between(list(xi_l), list(ti_l),
                             [min(ti_l) - 0.5] * len(ti_l),
                             color=T["lip"], alpha=0.10)
        ax2.set_ylabel("Tour de taille (cm)", fontsize=9, color=T["tx2"])
        ax2.grid(True)
        ax2.set_facecolor(T["bg_row"])

    # Axe X en dates réelles
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=8))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    fig.autofmt_xdate(rotation=30)
    for tick in ax1.xaxis.get_major_ticks():
        tick.label1.set_fontsize(8)

    fig.tight_layout(pad=1.2)
    canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
    plt.close(fig)

    # Message si pas de poids cible
    if not proj.get("has_cible"):
        ctk.CTkLabel(
            self.chart_frame,
            text="Définissez un poids cible dans Profil > Informations\npour voir la projection",
            font=ctk.CTkFont(size=9),
            text_color=T["tx2"],
            justify="center",
        ).pack(pady=(0, 8))
```

Note : `mdates` est déjà importé en haut de `profil.py` (`import matplotlib.dates as mdates`). Pas besoin d'import supplémentaire.

- [ ] **Step 2 : Lancer l'app et vérifier visuellement**

```
python launch.py
```

Aller dans **Mon Profil** → onglet suivi poids.

Vérifier :
- Si l'utilisateur a un `poids_cible` et des mesures : courbe bleue historique + courbe verte pointillée projetée + étoile + annotation date
- Si l'utilisateur n'a pas de `poids_cible` : graphique historique seul + label texte en dessous
- L'axe X affiche des dates réelles (`JJ/MM`) et non plus des entiers
- La courbe tour de taille (si données) s'affiche toujours correctement

- [ ] **Step 3 : Committer**

```bash
git add pages/profil.py
git commit -m "feat: extend profil _draw_chart with weight projection curve"
```

---

## Task 3 — Carte projection dans `pages/dashboard.py`

**Files:**
- Modify: `pages/dashboard.py` — remplacer le bloc poids dans `_draw_charts()` (lignes ~348-388)

- [ ] **Step 1 : Remplacer le bloc "Poids 30 derniers jours" dans `_draw_charts()`**

Localiser dans `_draw_charts()` le bloc qui commence par :
```python
        # ── Courbe poids 30 jours ────────────────────────────────
        pc = _card(self.charts_row, "⚖️  Poids — 30 derniers jours")
```
et se termine par `_spacer(pc, 2)`.

Remplacer **ce bloc entier** par :

```python
        # ── Carte progression poids ──────────────────────────────
        from datetime import datetime as _dt
        import matplotlib.dates as _mdates

        proj      = db.get_projection_poids()
        poids_data = db.get_suivi_poids(limit=90, frequence="tous")
        titre_pc  = "📈  Progression vers l'objectif" if proj.get("has_cible") else "⚖️  Poids — 90 derniers jours"
        pc = _card(self.charts_row, titre_pc)
        pc.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        if len(poids_data) >= 2:
            chart_p = ctk.CTkFrame(pc, fg_color="transparent", height=200)
            chart_p.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="ew")
            chart_p.grid_propagate(False)

            try:
                x_hist = [_mdates.date2num(_dt.strptime(d['date'][:10], "%Y-%m-%d"))
                           for d in poids_data]
            except ValueError:
                x_hist = list(range(len(poids_data)))
            ys = [d['poids'] for d in poids_data]

            fig, ax = plt.subplots(figsize=(5, 2.2))
            fig.patch.set_facecolor(T["bg_card"])
            ax.plot(x_hist, ys, color=T["blue"], linewidth=2,
                    marker="o", markersize=3, markerfacecolor=T["blue_l"])
            ax.fill_between(x_hist, ys, [min(ys) - 0.5] * len(ys),
                             color=T["blue"], alpha=0.1)

            # Projection plafonnée à 26 semaines (6 mois) pour la carte compacte
            if proj.get("has_cible") and proj.get("points"):
                pts    = proj["points"][:26]
                x_proj = [_mdates.date2num(_dt.strptime(p["date"], "%Y-%m-%d")) for p in pts]
                y_proj = [p["poids"] for p in pts]
                x_proj = [x_hist[-1]] + x_proj
                y_proj = [ys[-1]] + y_proj
                ax.plot(x_proj, y_proj, color=T["ac"], linewidth=1.5,
                        linestyle="--", alpha=0.85)
                ax.plot(x_proj[-1], y_proj[-1], marker="*", markersize=8,
                        color=T["ac"], zorder=5)

            target = proj.get("poids_cible", 0.0)
            if target > 0:
                ax.axhline(target, color=T["ac"], linewidth=1.0,
                           linestyle=":", alpha=0.7)

            ax.xaxis.set_major_locator(_mdates.AutoDateLocator(maxticks=6))
            ax.xaxis.set_major_formatter(_mdates.DateFormatter("%d/%m"))
            fig.autofmt_xdate(rotation=30)
            for tick in ax.xaxis.get_major_ticks():
                tick.label1.set_fontsize(7)
            ax.set_ylabel("kg", fontsize=8)
            ax.grid(True)
            fig.tight_layout(pad=0.8)

            canvas = FigureCanvasTkAgg(fig, master=chart_p)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
            plt.close(fig)

            # KPI sous le graphe
            if proj.get("has_cible"):
                kpi = ctk.CTkFrame(pc, fg_color="transparent")
                kpi.grid(row=2, column=0, padx=12, pady=(0, 2), sticky="ew")
                kpi.grid_columnconfigure((0, 1), weight=1)

                ctk.CTkLabel(kpi,
                             text=f"{proj['poids_actuel']} kg → {proj['poids_cible']} kg",
                             font=ctk.CTkFont(size=11, weight="bold"),
                             text_color=T["tx1"]).grid(row=0, column=0, sticky="w")

                if proj.get("jours_restants") and proj["jours_restants"] > 0:
                    sem = proj["jours_restants"] // 7
                    ctk.CTkLabel(kpi, text=f"~{sem} sem.",
                                 font=ctk.CTkFont(size=11, weight="bold"),
                                 text_color=T["ac"]).grid(row=0, column=1, sticky="e")

                signe      = "−" if proj["deficit_jour"] < 0 else "+"
                deficit_abs = abs(int(proj.get("deficit_jour", 0)))
                source_lbl  = " (prog.)" if proj.get("source") == "programme" else ""
                ctk.CTkLabel(pc,
                             text=f"{signe}{deficit_abs} kcal/j{source_lbl}  ·  {proj['kg_par_semaine']:+.2f} kg/sem",
                             font=ctk.CTkFont(size=10),
                             text_color=T["tx2"]).grid(
                    row=3, column=0, padx=12, pady=(0, 10), sticky="w")
                _spacer(pc, 4)
            else:
                ctk.CTkLabel(pc,
                             text="Définissez un poids cible dans Mon Profil",
                             font=ctk.CTkFont(size=10),
                             text_color=T["tx2"]).grid(
                    row=2, column=0, padx=12, pady=(0, 10))
                _spacer(pc, 3)
        else:
            ctk.CTkLabel(pc,
                         text="Enregistrez votre poids\ndans Mon Profil pour voir la courbe",
                         font=ctk.CTkFont(size=11), text_color=T["tx2"],
                         justify="center").grid(row=1, column=0, pady=30)
            _spacer(pc, 2)
```

Note : `T["blue_l"]` est utilisé ici — vérifier qu'il existe dans le thème actif (`theme.py`). Si absent, remplacer par `T["blue"]`.

- [ ] **Step 2 : Vérifier que `T["blue_l"]` existe**

```
python -c "from theme import T; print(T.get('blue_l', 'ABSENT'))"
```

Si `ABSENT` : remplacer `T["blue_l"]` par `T["blue"]` dans le bloc dashboard ci-dessus.

- [ ] **Step 3 : Lancer l'app et vérifier visuellement**

```
python launch.py
```

Aller dans **Tableau de bord**.

Vérifier :
- Carte "📈 Progression vers l'objectif" remplace la carte "Poids 30j"
- Mini-graphe avec courbe bleue + projection verte pointillée + étoile
- Ligne horizontale pointillée au niveau du poids cible
- KPI row : `75.x kg → 70 kg` | `~18 sem.`
- Ligne déficit : `−350 kcal/j · −0.32 kg/sem`
- Si `source == "programme"` : `−350 kcal/j (prog.) · −0.32 kg/sem`
- Carte "Calories journal — 14 jours" (droite) inchangée

- [ ] **Step 4 : Committer**

```bash
git add pages/dashboard.py
git commit -m "feat: replace weight chart with projection card in dashboard"
```

---

## Task 4 — Push et mise à jour backlog

- [ ] **Step 1 : Push**

```bash
git push origin master
```

- [ ] **Step 2 : Marquer la feature comme implémentée dans `CLAUDE.md`**

Dans le tableau **Backlog**, supprimer la ligne :
```
| 16 | **Graphique poids × objectif long terme** | ... | Haute |
```

Dans le tableau **Features déjà implémentées**, ajouter :
```
| 16 | **Graphique poids × objectif long terme** — projection hebdo jusqu'au poids cible, carte Dashboard compacte, axe X en vraies dates dans Profil | Session 9 |
```

- [ ] **Step 3 : Committer CLAUDE.md**

```bash
git add CLAUDE.md
git commit -m "docs: mark feature #16 as implemented in CLAUDE.md"
git push origin master
```

---

## Self-Review

**Couverture spec :**
- ✅ `get_projection_poids()` : déficit journal/programme, série hebdo, date atteinte, cas limites
- ✅ Profil `_draw_chart` : axe X dates réelles, courbe projetée, zone ±0.5, étoile, annotation
- ✅ Dashboard : carte compacte 90j + projection 6 mois max, KPI row, source label
- ✅ Cas sans poids cible : label dans Profil et Dashboard
- ✅ Cas `source == "programme"` : label `(prog.)` dans KPI dashboard
- ✅ Plafond 52 semaines (DB) / 26 semaines (dashboard)

**Placeholders :** aucun

**Cohérence des types :**
- `proj["points"]` → `list[dict]` avec clés `"date"` (str ISO) et `"poids"` (float) — utilisé de manière identique dans Tasks 2 et 3
- `proj["deficit_jour"]` → `float` — formaté avec `int()` + `abs()` dans Task 3 ✅
- `proj["kg_par_semaine"]` → `float` — formaté avec `{:+.2f}` ✅
- `proj["jours_restants"]` → `int | None` — vérifié `and proj["jours_restants"] > 0` avant calcul semaines ✅
