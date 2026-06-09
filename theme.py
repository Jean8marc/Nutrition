"""
NutriTrack Pro — Gestion des thèmes UI.
Les pages importent T (dict de couleurs actives) via : from theme import T
Changement de thème : save_theme(name) + redémarrage de l'app.
"""
import json
import os

_CONFIG = os.path.join(os.path.dirname(__file__), "config.json")

# ── Palettes ──────────────────────────────────────────────────────────────────
THEMES: dict[str, dict] = {
    "dark": {
        "name": "Sombre", "ctk_mode": "dark",
        # backgrounds
        "bg_app":  "#0d1117",
        "bg_card": "#161b22",
        "bg_el":   "#21262d",
        "bg_hl":   "#30363d",
        "bg_row":  "#1a2035",
        # text
        "tx1":     "#e6edf3",
        "tx2":     "#64748b",
        "tx3":     "#3d4a5c",
        # accent (vert)
        "ac":      "#22c55e",
        "ac_d":    "#16a34a",
        "ac_bg":   "#17352b",   # tint_low(ac, bg_card)
        "ac_sel":  "#1e3a2a",
        # macros
        "cal":     "#ec4899",
        "blue":    "#3b82f6",
        "blue_l":  "#60a5fa",
        "blue_d":  "#1e3a5f",
        "blue_dm": "#1e40af",
        "lip":     "#f59e0b",
        "fib":     "#a78bfa",
        # violet (IA / photo)
        "vio":     "#8b5cf6",
        "vio_d":   "#7c3aed",
        # statuts
        "err":     "#ef4444",
        "err_bg":  "#3d1515",
    },
    "light": {
        "name": "Clair", "ctk_mode": "light",
        "bg_app":  "#f0f4f8",
        "bg_card": "#ffffff",
        "bg_el":   "#e8edf3",
        "bg_hl":   "#cbd5e1",
        "bg_row":  "#f8fafc",
        "tx1":     "#0f172a",
        "tx2":     "#475569",
        "tx3":     "#94a3b8",
        "ac":      "#16a34a",
        "ac_d":    "#15803d",
        "ac_bg":   "#dcfce7",
        "ac_sel":  "#bbf7d0",
        "cal":     "#db2777",
        "blue":    "#2563eb",
        "blue_l":  "#3b82f6",
        "blue_d":  "#dbeafe",
        "blue_dm": "#bfdbfe",
        "lip":     "#d97706",
        "fib":     "#7c3aed",
        "vio":     "#7c3aed",
        "vio_d":   "#6d28d9",
        "err":     "#dc2626",
        "err_bg":  "#fee2e2",
    },
    "ocean": {
        "name": "Océan", "ctk_mode": "dark",
        "bg_app":  "#060d1a",
        "bg_card": "#0d1f38",
        "bg_el":   "#142847",
        "bg_hl":   "#1a3360",
        "bg_row":  "#0f2440",
        "tx1":     "#cfe8ff",
        "tx2":     "#6a9dc4",
        "tx3":     "#3d617f",
        "ac":      "#22d3ee",
        "ac_d":    "#06b6d4",
        "ac_bg":   "#0c3044",
        "ac_sel":  "#0a3347",
        "cal":     "#f472b6",
        "blue":    "#818cf8",
        "blue_l":  "#a5b4fc",
        "blue_d":  "#1e1b4b",
        "blue_dm": "#312e81",
        "lip":     "#fb923c",
        "fib":     "#c084fc",
        "vio":     "#818cf8",
        "vio_d":   "#6366f1",
        "err":     "#f87171",
        "err_bg":  "#1a1515",
    },
}

# ── Config I/O ────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    try:
        with open(_CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_theme(name: str) -> None:
    cfg = _load_config()
    cfg["theme"] = name
    with open(_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_theme_name() -> str:
    return _load_config().get("theme", "dark")


# ── Active theme — imported by all pages ──────────────────────────────────────
T: dict = THEMES.get(get_theme_name(), THEMES["dark"])
