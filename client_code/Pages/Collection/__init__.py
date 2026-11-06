from anvil import *
import anvil.js

from ._anvil_designer import CollectionTemplate
from ... import router, state


def host_of(url):
    """'https://www.canada.ca/en/...' -> 'canada.ca' (shown as the source link)."""
    rest = (url or "").split("://", 1)[-1]
    host = rest.split("/", 1)[0]
    return host[4:] if host.startswith("www.") else host


class Collection(CollectionTemplate):
    """#collection/<id> (Operate): one learning module: its number, source, overall progress, a button to study the
    whole module (#module/<id>) and its parts (#quiz/<id>). Data: get_collection (or the guest twin); a module that
    is gone or hidden shows a friendly "not found"."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.col_id = args[0] if args else None
        self.data: dict = {}
        try:
            self.data = state.learn("get_collection", self.col_id, state.today()) if self.col_id else {}
        except Exception:
            self.data = {}
        state.heading(self.title, 1)
        self.found.visible = bool(self.data)
        self.missing.visible = not self.data
        if self.data:
            self._draw()

    def _draw(self):
        c, parts = self.data.get("collection") or {}, self.data.get("quizzes") or []
        n = self.dom_nodes
        anvil.js.get_dom_node(self.wrap).style.setProperty("--c", c.get("color") or "")
        if c.get("number"):
            n["crumb_mod"].textContent = "Module %d%s" % (c["number"], (" of %d" % c["modules_total"]) if c.get("modules_total") else "")
        self.title.text = c.get("title") or ""
        self.description.text = c.get("description") or ""
        self.description.visible = bool(c.get("description"))
        self.src_line.visible = bool(c.get("source"))
        if c.get("source"):
            state.set_attr(self.src_link, "href", c["source"])
            n["src_host"].textContent = host_of(c["source"]) or c["source"]
        total = sum(q.get("card_count") or 0 for q in parts)
        learned = sum(q.get("learned") or 0 for q in parts)
        due = sum(q.get("due") or 0 for q in parts)
        fresh = sum(q.get("new") or 0 for q in parts)
        pct = int(round(100.0 * learned / total)) if total else 0
        complete = total > 0 and learned >= total
        self.study_button.visible = self.summary.visible = total > 0
        self.study_button.text = "Review this module" if complete else ("Study this module" if due + fresh else "Study ahead")
        n["sum_learned"].textContent = "%d of %d cards learned" % (learned, total)
        n["sum_pct"].textContent = "· %d%%" % pct
        self.b_complete.visible = complete
        n["b_due"].textContent = "%d due" % due
        n["b_due"].hidden = not due
        n["b_new"].textContent = "%d new" % fresh
        n["b_new"].hidden = not fresh
        n["bar_fill"].style.width = "%d%%" % pct
        n["bar"].setAttribute("aria-valuenow", str(pct))
        n["sum_parts"].textContent = "%s. Study the whole module in order, or pick a part below." % state.plural(len(parts), "part")
        self.parts_panel.items = [dict(q, i=i) for i, q in enumerate(parts)]
        self.no_parts.visible = not parts

    @handle("study_button", "click")
    def study_button_click(self, **event_args):
        router.go("module", self.col_id)
