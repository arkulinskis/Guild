from anvil import *

from ._anvil_designer import SessionRowTemplate
from ... import router, state


def session_href(r):
    """A finished session links back to what was studied: the part, the whole module, or the daily review."""
    if r.get("quiz_id"):
        return router.href("quiz", r["quiz_id"])
    if r.get("collection_id"):
        return router.href("collection", r["collection_id"])
    return router.href("review")


class SessionRow(SessionRowTemplate):
    """One recent session on Home. item = a session from get_home: quiz_id, collection_id, title, collection_title,
    finished, reviewed, again."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r, n = self.item, self.dom_nodes
        state.set_attr(self.row, "href", session_href(r))
        n["title"].textContent = r.get("title") or ""
        n["sub"].textContent = "%s · %s" % (r.get("collection_title") or "", state.fmt_date(r.get("finished")))
        n["count"].textContent = state.plural(r.get("reviewed") or 0, "card")
        n["again"].className = "badge " + ("warn" if r.get("again") else "good")
        n["again"].textContent = ("%d still learning" % r["again"]) if r.get("again") else "all got it"
