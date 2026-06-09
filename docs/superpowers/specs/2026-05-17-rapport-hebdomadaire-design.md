# Design — Rapport hebdomadaire

**Date :** 2026-05-17
**Projet :** NutriTrack Pro
**Statut :** Approuvé

## Contexte

Export HTML d'un bilan nutritionnel + sport de la semaine, déclenché depuis Stats ou Planning. Source : journal alimentaire (`journal_repas`). Format : HTML/CSS auto-suffisant avec bouton d'impression natif.

## Nouveau fichier : `rapport.py`

Fonction principale :

```python
def generer_rapport_html(data: dict) -> str:
    # Reçoit le dict de get_rapport_semaine()
    # Retourne le chemin vers le fichier HTML temporaire créé
    # Utilise tempfile.mkstemp(suffix='.html')
```

Le HTML est entièrement auto-suffisant (CSS inline, aucune dépendance réseau). Palettes : couleurs vives pour l'écran, noir/blanc pour l'impression via `@media print`. Le bouton "🖨️ Imprimer" appelle `window.print()` et est masqué à l'impression.

## Nouvelle fonction dans `database.py`

```python
def get_rapport_semaine(date_lundi_iso: str) -> dict:
```

Retourne :
```python
{
  'semaine_label': 'Semaine du 12 au 18 mai 2026',
  'date_lundi': '2026-05-12',
  'user': {'prenom': str, 'nom': str, 'objectif': str},
  'cible': {'calories': int, 'proteines': int, 'glucides': int, 'lipides': int},
  'jours': [   # 7 dicts, lundi → dimanche
    {
      'date': str,           # ISO
      'label': str,          # 'Lundi 12 mai'
      'calories': float,
      'proteines': float,
      'glucides': float,
      'lipides': float,
      'fibres': float,
      'eau_ml': int,
      'a_objectif': bool,    # calories dans ±10% de la cible
      'enregistre': bool,    # au moins 1 entrée journal ce jour
    }
  ],
  'moyennes': {              # sur les jours enregistrés uniquement
    'calories': float, 'proteines': float,
    'glucides': float, 'lipides': float, 'eau_ml': float
  },
  'sport': {
    'seances': [             # liste des activites_sport de la semaine
      {'label': str, 'date': str, 'duree_min': int, 'calories_brulees': float}
    ],
    'total_cal': float,
    'total_min': int,
    'nb_seances': int,
  },
  'adherence': {
    'jours_ok': int,         # jours à l'objectif ±10%
    'jours_enregistres': int,
    'pct': int,              # % arrondi
  }
}
```

Agrégation via `journal_repas` (même logique que `get_nutri_journal_jour()`). Eau via `suivi_eau`. Sport via `activites_sport`.

## Structure HTML générée

```
En-tête  : Logo NutriTrack Pro | Nom utilisateur | Semaine | [🖨️ Imprimer]
KPI row  : 4 cards — Calories moy. / Protéines moy. / Eau moy. / Séances sport
Tableau  : 7 lignes (Lun→Dim) × colonnes Cal/Prot/Gluc/Lip/Fibres/Eau
           Fond vert si a_objectif, rouge pâle si enregistré mais hors objectif,
           gris si non enregistré
Sport    : Liste des séances + Total min + Total kcal brûlées
Adhérence: Barre de progression CSS + "5/7 jours à l'objectif (71 %)"
Pied     : "Généré par NutriTrack Pro le 2026-05-17"
```

## Interface utilisateur

### `RapportDialog` (nouveau — `pages/rapport_dialog.py` ou inline dans stats/planning)

CTkToplevel 420×200 px, commun aux deux pages :
- Sélecteur semaine : `◀  Semaine du 12 mai 2026  ▶`
  - ◀/▶ déplacent d'une semaine
  - Par défaut : semaine en cours (lundi de la semaine actuelle)
- Bouton "📄 Générer & ouvrir" → `get_rapport_semaine()` + `generer_rapport_html()` + `webbrowser.open(path)`
- Gestion d'erreur : si aucune donnée journal pour la semaine → message "Aucune donnée enregistrée pour cette semaine."

### Déclencheur dans `pages/stats.py`

Bouton "📄 Rapport semaine" ajouté dans la zone du sélecteur de période (en-tête), à droite des boutons 7j/30j/90j.

### Déclencheur dans `pages/planning.py`

Bouton "📄 Rapport semaine" ajouté dans la barre de navigation de la page Planning, à côté des boutons existants (🛒 Liste de courses, 📄 Export HTML).

## Fichiers impactés

| Fichier | Modification |
|---|---|
| `rapport.py` | Nouveau — génération HTML |
| `database.py` | Nouvelle fonction `get_rapport_semaine()` |
| `pages/stats.py` | Ajout bouton + `RapportDialog` |
| `pages/planning.py` | Ajout bouton + `RapportDialog` |
