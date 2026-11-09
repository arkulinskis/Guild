import json

from anvil import *
import anvil.media
import anvil.server

from ._anvil_designer import CurriculumTemplate
from ... import router, state


class Curriculum(CurriculumTemplate):
    """#curriculum (admins; Operate): every module, hidden ones too. Open a module to see its parts, open a part to
    see its cards (loaded when first opened); preview a part as flashcards (nothing is recorded); edit or delete
    modules, parts and cards (Dialogs/Edit); download a module or everything as importable JSON.

    The page keeps the data (self.mods, self.cards) and the rows call back into it: each row's item carries
    "page" (this Form). After every change the list is drawn again; open/closed state lives in self.open."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        data = anvil.server.call("admin_curriculum")
        self.mods = data.get("modules") or []
        self.colors = data.get("colors") or []
        self.cards = {}          # part id -> list of cards, or {"error": ...}
        self.open = set()        # ids of open modules and parts
        state.heading(self.title, 1)
        state.set_control_attr(self.filter_box, "aria-label", "Filter modules")
        state.set_control_attr(self.filter_box, "type", "search")
        self.draw()

    # ---- drawing
    def _totals(self):
        parts = sum(len(m.get("parts") or []) for m in self.mods)
        cards = sum(m.get("card_count") or 0 for m in self.mods)
        return "%s · %s · %s" % (state.plural(len(self.mods), "module"), state.plural(parts, "part"), state.plural(cards, "card"))

    def draw(self):
        self.totals.text = self._totals()
        f = (self.filter_box.text or "").strip().lower()
        shown = [m for m in self.mods if not f or f in ("%s %s" % (state.pad(m.get("number")), m.get("title") or "")).lower()
                 or any(f in (p.get("title") or "").lower() for p in (m.get("parts") or []))]
        key = state.focus_key()
        self.mods_panel.items = [{"m": m, "page": self} for m in shown]
        state.refocus(self.mods_panel, key)
        self.empty.visible = not shown
        self.dom_nodes["empty_text"].textContent = ("No module matches that filter." if self.mods
                                                    else "No modules yet. Import module files from your profile.")

    @handle("filter_box", "change")
    def filter_box_change(self, **event_args):
        self.draw()

    # ---- lookups
    def find_mod(self, mod_id):
        return next((m for m in self.mods if m["id"] == mod_id), None)

    def find_part(self, part_id):
        for m in self.mods:
            for p in m.get("parts") or []:
                if p["id"] == part_id:
                    return m, p
        return None, None

    # ---- opening modules and parts
    def toggle(self, item_id, part=False):
        if item_id in self.open:
            self.open.discard(item_id)
        else:
            self.open.add(item_id)
            if part and (item_id not in self.cards or isinstance(self.cards[item_id], dict)):
                self.load_part(item_id)
        self.draw()

    def load_part(self, part_id):
        try:
            res = anvil.server.call("admin_part_cards", part_id)
        except Exception as e:
            res = {"ok": False, "error": str(e)}
        self.cards[part_id] = res.get("cards") if res.get("ok") else {"error": res.get("error") or "Could not load the cards."}

    def preview(self, part_id):
        if not isinstance(self.cards.get(part_id), list):
            self.load_part(part_id)
        cs = self.cards.get(part_id)
        if isinstance(cs, dict):
            state.toast(cs["error"], "error")
            return
        if cs:
            from ...Dialogs.Preview import Preview
            m, p = self.find_part(part_id)
            alert(Preview(cards=cs, part_title=(p or {}).get("title") or ""), buttons=[], large=True, role="app-dialog",
                  dismissible=True)
        if part_id in self.open:
            self.draw()

    # ---- editing (one dialog for modules, parts and cards)
    def _edit(self, kind, item, quiz_id=None):
        from ...Dialogs.Edit import Edit
        return alert(Edit(kind=kind, item=item, quiz_id=quiz_id), buttons=[], large=True, role="app-dialog", dismissible=True)

    def edit_module(self, mod_id):
        m = self.find_mod(mod_id)
        res = self._edit("module", m)
        if res:
            i = self.mods.index(m)
            self.mods[i] = res["module"]
            self.mods.sort(key=lambda x: x.get("number") or 0)
            self.draw()
            state.toast("Module saved", "ok")

    def edit_part(self, part_id):
        m, p = self.find_part(part_id)
        res = self._edit("part", p)
        if res:
            parts = m["parts"]
            parts[parts.index(p)] = res["part"]
            parts.sort(key=lambda x: x.get("number") or 0)
            self.draw()
            state.toast("Part saved", "ok")

    def edit_card(self, part_id, card=None):
        res = self._edit("card", card or {}, quiz_id=part_id)
        if not res:
            return
        m, p = self.find_part(part_id)
        cs = self.cards.get(part_id)
        if isinstance(cs, list):
            if card and card.get("id"):
                ids = [c["id"] for c in cs]
                cs[ids.index(card["id"])] = res["card"]
            else:
                cs.append(res["card"])
        self._recount(m, p, res.get("card_count"))
        self.draw()
        state.toast("Card saved" if card and card.get("id") else "Card added", "ok")

    @staticmethod
    def _recount(m, p, card_count):
        if m is not None and p is not None and card_count is not None:
            m["card_count"] = (m.get("card_count") or 0) + card_count - (p.get("card_count") or 0)
            p["card_count"] = card_count

    # ---- deleting
    def delete(self, kind, item_id, part_id=None):
        if kind == "module":
            m = self.find_mod(item_id)
            msg = ("This removes its %s and %s, and every learner's progress on them. It can't be undone.\n\n"
                   "Tip: cancel and use \"Download JSON\" first to keep a copy." % (state.plural(len(m.get("parts") or []), "part"), state.plural(m.get("card_count") or 0, "card")))
            title = "Delete module %s · %s?" % (state.pad(m.get("number")), m.get("title"))
        elif kind == "part":
            m, p = self.find_part(item_id)
            msg = "This removes its %s and every learner's progress on them. It can't be undone." % state.plural(p.get("card_count") or 0, "card")
            title = "Delete the part \"%s\"?" % p.get("title")
        else:
            msg = "Every learner's progress on it is removed too. It can't be undone."
            title = "Delete this card?"
        if not confirm(msg, title=title, buttons=[("Cancel", False), ("Delete", True)]):
            return
        try:
            res = anvil.server.call("admin_delete", kind, item_id)
        except Exception as e:
            res = {"ok": False, "error": str(e)}
        if not res.get("ok"):
            state.toast(res.get("error") or "Could not delete.", "error")
            return
        if kind == "module":
            self.mods = [x for x in self.mods if x["id"] != item_id]
        elif kind == "part":
            m, p = self.find_part(item_id)
            m["parts"] = [x for x in m["parts"] if x["id"] != item_id]
            m["card_count"] = (m.get("card_count") or 0) - (p.get("card_count") or 0)
            self.cards.pop(item_id, None)
        else:
            m, p = self.find_part(part_id)
            if isinstance(self.cards.get(part_id), list):
                self.cards[part_id] = [c for c in self.cards[part_id] if c["id"] != item_id]
            self._recount(m, p, res.get("card_count"))
        self.draw()
        state.toast(res.get("message") or "Deleted", "ok")

    # ---- downloads
    def export(self, mod_id=None):
        res: dict = {}
        try:
            res = anvil.server.call("admin_export", mod_id)
        except Exception as e:
            res = {"ok": False, "error": str(e)}
        if not res.get("ok"):
            state.toast(res.get("error") or "Could not prepare the download.", "error")
            return
        items: list = list(res.get("items") or [])
        text = json.dumps(items, indent=1, ensure_ascii=False)
        anvil.media.download(BlobMedia("application/json", text.encode("utf-8"), name=str(res.get("filename") or "curriculum.json")))
        n = sum(len(it.get("questions") or []) for it in items)
        state.toast("Downloaded %s (%s, %s)" % (res.get("filename"), state.plural(len(items), "part"), state.plural(n, "card")), "ok")

    @handle("export_all_button", "click")
    def export_all_button_click(self, **event_args):
        self.export(None)

    def view_as_learner(self, mod_id):
        router.go("collection", mod_id)
