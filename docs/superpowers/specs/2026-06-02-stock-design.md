# Gestion de stock des aliments — Design Spec

**Date :** 2026-06-02
**Projet :** NutriTrack Pro v7
**Statut :** Approuvé

---

## Contexte et objectif

L'utilisateur veut gérer un garde-manger intelligent : savoir quels aliments il a physiquement chez lui, et utiliser cette information pour déterminer quelles recettes sont "faisables" immédiatement. La base `aliments` reste indépendante (base nutritionnelle pour les recettes) ; le `stock` est une couche distincte qui y fait référence.

**Flux principal :** J'ai du jarret de bœuf → le phở est faisable → je le planifie → l'app propose de déduire les ingrédients du stock après cuisson.

---

## 1. Base de données

### Nouvelle table `stock`

```sql
CREATE TABLE IF NOT EXISTS stock (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL,
    aliment_id       INTEGER REFERENCES aliments(id),
    quantite         REAL    DEFAULT 0,
    unite            TEXT    DEFAULT 'g',
    date_peremption  TEXT    NULL,        -- ISO date YYYY-MM-DD, facultatif
    notes            TEXT    DEFAULT '',
    updated_at       TEXT    DEFAULT ''
);
```

- Ajoutée dans `_migrate()` via `CREATE TABLE IF NOT EXISTS` (non destructif)
- Stock **per-user** (même modèle que `programmes`, `activites_sport`)
- Un aliment ne peut avoir qu'une entrée stock par utilisateur (contrainte gérée par `upsert_stock`)

### Fonctions dans `database.py`

| Fonction | Description |
|---|---|
| `get_stock(user_id)` | Liste complète du stock, jointure avec `aliments` pour le nom/catégorie |
| `upsert_stock(user_id, aliment_id, quantite, unite, date_peremption, notes)` | Insert ou update si l'aliment existe déjà pour ce user |
| `delete_stock(user_id, stock_id)` | Supprime une entrée stock |
| `deduct_stock(user_id, ingredients)` | Déduit une liste `[{aliment_id, quantite_g}]` du stock, plancher à 0, supprime les entrées à 0 |
| `get_stock_alerts(user_id, jours=3)` | Retourne les items périmés (date < today) ou expirant dans <= `jours` jours |
| `check_recette_faisable(recette_id, user_id)` | Retourne `{faisable: bool, manquants: [{nom, qte_requise, qte_stock, unite}]}` |

### Logique de `check_recette_faisable`

Pour chaque ingrédient de la recette :
1. Convertir `quantite` en grammes via `quantite_en_grammes()` (gère g, ml, unité×poids_unite_g, CAS, etc.)
2. Convertir la quantité stock en grammes via le même helper (l'unité stock peut différer de l'unité recette)
3. Chercher l'aliment dans le stock de l'utilisateur
4. Si absent ou quantité convertie insuffisante → manquant
5. `faisable = True` uniquement si zéro manquant

**Cas limite unités :** si le stock est en `unité` et la recette en `g`, la conversion utilise `poids_unite_g` de l'aliment. Si `poids_unite_g = 0`, l'ingrédient est considéré comme non comparable → ignoré (ni faisable ni manquant).

---

## 2. Page Stock (`pages/stock.py`)

### Structure

- Même pattern que les autres pages : frame scrollable, `refresh()` public
- Entrée sidebar : `("stock", "📦", "Stock")` entre Aliments et Recettes dans `main.py`

### Layout

```
┌─────────────────────────────────────────────────────┐
│  📦 Mon Stock          [+ Ajouter]  [🔍 Recherche]  │
├─────────────────────────────────────────────────────┤
│ ALERTES (si actives)                                │
│  🔴 Jarret de bœuf — périmé                         │
│  🟡 Poulet blanc — expire dans 2j                   │
├─────────────────────────────────────────────────────┤
│ Filtre catégorie : [Toutes ▼]                       │
├─────────────────────────────────────────────────────┤
│ Aliment          Qté    Unité   DLC      Statut      │
│ Poulet blanc     500    g       03/06    🟡 Bientôt  │
│ Riz blanc cuit   800    g       —        🟢 OK       │
│   [✏️] [🗑️]                                         │
└─────────────────────────────────────────────────────┘
```

### Codes couleur DLC

| Condition | Couleur | Label |
|---|---|---|
| date < aujourd'hui | 🔴 `err` | Périmé |
| date <= aujourd'hui + 3j | 🟡 `cal` | Bientôt |
| date > aujourd'hui + 3j | 🟢 `ac` | OK |
| pas de date | — | — |

### `StockDialog` (CTkToplevel)

Champs :
- Recherche aliment (parmi les aliments de la base, avec filtre live)
- Quantité (float)
- Unité : g / ml / unité / kg / L
- Date péremption JJ/MM/AAAA (optionnel)
- Notes (optionnel)

---

## 3. Intégration Recettes (`pages/recettes.py`)

### Badge sur chaque carte

- `check_recette_faisable()` appelé au `refresh()`
- **✅ Faisable** (vert) si tous les ingrédients présents en quantité suffisante
- **⚠️ N manquant(s)** (orange) si ingrédients insuffisants — clic ouvre mini-dialog listant les manquants
- **— Stock non géré** (gris) si le stock est vide (aucun aliment saisi par l'utilisateur)

### Filtre

Bouton toggle **"Faisables uniquement"** en haut de page — masque les recettes avec manquants.

---

## 4. Intégration Planning (`pages/planning.py`)

### Sélection de recette

Dans le dialog d'ajout de repas, la liste des recettes est triée : faisables (✅) en tête, autres (⚠️) en dessous.

### Dialog de déduction semi-auto

Bouton **"Marquer comme cuisinée"** sur les repas planifiés de type recette.

```
┌─────────────────────────────────────────────────────┐
│  Recette cuisinée — déduire du stock ?              │
│                                                     │
│  Phở bœuf & os à moelle (4 portions)               │
│                                                     │
│  ✅ Jarret de bœuf      400g  → reste 100g          │
│  ✅ Nouilles de riz     300g  → reste 200g          │
│  ⚠️ Gingembre frais    60g   → stock 0g (insuffisant)│
│  —  Anis étoilé         8g   → non géré             │
│                                                     │
│  [Déduire le disponible]        [Ignorer]           │
└─────────────────────────────────────────────────────┘
```

**Règles métier :**
- Ingrédients absents du stock → ignorés (pas d'erreur)
- Ingrédients insuffisants → déduits jusqu'à 0, entrée supprimée
- Pas de stock négatif
- Bouton visible uniquement sur les repas liés à une recette (pas les repas libres)
- Le bouton déclenche uniquement le dialog de déduction — aucun état "cuisinée" n'est persisté dans `planning_repas` (hors scope)

---

## 5. Intégration Dashboard (`pages/dashboard.py`)

Carte **"Stock — Alertes péremption"** conditionnelle :
- Absente si `get_stock_alerts()` retourne une liste vide
- Présente si au moins un aliment périmé ou expirant dans 3 jours
- Lien "Voir le stock →" navigue vers la page Stock via callback

---

## Fichiers modifiés

| Fichier | Modification |
|---|---|
| `database.py` | Table `stock` dans `_migrate()` + 6 fonctions |
| `pages/stock.py` | Nouveau fichier — page complète + `StockDialog` |
| `pages/recettes.py` | Badges faisabilité + filtre "Faisables uniquement" |
| `pages/planning.py` | Tri recettes + dialog déduction semi-auto |
| `pages/dashboard.py` | Carte alertes péremption conditionnelle |
| `main.py` | Import + entrée sidebar `📦 Stock` |

---

## Hors scope

- Historique des mouvements de stock
- Emplacements physiques (Frigo / Placard / Congélateur)
- Déduction automatique depuis le Journal alimentaire
- Synchronisation cloud du stock
