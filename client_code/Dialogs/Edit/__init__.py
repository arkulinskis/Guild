import anvil.server
from anvil import *

from ._anvil_designer import EditTemplate
from ... import state

SAVE = {"module": ("Edit module", "Save module"), "part": ("Edit part", "Save part")}


class Edit(EditTemplate):
    """Edit a module, a part or a card on Manage curriculum (kind = "module" | "part" | "card"; a card without an id
    is a new one in part quiz_id). Problems the server finds (empty title, duplicate question, bad colour) show inside
    the dialog. Closes with the server's reply ({ok, module|part|card, card_count}) or None."""

    def __init__(self, kind="card", item=None, quiz_id=None, **properties):
        super().__init__(**properties)
        self.kind, self.it, self.quiz_id = kind, dict(item or {}), quiz_id
        it = self.it
        state.heading(self.heading, 2)
        if kind == "card":
            self.heading.text = "Edit card" if it.get("id") else "New card"
            self.save_button.text = "Save card" if it.get("id") else "Add card"
        else:
            self.heading.text, self.save_button.text = SAVE[kind]
        self.top_row.visible = self.title_field.visible = self.description_field.visible = kind != "card"
        self.published_field.visible = kind != "card"
        self.card_fields.visible = kind == "card"
        self.color_field.visible = kind == "module"
        self.source_field.visible = kind == "part"
        self.title_hint.visible = kind == "module"
        self.dom_nodes["number_hint"].textContent = "Its place in the learning path." if kind == "module" else "Its order within the module."
        state.set_control_attr(self.number_box, "type", "number")
        state.set_control_attr(self.number_box, "min", "0")
        state.set_control_attr(self.number_box, "max", "9999")
        state.set_control_attr(self.color_box, "type", "color")
        state.set_control_attr(self.color_box, "aria-label", "Module colour")
        self.number_box.text = "" if it.get("number") is None else str(it.get("number"))
        self.color_box.text = it.get("color") or "#2e4a70"
        self.source_box.text = "" if it.get("source") == "import" else (it.get("source") or "")
        self.title_box.text = it.get("title") or ""
        self.description_box.text = it.get("description") or ""
        self.published_box.checked = bool(it.get("published")) if kind != "card" else False
        self.question_box.text = it.get("question") or ""
        self.answer_box.text = it.get("answer") or ""
        self.explanation_box.text = it.get("explanation") or ""
        self.concept_box.text = it.get("concept") or ""

    @handle("", "show")
    def form_show(self, **event_args):
        (self.question_box if self.kind == "card" else self.title_box).focus()

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    def _fields(self):
        if self.kind == "card":
            return {"question": self.question_box.text or "", "answer": self.answer_box.text or "",
                    "explanation": self.explanation_box.text or "", "concept": self.concept_box.text or ""}
        f = {"number": self.number_box.text or "", "title": self.title_box.text or "",
             "description": self.description_box.text or "", "published": bool(self.published_box.checked)}
        if self.kind == "module":
            f["color"] = state.control(self.color_box).value or self.color_box.text or ""
        else:
            f["source"] = self.source_box.text or ""
        return f

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        fields = self._fields()
        self.save_button.enabled = False
        try:
            if self.kind == "module":
                r = anvil.server.call("admin_save_module", self.it.get("id"), fields)
            elif self.kind == "part":
                r = anvil.server.call("admin_save_part", self.it.get("id"), fields)
            else:
                r = anvil.server.call("admin_save_card", self.quiz_id, self.it.get("id"), fields)
        except Exception as e:
            r = {"ok": False, "error": str(e)}
        finally:
            self.save_button.enabled = True
        if not r or not r.get("ok"):
            self.message.text, self.message.visible = str((r or {}).get("error") or "Could not save."), True
            return
        self.raise_event("x-close-alert", value=r)
