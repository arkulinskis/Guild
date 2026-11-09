from anvil import *

from ._anvil_designer import SegTemplate


class Seg(SegTemplate):
    """One module's segment in the learning-path bar on Home (decoration: the bar is aria-hidden).
    item = {pct, done}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.dom_nodes["seg"].classList.toggle("done", bool(self.item.get("done")))
        self.dom_nodes["fill"].style.width = "%d%%" % (self.item.get("pct") or 0)
