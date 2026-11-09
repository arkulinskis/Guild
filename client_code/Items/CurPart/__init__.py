from anvil import *

from ._anvil_designer import CurPartTemplate
from ... import state


class CurPart(CurPartTemplate):
    """One part inside an open module on Manage curriculum. item = {"p": part, "page": the Curriculum page}.
    Opening it shows its cards (loaded by the page the first time); Preview / Edit / Delete / Add a card call back
    into the page."""

    def __init__(self, **properties):
        super().__init__(**properties)
        p, page, n = self.item["p"], self.item["page"], self.dom_nodes
        is_open = p["id"] in page.open
        n["tog"].setAttribute("aria-expanded", "true" if is_open else "false")
        n["tog"].setAttribute("data-key", "part:" + p["id"])
        n["num"].textContent = str(p.get("number") or "")
        n["title"].textContent = p.get("title") or ""
        n["sub"].textContent = state.plural(p.get("card_count") or 0, "card")
        self.hidden_badge.visible = not p.get("published")
        self.preview_button.enabled = bool(p.get("card_count"))
        for btn, what in ((self.preview_button, "Preview"), (self.edit_button, "Edit"), (self.delete_button, "Delete")):
            state.set_control_attr(btn, "aria-label", "%s part: %s" % (what, p.get("title") or ""))
            state.set_control_attr(btn, "data-key", "%s:%s" % (what, p["id"]))
        state.set_control_attr(self.add_button, "data-key", "add:" + p["id"])
        self.body.visible = is_open
        if is_open:
            n["desc"].textContent = p.get("description") or ""
            n["desc"].hidden = not p.get("description")
            cs = page.cards.get(p["id"])
            if isinstance(cs, dict):
                self.load_msg.text, self.load_msg.visible = cs.get("error") or "", True
                cs = []
            cs = cs or []
            self.cards_panel.items = [{"c": c, "i": i, "part": p["id"], "page": page} for i, c in enumerate(cs)]
            self.cards_list.visible = bool(cs)
            self.no_cards.visible = not cs and not self.load_msg.visible

    def tog_click(self, event):
        self.item["page"].toggle(self.item["p"]["id"], part=True)

    @handle("preview_button", "click")
    def preview_button_click(self, **event_args):
        self.item["page"].preview(self.item["p"]["id"])

    @handle("edit_button", "click")
    def edit_button_click(self, **event_args):
        self.item["page"].edit_part(self.item["p"]["id"])

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        self.item["page"].delete("part", self.item["p"]["id"])

    @handle("add_button", "click")
    def add_button_click(self, **event_args):
        self.item["page"].edit_card(self.item["p"]["id"], None)
