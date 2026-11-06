from anvil import *
import anvil.js

from ._anvil_designer import ProgressRowTemplate
from ... import router, state


class ProgressRow(ProgressRowTemplate):
    """One module's progress on the Profile page. item = {id, number, title, color, learned, total, due, complete};
    links to #collection/<id>."""

    def __init__(self, **properties):
        super().__init__(**properties)
        p, n = self.item, self.dom_nodes
        total, learned = p.get("total") or 0, p.get("learned") or 0
        state.set_attr(self.row, "href", router.href("collection", p.get("id")))
        anvil.js.get_dom_node(self.row).style.setProperty("--c", p.get("color") or "")
        n["title"].textContent = ("✓ " if p.get("complete") else "") + ((state.pad(p["number"]) + " · ") if p.get("number") else "") + (p.get("title") or "")
        n["count"].textContent = "%d/%d%s" % (learned, total, (" · %d due" % p["due"]) if p.get("due") else "")
        n["bar"].style.width = "%d%%" % (int(round(100.0 * learned / total)) if total else 0)
