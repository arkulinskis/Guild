import re

from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import ShellTemplate
from ... import auth, router, state

_ACRONYMS: dict = {"rows": None, "mods": {}}


def _squash(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def acronyms():
    """The Lookup dictionary (theme/assets/acronyms.js, built by tools/build_acronyms.py in the old project):
    rows of (abbreviation, meaning, [module numbers]), read from the page once."""
    if _ACRONYMS["rows"] is None:
        rows = []
        try:
            for r in window.QB_ACRONYMS:
                rows.append((str(r[0]), str(r[1]), [int(n) for n in r[2]]))
            mods = window.QB_ACRONYM_MODULES
            _ACRONYMS["mods"] = {str(k): str(mods[k]) for k in window.Object.keys(mods)}
        except Exception:
            pass
        _ACRONYMS["rows"] = rows
    return _ACRONYMS["rows"]


def lookup(query):
    """Exact abbreviation first, then abbreviations that start with it (shortest first), then meanings that contain
    the words (3+ letters). At most 30, like the old panel."""
    k, w = _squash(query), query.strip().lower()
    if not k:
        return []
    exact, prefix, words = [], [], []
    for r in acronyms():
        a = _squash(r[0])
        if a == k:
            exact.append(r)
        elif a.startswith(k):
            prefix.append(r)
        elif len(w) >= 3 and w in r[1].lower():
            words.append(r)
    prefix.sort(key=lambda r: len(r[0]))
    return (exact + prefix + words)[:30]


class Shell(ShellTemplate):
    """The frame around every page: the header (signed-in learners and guests only, as before: the sign-in page has
    no top bar), the Lookup panel, the guest strip, and the footer with the civilian disclaimer and its four links
    (Submit feedback, Privacy & Terms, Contact developer, Parent company).

    Anvil keeps ONE Shell while pages come and go (open_form only swaps the "content" slot when the layout matches),
    so everything that depends on who is signed in or which page is open is drawn in refresh(), which router.show()
    calls after every page change. Never only in __init__."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self._outside = anvil.js.report_exceptions(self._close_outside)
        self._keys = anvil.js.report_exceptions(self._key)
        self._resize = anvil.js.report_exceptions(self._foot_height)
        state.set_control_attr(self.lookup_box, "aria-label", "Abbreviation to look up")
        state.set_control_attr(self.lookup_box, "type", "search")
        state.set_control_attr(self.lookup_box, "autocomplete", "off")
        state.set_control_attr(self.lookup_box, "spellcheck", "false")
        self.lookup.visible = False
        self.refresh("")

    def refresh(self, page=None):
        me = state.me()
        self.classes.update({"signed-in": bool(me), "signed-out": not me})
        root = window.document.documentElement
        if root is not None:
            root.classList.toggle("qb-signed-out", not me)
        self.header.visible = bool(me)
        self._open_menu(False)
        self._open_lookup(False)
        if not me:
            return
        guest = bool(me.get("guest"))
        self.guest_strip.visible = guest
        n = self.dom_nodes
        n["xp"].textContent = "%d XP%s" % (me.get("xp") or 0, (" · 🔥 %d" % me["streak"]) if me.get("streak") else "")
        n["avatar"].textContent = state.initials(me.get("display_name") or me.get("email"))
        n["avatar"].style.setProperty("--c", state.avatar_bg(me.get("avatar_color")))
        self.menu_name.text = me.get("display_name") or ""
        self.menu_email.text = "Guest · nothing is saved" if guest else (me.get("email") or "")
        self.admin_link.visible = bool(me.get("is_admin"))
        n["sign_out_text"].textContent = "Exit guest mode" if guest else "Sign out"

    # ---- account menu
    def _open_menu(self, on):
        self.menu.visible = on
        state.set_attr(self.me_button, "aria-expanded", "true" if on else "false")

    def me_click(self, event):
        self._open_lookup(False)
        self._open_menu(not self.menu.visible)

    def feedback_click(self, event):
        self._open_menu(False)
        state.feedback()

    def sign_out_click(self, event):
        was_guest = state.is_guest()
        auth.sign_out()
        if not was_guest:
            state.toast("Signed out. See you soon!")
        router.go("auth")

    # ---- Lookup: a small abbreviation dictionary under the header (not modal: the page stays usable)
    def _open_lookup(self, on):
        self.lookup.visible = on
        state.set_attr(self.lookup_button, "aria-expanded", "true" if on else "false")
        self.lookup_button.classes["on"] = on
        if on:
            bottom = anvil.js.get_dom_node(self.header).getBoundingClientRect().bottom
            root = window.document.documentElement
            if root is not None:
                getattr(root, "style").setProperty("--qb-dict-top", "%dpx" % (bottom + 8))
            self._draw_lookup()
            state.focus(self.lookup_box)
            getattr(state.control(self.lookup_box), "select")()

    def lookup_click(self, event):
        self._open_menu(False)
        self._open_lookup(not self.lookup.visible)

    def lookup_close_click(self, event):
        self._open_lookup(False)
        getattr(anvil.js.get_dom_node(self.lookup_button), "focus")()

    @handle("lookup_box", "change")
    def lookup_box_change(self, **event_args):
        self._draw_lookup()

    def _draw_lookup(self):
        q = (self.lookup_box.text or "").strip()
        hits = lookup(q) if q else []
        mods = _ACRONYMS["mods"]
        if not q:
            self.lookup_note.text = ("Type an abbreviation to see what it stands for. The list holds the %d abbreviations "
                                     "found in this guide's study materials." % len(acronyms()))
        elif not hits:
            self.lookup_note.text = "“%s” isn't in this guide's list. Try a web search instead." % q
        self.lookup_note.visible = not hits
        items = []
        for abbr, meaning, nums in hits:
            src = ["Module %d: %s" % (num, mods[str(num)]) for num in nums if str(num) in mods]
            more = (" · +%d more" % (len(src) - 2)) if len(src) > 2 else ""
            items.append({"abbr": abbr, "meaning": meaning, "src": " · ".join(src[:2]) + more})
        self.hits_panel.items = items
        self.google_link.visible = bool(q)
        state.set_attr(self.google_link, "href", "https://www.google.com/search?q=" + window.encodeURIComponent(q + " CAF"))
        self.dom_nodes["google_text"].textContent = "Search Google for “%s CAF”" % q

    # ---- outside clicks and Escape close the menu and the Lookup panel
    def _close_outside(self, event):
        t = event.target
        if self.menu.visible and not t.closest(".me"):
            self._open_menu(False)
        if self.lookup.visible and not t.closest(".qb-dict, .look"):
            self._open_lookup(False)

    def _key(self, event):
        if event.key == "Escape":
            if self.lookup.visible:
                self._open_lookup(False)
                getattr(anvil.js.get_dom_node(self.lookup_button), "focus")()
            self._open_menu(False)

    def _foot_height(self, *args):
        """The sign-in page fills the screen minus the footer, so the disclaimer shows without scrolling."""
        h = anvil.js.get_dom_node(self.footer).offsetHeight
        root = window.document.documentElement
        if root is not None:
            getattr(root, "style").setProperty("--qb-foot-h", "%dpx" % h)

    @handle("", "show")
    def form_show(self, **event_args):
        window.document.addEventListener("click", self._outside, True)
        window.document.addEventListener("keydown", self._keys)
        window.addEventListener("resize", self._resize)
        self._foot_height()

    @handle("", "hide")
    def form_hide(self, **event_args):
        window.document.removeEventListener("click", self._outside, True)
        window.document.removeEventListener("keydown", self._keys)
        window.removeEventListener("resize", self._resize)
