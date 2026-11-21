import datetime

from anvil import *

from ._anvil_designer import PlanTemplate
from ... import state

TRACK_KEYS = ("joining", "officer", "policy", "history", "all")


class Plan(PlanTemplate):
    """Mission plan (Home): pick a track (who it's for, its cards and modules), an optional target date and what the
    date is for. tracks/labels come from get_home; plan = the current plan or None. Saves with save_plan (guests:
    guest_save_plan); problems show inside the dialog. Closes with True once saved, else None."""

    def __init__(self, tracks=(), labels=(), plan=None, **properties):
        super().__init__(**properties)
        state.heading(self.heading, 2)
        p = plan or {}
        self.track = p.get("track") or "joining"
        self.label = p.get("label") or "Recruiting interview"
        n = self.dom_nodes
        by_key = {t.get("key"): t for t in (tracks or [])}
        for key in TRACK_KEYS:
            t = by_key.get(key) or {}
            n["t_" + key].textContent = t.get("title") or key.title()
            n["w_" + key].textContent = t.get("who") or ""
            cards, mods = t.get("cards") or 0, t.get("modules") or 0
            n["n_" + key].textContent = ("%s · %s" % (state.plural(cards, "card"), state.plural(mods, "module"))) if cards else "No cards yet"
        today = datetime.date.today()
        state.set_control_attr(self.date_box, "type", "date")
        state.set_control_attr(self.date_box, "min", (today + datetime.timedelta(days=1)).isoformat())
        state.set_control_attr(self.date_box, "max", (today + datetime.timedelta(days=730)).isoformat())
        state.set_control_attr(self.date_box, "aria-label", "Target date (optional)")
        self.date_box.text = p.get("target_date") or ""
        self._draw()

    def _draw(self):
        for key in TRACK_KEYS:
            el = getattr(self, "tr_" + key)
            el.classes["on"] = key == self.track
            state.set_attr(el, "aria-pressed", "true" if key == self.track else "false")
        for el, value in ((self.l_bmq, "BMQ start"), (self.l_interview, "Recruiting interview"), (self.l_course, "Course"),
                          (self.l_exam, "Exam"), (self.l_own, "Own goal")):
            el.classes["on"] = value == self.label
            state.set_attr(el, "aria-pressed", "true" if value == self.label else "false")

    def track_click(self, event):
        self.track = event.currentTarget.getAttribute("data-track")
        self._draw()

    def label_click(self, event):
        self.label = event.currentTarget.getAttribute("data-l")
        self._draw()

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        when = (self.date_box.text or "").strip() or None
        self.save_button.enabled = False
        try:
            r = state.learn("save_plan", self.track, when, self.label if when else None, state.today())
        finally:
            self.save_button.enabled = True
        if not r or not r.get("ok"):
            self.message.text = (r or {}).get("error") or "Could not save your plan."
            self.message.visible = True
            return
        self.raise_event("x-close-alert", value=True)
