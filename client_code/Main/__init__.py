# Main — Custom HTML form, set as the Startup Form.
# Paste this as the form's Python code (Code view). HTML: forms/Main.html
import json

from ._anvil_designer import MainTemplate
from anvil import *
import anvil.server
import anvil.users

from .. import qb_ui
from ..AuthPage import AuthPage
from ..HomePage import HomePage
from ..CollectionPage import CollectionPage
from ..QuizPage import QuizPage
from ..ProfilePage import ProfilePage

PAGES = {
    "auth": AuthPage,
    "home": HomePage,
    "collection": CollectionPage,
    "quiz": QuizPage,
    "profile": ProfilePage,
}


class Main(MainTemplate):
    def __init__(self, **properties):
        super().__init__(**properties)
        self.header = None
        self.me = None
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        if self.header is not None:
            return
        self.header = qb_ui.mount(self, "header", {"app_name": qb_ui.APP_NAME, "logo_url": qb_ui.LOGO_URL}, self._on_header_event)
        if anvil.users.get_user():
            self.signed_in()
        else:
            self.go("auth")

    # ---- navigation (pages call get_open_form().go(...)) ----
    def go(self, page, **kwargs):
        if page != "auth" and not (anvil.users.get_user() or qb_ui.GUEST[0]):
            page, kwargs = "auth", {}
        self.clear()
        self.add_component(PAGES[page](**kwargs))
        self.header.setActive(page)
        qb_ui.scroll_top()

    def start_guest(self):
        """Try the app without an account: progress is kept for this browser session only."""
        self.me = anvil.server.call("start_guest", qb_ui.today())
        qb_ui.GUEST[0] = True
        self.refresh_user(self.me)
        self.go("home")

    def signed_in(self):
        if qb_ui.GUEST[0]:
            anvil.server.call("end_guest")
            qb_ui.GUEST[0] = False
        self.me = anvil.server.call("get_me", qb_ui.today())
        name = qb_ui.pending_name()
        if name and self.me.get("default_name"):
            self.me = anvil.server.call("update_profile", display_name=name)["me"]
        qb_ui.pending_name(clear=True)
        self.refresh_user(self.me)
        self.go("home")

    def refresh_user(self, me=None):
        self.me = me or qb_ui.call("get_me", qb_ui.today())
        self.header.setUser(json.dumps(self.me) if self.me else None)

    def sign_out(self):
        if qb_ui.GUEST[0]:
            anvil.server.call("end_guest")  # guest progress is discarded
            qb_ui.GUEST[0] = False
        else:
            anvil.users.logout()
        self.me = None
        self.header.setUser(None)
        self.go("auth")

    def _on_header_event(self, event, payload):
        if event == "nav":
            self.go(payload.get("page", "home"))
        elif event == "signout":
            self.sign_out()
