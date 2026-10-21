# ProfilePage — Custom HTML form. HTML: forms/ProfilePage.html
from ._anvil_designer import ProfilePageTemplate
from anvil import *
import anvil.server

from .. import qb_ui


class ProfilePage(ProfilePageTemplate):
    def __init__(self, **properties):
        super().__init__(**properties)
        self.data = anvil.server.call("get_profile", qb_ui.today())
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        qb_ui.mount(self, "profile", self.data, self._on_event)

    def _on_event(self, event, p):
        if event == "save":
            res = anvil.server.call("update_profile", display_name=p.get("display_name"),
                                    bio=p.get("bio"), avatar_color=p.get("avatar_color"))
            if res.get("ok"):
                get_open_form().refresh_user(res["me"])
            return res
        if event == "open_quiz":
            get_open_form().go("quiz", quiz_id=p["id"])
        elif event == "open_review":
            get_open_form().go("quiz", quiz_id=None)  # daily review
        elif event == "signout":
            get_open_form().sign_out()
        elif event == "import_json":
            return anvil.server.call("import_quiz_json", p.get("text", ""))
        elif event == "seed_demo":
            return anvil.server.call("seed_demo")
