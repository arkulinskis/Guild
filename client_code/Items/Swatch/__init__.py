from anvil import *

from ._anvil_designer import SwatchTemplate

NAMES = {"#2e4a70": "navy", "#c8102e": "Canada red", "#556b2f": "army olive", "#3b6ea5": "air force blue",
         "#8a7a4f": "khaki", "#5c6470": "slate", "#2f7a78": "sea green", "#7a2e3b": "maroon"}


class Swatch(SwatchTemplate):
    """One avatar colour on the Profile page. item = {color, on}. A click raises x-pick on the panel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        b, c = self.dom_nodes["btn"], self.item["color"]
        b.style.setProperty("--c", c)
        b.setAttribute("data-key", c)
        b.setAttribute("aria-label", "Colour: " + NAMES.get(c.lower(), c))
        b.setAttribute("aria-pressed", "true" if self.item.get("on") else "false")
        b.classList.toggle("on", bool(self.item.get("on")))

    def btn_click(self, event):
        self.parent.raise_event("x-pick", color=self.item["color"])
