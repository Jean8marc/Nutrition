# Design — Zones de fréquence cardiaque

**Date :** 2026-05-17
**Projet :** NutriTrack Pro — Module Sport
**Statut :** Approuvé

## Contexte

Utilisateur principal : Jean-Marc, 60 ans, 4 stents cardiaques, débutant en sport (tapis de marche). Peut lire sa FC sur les poignées du tapis. Pas de FC max prescrite par le cardiologue → formule 220−âge.

## Base de données

Deux migrations `ALTER TABLE` dans `database._migrate()`, gardées par `try/except` :

```sql
ALTER TABLE users ADD COLUMN fc_max INTEGER DEFAULT 0;
ALTER TABLE activites_sport ADD COLUMN fc_observee INTEGER DEFAULT 0;
```

`fc_max = 0` signifie "calculé automatiquement" (220 − âge du profil).

## Nouvelles fonctions dans `database.py`

```python
def get_fc_max() -> int
    # Retourne users.fc_max si > 0, sinon 220 - profil['age']

def get_zones_cardiaques(fc_max: int) -> list[dict]
    # Retourne 5 zones : [{num, label, pct_min, pct_max, bpm_min, bpm_max, color_key}]
    # Zone 1 : 50-60% — Récupération        — T["ac"]   (vert)
    # Zone 2 : 60-70% — Endurance de base   — T["blue"] (bleu)
    # Zone 3 : 70-80% — Aérobie             — T["lip"]  (orange)
    # Zone 4 : 80-90% — Seuil               — T["cal"]  (jaune-orange)
    # Zone 5 : 90-100% — Maximum            — T["err"]  (rouge)

def get_zone_for_fc(fc_obs: int, fc_max: int) -> dict | None
    # Retourne la zone correspondant à fc_obs, ou None si fc_obs == 0

def is_fc_alert(fc_obs: int, fc_max: int) -> bool
    # True si fc_obs > 85% de fc_max
```

## Pages modifiées

### `pages/profil.py`

Dans la section "Informations physiques", ajouter un champ FC max :
- Label : "FC max (bpm)"
- Widget : CTkEntry numérique, placeholder = valeur calculée (ex. "160 bpm — calculé")
- Sauvegardé dans `users.fc_max` (0 si vide = auto)
- Affiché juste après le poids cible

### `pages/sport.py` — SportDialog

1. **Carte "Zone cible"** (entre le sélecteur d'activité et la durée) :
   - Affiche les bpm min–max de la zone recommandée (Zone 2 par défaut)
   - Label : "Zone cible : 🟡 Endurance — 96 à 112 bpm"

2. **Champ "FC observée"** (entre l'aperçu calories et les notes) :
   - CTkEntry numérique optionnel, placeholder "bpm observés sur l'appareil"
   - Si valeur > 85% FC max : bandeau `⚠️ FC élevée — consultez votre cardiologue avant d'augmenter l'intensité`

3. **Sauvegarde** : `fc_observee` enregistrée dans `activites_sport`

### `pages/sport.py` — Liste des séances

Dans chaque ligne de séance, si `fc_observee > 0` : badge coloré `"🟢 Z1 · 88 bpm"` basé sur `get_zone_for_fc()`.

### `pages/sport.py` — Carte de référence

En bas de la page Sport, carte fixe "❤️ Vos zones cardiaques" :
- Tableau des 5 zones avec bpm calculés selon FC max du profil
- Chaque ligne colorée selon la zone
- Mention "FC max : 160 bpm (calculé)" ou "(personnalisé)" si saisi manuellement

## Sécurité

- Alerte visuelle (non bloquante) si FC > 85% FC max
- Zones 4 et 5 affichées avec mention "⚠️ Demandez l'avis de votre médecin"
- Aucune donnée médicale stockée au-delà de la FC max et FC observée par séance
