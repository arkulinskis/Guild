# CollectionPage — Custom HTML form. HTML: forms/CollectionPage.html
# One learning module and its parts.
from ._anvil_designer import CollectionPageTemplate
from anvil import *
import anvil.server

from .. import qb_ui


class CollectionPage(CollectionPageTemplate):
    def __init__(self, collection_id=None, **properties):
        super().__init__(**properties)
        self.data = anvil.server.call("get_collection", collection_id, qb_ui.today())
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        qb_ui.mount(self, "collection", self.data, self._on_event)

    def _on_event(self, event, p):
        if event == "back":
            get_open_form().go("home")
        elif event == "open_quiz":
            get_open_form().go("quiz", quiz_id=p["id"])
        elif event == "study_module":
            get_open_form().go("quiz", collection_id=p["id"])  # every part of the module, in order
