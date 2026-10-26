# CurriculumPage — Custom HTML form (admins only). HTML: forms/CurriculumPage.html
# Reached from Profile → Manage curriculum. Learners never see it.
from ._anvil_designer import CurriculumPageTemplate
from anvil import *
import anvil.server

from .. import qb_ui


class CurriculumPage(CurriculumPageTemplate):
    def __init__(self, **properties):
        super().__init__(**properties)
        self.data = anvil.server.call("admin_curriculum")
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        qb_ui.mount(self, "curriculum", self.data, self._on_event)

    def _on_event(self, event, p):
        if event == "back":
            get_open_form().go("profile")
        elif event == "open_collection":
            get_open_form().go("collection", collection_id=p["id"])
        elif event == "load_part":
            return anvil.server.call("admin_part_cards", p["id"])
        elif event == "save_module":
            return anvil.server.call("admin_save_module", p["id"], p["fields"])
        elif event == "save_part":
            return anvil.server.call("admin_save_part", p["id"], p["fields"])
        elif event == "save_card":
            return anvil.server.call("admin_save_card", p["quiz_id"], p.get("id"), p["fields"])
        elif event == "delete":
            return anvil.server.call("admin_delete", p["kind"], p["id"])
        elif event == "export":
            return anvil.server.call("admin_export", p.get("id"))
        elif event == "reload":
            return anvil.server.call("admin_curriculum")
