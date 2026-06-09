# Stock v2 — Cycle complet garde-manger — Design Spec

**Date :** 2026-06-02
**Projet :** NutriTrack Pro v7
**Statut :** Approuvé
**Dépend de :** spec `2026-06-02-stock-design.md` (stock v1 déjà implémenté)

---

## Contexte et objectif

Le stock v1 existe (table `stock`, page `📦 Stock`, badges recettes, déduction planning). Ce spec étend le stock en **cycle de vie complet** :
- **Entrée** : depuis le scan, la page Aliments, ou le journal (sans ressaisir le nom)
- **Consommation** : déduction semi-auto depuis journal + hydratation automatique + alertes universelles
- **Réapprovisionnement** : seuils minimum, staples, liste de courses intégrée

---

## 1. Base de données

### Colonnes ajoutées à la table `stock`

```sql
ALTER TABLE stock ADD COLUMN quantite_min    REAL    DEFAULT 0;
ALTER TABLE stock ADD COLUMN est_staple      INTEGER DEFAULT 0;
ALTER TABLE stock ADD COLUMN quantite_cible  REAL    DEFAULT 0;
ALTER TABLE stock ADD COLUMN nb_utilisations INTEGER DEFAULT 0;
ALTER TABLE stock ADD COLUMN est_eau         INTEGER DEFAULT 0;
```

Ajoutées dans `_migrate()` via `try/except ALTER TABLE` (non destructif).

### Smart defaults pour `quantite_min`

Appliqués automatiquement dans `upsert_stock()` uniquement lors d'un INSERT (pas d'un UPDATE) :
- `unite = 'unité'` → `quantite_min = 1`
- `categorie = 'Épices'` → `quantite_min = quantite * 0.10` (10% de la quantité initiale)
- Autre → `quantite_min = 0`

### Nouvelles fonctions DB

| Fonction | Description |
|---|---|
| `add_to_stock_from_aliment(aliment_id, quantite, unite)` | Upsert + smart defaults + incrément `nb_utilisations`. Retourne le dict stock mis à jour. |
| `get_stock_sous_seuil()` | Items où `quantite < quantite_min AND quantite_min > 0`, joint avec `aliments` |
| `get_staples_a_reapprovisionner()` | Staples où `quantite < quantite_cible AND est_staple = 1` |
| `get_liste_courses_stock(nb_jours=7)` | Combine staples à réappro + ingrédients manquants pour recettes planifiées dans les nb_jours prochains jours |
| `get_suggestions_staples(limit=5)` | Top aliments par `nb_utilisations` non encore staples (`est_staple = 0`) |
| `increment_stock_usage(aliment_id)` | +1 sur `nb_utilisations` de l'item stock de l'utilisateur courant |
| `get_stock_eau_aliment_id()` | Retourne l'`aliment_id` de l'item stock marqué comme source d'eau (`est_eau = 1`), ou None |
| `set_stock_eau(stock_id)` | Met `est_eau = 1` sur cet item, remet à 0 tous les autres du user courant |

**Colonne supplémentaire :**
```sql
ALTER TABLE stock ADD COLUMN est_eau INTEGER DEFAULT 0;
```
Un seul item stock peut avoir `est_eau = 1` par utilisateur (contrainte gérée par `set_stock_eau(stock_id)`).

### Modification de `deduct_stock()`

La fonction existante `deduct_stock(ingredients)` retourne maintenant une liste des items passés sous leur seuil :

```python
def deduct_stock(ingredients: list) -> list:
    """
    Déduit du stock. Retourne la liste des items qui sont passés sous quantite_min.
    [{nom, quantite, quantite_min, unite}]
    """
```

---

## 2. Points d'entrée stock

### A) Page Aliments — bouton `📦` par ligne

Sur chaque ligne aliment dans `pages/aliments.py`, ajouter un bouton `📦` qui ouvre `AddToStockDialog(parent, aliment)`.

`AddToStockDialog` est un CTkToplevel léger (pas le StockDialog complet) :
- Affiche le nom de l'aliment (pré-rempli, non modifiable)
- Champ quantité + unité (pré-remplie depuis `aliment['unite']`)
- Champ DLC optionnel
- Case "Marquer comme staple" + champ quantité cible (visible si staple coché)
- Bouton Ajouter → appelle `add_to_stock_from_aliment()`

### B) Scanner code-barres — après identification (`barcode_scanner.py`)

Dans le dialog de résultat de scan, après affichage du produit identifié, ajouter un bouton :
`📦 Ajouter au stock`

Ce bouton ouvre `AddToStockDialog` avec l'aliment pré-rempli. Si le produit n'était pas encore dans la base `aliments`, il y est ajouté d'abord (comportement existant), puis `AddToStockDialog` s'ouvre.

### C) Journal — lors de l'ajout d'un aliment

Dans `pages/journal.py`, dans le dialog d'ajout rapide (saisie aliment + quantité) :

**Cas 1 : aliment PAS en stock** → après validation, afficher une section optionnelle :
```
☐ Ajouter aussi au stock
   Quantité achetée : [____] [g ▼]
```
Si coché → `add_to_stock_from_aliment()` avec la quantité saisie.

**Cas 2 : aliment DÉJÀ en stock** → dans le dialog de saisie, afficher :
```
☑ Déduire du stock  (stock actuel : 350g)
```
Cochée par défaut si stock ≥ quantité consommée, décochée si insuffisant (affichage orange).
Si cochée → `deduct_stock()` à la validation. Si des items passent sous seuil → toast d'alerte.

---

## 3. Déduction universelle + alertes

### Principe

Toute déduction passe par `deduct_stock()` qui retourne les items sous seuil. L'appelant affiche un toast si la liste est non vide.

### Toast d'alerte

Widget non-bloquant (4 secondes, coin bas-droite) :
```
⚠️  Stock faible — Poulet blanc : 100g (seuil : 200g)
                                        [Voir le stock →]
```
Implémenté dans `pages/stock.py` comme fonction `show_stock_alert_toast(parent, items_sous_seuil)`.

### Sources de déduction

| Source | Fichier | Action |
|---|---|---|
| Journal — checkbox | `pages/journal.py` | `deduct_stock()` + toast si retour non vide |
| Planning — bouton 🍳 | `pages/planning.py` | Déjà implémenté — ajouter la vérification du retour + toast |
| Hydratation — boutons +ml | `pages/journal.py` | Si `get_stock_eau_aliment_id()` non None → `deduct_stock([{aliment_id, quantite_g: ml}])` |
| Stock — édition manuelle (baisse) | `pages/stock.py` | Toast si nouvelle quantité < `quantite_min` |

---

## 4. Configuration seuils & staples dans StockDialog

`StockDialog` (pages/stock.py) gagne 4 nouveaux champs :

```
Seuil d'alerte minimum
Quantité min : [____] [g ▼]      ← 0 = désactivé

☐ Produit de première nécessité (staple)
   Quantité cible : [____] [g ▼] ← visible seulement si staple coché

☐ Source d'eau (lier au tracker hydratation)
```

La case "Source d'eau" désigne cet item comme référence pour la déduction hydratation. Un seul item peut l'être à la fois (appel `set_stock_eau(stock_id)` qui remet à zéro les autres).

---

## 5. Liste de courses dans la page Stock

Nouvelle section collapsible en bas de `pages/stock.py` :

```
🛒  Liste de courses                              [Actualiser]

STAPLES À RÉAPPROVISIONNER
• Poulet blanc      manque 300g   (cible 500g)
• Œufs              manque 4 uni  (cible 6)
• Eau plate         manque 2L     (cible 6L)

RECETTES PLANIFIÉES (7 prochains jours) — MANQUANTS
• Jarret de bœuf    400g    → Phở bœuf (Lundi)
• Nouilles de riz   300g    → Phở bœuf (Lundi)

SUGGESTIONS — fréquemment utilisés
• Riz blanc cuit    utilisé 12×    [+ Ajouter aux staples]
• Tomate            utilisé 9×     [+ Ajouter aux staples]

[📋 Copier la liste]   [🖨️ Imprimer]
```

**Logique :**
- Staples : `get_staples_a_reapprovisionner()`
- Recettes : `get_liste_courses_stock(nb_jours=7)` — ingrédients manquants pour recettes planifiées la semaine suivante
- Suggestions : `get_suggestions_staples(limit=5)`
- Export : texte brut pour copier/presse-papiers ; HTML simple pour imprimer (même pattern que `rapport.py`)

---

## 6. Bandeau alertes Stock étendu

La section alertes existante en haut de `StockPage` affiche maintenant **deux types d'alertes** :
1. DLC (déjà implémenté) : 🔴 périmé / 🟡 bientôt
2. Stock faible (nouveau) : 🟠 `Poulet blanc — 100g restants (seuil : 200g)`

Même bandeau, deux sources fusionnées, trié par criticité (périmé en premier, puis faible stock).

---

## Fichiers modifiés

| Fichier | Modification |
|---|---|
| `database.py` | 4 colonnes ALTER TABLE, 7 nouvelles fonctions, modification `deduct_stock()` |
| `pages/stock.py` | `StockDialog` + 4 champs, section liste de courses, toast helper, alertes stock faible |
| `pages/aliments.py` | Bouton 📦 par ligne + `AddToStockDialog` |
| `barcode_scanner.py` | Bouton "📦 Ajouter au stock" post-scan |
| `pages/journal.py` | Checkbox déduction + section ajout stock + déduction hydratation |
| `pages/planning.py` | `DeductionStockDialog` : ajouter vérification retour + toast |
| `pages/dashboard.py` | Carte stock : ajouter items sous seuil min en plus des alertes DLC |

---

## Hors scope

- Historique des mouvements de stock (entrées/sorties loggées)
- Synchronisation multi-appareils
- Code-barres sur les listes de courses (scan pour valider achat)
- Import automatique depuis reçus de caisse
