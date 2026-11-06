from anvil import *

from ._anvil_designer import StillCardTemplate


class StillCard(StillCardTemplate):
    """A card still in rotation, on the study summary: the question opens to show the answer.
    item = a study card {text, answer, explanation}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c, n = self.item, self.dom_nodes
        n["q"].textContent = c.get("text") or ""
        n["a"].textContent = c.get("answer") or ""
        n["e"].textContent = c.get("explanation") or ""
        n["e"].hidden = not c.get("explanation")
