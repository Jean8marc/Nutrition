# Spec — Feature #16 : Graphique poids × objectif long terme

**Date :** 2026-06-09
**Priorité :** Haute
**Périmètre :** `database.py` + `pages/profil.py` + `pages/dashboard.py`

---

## Objectif

Ajouter une courbe projetée sur le graphique poids existant indiquant quand l'utilisateur atteindra son poids cible, basée sur son déficit calorique moyen réel (journal) ou théorique (programme actif en fallback).

---

## 1. Couche données — `get_projection_poids()`

### Emplacement
`database.py`, après `get_reequilibrage_data()`.

### Algorithme

1. Charger profil courant (`poids`, `poids_cible`, sexe, âge, taille, activite)
2. Calculer TDEE : `calc_calories_cible({...profil, objectif: 'maintien'})`
3. Choisir la source du déficit :
   - Appeler `get_adherence_stats(90)` → si `jours >= 7` : `deficit_jour = avg_cal − TDEE` (source `"journal"`)
   - Sinon : `deficit_jour = programme.calories_jour − TDEE` (source `"programme"`) ; si pas de programme actif : `deficit_jour = 0`
4. Taux de variation : `kg_par_semaine = deficit_jour * 7 / 7700`
5. Poids de départ : dernier enregistrement `suivi_poids` ou `profil.poids`
6. Projeter semaine par semaine depuis aujourd'hui :
   - Arrêter quand `poids_proj <= poids_cible` (perte) ou `poids_proj >= poids_cible` (prise de masse)
   - Arrêter après 52 semaines (12 mois max)
7. Calculer `date_atteinte` et `jours_restants` à partir du nombre de semaines

### Valeur retournée

```python
{
  "poids_actuel":   float,      # dernier suivi_poids ou profil.poids
  "poids_cible":    float,      # 0.0 si non défini
  "has_cible":      bool,       # poids_cible > 0
  "deficit_jour":   float,      # kcal/j (négatif = déficit, positif = surplus)
  "kg_par_semaine": float,      # variation hebdomadaire projetée
  "source":         str,        # "journal" | "programme" | "none"
  "date_atteinte":  str | None, # date ISO ou None si inaccessible / déjà atteint
  "jours_restants": int | None,
  "points":         [{"date": str, "poids": float}, ...]  # série hebdo depuis aujourd'hui
}
```

### Cas limites
- `poids_cible == 0` → `has_cible=False`, `points=[]`, `date_atteinte=None`
- `deficit_jour == 0` ou direction opposée à l'objectif → `points=[]`, `date_atteinte=None`
- Objectif déjà atteint (`poids_actuel <= poids_cible` en perte) → `jours_restants=0`, `date_atteinte=aujourd'hui`

---

## 2. Page Profil — extension de `_draw_chart()`

### Modifications dans `pages/profil.py`

La méthode `_draw_chart(data)` appelle `db.get_projection_poids()` en début de méthode.

**Axe X :** remplacer `range(len(labels))` par de vraies dates `matplotlib.dates` (`mdates.date2num`) pour que l'axe temporel soit continu et que la projection future s'aligne correctement.

**Courbe projetée (si `has_cible=True` et `points` non vides) :**
- Ligne pointillée couleur `T["ac"]`, `linewidth=1.8`, `linestyle="--"`, `alpha=0.85`, label `"Projection"`
- Zone d'incertitude : `fill_between` ±0.5 kg, `color=T["ac"]`, `alpha=0.07`
- Marqueur d'arrivée : `marker="*"`, `markersize=10` sur le dernier point projeté
- Annotation flottante : `"Objectif ~{date_atteinte_courte}"` (ex: `"jan. 2026"`) positionnée au-dessus du marqueur

**Légende :** enrichie avec `"Projection"` (ligne verte pointillée).

**Cas sans poids cible (`has_cible=False`) :**
Un `CTkLabel` texte `T["tx2"]`, fontsize 9, centré sous le graphique :
`"Définissez un poids cible dans Profil > Informations pour voir la projection"`

**Pas de changement** sur la courbe historique, la courbe tour de taille, ni la ligne `axhline` objectif existante.

---

## 3. Dashboard — carte compacte

### Emplacement
`pages/dashboard.py` — nouvelle méthode `_build_weight_card(parent)`, appelée dans `_build_right_column()` (ou colonne gauche selon l'espace disponible, à déterminer en lisant le layout existant).

La carte est **masquée** si `get_suivi_poids(limit=2)` est vide (aucune mesure enregistrée).

### Structure visuelle

```
┌─────────────────────────────────────────┐
│  📈  Progression vers l'objectif        │
│                                         │
│  [mini graphique Matplotlib ~280×130px] │
│   courbe réelle (bleue)                 │
│   projection (verte pointillée)         │
│   ligne cible horizontale               │
│                                         │
│  75.2 kg → 70 kg  |  ~18 semaines      │
│  Déficit ~350 kcal/j · −0.32 kg/sem    │
│                                         │
│  [si pas de cible]                      │
│  "Définissez un poids cible"            │
└─────────────────────────────────────────┘
```

### Détails

- Mini-graphe : affiche les **90 derniers jours** de poids réel + projection jusqu'à l'objectif (plafonnée à 6 mois pour ne pas écraser la carte)
- KPI row sous le graphe : 4 `CTkLabel` — poids actuel → cible, semaines restantes, déficit moyen, rythme kg/semaine
- Si `has_cible=False` : mini-graphe seul + label "Définissez un poids cible" à la place des KPIs
- Si `source == "programme"` : KPI déficit accompagné d'un label secondaire `"(objectif programme)"` pour distinguer du réel

---

## Fichiers modifiés

| Fichier | Nature |
|---|---|
| `database.py` | Nouvelle fonction `get_projection_poids()` |
| `pages/profil.py` | Extension `_draw_chart()` + axe X en dates réelles |
| `pages/dashboard.py` | Nouvelle méthode `_build_weight_card()` + appel dans le layout |

---

## Ce qui ne change pas

- Table `suivi_poids` — aucune modification de schéma
- Logique de saisie/suppression de mesures dans Profil
- `get_reequilibrage_data()` — utilisé séparément dans Programmes, non touché
- Formule 7700 kcal/kg déjà établie dans le projet
