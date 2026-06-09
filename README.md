# 🥗 NutriTrack Pro

Application Python de gestion nutritionnelle complète avec interface graphique moderne.

---

## 📋 Fonctionnalités

| Module | Description |
|---|---|
| **🏠 Tableau de bord** | Vue d'ensemble : profil, programme actif, objectifs du jour |
| **👤 Mon Profil** | Fiche complète, calcul IMC, macros cibles (Mifflin-St Jeor), suivi du poids avec graphique |
| **🥑 Aliments** | Base de 40+ aliments : calories, protéines, glucides, lipides, fibres, index glycémique |
| **👨‍🍳 Recettes** | Créez des recettes avec ingrédients, calcul nutritionnel automatique par portion |
| **📋 Programmes** | Programmes perte de poids / maintien / prise de masse, activation en un clic |

---

## 🚀 Installation & Lancement

### Prérequis
- Python 3.9+ avec **tkinter** (inclus par défaut sur Windows/macOS)
- Sur Linux : `sudo apt install python3-tk`

### Installation des dépendances
```bash
pip install customtkinter Pillow matplotlib
```

### Lancement
```bash
cd nutrition_app
python launch.py
```
ou directement :
```bash
python main.py
```

---

## 🗂️ Structure du projet

```
nutrition_app/
├── main.py           # Application principale + navigation
├── database.py       # Couche BDD SQLite + logique métier
├── launch.py         # Script de lancement avec vérif. dépendances
├── nutrition.db      # Base SQLite (créée au premier lancement)
├── pages/
│   ├── dashboard.py  # Tableau de bord
│   ├── profil.py     # Fiche profil + suivi poids
│   ├── aliments.py   # Gestion des aliments
│   ├── recettes.py   # Gestion des recettes
│   └── programmes.py # Gestion des programmes
└── README.md
```

---

## 🧮 Calculs nutritionnels

### IMC
```
IMC = Poids (kg) / Taille² (m)
```

| IMC | Catégorie |
|---|---|
| < 18.5 | Insuffisance pondérale |
| 18.5 – 24.9 | Poids normal |
| 25 – 29.9 | Surpoids |
| 30 – 34.9 | Obésité modérée |
| ≥ 35 | Obésité sévère |

### Calories cibles (Mifflin-St Jeor + TDEE)
**Homme :** `BMR = 10×poids + 6.25×taille – 5×âge + 5`  
**Femme :** `BMR = 10×poids + 6.25×taille – 5×âge – 161`

| Niveau d'activité | Facteur |
|---|---|
| Sédentaire | × 1.2 |
| Légèrement actif | × 1.375 |
| Modérément actif | × 1.55 |
| Très actif | × 1.725 |
| Extrêmement actif | × 1.9 |

**Ajustements objectifs :**
- Perte de poids : TDEE − 500 kcal
- Maintien : TDEE
- Prise de masse : TDEE + 300 kcal

### Index Glycémique
| IG | Catégorie |
|---|---|
| < 55 | 🟢 Bas |
| 55 – 69 | 🟡 Moyen |
| ≥ 70 | 🔴 Élevé |

---

## 🛠️ Technologies

- **Interface** : CustomTkinter (thème sombre moderne)
- **Base de données** : SQLite 3 (sans serveur, portable)
- **Graphiques** : Matplotlib (suivi du poids)
- **Images** : Pillow

---

## 📝 Données de démo

Au premier lancement, l'application charge automatiquement :
- **40 aliments** dans 7 catégories
- **5 recettes** de démonstration
- **3 programmes** nutritionnels (perte de poids, maintien, prise de masse)

---

*NutriTrack Pro v1.0.0*
