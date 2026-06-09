# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**NutriTrack Pro** — desktop nutrition management app (Python 3.9+, Windows/macOS/Linux).

## Commands

```bash
# Install required dependencies (see requirements.txt for pinned versions)
pip install -r requirements.txt

# Or manually:
pip install customtkinter Pillow matplotlib requests

# Optional: barcode scanning
pip install opencv-python pyzbar

# Optional: AI photo analysis
pip install anthropic

# Run with dependency check
python launch.py

# Run directly
python main.py
```

No test suite or linter is configured. Errors are written to `nutritrack.log` (rotating, max 1 MB × 3 files).

## Architecture

The app is structured as a flat set of modules plus a `pages/` subdirectory:

- **`main.py`** — Creates `NutriTrackApp`, shows `LoginScreen` (modal), then manages sidebar navigation between 8 page classes: dashboard, journal, stats, profil, aliments, recettes, planning, programmes. Contient le switcher de thème (bas de sidebar) qui appelle `theme.save_theme()` puis redémarre l'app via `subprocess.Popen`.
- **`theme.py`** — Gestion des thèmes UI. Définit `THEMES` (dict de 3 palettes : `dark`, `light`, `ocean`), `T` (palette active, importée par toutes les pages), `save_theme(name)` (écrit dans `config.json`), `get_theme_name()`. Clés du dict : `bg_app`, `bg_card`, `bg_el`, `bg_hl`, `bg_row`, `tx1`/`tx2`/`tx3`, `ac`/`ac_d`/`ac_bg`/`ac_sel`, `cal`, `blue`/`blue_l`/`blue_d`/`blue_dm`, `lip`, `fib`, `vio`/`vio_d`, `err`/`err_bg`. Le mode CTk (`ctk_mode`) est lu dans `T` avant création des widgets.
- **`database.py`** — Single module containing *all* SQLite logic and business calculations. Every page calls into this module; pages contain no DB code of their own.
- **`pages/`** — Pure UI components. Each page class takes a parent frame. Every page exposes a `refresh()` method called by the main window on tab switch.
- **`pages/journal.py`** — Journal alimentaire quotidien : saisie rapide (aliment de la base + quantité, ou libre), navigation par jour, bilan macros temps réel avec **anneaux circulaires `MacroRing`** (grille 2 colonnes : Énergie/Protéines, Glucides/Lipides, Fibres centré) + widget hydratation (boutons +150/+250/+500 ml). Section "⚡ Récemment utilisés" en haut de la liste de recherche.
- **`pages/stats.py`** — Statistiques nutritionnelles avancées : sélecteur de période (7/30/90 jours), 4 KPI cards (calories moy., % jours à l'objectif, protéines moy., jours enregistrés), camembert répartition macros, graphique barres calories journalières vs cible, analyse meilleure/pire semaine.
- **`pages/programmes.py`** — Gestion des programmes nutritionnels (CRUD, activation). Bouton 🔄 sur le programme actif ouvre `ReequilibrageDialog` (mode rééquilibrage progressif).
- **`login.py`** — Standalone `LoginScreen` CTkToplevel that sets `database._current_user_id` on user selection/creation.
- **`barcode_scanner.py`** — Integrates camera (OpenCV) + Open Food Facts REST API; degrades gracefully to manual entry when OpenCV/pyzbar are absent. `fetch_product()` checks `off_cache.lookup()` first (no network), then falls back to the OFF API. Raises `ConnectionError` on network failure (distinct from product-not-found `None`). Le champ de saisie manuelle intercepte les frappes via `_remap_azerty_key` (`<KeyPress>` binding) pour corriger le remappage AZERTY : les scanners USB envoient les chiffres sans Shift (comportement QWERTY), ce qui produirait des caractères spéciaux (`&é"'(-è_çà`) au lieu de chiffres sur un layout AZERTY. Le dictionnaire `_AZERTY_TO_DIGIT` (module-level) mappe ces caractères vers les chiffres correspondants. **⚠️ Import circulaire** : `barcode_scanner` est importé par `pages/aliments.py` et `pages/stock.py`. Ne jamais importer `pages/stock.py` au niveau module dans `barcode_scanner.py` — cela crée un import circulaire qui provoque `MANUAL_OK = False` dans `pages/stock.py` (le module `barcode_scanner` est partiellement initialisé quand `stock.py` tente de l'importer, l'`except ImportError` est déclenché, et `MANUAL_OK` reste `False`). L'import de `AddToStockDialog` doit rester **lazy** (à l'intérieur de `_on_confirm`).
- **`off_cache.py`** — Cache local Open Food Facts. `build_cache(csv_path, progress_cb, cancel_event)` importe le CSV OFF (~12 Go, tab-séparé) dans `off_cache.db` (SQLite, ~300 Mo) par batches de 5000 lignes. `lookup(barcode)` → dict compatible `fetch_product()` ou None. `ImportCacheDialog` : fenêtre CTkToplevel avec barre de progression + ETA, bouton Parcourir, annulation. `cache_info()` → `{"count": int, "size_mb": float}`. Chemin par défaut : `Telechargement/fr.openfoodfacts.org.products.csv`.
- **`photo_analyzer.py`** — Calls Anthropic Claude Vision (`claude-sonnet-4-6`) to parse nutrition labels from photos; requires an API key in `config.json`.
- **`logger.py`** — Centralised `get_logger(name)` factory; all modules import this for error logging to `nutritrack.log`.
- **`colors.py`** — Hex color utilities: `blend()`, `tint_low/mid/high()`. Le paramètre `bg` doit être passé explicitement avec `T["bg_card"]` pour respecter le thème actif.
- **`pages/sport.py`** — Sport & Activité : suivi des séances (tapis marche, vélo appart, rameur, VAE, marche ext.), navigation par jour, 4 KPI cards (séances, cal brûlées, minutes semaine, progression vs semaine préc.), bannière impact nutritionnel (<100/100-250/>250 kcal : hydratation, collation, budget ajusté), liste des séances du jour avec **badge zone cardiaque** (`Z2 · 100 bpm`), graphique barres 7j (Matplotlib), **carte référence zones cardiaques** (5 zones avec bpm calculés, avertissement médical sur Z4+). `SportDialog` : sélection activité, **carte zone cible** (Zone 2 recommandée par défaut), slider durée 5-120 mn, slider vitesse (km/h) ou boutons intensité (Léger/Modéré/Intense), aperçu calories live, **champ FC observée** (bpm) avec alerte si >85% FC max + affichage zone correspondante.
- **`rapport.py`** — Génération du rapport hebdomadaire HTML. `generer_rapport_html(data)` → crée un fichier temporaire `.html` via `tempfile.mkstemp`. `_build_html(data)` → HTML pur auto-suffisant (CSS inline) avec : en-tête, KPI row (4 cards), tableau 7 jours coloré (vert=objectif, rouge=hors objectif, gris=non enregistré), section sport, barre d'adhérence. Bouton `🖨️ Imprimer` (`window.print()`) masqué via `@media print`.
- **`pages/rapport_dialog.py`** — `RapportDialog` CTkToplevel 460×190 : sélecteur semaine ◀/▶ (par défaut semaine courante), bouton "Générer & ouvrir" → `db.get_rapport_semaine()` + `rp.generer_rapport_html()` + `webbrowser.open()`. Affiche une info-dialog si aucune donnée journal pour la semaine sélectionnée.
- **`widgets.py`** — Shared reusable UI widgets. Contient `MacroRing` : anneau de progression circulaire (`tkinter.Canvas`) affichant valeur + unité au centre, pourcentage en dessous, label en bas. Utilise `T` pour les couleurs. `bg_color` défaut = `T["bg_card"]`.

### Session model

Multi-user support is handled via the module-level `database._current_user_id` integer. All `DatabaseManager` methods accept an implicit current user from this global rather than passing a user ID per call.

### Database (`nutrition.db`)

SQLite, auto-created at startup. Key tables:

| Table | Purpose |
|---|---|
| `users` | Profiles: physique data, objectif, activite, poids_cible, avatar_color, **coefficient_proteines** (g/kg, 0=auto), **objectif_eau_ml** (défaut 2000), **fc_max** (bpm, 0=auto 220−âge) |
| `aliments` | 80+ foods: full macro breakdown, categorie, ig, allergenes, unite, poids_unite_g. Catégories : Viandes & Poissons, Œufs & Laitiers, Céréales & Féculents, Légumineuses, Légumes, Fruits & Oléagineux, Matières grasses, Condiments, **Épices** |
| `recettes` | Recipes: categorie, portions, temps_prep/cuisson, difficulte, cout, allergenes |
| `recette_ingredients` | Food→recipe links with quantite, unite_recette, coefficient_cuisson |
| `recette_etapes` | Ordered cooking steps per recipe |
| `programmes` | Calorie/macro targets (pct splits); **scoped per user** via `user_id`. One row per user has `actif=1`. `_migrate()` auto-crée 3 programmes calibrés (BMR/TDEE du profil) pour chaque utilisateur sans programmes. |
| `suivi_poids` | Per-user weight + waist history |
| `suivi_eau` | Per-user daily water intake: date, heure, ml, notes |
| `planning_repas` | Weekly planner: date, type_repas, recette_id or free-text + nutrition values |
| `activites_sport` | Per-user sport sessions: date, heure, type_activite, duree_min, vitesse_kmh, intensite, calories_brulees, notes, **fc_observee** (bpm, 0=non renseigné) |

Schema migrations are handled by `_migrate()` in `database.py` — ALTER TABLE statements guarded by try/except to add columns to existing DBs without recreation.

**`planning_repas.type_repas` — valeurs valides** (définies dans `TYPES_REPAS` dans `database.py`) :
`petit_dejeuner`, `collation_matin`, `dejeuner`, `collation_soir`, `diner` — toujours en minuscules sans accents. Toute autre valeur (ex. `"Déjeuner"`) est ignorée par l'UI.

Backup: `export_backup(dest_path)` uses the SQLite `backup()` API (safe under concurrent writes). UI button in Profil → header.

### Nutritional calculations (all in `database.py`)

- **BMR/TDEE:** Mifflin-St Jeor formula; activity factor × BMR; goal offsets (−500 / 0 / +300 kcal).
- **Recipe nutrition:** `calc_recette_nutrition(recette_id)` — ingredients summed with `coefficient_cuisson` per cooking method, then divided by `portions`. Results are **cached** in `_recette_nutrition_cache`; call `invalidate_recette_cache(rid)` after any recipe/ingredient write (already called by `update_recette` and `delete_recette`).
- **Daily totals (planning):** `get_nutri_jour(jour_iso)` aggregates `*_custom` fields from `planning_repas` for a given day.
- **Journal totals:** `get_nutri_journal_jour(jour_iso)` aggregates `journal_repas` entries. `get_calories_14j()` returns a 14-day calorie history for the dashboard chart.
- **Shopping list:** `get_liste_courses(date_debut, date_fin)` aggregates ingredient quantities across all recipe-based meals in a date range, scaled to the planned number of portions.
- **Favorites:** `toggle_recette_favori(rid)` flips `recettes.favori` (0/1). `get_recettes(favori_only=True)` filters to starred recipes only; default sort puts favorites first (`ORDER BY favori DESC`).
- **Unit conversion:** `_convert_to_grams()` maps culinary units (CAS, CAC, verre, tasse, bol, pincée…) to grams.
- **Nutri-Score:** simplified FSA algorithm (energy + fat + sugars = negative; fiber + protein = positive) → A–E rating.
- **IG tiers:** < 55 bas, 55–69 moyen, ≥ 70 élevé.
- **Stats nutritionnelles:** `get_stats_nutrition(days)` — totaux journaliers du journal sur N jours. `get_adherence_stats(days)` — calcule avg_cal, avg_prot, pct_cal_ok (±10%), pct_prot_ok, répartition macros en %, meilleure/pire semaine par rapport à la cible.
- **Rééquilibrage progressif:** `get_reequilibrage_data()` — compare poids réels (`suivi_poids` hebdo) à la trajectoire projetée (7700 kcal = 1 kg); suggère ±100 kcal/jour si écart moyen > 0,5 kg sur 4 semaines. `apply_reequilibrage(new_calories)` — met à jour `calories_jour` du programme actif de l'utilisateur courant.
- **Programmes per-user:** `get_programmes()`, `get_programme_actif()`, `add_programme()`, `set_programme_actif()` — toutes filtrées par `_current_user_id`. `set_programme_actif(pid)` remet à zéro uniquement les programmes du user courant (pas de collision inter-utilisateurs).
- **Protéines dynamiques:** `calc_macros_cibles(profil)` utilise `poids × coefficient_proteines` si `coeff ≥ 0.1`, sinon 30 % des calories (auto). Le coefficient se règle dans Profil → Informations (slider 0–2.5 g/kg).
- **Suivi de l'eau:** `add_eau(ml, date_str)`, `get_total_eau_jour(date_str)`, `get_objectif_eau()` → lit `users.objectif_eau_ml`. Widget dans le bilan Journal (boutons +150/+250/+500 ml) et dans la carte "Consommé aujourd'hui" du Dashboard.
- **Sport & activité:** Formule MET : `calories = MET × poids_kg × (duree_min / 60)`. MET par activité dans `_MET_SPORT` (tapis vitesse-dépendant, vélo/rameur/marche intensité-dépendant, VAE fixe 3.5). `ACTIVITES_SPORT` dict (label, icon, param). `calc_calories_sport()`, `add_activite_sport()`, `get_activites_sport_jour()`, `delete_activite_sport()`, `get_calories_sport_jour()`, `get_stats_sport_semaine()` (cette semaine vs précédente), `get_progression_sport(nb_jours)` (séries temporelles avec jours vides à 0).
- **Zones cardiaques:** `get_fc_max()` → lit `users.fc_max` si > 0, sinon `220 − âge` (min 100). `get_zones_cardiaques(fc_max)` → liste de 5 dicts `{num, label, bpm_min, bpm_max, pct_min, pct_max, color_key}`. Zones : Z1 Récupération 50–60% (`ac`), Z2 Endurance 60–70% (`blue`), Z3 Aérobie 70–80% (`lip`), Z4 Seuil 80–90% (`cal`), Z5 Maximum 90–100% (`err`). `get_zone_for_fc(fc_obs, fc_max)` → zone ou None. `is_fc_alert(fc_obs, fc_max)` → True si fc_obs > 85% fc_max. `save_user()` persiste `fc_max` dans l'UPDATE.
- **Rapport hebdomadaire:** `get_rapport_semaine(date_lundi_iso)` → dict complet : `semaine_label`, `user`, `cible`, `jours` (7 entrées avec calories/macros/eau/a_objectif/enregistre), `moyennes` (sur jours enregistrés seulement, `max(1,n)` garde contre division par zéro), `sport` (séances + totaux), `adherence` (jours_ok / 7 × 100 %).
- **Gestion de stock:** Table `stock` per-user (colonnes : id, user_id, aliment_id, quantite, unite, date_peremption NULL, notes, updated_at). Toutes les fonctions utilisent `_current_user_id` implicitement (pas de paramètre user_id). `get_stock()`, `upsert_stock(aliment_id, quantite, unite, date_peremption, notes)`, `delete_stock(stock_id)`, `deduct_stock(ingredients)` où `ingredients=[{aliment_id, quantite_g}]`, `get_stock_alerts(jours=3)` → items périmés ou expirant dans ≤ jours jours, `check_recette_faisable(recette_id)` → `{faisable: bool, manquants: [{nom, qte_requise, qte_stock, unite}]}`.

### UI conventions

- Framework: **CustomTkinter** with a fixed dark palette (`#0d1117` bg, `#22c55e` accent green, `#e6edf3` primary text).
- Layout: 220 px fixed sidebar + scrollable right content area; grid with `weight=1` columns.
- Dialogs: all add/edit forms are `CTkToplevel` modal windows (e.g., `AlimentDialog`, `RecetteDialog`, `ScaleDialog`, `ListeCoursesDialog`, `ReequilibrageDialog`).
- Color utilities in `colors.py`: `blend_hex()`, `tint_low/mid/high()` simulate alpha blending on solid backgrounds.

### Features par page

| Page | Fonctionnalités clés |
|---|---|
| **Dashboard** | Stats, profil résumé, programme actif, objectifs macros, widget **suivi du jour** (**4 anneaux `MacroRing`** Énergie/Protéines/Glucides/Lipides + **barre eau**), **carte sport** (séances du jour, cal brûlées, budget ajusté, conseil récupération), **graphiques** (courbe poids 30j + barres calories journal 14j via Matplotlib) |
| **Journal** | Saisie rapide quotidienne (aliment base ou libre + heure + quantité), navigation par jour, bilan macros temps réel (**5 anneaux `MacroRing`** en grille 2 col + Fibres centré) + **widget hydratation** (barre progression + boutons +150/+250/+500 ml), section **⚡ Récemment utilisés** dans la recherche |
| **Statistiques** | Sélecteur période 7/30/90j, 4 KPI cards (calories moy., % jours à l'objectif ±10%, protéines moy., jours enregistrés), **camembert macros** (Matplotlib), **barres calories vs cible**, analyse **meilleure/pire semaine**, bouton **📄 Rapport** (ouvre `RapportDialog`) |
| **Aliments** | CRUD, search/filter, Nutri-Score live, CSV import/export, scan code-barres, **analyse photo IA**, **⚖ Comparateur** (jusqu'à 3 aliments côte à côte), **🗄️ Cache OFF** (import du CSV OFF + gestion via `ImportCacheDialog`) |
| **Recettes** | CRUD complet, calcul nutrition (mis en cache), bouton **⭐ favori** par carte, filtre **☆ Favoris**, bouton **⚖️ Adapter** (mise à l'échelle) |
| **Planning** | Vue semaine, favoris en tête de liste (⭐), alerte allergènes, **🛒 Liste de courses**, **📄 Export HTML**, génération automatique, bouton **📄 Rapport semaine** (ouvre `RapportDialog`) |
| **Profil** | Infos (incl. **slider protéines dynamiques** 0–2.5 g/kg + **objectif eau** + **champ FC max** bpm, vide=auto), suivi poids (graphe Matplotlib), bilan, programmes, bouton **💾 Sauvegarder DB** |
| **Programmes** | CRUD programmes (objectif, calories, macros %, durée). Bouton **🔄 Rééquilibrage** sur le programme actif : graphe poids réel vs projeté, suggestion ±100 kcal/jour, application en 1 clic |
| **Sport** | Navigation par jour, 4 KPI cards, bannière impact nutritionnel (3 niveaux), liste séances + badge zone cardiaque + suppression, graphique barres 7j, **carte zones cardiaques** (5 zones, FC max, avertissement Z4+). `SportDialog` : 5 types d'activité, **carte zone cible** (Z2 recommandée), slider durée, vitesse ou intensité selon activité, aperçu calories live, **champ FC observée** + alerte >85% FC max |
| **Stock** | Garde-manger per-user : liste avec filtre catégorie + recherche, codes couleur DLC (🔴périmé/🟡bientôt/🟢OK), section alertes conditionnelle. `StockDialog` : recherche aliment live, quantité + unité (g/ml/kg/L/unité), DLC optionnel JJ/MM/AAAA, notes. Intégration **Recettes** : badge ✅/⚠️ par carte + filtre "Faisables" + tooltip manquants. Intégration **Planning** : tri faisables en tête de liste + bouton 🍳 sur slots → `DeductionStockDialog` (déduction semi-auto après cuisson). Intégration **Dashboard** : carte alertes péremption conditionnelle + navigation vers Stock. |

### Optional feature flags

`barcode_scanner.py` exports `MANUAL_OK` and `CAMERA_OK` booleans checked before enabling camera mode. `photo_analyzer.py` reads `config.json` for `anthropic_api_key`; the UI disables the photo button when the key is absent.

---

## Backlog — fonctionnalités à implémenter

Les features ci-dessous ont été identifiées mais pas encore développées. Numérotation de référence conservée.

| # | Feature | Description courte | Priorité |
|---|---|---|---|
| 3 | **Notifications / rappels** | Alertes configurables (hydratation, repas manqués) via `plyer` ou `win10toast` | Moyenne |
| 8 | **Synchronisation cloud** | Export/import JSON vers endpoint configurable pour sauvegarde distante multi-device | Basse |
| 17 | **Bilan cardiaque dans le rapport** | Ajouter section FC observée (moyenne, max, distribution par zone) dans le rapport hebdomadaire | Moyenne |
| 18 | **Historique FC dans Sport** | Graphique barres 7j des FC observées par séance, visible en bas de la page Sport | Moyenne |

### Features déjà implémentées (pour référence)

| # | Feature | Session |
|---|---|---|
| 1 | Suivi de l'eau (journal + dashboard + profil) | Session 3 |
| 4 | Statistiques nutritionnelles avancées (stats.py) | Session 2 |
| 5 | Objectif protéines dynamique (slider g/kg) | Session 3 |
| 6 | Comparateur d'aliments (jusqu'à 3) | Session 3 |
| 7 | Historique repas fréquents dans le journal | Session 3 |
| 10 | Thèmes UI (`theme.py` — 3 palettes : Sombre/Clair/Océan, switcher sidebar, `config.json`) | Session 4 |
| 9 | Mode hors-ligne / cache OFF (`off_cache.py` + `ImportCacheDialog` + `fetch_product()` priorité cache) | Session 4 |
| 11 | Widget macro circulaire (`MacroRing` dans `widgets.py`) — Dashboard + Journal bilan | Session 4 |
| 12 | Rééquilibrage progressif (programmes.py) | Session 2 |
| 13 | **Programmes per-user** — `user_id` dans `programmes`, migration auto, 3 programmes calibrés (BMR/TDEE) créés par utilisateur | Session 5 |
| 14 | **Module Sport & Activité** — `pages/sport.py`, table `activites_sport`, fonctions MET, carte dashboard, sidebar | Session 5 |
| 15 | **Zones de fréquence cardiaque** — `users.fc_max` + `activites_sport.fc_observee`, 4 fonctions DB, carte zone cible dans SportDialog, champ FC observée avec alerte >85%, badge sur séances, carte référence 5 zones en bas de Sport, champ FC max dans Profil | Session 6 |
| 2 | **Rapport hebdomadaire HTML** — `get_rapport_semaine()` DB, `rapport.py` génération HTML pur auto-suffisant, `RapportDialog` sélecteur semaine, boutons depuis Stats et Planning | Session 6 |
| 19 | **Gestion de stock v1** — table `stock`, 6 fonctions DB, `pages/stock.py`, badges faisabilité Recettes, tri+déduction Planning, alertes Dashboard | Session 7 |
| 20 | **Gestion de stock v2** — cycle complet : 5 colonnes stock (quantite_min, est_staple, quantite_cible, nb_utilisations, est_eau), `AddToStockDialog`, `show_stock_alert_toast`, bouton 📦 Aliments, bouton "Aliments+Stock" scanner, checkbox déduction Journal, déduction hydratation, toast alertes Planning, liste de courses Stock, alertes seuil Dashboard | Session 8 |
| 16 | **Graphique poids × objectif long terme** — `get_projection_poids()` DB, courbe projection hebdo + zone ±0.5 kg + étoile dans Profil (axe X en vraies dates), carte Dashboard compacte 90j + KPIs | Session 9 |

### Recettes & aliments ajoutés (Session 5)

| Recette | Portions | Kcal/portion | Notes |
|---|---|---|---|
| Frites filet américain & salade de tomates | 1 | 544 | Henry Boucher nature, vinaigrette colza |
| Shorba au poulet (version saine) | 4 | 432 | 16 ingrédients, 7 étapes, 41g prot/bol |
| Lapin mijoté au vin blanc et légumes | 3 | 548 | Demi-lapin LIDL, lardons, carottes, PDT |

Aliments ajoutés (IDs 71–86) : Filet américain Henry Boucher, Frites surgelées cuites, Huile de colza, Échalotte, Persil frais, Vinaigre d'alcool blanc, Vermicelles fins, Concentré de tomates, Coriandre fraîche, Cannelle moulue, Lapin chair crue, Vin blanc sec cuisson, Pomme de terre cuite à l'eau, Thym séché.

### Recettes & aliments ajoutés (Session 7)

| Recette | Portions | Kcal/portion | Notes |
|---|---|---|---|
| Phở bœuf & os à moelle | 4 | 534 | Bouillon 3h, jarret + bœuf tranché fin, nouilles de riz, 12 ingrédients, 6 étapes, 58g prot/bol |

Aliments ajoutés (IDs 88–96, + Gingembre frais ID 64 déjà existant) : Os à moelle de bœuf, Jarret de bœuf (cru), Bœuf tranché fin (tende de tranche), Nouilles de riz pho (sèches), Anis étoilé (badiane), Sauce poisson (nuoc mam), Germes de soja, Oignon jaune, Oignons verts (cébettes). Note : Os à moelle compté pour 80g (moelle extraite) — les os eux-mêmes sont filtrés et non consommés.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
