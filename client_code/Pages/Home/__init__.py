import datetime

from anvil import *

from ._anvil_designer import HomeTemplate
from ... import router, state

FILTERS = ("all", "todo", "due", "done")


class Home(HomeTemplate):
    """#home (Operate): the greeting, four stat tiles, the "continue" card (due reviews first, else the next part with
    new cards), the learning path (a segment per module, a filter remembered on this device, one row per module)
    and the last five sessions. Data: get_home (or guest_get_home)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.data = state.learn("get_home", state.today())
        state.heading(self.greeting, 1)
        f = state.store_get("modFilter", "all")
        self._filter = f if f in FILTERS else "all"
        self._draw()

    def _draw(self):
        d = self.data
        me, st, mods, recent, cont = d.get("me") or {}, d.get("stats") or {}, d.get("collections") or [], d.get("recent") or [], d.get("continue")
        h = datetime.datetime.now().hour
        first = (me.get("display_name") or "").split(" ")[0]
        self.greeting.text = ("Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening") + (", " + first if first else "")
        total, done = st.get("modules_total") or len(mods), st.get("modules_complete") or 0
        due = st.get("due") or 0
        if due:
            self.lead.text = "You have %s to review today." % state.plural(due, "card")
        elif total:
            self.lead.text = "Work through %d learning modules about the Canadian Armed Forces, one card at a time." % total
        else:
            self.lead.text = "The learning modules will appear here once they are imported."
        n = self.dom_nodes
        n["s_done"].textContent = str(done)
        n["s_done_of"].textContent = " / %d" % total
        n["s_learned"].textContent = str(st.get("learned") or 0)
        n["s_learned_of"].textContent = " / %d" % (st.get("total_cards") or 0)
        n["s_due"].textContent = str(due)
        n["s_streak"].textContent = "%d%s" % (st.get("streak") or 0, " 🔥" if st.get("streak") else "")

        # the "continue" card
        self.cont_link.visible = bool(cont)
        self.calm_box.visible = not cont and bool(st.get("total_cards"))
        if cont and cont.get("kind") == "review":
            state.set_attr(self.cont_link, "href", router.href("review"))
            n["cont_icon"].className = "ic ic-refresh"
            n["cont_title"].textContent = cont.get("title") or ""
            n["cont_meta"].textContent = "Due today · " + (cont.get("subtitle") or "")
            n["cont_badge"].className = "badge warn"
            n["cont_badge"].textContent = str(cont.get("due") or "")
        elif cont:
            state.set_attr(self.cont_link, "href", router.href("quiz", cont.get("quiz_id")))
            n["cont_icon"].className = "ic ic-play"
            n["cont_title"].textContent = cont.get("title") or ""
            lead = ("Keep going" if cont.get("started") else "Start learning") + ((" · Module %d" % cont["module"]) if cont.get("module") else "")
            n["cont_meta"].textContent = lead + " · " + (cont.get("subtitle") or "")
            n["cont_badge"].className = "badge accent"
            n["cont_badge"].textContent = "new"
        n["calm_next"].textContent = ("Your next review is %s." % state.when(st["next_due"])) if st.get("next_due") else ""

        # the learning path
        n["n_modules"].textContent = state.plural(total, "module")
        self.path_top.visible = bool(mods)
        n["path_big"].textContent = "%d of %d" % (done, total)
        n["path_sub"].textContent = "modules complete · %d started" % (st.get("modules_started") or 0)
        self.seg_panel.items = [{"pct": 100 if m.get("complete") else self._pct(m), "done": bool(m.get("complete"))} for m in mods]
        self._draw_modules()
        self.recent_section.visible = bool(recent)
        self.recent_panel.items = recent

    @staticmethod
    def _pct(m):
        return int(round(100.0 * (m.get("learned") or 0) / m["card_count"])) if m.get("card_count") else 0

    def _draw_modules(self):
        mods = (self.data.get("collections") or [])
        f = self._filter
        shown = [m for m in mods if f == "all" or (f == "todo" and not m.get("complete")) or (f == "due" and m.get("due"))
                 or (f == "done" and m.get("complete"))]
        self.modules_panel.items = shown
        self.no_modules.visible = not mods
        self.no_match.visible = bool(mods) and not shown
        for name, el in zip(FILTERS, (self.f_all, self.f_todo, self.f_due, self.f_done)):
            el.classes["on"] = name == f

    def filter_click(self, event):
        self._filter = event.currentTarget.getAttribute("data-f")
        state.store_set("modFilter", self._filter)
        self._draw_modules()
