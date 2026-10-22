# AuthPage — Custom HTML form. HTML: forms/AuthPage.html
from ._anvil_designer import AuthPageTemplate
from anvil import *
import anvil.server
import anvil.users

from .. import qb_ui


class AuthPage(AuthPageTemplate):
    def __init__(self, **properties):
        super().__init__(**properties)
        self.add_event_handler("show", self._on_show)

    def _on_show(self, **event_args):
        qb_ui.mount(self, "auth", {"app_name": qb_ui.APP_NAME, "logo_url": qb_ui.LOGO_URL, "google": qb_ui.GOOGLE_LOGIN}, self._on_event)

    def _on_event(self, event, p):
        try:
            if event == "login":
                anvil.users.login_with_email(p["email"].strip(), p["password"], remember=True)
            elif event == "signup":
                name = p.get("name", "").strip()
                anvil.users.signup_with_email(p["email"].strip(), p["password"], remember=True)
                if anvil.users.get_user() is None:
                    # "Require email confirmation" is on: keep the name for the first sign-in.
                    qb_ui.pending_name(name)
                    return {"ok": True, "mode": "login",
                            "message": "Account created. Check your email for a confirmation link, then sign in."}
                qb_ui.pending_name(name)
            elif event == "reset":
                try:
                    anvil.users.send_password_reset_email(p["email"].strip())
                except anvil.users.AuthenticationFailed:
                    pass  # same reply either way, so nobody can probe which emails have accounts
                return {"ok": True, "message": "If that email has an account, a reset link is on its way."}
            elif event == "google":
                if not anvil.users.login_with_google(remember=True):
                    return {"ok": False, "error": "Google sign-in was cancelled."}
            else:
                return None
        except anvil.users.UserExists:
            return {"ok": False, "error": "An account with that email already exists. Try signing in."}
        except anvil.users.EmailNotConfirmed:
            return {"ok": False, "error": "Please confirm your email first. Check your inbox for the link."}
        except anvil.users.AccountIsNotEnabled:
            return {"ok": False, "error": "This account is disabled. Contact the app owner."}
        except anvil.users.TooManyPasswordFailures:
            return {"ok": False, "error": "Too many wrong attempts. Wait a while, or reset your password."}
        except anvil.users.PasswordNotAcceptable as e:
            return {"ok": False, "error": str(e) or "Please choose a stronger password."}
        except anvil.users.AuthenticationFailed:
            return {"ok": False, "error": "That email and password don't match."}

        get_open_form().signed_in()
        return {"ok": True}
