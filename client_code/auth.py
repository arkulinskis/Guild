"""Sign in, create an account, reset a password, try it as a guest, sign out.

Each returns {"ok": True, "message"?} or {"ok": False, "error": "..."} for the expected problems (wrong password,
account exists ...), so the Auth page can show them next to the form. On success the signed-in learner is stored in
state and the Privacy & Terms kit is told. Google sign-in is off for CAF Guide (the Users service has use_google: false).
"""
import anvil.server
import anvil.users

from . import legal, state

AUTH_ERRORS = [
    (anvil.users.UserExists, "An account with that email already exists. Try signing in."),
    (anvil.users.EmailNotConfirmed, "Please confirm your email first. Check your inbox for the link."),
    (anvil.users.AccountIsNotEnabled, "This account is disabled. Contact the app owner."),
    (anvil.users.TooManyPasswordFailures, "Too many wrong attempts. Wait a while, or reset your password."),
    (anvil.users.PasswordNotAcceptable, None),  # Anvil's own message says what's wrong
    (anvil.users.AuthenticationFailed, "That email and password don't match."),
]

# What signing in or up can raise for ordinary reasons (some aren't AuthenticationFailed subclasses everywhere).
EXPECTED = tuple(cls for cls, _ in AUTH_ERRORS)


def _problem(e):
    for cls, msg in AUTH_ERRORS:
        if isinstance(e, cls):
            return {"ok": False, "error": msg or str(e) or "Please choose a stronger password."}
    return {"ok": False, "error": str(e)}


def _end_guest():
    if state.is_guest():
        try:
            anvil.server.call("end_guest")  # guest progress is discarded
        except Exception:
            pass
        state.set_me(None)


def _signed_in():
    """After sign-in or sign-up: the learner, with the name typed at sign-up if the account still has the
    made-up one (as the old app did)."""
    _end_guest()
    me = anvil.server.call("get_me", state.today())
    name = state.pending_name()
    if name and me.get("default_name"):
        me = anvil.server.call("update_profile", display_name=name)["me"]
    state.pending_name(clear=True)
    state.set_me(me)
    legal.refresh_soon()  # records the sign-up tick box, or reminds people to review new terms
    return {"ok": True}


def sign_in(email, password):
    try:
        anvil.users.login_with_email(email.strip(), password, remember=True)
    except EXPECTED as e:
        return _problem(e)
    return _signed_in()


def sign_up(name, email, password):
    state.pending_name(name.strip())
    try:
        anvil.users.signup_with_email(email.strip(), password, remember=True)
    except EXPECTED as e:
        state.pending_name(clear=True)
        return _problem(e)
    if anvil.users.get_user() is None:
        # "Require email confirmation" is on: the name waits for the first sign-in.
        return {"ok": True, "message": "Account created. Check your email for a confirmation link, then sign in.",
                "confirm": True}
    return _signed_in()


def reset(email):
    try:
        anvil.users.send_password_reset_email(email.strip())
    except anvil.users.AuthenticationFailed:
        pass  # same answer either way, so nobody can find out which emails have accounts
    return {"ok": True, "message": "If that email has an account, a reset link is on its way."}


def try_as_guest():
    """Try the app without an account: progress is kept for this browser session only."""
    state.set_me(anvil.server.call("start_guest", state.today()))
    return {"ok": True}


def sign_out():
    """Sign out, or leave guest mode (guest progress is discarded)."""
    if state.is_guest():
        _end_guest()
    else:
        anvil.users.logout()
        state.set_me(None)
    legal.signed_out()
