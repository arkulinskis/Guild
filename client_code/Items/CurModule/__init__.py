from anvil import *
import anvil.js

from ._anvil_designer import CurModuleTemplate
from ... import router, state


class CurModule(CurModuleTemplate):
    """One module on Manage curriculum. item = {"m": module from admin_curriculum, "page": the Curriculum page}.
    The title button opens it (its parts); Edit / Download JSON / Delete call back into the page."""

    def __init__(self, **properties):
        super().__init__(**properties)
        m, page, n = self.item["m"], self.item["page"], self.dom_nodes
        is_open = m["id"] in page.open
        parts = m.get("parts") or []
        anvil.js.get_dom_node(self.box).style.setProperty("--c", m.get("color") or "")
        n["tog"].setAttribute("aria-expanded", "true" if is_open else "false")
        n["tog"].setAttribute("data-key", "mod:" + m["id"])
        n["num"].textContent = state.pad(m.get("number"))
        n["title"].textContent = m.get("title") or ""
        n["sub"].textContent = "%s · %s" % (state.plural(len(parts), "part"), state.plural(m.get("card_count") or 0, "card"))
        self.hidden_badge.visible = not m.get("published")
        for btn, what in ((self.edit_button, "Edit"), (self.export_button, "Download JSON"), (self.delete_button, "Delete")):
            state.set_control_attr(btn, "aria-label", "%s module %s" % (what, state.pad(m.get("number"))))
            state.set_control_attr(btn, "data-key", "%s:%s" % (what, m["id"]))
        self.body.visible = is_open
        if is_open:
            n["desc"].textContent = m.get("description") or ""
            n["desc"].hidden = not m.get("description")
            self.parts_panel.items = [{"p": p, "page": page} for p in parts]
            self.no_parts.visible = not parts
            self.learner_row.visible = bool(m.get("published"))
            state.set_attr(self.learner_link, "href", router.href("collection", m["id"]))

    def tog_click(self, event):
        self.item["page"].toggle(self.item["m"]["id"])

    @handle("edit_button", "click")
    def edit_button_click(self, **event_args):
        self.item["page"].edit_module(self.item["m"]["id"])

    @handle("export_button", "click")
    def export_button_click(self, **event_args):
        self.item["page"].export(self.item["m"]["id"])

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        self.item["page"].delete("module", self.item["m"]["id"])
