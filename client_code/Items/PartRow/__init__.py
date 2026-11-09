import re

from anvil import *

from ._anvil_designer import PartRowTemplate
from ... import router, state


class PartRow(PartRowTemplate):
    """One part of a module (Collection page). item = a quiz from get_collection + i (its place): id, title,
    description, difficulty, card_count, learned, due, new. The row links to #quiz/<id>."""

    def __init__(self, **properties):
        super().__init__(**properties)
        q, n = self.item, self.dom_nodes
        total, learned = q.get("card_count") or 0, q.get("learned") or 0
        done = bool(total) and learned == total
        state.set_attr(self.row, "href", router.href("quiz", q["id"]))
        n["num"].textContent = "✓" if done else str((q.get("i") or 0) + 1)
        n["num"].classList.toggle("done", done)
        n["title"].textContent = re.sub(r"^Part \d+ · ", "", q.get("title") or "")
        n["sub"].textContent = q.get("description") or ""
        n["bar"].style.width = "%d%%" % (int(round(100.0 * learned / total)) if total else 0)
        n["mini"].setAttribute("title", "%d of %d learned" % (learned, total))
        n["difficulty"].textContent = q.get("difficulty") or ""
        n["difficulty"].hidden = not q.get("difficulty")
        n["count"].textContent = "%d/%d" % (learned, total)
        if q.get("due"):
            kind, text = "warn", "%d due" % q["due"]
        elif q.get("new") == total:
            kind, text = "", "not started"
        elif q.get("new"):
            kind, text = "accent", "%d new" % q["new"]
        else:
            kind, text = "good", "up to date"
        n["status"].className = "badge " + kind
        n["status"].textContent = text
