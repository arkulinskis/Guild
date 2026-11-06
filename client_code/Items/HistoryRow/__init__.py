from anvil import *

from ._anvil_designer import HistoryRowTemplate
from ... import state
from ..SessionRow import session_href


class HistoryRow(HistoryRowTemplate):
    """One finished session in Profile's "Recent sessions". item = a session dict from get_profile."""

    def __init__(self, **properties):
        super().__init__(**properties)
        h, n = self.item, self.dom_nodes
        state.set_attr(self.row, "href", session_href(h))
        n["title"].textContent = h.get("title") or ""
        n["col"].textContent = h.get("collection_title") or ""
        n["when"].textContent = state.fmt_date(h.get("finished"))
        n["count"].textContent = "%d reviewed" % (h.get("reviewed") or 0)
        n["again"].className = "badge " + ("warn" if h.get("again") else "good")
        n["again"].textContent = ("%d still learning" % h["again"]) if h.get("again") else "all got it"
