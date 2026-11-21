import datetime
import math

from anvil import *

from ._anvil_designer import HomeTemplate
from ... import router, state

FILTERS = ("track", "all", "todo", "due", "done")
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
LIGHT_DAY = 25  # cards a "welcome back" day suggests


def finish_day(days):
    """'tomorrow', 'Friday' or '2 Dec': the day a backlog is cleared when it takes this many daily sessions."""
    end = datetime.date.today() + datetime.timedelta(days=days - 1)
    if days == 2:
        return "tomorrow"
    if days <= 7:
        return WEEKDAYS[end.weekday()]
    return state.short_date(end.isoformat())


class Home(HomeTemplate):
    """#home (Operate): the greeting, four stat tiles (the streak with its shields), the mission plan card (track,
    target date, readiness bar, daily pace; Dialogs/Plan), the "continue" card (due reviews first, a "welcome back"
    light day after a break or a pile-up, else the next part with new cards in the track's order), the learning path
    (a segment per module, a filter remembered on this device incl. "My track", one row per module) and the last five
    sessions. Data: get_home (or guest_get_home)."""

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
        shields_on, held = bool(me.get("shields_on")), me.get("shields") or 0
        n["s_shields"].hidden = not (shields_on and held)
        n["s_shield_n"].textContent = str(held)
        n["s_shields"].setAttribute("title", state.plural(held, "streak shield"))
        n["s_shields"].setAttribute("aria-label", state.plural(held, "streak shield"))
        n["shield_hint"].hidden = not shields_on
        self._draw_plan()

        # the "continue" card
        self.cont_link.visible = bool(cont)
        self.calm_box.visible = not cont and bool(st.get("total_cards"))
        away = d.get("away_days") or 0
        if cont and cont.get("kind") == "review" and (due > 50 or away >= 3):
            # Welcome back: a pile of reviews is normal after a break. A light day and a plain finish day.
            size = min(LIGHT_DAY, state.store_get("sessSize", 50) or 50)
            days = int(math.ceil(due / float(size)))
            state.set_attr(self.cont_link, "href", router.href("review", "light"))
            n["cont_icon"].className = "ic ic-sun"
            n["cont_title"].textContent = "Welcome back. %s piled up, which is fine." % state.plural(due, "card")
            if days <= 1:
                n["cont_meta"].textContent = "One short session clears them. Cards come back most overdue first."
            else:
                n["cont_meta"].textContent = "Do %d today; at %d a day you're clear by %s." % (size, size, finish_day(days))
            n["cont_badge"].className = "badge warn"
            n["cont_badge"].textContent = "%d today" % min(size, due)
        elif cont and cont.get("kind") == "review":
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
            if cont.get("track"):
                lead = "Your track · " + lead
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

    # ---- mission plan
    def _draw_plan(self):
        d, n = self.data, self.dom_nodes
        p, ready = d.get("plan"), bool(d.get("plan_ready"))
        self.plan_empty.visible = ready and not p and bool(d.get("tracks"))
        self.plan_box.visible = ready and bool(p)
        if not p:
            return
        total = p.get("total") or 0
        r, s, ns = p.get("ready") or 0, p.get("shaky") or 0, p.get("not_started") or 0
        n["plan_title"].textContent = p.get("title") or "Your track"
        label, days = p.get("label") or "Your date", p.get("days_left")
        if days is None:
            n["plan_when"].textContent = "No date set · study at your own pace"
        elif days > 1:
            n["plan_when"].textContent = "%s in %d days · %s" % (label, days, state.fmt_date(p.get("target_date")))
        elif days == 1:
            n["plan_when"].textContent = "%s tomorrow" % label
        elif days == 0:
            n["plan_when"].textContent = "%s is today" % label
        else:
            n["plan_when"].textContent = "%s was on %s" % (label, state.fmt_date(p.get("target_date")))
        n["plan_pct"].textContent = "%d%%" % (int(round(100.0 * r / total)) if total else 0)
        for node, v in ((n["bar_r"], r), (n["bar_s"], s), (n["bar_n"], ns)):
            node.style.width = "%.2f%%" % ((100.0 * v / total) if total else 0)
        n["lg_r"].textContent, n["lg_s"].textContent, n["lg_n"].textContent = str(r), str(s), str(ns)
        k = p.get("new_per_day")
        if not total:
            pace = "This track's modules aren't in the guide yet. Change the track to keep going."
        elif not ns:
            pace = "Every card in this track is started. Keep up the reviews and the Shaky ones turn Ready."
        elif days is None:
            pace = "%s not started yet. Add a date to get a daily pace." % state.plural(ns, "card")
        elif days == 0:
            pace = "Good luck today. A quick review of the Shaky cards is the best last-minute study."
        elif days < 0:
            pace = "That date has passed. Change it, or keep going at your own pace."
        else:
            pace = "About %s a day gets you there%s." % (state.plural(k or 0, "new card"),
                                                        " with a week to spare" if p.get("buffer") else " on time")
        n["plan_pace"].textContent = pace

    def _open_plan(self):
        from ...Dialogs.Plan import Plan
        d = self.data
        saved = alert(Plan(tracks=d.get("tracks") or [], labels=d.get("plan_labels") or [], plan=d.get("plan")),
                      buttons=[], large=False, role="app-dialog", dismissible=True)
        if saved:
            self.data = state.learn("get_home", state.today())
            p = self.data.get("plan") or {}
            if p.get("track") and p.get("track") != "all":
                self._filter = "track"
                state.store_set("modFilter", "track")
            self._draw()
            state.toast("Plan saved: %s" % (p.get("title") or "your track"), "ok")

    @handle("plan_choose", "click")
    def plan_choose_click(self, **event_args):
        self._open_plan()

    @handle("plan_change", "click")
    def plan_change_click(self, **event_args):
        self._open_plan()

    def _track_on(self):
        p = self.data.get("plan") or {}
        return bool(p.get("track")) and p.get("track") != "all"

    @staticmethod
    def _pct(m):
        return int(round(100.0 * (m.get("learned") or 0) / m["card_count"])) if m.get("card_count") else 0

    def _draw_modules(self):
        mods = (self.data.get("collections") or [])
        track_on = self._track_on()
        if self._filter == "track" and not track_on:
            self._filter = "all"
        f = self._filter
        self.f_track.visible = track_on
        if f == "track":
            order = (self.data.get("plan") or {}).get("modules") or []
            shown = sorted([m for m in mods if m.get("number") in order], key=lambda m: order.index(m.get("number")))
        else:
            shown = [m for m in mods if f == "all" or (f == "todo" and not m.get("complete")) or (f == "due" and m.get("due"))
                     or (f == "done" and m.get("complete"))]
        self.modules_panel.items = shown
        self.no_modules.visible = not mods
        self.no_match.visible = bool(mods) and not shown
        for name, el in zip(FILTERS, (self.f_track, self.f_all, self.f_todo, self.f_due, self.f_done)):
            el.classes["on"] = name == f

    def filter_click(self, event):
        self._filter = event.currentTarget.getAttribute("data-f")
        state.store_set("modFilter", self._filter)
        self._draw_modules()
