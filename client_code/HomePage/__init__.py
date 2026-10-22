# HomePage — Custom HTML form. HTML: forms/HomePage.html
from ._anvil_designer import HomePageTemplate
from anvil import *
import anvil.server

from .. import qb_ui


class HomePage(HomePageTemplate):
    def __init__(self, **properties):
        super().__init__(**properties)
        self.data = qb_ui.call("get_home", qb_ui.today())
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        qb_ui.mount(self, "home", self.data, self._on_event)

    def _on_event(self, event, p):
        if event == "open_collection":
            get_open_form().go("collection", collection_id=p["id"])
        elif event == "open_quiz":
            get_open_form().go("quiz", quiz_id=p["id"])
        elif event == "open_review":
            get_open_form().go("quiz", quiz_id=None)  # daily review: due cards from every collection
