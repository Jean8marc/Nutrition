#!/usr/bin/env python3
"""
NutriTrack Pro — Script de lancement
Vérifie les dépendances avant de démarrer l'application.
"""
import sys
import subprocess

REQUIRED = {
    "customtkinter": "customtkinter",
    "PIL":           "Pillow",
    "matplotlib":    "matplotlib",
    "requests":      "requests",
    "cv2":           "opencv-python",
    "pyzbar":        "pyzbar",
}

def check_and_install():
    missing = []
    for module, pkg in REQUIRED.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"📦  Installation des dépendances manquantes : {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing, "-q"])
        print("✅  Dépendances installées.")

if __name__ == "__main__":
    check_and_install()
    from main import main
    main()
