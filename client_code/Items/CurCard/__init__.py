from anvil import *

from ._anvil_designer import CurCardTemplate
from ... import state


class CurCard(CurCardTemplate):
    """One card inside an open part on Manage curriculum: question, answer, explanation, concept.
    item = {"c": card from admin_part_cards, "i": its place, "part": the part id, "page": the Curriculum page}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c, n = self.item["c"], self.dom_nodes
        n["n"].textContent = str(self.item["i"] + 1)
        n["q"].textContent = c.get("question") or ""
        n["a"].textContent = c.get("answer") or ""
        n["e"].textContent = c.get("explanation") or ""
        n["concept"].textContent = c.get("concept") or ""
        n["concept"].hidden = not c.get("concept")
        n["e_row"].hidden = not (c.get("explanation") or c.get("concept"))
        for btn, what in ((self.edit_button, "Edit"), (self.delete_button, "Delete")):
            state.set_control_attr(btn, "aria-label", "%s card %d" % (what, self.item["i"] + 1))
            state.set_control_attr(btn, "data-key", "%s:%s" % (what, c["id"]))

    @handle("edit_button", "click")
    def edit_button_click(self, **event_args):
        self.item["page"].edit_card(self.item["part"], self.item["c"])

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        self.item["page"].delete("card", self.item["c"]["id"], self.item["part"])
