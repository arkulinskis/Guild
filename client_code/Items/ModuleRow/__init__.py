from anvil import *
import anvil.js

from ._anvil_designer import ModuleRowTemplate
from ... import router, state


class ModuleRow(ModuleRowTemplate):
    """One module on the learning path (Home). item = a collection summary from get_home: id, number, title,
    description, color, card_count, learned, due, started, complete. The whole row links to #collection/<id>."""

    def __init__(self, **properties):
        super().__init__(**properties)
        m, n = self.item, self.dom_nodes
        total, learned = m.get("card_count") or 0, m.get("learned") or 0
        pct = int(round(100.0 * learned / total)) if total else 0
        state.set_attr(self.row, "href", router.href("collection", m["id"]))
        node = anvil.js.get_dom_node(self.row)
        node.style.setProperty("--c", m.get("color") or "")
        self.row.classes["complete"] = bool(m.get("complete"))
        n["num"].textContent = "✓" if m.get("complete") else state.pad(m.get("number"))
        n["title"].textContent = m.get("title") or ""
        n["sub"].textContent = m.get("description") or ""
        n["bar"].style.width = "%d%%" % pct
        n["mini"].setAttribute("title", "%d of %d cards learned" % (learned, total))
        n["count"].textContent = "%d/%d" % (learned, total)
        if m.get("complete"):
            kind, text = "good", "✓ complete"
        elif m.get("due"):
            kind, text = "warn", "%d due" % m["due"]
        elif m.get("started"):
            kind, text = "accent", "in progress"
        else:
            kind, text = "", "not started"
        n["status"].className = "badge " + kind
        n["status"].textContent = text
        node.setAttribute("aria-label", "Module %d: %s. %d of %d cards learned, %s." % (m.get("number") or 0, m.get("title") or "", learned, total, text.replace("✓ ", "")))
