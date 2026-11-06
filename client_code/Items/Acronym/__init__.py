from anvil import *

from ._anvil_designer import AcronymTemplate


class Acronym(AcronymTemplate):
    """One Lookup result in the header's dictionary. item = {abbr, meaning, src} (src: the modules it appears in)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        n = self.dom_nodes
        n["abbr"].textContent = self.item["abbr"]
        n["meaning"].textContent = self.item["meaning"]
        n["src"].textContent = self.item.get("src") or ""
        n["src"].hidden = not self.item.get("src")
