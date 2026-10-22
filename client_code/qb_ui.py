# qb_ui — client Module (Anvil IDE: Client Code → + Add Module → name it "qb_ui").
# Glue between Python forms and the HTML components defined in each form's HTML.
import json
import datetime

import anvil.js
import anvil.server
from anvil.js import window

# Guest mode ("Try without signing in"): learner calls go to the guest_ versions on the server,
# which keep progress in this browser session only. Main sets this.
GUEST = [False]


def call(name, *args, **kwargs):
    """anvil.server.call for learner functions, routed to guest_<name> while in guest mode."""
    return anvil.server.call(("guest_" + name) if GUEST[0] else name, *args, **kwargs)

APP_NAME = "CAF Guide"
# The app logo uploaded in Anvil (Theme → Assets); shown in the header and on the sign-in page.
LOGO_URL = "_/theme/8ff385ff-2cd5-4868-9642-6374157bd844.jpg"
# Show a "Continue with Google" button (also needs Google enabled in the Users service).
GOOGLE_LOGIN = False


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
    selector = '[data-qb-root="%s"]' % name
    node = anvil.js.get_dom_node(form)
    # A form whose HTML is a single element *is* that element, so check the node itself first.
    root = node if node.matches(selector) else node.querySelector(selector)

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
