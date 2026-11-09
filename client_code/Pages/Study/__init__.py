import random

from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import StudyTemplate
from ... import router, state

REQUEUE_GAP = 3   # a "still learning" card returns after this many other cards
MAX_REPEATS = 2   # ...at most this many extra times per session
GAPS = [0, 1, 3, 7, 16, 35, 90]  # keep in step with BOX_INTERVALS in server_code/QuizService.py


class Study(StudyTemplate):
    """An active-recall session (Operate). Three addresses, one page:
        #quiz/<id>     one part          #module/<id>  every part of a module, in order
        #review        the daily review of due cards from every module
    Screens: intro -> card (question; Space or a click shows the answer; rate yourself) -> summary.
    "Got it" sends the card further out (1, 3, 7, 16 ... days); "Still learning" brings it back later in this session
    and keeps it due. No multiple choice, ever: active recall is the point.

    Every rating is saved as it happens, one after another, without holding up the next card (rate_card through
    call_s in a queue); the summary waits for the queue, then finish_session awards XP and the streak.
    Keys: Space/Enter shows the answer, 1 = still learning, 2 = got it."""

    def __init__(self, args=(), mode="review", **properties):
        super().__init__(**properties)
        self.mode = mode
        self.quiz_id = args[0] if mode == "quiz" and args else None
        self.collection_id = args[0] if mode == "module" and args else None
        self._queue, self._busy, self._finish_pending, self._save_failed = [], False, False, False
        self._by_id: dict = {}
        self.card: dict = {}
        self.queue: list = []
        self.revealed = False
        self.screen = ""
        self._keys = anvil.js.report_exceptions(self._key)
        self._pump_soon = anvil.js.report_exceptions(self._pump)
        state.heading(self.title, 1)
        state.heading(self.done_title, 1)
        state.live(self.next_label)
        self.shuffle_box.checked = bool(state.store_get("shuffle", False))
        self.data: dict = self._load("due") or {}
        if not self.data:
            self._show("missing")
        else:
            self._intro()

    def _load(self, scope):
        if self.mode in ("quiz", "module") and not (self.quiz_id or self.collection_id):
            return None
        try:
            return state.learn("get_study", self.quiz_id, scope, state.today(), self.collection_id)
        except Exception as e:
            if "not found" in str(e):  # the part or module was removed or hidden
                return None
            raise

    # ------------------------------------------------------------ helpers
    def _show(self, which):
        self.intro.visible = which == "intro"
        self.card_view.visible = which == "card"
        self.done_view.visible = which == "done"
        self.missing.visible = which == "missing"
        self.screen = which

    def _quiz(self):
        return (self.data or {}).get("quiz") or {}

    def _back(self):
        """Where Back/Done goes: the module page, or Home for the daily review."""
        cid = self._quiz().get("collection_id")
        return (router.href("collection", cid), self._quiz().get("collection_title") or "Back") if cid else (router.href("home"), "Learning path")

    def _set_back(self, link, text_node):
        url, text = self._back()
        state.set_attr(link, "href", url)
        self.dom_nodes[text_node].textContent = text

    # ------------------------------------------------------------ intro
    def _intro(self):
        self._show("intro")
        q, c, cards = self._quiz(), self.data.get("counts") or {}, self.data.get("cards") or []
        mixed = not q.get("id") and not q.get("module_id")
        n = self.dom_nodes
        self._set_back(self.back_link, "back_text")
        state.set_attr(self.back_button, "href", self._back()[0])
        self.title.text = q.get("title") or ""
        self.description.text = q.get("description") or ""
        self.description.visible = bool(q.get("description"))
        if mixed:
            ctx = "Spaced repetition: cards come back just before you would forget them."
        elif q.get("number"):
            ctx = "Module %d · %s." % (q["number"], "whole module" if q.get("module_id") else (q.get("collection_title") or ""))
        else:
            ctx = (q.get("collection_title") or "") + "."
        n["context_text"].textContent = ctx
        self.source_part.visible = bool(q.get("source"))
        if q.get("source"):
            from ..Collection import host_of
            state.set_attr(self.source_link, "href", q["source"])
            n["source_host"].textContent = host_of(q["source"]) or q["source"]
        self.counts.visible = not mixed
        n["c_total"].textContent = state.plural(c.get("total") or 0, "card")
        n["c_learned"].textContent = "%d learned" % (c.get("learned") or 0)
        n["c_due"].textContent = "%d due" % (c.get("due") or 0)
        n["c_due"].hidden = not c.get("due")
        n["c_new"].textContent = "%d new" % (c.get("new") or 0)
        n["c_new"].hidden = not c.get("new")
        self.ready.visible = bool(cards)
        self.caught_up.visible = not cards
        if cards:
            n_new = len([x for x in cards if x.get("is_new")])
            n_rev = len(cards) - n_new
            self.start_button.text = "Start · " + state.plural(len(cards), "card")
            parts = [p for p in [("%d to review" % n_rev) if n_rev else "", ("%d new" % n_new) if n_new else ""] if p]
            limit = " (session limit)" if c.get("limit") and len(cards) >= c["limit"] else ""
            n["start_note"].textContent = " · ".join(parts) + limit
        else:
            n["next_text"].textContent = (self._due_text(c["next_due"]) + ".") if c.get("next_due") else "Nothing is due."
            self.all_button.visible = not mixed and bool(c.get("total"))
            self.all_button.text = "Study all %s anyway" % state.plural(c.get("total") or 0, "card")

    @staticmethod
    def _due_text(iso, count=0):
        if not iso:
            return ""
        when = state.when(iso)
        return ("%s due %s" % (state.plural(count, "card"), when)) if count else "Next card due " + when

    @handle("shuffle_box", "change")
    def shuffle_box_change(self, **event_args):
        state.store_set("shuffle", bool(self.shuffle_box.checked))

    @handle("start_button", "click")
    def start_button_click(self, **event_args):
        self._start(self.data.get("cards") or [])

    @handle("all_button", "click")
    def all_button_click(self, **event_args):
        self.all_button.enabled = False
        try:
            d = self._load("all")
        finally:
            self.all_button.enabled = True
        if d:
            self.data = d
            self._start(d.get("cards") or [])

    # ------------------------------------------------------------ the session
    def _start(self, cards):
        live = []
        for c in cards:  # one live copy per card, so its level carries over into "go again"
            if c["id"] not in self._by_id:
                self._by_id[c["id"]] = dict(c)
            live.append(self._by_id[c["id"]])
        if self.shuffle_box.checked:
            random.shuffle(live)
        self.queue = live
        self.total = len(live)
        self.ratings, self.seen, self.repeats = [], {}, {}
        self._next()
        state.focus(self.reveal_button)

    def _remaining(self):
        ids = {c["id"] for c in self.queue}
        if self.card:
            ids.add(self.card["id"])
        return len(ids)

    def _next(self):
        self.card = self.queue.pop(0) if self.queue else {}
        self.revealed = False
        if not self.card:
            self._finish()
            return
        self._show("card")
        self._draw_card()

    def _draw_card(self):
        c, n = self.card, self.dom_nodes
        left = self._remaining()
        done = self.total - left
        self.stop_button.text = "Finish" if self.ratings else "Stop"
        n["q_title"].textContent = self._quiz().get("title") or ""
        n["left"].textContent = "%d left" % left
        pct = int(100.0 * done / max(1, self.total))
        n["sess_fill"].style.width = "%d%%" % pct
        n["sess_bar"].setAttribute("aria-valuenow", str(pct))
        n["m_concept"].textContent = c.get("concept") or ""
        n["m_concept"].hidden = not c.get("concept")
        n["m_part"].textContent = c.get("quiz_title") or ""
        n["m_part"].hidden = not c.get("quiz_title")
        n["m_new"].hidden = not (c.get("is_new") and c["id"] not in self.seen)
        n["m_again"].hidden = not self.repeats.get(c["id"])
        box = c.get("box") or 0
        for i, dot in enumerate((n["d1"], n["d2"], n["d3"], n["d4"], n["d5"])):
            dot.className = "on" if box >= i + 1 else ""
        n["level"].setAttribute("aria-label", "Level %d of 5" % min(box, 5))
        self.qtext.text = c.get("text") or ""
        self.front.classes["clickable"] = not self.revealed
        self.reveal_row.visible = not self.revealed
        self.back_side.visible = self.revealed
        if self.revealed:
            self.answer.text = c.get("answer") or ""
            self.explanation.text = c.get("explanation") or ""
            self.explanation.visible = bool(c.get("explanation"))
            d = GAPS[min(box + 1, len(GAPS) - 1)]
            n["gap_text"].textContent = "see it again in " + ("1 day" if d == 1 else "%d days" % d)
            n["keys"].innerHTML = "<kbd>1</kbd> still learning · <kbd>2</kbd> got it"
        else:
            n["keys"].innerHTML = "<kbd>Space</kbd> show answer"

    def _reveal(self):
        if self.screen == "card" and not self.revealed:
            self.revealed = True
            self._draw_card()
            getattr(anvil.js.get_dom_node(self.back_side), "focus")()  # screen readers read the answer next

    def front_click(self, event):
        if not self.revealed and not event.target.closest("button"):
            self._reveal()

    @handle("reveal_button", "click")
    def reveal_button_click(self, **event_args):
        self._reveal()

    def again_click(self, event):
        self._rate(False)

    def got_click(self, event):
        self._rate(True)

    def _rate(self, knew):
        if self.screen != "card" or not self.revealed:
            return
        c = self.card
        self.ratings.append({"question_id": c["id"], "knew": knew, "first": c["id"] not in self.seen})
        self.seen[c["id"]] = True
        self._queue.append((c["id"], knew))
        window.setTimeout(self._pump_soon, 0)  # saved in the background, in order
        if knew:
            c["box"] = min((c.get("box") or 0) + 1, 6)
        else:
            c["box"] = 0
            if self.repeats.get(c["id"], 0) < MAX_REPEATS:
                self.repeats[c["id"]] = self.repeats.get(c["id"], 0) + 1
                self.queue.insert(min(REQUEUE_GAP, len(self.queue)), c)
        self._next()
        if self.screen == "card":
            state.focus(self.reveal_button)

    def _pump(self, *args):
        """Save the queued ratings one after another (no spinner, the next card is already showing)."""
        if self._busy:
            return
        self._busy = True
        try:
            while self._queue:
                qid, knew = self._queue.pop(0)
                try:
                    res = anvil.server.call_s(("guest_rate_card" if state.is_guest() else "rate_card"), qid, knew, state.today())
                    if isinstance(res, dict) and res.get("box") is not None and qid in self._by_id:
                        self._by_id[qid]["box"] = res["box"]
                except Exception as e:
                    if not self._save_failed:
                        state.toast("Could not save a rating: %s" % e, "error")
                    self._save_failed = True
        finally:
            self._busy = False
        if self._finish_pending and not self._queue:
            self._finish_pending = False
            self._save_session()

    @handle("stop_button", "click")
    def stop_button_click(self, **event_args):
        if self.ratings:
            self.queue = []
            self.card = {}
            self._finish()
        else:
            self._intro()

    # ------------------------------------------------------------ the summary
    def _finish(self):
        if not self.ratings:
            self._intro()
            return
        self._show("done")
        n = self.dom_nodes
        first, last, order = {}, {}, []
        for r in self.ratings:
            if r["question_id"] not in first:
                first[r["question_id"]] = r["knew"]
                order.append(r["question_id"])
            last[r["question_id"]] = r["knew"]
        total = len(order)
        first_try = len([i for i in order if first[i]])
        still = [i for i in order if not last[i]]
        recovered = total - first_try - len(still)
        self.still_cards = [self._by_id[i] for i in still if i in self._by_id]
        self._set_back(self.done_back, "done_back_text")
        self.done_title.text = "%s · session complete" % (self._quiz().get("title") or "")
        n["n_reviewed"].textContent = str(total)
        n["n_reviewed_k"].textContent = "card reviewed" if total == 1 else "cards reviewed"
        n["split_g"].style.width = "%.2f%%" % (100.0 * (total - len(still)) / total)
        n["split_a"].style.width = "%.2f%%" % (100.0 * len(still) / total)
        n["r_first"].textContent = "%d got it first time" % first_try
        n["r_recovered"].textContent = "%d after another look" % recovered
        n["r_recovered"].hidden = not recovered
        n["r_still"].textContent = "%d still learning" % len(still)
        n["r_still"].hidden = not still
        self.next_label.text = ""
        self.gains_saving.visible, self.gains.visible = True, False
        self.again_all_button.visible = bool(self.still_cards)
        self.again_all_button.text = "Go again with the %s I'm still learning" % state.plural(len(self.still_cards), "card")
        self.done_button.role = ["btn"] if self.still_cards else ["btn", "btn-primary"]
        self.still_part.visible = bool(self.still_cards)
        self.still_panel.items = self.still_cards
        self._still_count = len(still)
        self._finish_pending = True
        window.setTimeout(self._pump_soon, 0)

    def _save_session(self):
        ratings = [{"question_id": r["question_id"], "knew": r["knew"], "first": r["first"]} for r in self.ratings]
        n = self.dom_nodes
        try:
            res = state.learn("finish_session", self._quiz().get("id"), ratings, state.today(), self.collection_id) or {}
        except Exception as e:
            self.gains_saving.visible, self.gains.visible = False, True
            for key in ("g_xp", "g_streak", "g_saved"):
                n[key].hidden = True
            n["g_failed"].hidden = False
            state.toast("Could not save the session: %s" % e, "error")
            return
        if res.get("me"):
            state.set_me(res["me"])
            shell = getattr(self, "layout", None)
            if shell is not None and hasattr(shell, "refresh"):
                shell.refresh(router.current())  # XP and streak in the header
        self.gains_saving.visible, self.gains.visible = False, True
        n["g_xp"].textContent = "+%d XP" % (res.get("xp_gained") or 0)
        n["g_xp"].hidden = not res.get("xp_gained")
        n["g_streak"].textContent = "🔥 %d-day streak" % (res.get("streak") or 0)
        n["g_streak"].hidden = not res.get("streak")
        n["g_saved"].hidden = bool(res.get("xp_gained") or res.get("streak"))
        n["g_failed"].hidden = True
        if self._still_count:
            self.next_label.text = "Cards you are still learning stay due, so they will be in your next review."
        elif res.get("next_due"):
            self.next_label.text = self._due_text(res["next_due"]) + ". Come back then to keep the streak going."

    @handle("again_all_button", "click")
    def again_all_button_click(self, **event_args):
        self._start(self.still_cards)

    @handle("done_button", "click")
    def done_button_click(self, **event_args):
        window.location.hash = self._back()[0]

    # ------------------------------------------------------------ keyboard
    def _key(self, event):
        k = getattr(event, "key", None)  # browser autofill fires "keydown" events that carry no key
        if not k or self.screen != "card" or getattr(event, "ctrlKey", False) or getattr(event, "metaKey", False) or getattr(event, "altKey", False):
            return
        tag = str(getattr(event.target, "tagName", "") or "")
        if tag in ("INPUT", "TEXTAREA", "SELECT"):
            return
        if not self.revealed and k in (" ", "Enter") and tag != "BUTTON":  # a focused button does its own job
            event.preventDefault()
            self._reveal()
        elif self.revealed and k == "1":
            event.preventDefault()
            self._rate(False)
        elif self.revealed and k == "2":
            event.preventDefault()
            self._rate(True)
        elif self.revealed and k in (" ", "Enter") and tag != "BUTTON":
            event.preventDefault()  # Space after revealing doesn't scroll; a focused rating button still works

    @handle("", "show")
    def form_show(self, **event_args):
        window.document.addEventListener("keydown", self._keys)

    @handle("", "hide")
    def form_hide(self, **event_args):
        window.document.removeEventListener("keydown", self._keys)
