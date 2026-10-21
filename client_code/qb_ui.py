# qb_ui — client Module (Anvil IDE: Client Code → + Add Module → name it "qb_ui").
# Glue between Python forms and the HTML components defined in each form's HTML.
import json
import datetime

import anvil.js
from anvil.js import window

APP_NAME = "Quizbook"
# "Sign in with Google" is enabled in this app's Users service. Set to False to hide the button.
GOOGLE_LOGIN = True


def today():
    """The user's local date (the browser's clock), used for daily streaks."""
    return datetime.date.today().isoformat()


def mount(form, name, data, on_event=None):
    """Draw component `name` inside `form` and route its events to on_event(event, payload).

    Data goes to JS as a JSON string, so only pass JSON-friendly values
    (the server already turns dates into ISO strings). Whatever on_event
    returns (a dict, or None) is handed back to the component.
    Returns the component's JS API object (e.g. header.setUser(...)).
    """
    root = anvil.js.get_dom_node(form).querySelector('[data-qb-root="%s"]' % name)

    def emit(event, payload_json):
        if on_event is None:
            return None
        return on_event(event, json.loads(payload_json) if payload_json else {})

    return window.QB.mount(name, root, json.dumps(data), emit)


def toast(message, error=False):
    window.QB.toast(message, error)


def scroll_top():
    window.scrollTo(0, 0)


def pending_name(value=None, clear=False):
    """Remember a name typed at sign-up when the account needs email confirmation first."""
    try:
        if clear:
            window.localStorage.removeItem("qb.pendingName")
        elif value is not None:
            window.localStorage.setItem("qb.pendingName", value)
        else:
            return window.localStorage.getItem("qb.pendingName")
    except Exception:
        return None
