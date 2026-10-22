# ProfilePage — Custom HTML form. HTML: forms/ProfilePage.html
from ._anvil_designer import ProfilePageTemplate
from anvil import *
import anvil.server
import anvil.users

from .. import qb_ui


class ProfilePage(ProfilePageTemplate):
    def __init__(self, **properties):
        super().__init__(**properties)
        self.data = qb_ui.call("get_profile", qb_ui.today())
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        qb_ui.mount(self, "profile", self.data, self._on_event)

    def _on_event(self, event, p):
        if event == "save":
            res = qb_ui.call("update_profile", display_name=p.get("display_name"),
                                    bio=p.get("bio"), avatar_color=p.get("avatar_color"))
            if res.get("ok"):
                get_open_form().refresh_user(res["me"])
            return res
        if qb_ui.GUEST[0] and event in ("import_json", "seed_demo", "change_password", "reset_email"):
            return {"ok": False, "error": "Create an account to use this."}
        if event == "open_quiz":
            get_open_form().go("quiz", quiz_id=p["id"])
        elif event == "open_collection":
            get_open_form().go("collection", collection_id=p["id"])
        elif event == "open_review":
            get_open_form().go("quiz", quiz_id=None)  # daily review
        elif event == "signout":
            get_open_form().sign_out()
        elif event == "import_json":
            return anvil.server.call("import_quiz_json", p.get("text", ""))
        elif event == "seed_demo":
            return anvil.server.call("seed_demo")
        elif event == "change_password":
            return self._change_password(p.get("old", ""), p.get("new", ""))
        elif event == "reset_email":
            email = self.data["me"]["email"]
            try:
                anvil.users.send_password_reset_email(email)
            except anvil.users.AuthenticationFailed:
                return {"ok": False, "error": "Could not send a reset email for this account."}
            return {"ok": True, "message": "A reset link is on its way to " + email + "."}

    def _change_password(self, old, new):
        try:
            anvil.users.reset_password(old, new)
        except anvil.users.TooManyPasswordFailures:
            return {"ok": False, "error": "Too many wrong attempts. Wait a while, or email yourself a reset link."}
        except anvil.users.PasswordNotAcceptable as e:
            return {"ok": False, "error": str(e) or "Please choose a stronger password."}
        except anvil.users.AuthenticationFailed:
            return {"ok": False, "error": "Your current password is not right."}
        return {"ok": True}
