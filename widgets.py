"""Shared reusable UI widgets for NutriTrack Pro."""
import tkinter as tk
import customtkinter as ctk
from theme import T


class MacroRing(ctk.CTkFrame):
    """Circular progress ring for a single macro nutrient.

    Draws a canvas-based arc ring showing value/cible as center text,
    a percentage label, and the macro name below.
    """

    def __init__(self, parent, label: str, value: float, cible: float,
                 unit: str, color: str, size: int = 96,
                 bg_color: str = T["bg_card"], **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._color = color
        self._size = size
        self._bg_color = bg_color

        self._canvas = tk.Canvas(
            self, width=size, height=size,
            bg=bg_color, highlightthickness=0
        )
        self._canvas.pack()

        self._pct_lbl = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=color
        )
        self._pct_lbl.pack(pady=(2, 0))

        self._name_lbl = ctk.CTkLabel(
            self, text=label,
            font=ctk.CTkFont(size=10),
            text_color=T["tx2"]
        )
        self._name_lbl.pack()

        self.set(value, cible, unit)

    def set(self, value: float, cible: float, unit: str):
        pct = min(1.0, float(value) / max(1, float(cible)))
        self._paint(pct, value, unit)
        self._pct_lbl.configure(text=f"{int(pct * 100)} %")

    def _paint(self, pct: float, value: float, unit: str):
        c = self._canvas
        c.delete("all")
        s = self._size
        pad = 10
        x0, y0, x1, y1 = pad, pad, s - pad, s - pad
        stroke = 10

        # Background ring
        c.create_arc(x0, y0, x1, y1, start=90, extent=359.9,
                     style="arc", outline=T["bg_el"], width=stroke)

        # Progress arc (clockwise from top)
        if pct > 0.005:
            c.create_arc(x0, y0, x1, y1, start=90, extent=-(pct * 359.9),
                         style="arc", outline=self._color, width=stroke)

        cx, cy = s // 2, s // 2

        # Value (top line inside ring)
        c.create_text(cx, cy - 8,
                      text=str(int(value)),
                      fill=T["tx1"],
                      font=("Helvetica", 12, "bold"),
                      anchor="center")

        # Unit (bottom line inside ring)
        c.create_text(cx, cy + 8,
                      text=unit,
                      fill=T["tx2"],
                      font=("Helvetica", 8),
                      anchor="center")
