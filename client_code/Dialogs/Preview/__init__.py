from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import PreviewTemplate
from ... import state


class Preview(PreviewTemplate):
    """Flip through a part's cards as flashcards on Manage curriculum. Nothing is recorded.
    Keys: Space/Enter shows the answer (then moves on), Left/Right move, Esc closes (Anvil's dialog)."""

    def __init__(self, cards=(), part_title="", **properties):
        super().__init__(**properties)
        self.cards, self.i, self.flip = list(cards), 0, False
        self.part_label.text = part_title
        self._keys = anvil.js.report_exceptions(self._key)
        self._draw()

    def _draw(self):
        c, n = self.cards[self.i] if self.cards else {}, self.dom_nodes
        n["pos"].textContent = "%d / %d" % (self.i + 1, len(self.cards))
        n["concept"].textContent = c.get("concept") or ""
        n["concept"].hidden = not c.get("concept")
        n["qq"].textContent = c.get("question") or ""
        n["aa"].textContent = c.get("answer") or ""
        n["aa"].hidden = not self.flip
        n["ee"].textContent = c.get("explanation") or ""
        n["ee"].hidden = not (self.flip and c.get("explanation"))
        self.flip_button.visible = not self.flip
        self.prev_button.enabled = self.i > 0
        self.next_button.enabled = self.i < len(self.cards) - 1

    def _move(self, d):
        i = max(0, min(len(self.cards) - 1, self.i + d))
        if i != self.i:
            self.i, self.flip = i, False
            self._draw()

    @handle("prev_button", "click")
    def prev_button_click(self, **event_args):
        self._move(-1)

    @handle("next_button", "click")
    def next_button_click(self, **event_args):
        self._move(1)

    @handle("flip_button", "click")
    def flip_button_click(self, **event_args):
        self.flip = True
        self._draw()
        state.focus(self.next_button)

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    def _key(self, event):
        tag = str(getattr(event.target, "tagName", "") or "")
        if event.key == "ArrowRight":
            self._move(1)
        elif event.key == "ArrowLeft":
            self._move(-1)
        elif event.key in (" ", "Enter") and tag != "BUTTON":
            event.preventDefault()
            if not self.flip:
                self.flip_button_click()
            else:
                self._move(1)

    @handle("", "show")
    def form_show(self, **event_args):
        window.document.addEventListener("keydown", self._keys)
        state.focus(self.flip_button)

    @handle("", "hide")
    def form_hide(self, **event_args):
        window.document.removeEventListener("keydown", self._keys)
