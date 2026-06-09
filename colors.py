"""
NutriTrack Pro — Utilitaires couleurs
CustomTkinter n'accepte pas les couleurs hex avec canal alpha (#rrggbbAA).
Ces fonctions calculent la couleur résultante sur fond sombre.
"""


def blend(hex_color: str, alpha: float = 0.16, bg: str = "#161b22") -> str:
    """
    Mélange hex_color sur bg avec le niveau de transparence alpha (0.0–1.0).
    Retourne une couleur solide compatible CustomTkinter.

    Équivalences courantes :
      "28" (hex) ≈ alpha 0.157
      "44" (hex) ≈ alpha 0.267
      "66" (hex) ≈ alpha 0.400
    """
    def _parse(h: str):
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    r1, g1, b1 = _parse(hex_color)
    r2, g2, b2 = _parse(bg)
    r = int(r1 * alpha + r2 * (1 - alpha))
    g = int(g1 * alpha + g2 * (1 - alpha))
    b = int(b1 * alpha + b2 * (1 - alpha))
    return f"#{r:02x}{g:02x}{b:02x}"


# Raccourcis pour les trois niveaux utilisés dans l'app
def tint_low(color: str, bg: str = "#161b22") -> str:
    """Tinte légère — remplace color+'28'"""
    return blend(color, alpha=0.157, bg=bg)


def tint_mid(color: str, bg: str = "#161b22") -> str:
    """Tinte moyenne — remplace color+'44'"""
    return blend(color, alpha=0.267, bg=bg)


def tint_high(color: str, bg: str = "#161b22") -> str:
    """Tinte forte — remplace color+'66'"""
    return blend(color, alpha=0.400, bg=bg)
