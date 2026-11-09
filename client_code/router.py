"""Page addresses: #name/arg1/arg2 -> a page Form (open_form), with sign-in rules.

Links in templates are plain <a href="#home">; code calls router.go("collection", id).

    PAGES[name] = (who may open it, browser-tab title)   who: None = anyone, "guest" = signed out only,
                  "user" = signed in or trying it as a guest, "admin"
The old JavaScript version had no addresses (one page that swapped its content), so these are new:
    #auth #auth/signup #auth/reset     sign in, create an account, reset the password (the front page)
    #home                              the learning path
    #collection/<id>                   one module and its parts
    #quiz/<id>                         study one part        #module/<id>  study a whole module
    #review                            the daily review of due cards from every module
    #profile                           your profile           #curriculum   Manage curriculum (admins; #admin too)
New page: add it to PAGES and to _form().
"""
import anvil
import anvil.js
from anvil.js import window

from . import state

PAGES = {
    "auth": ("guest", "Sign in"),
    "home": ("user", "Your learning path"),
    "collection": ("user", "Module"),
    "quiz": ("user", "Study"),
    "module": ("user", "Study a module"),
    "review": ("user", "Daily review"),
    "profile": ("user", "Your profile"),
    "curriculum": ("admin", "Manage curriculum"),
    "admin": ("admin", "Manage curriculum"),
}
NAV = []  # no main menu: the header has the Lookup button and the account menu (as in the old app)
APP_NAME = "CAF Guide"
_r: dict = {"after": "", "listening": False, "page": None}


def _form(name):
    """The page's Form class (imported when first needed, so start-up stays quick)."""
    if name == "auth":
        from .Pages.Auth import Auth
        return Auth
    if name == "home":
        from .Pages.Home import Home
        return Home
    if name == "collection":
        from .Pages.Collection import Collection
        return Collection
    if name in ("quiz", "module", "review"):
        from .Pages.Study import Study
        return Study
    if name == "profile":
        from .Pages.Profile import Profile
        return Profile
    from .Pages.Curriculum import Curriculum
    return Curriculum


def parse(hash_text):
    h = (hash_text or "").lstrip("#").lstrip("!").lstrip("/").split("?")[0]
    parts = [window.decodeURIComponent(p) for p in h.split("/") if p]
    return (parts[0] if parts else ""), parts[1:]


def href(name, *args):
    """'#name/arg1/arg2' with every part URL-encoded (row ids contain brackets and commas)."""
    return "#" + "/".join([name] + [window.encodeURIComponent(str(a)) for a in args if a not in (None, "")])


def home_page():
    return "home" if state.me() else "auth"


def current():
    return _r["page"]


def show():
    """Open the page for the current address."""
    name, args = parse(window.location.hash)
    if name not in PAGES:
        name, args = home_page(), []
    who = PAGES[name][0]
    if who == "guest" and state.me():
        name, args = "home", []
    elif who in ("user", "admin") and not state.me():
        _r["after"] = window.location.hash
        name, args = "auth", []
    elif who == "admin" and not state.is_admin():
        state.toast("That page is for admins only.", "error")
        name, args = "home", []
    window.document.title = PAGES[name][1] + " · " + APP_NAME
    window.UI_READY = False
    form = _form(name)
    page = form(args=args, mode=name) if name in ("quiz", "module", "review") else form(args=args)
    _r["page"] = name
    anvil.open_form(page)
    shell = getattr(page, "layout", None)
    if shell is not None and hasattr(shell, "refresh"):
        shell.refresh(name)  # Anvil reuses the layout between pages: tell it who is signed in and which page is open
    window.scrollTo(0, 0)
    window.UI_READY = True  # tests and screenshots wait for this


def go(name, *args):
    """Go to a page. Same address again = reload the page."""
    target = href(name, *args)
    if window.location.hash == target:
        show()
    else:
        window.location.hash = target


def replace(name, *args):
    """Change the address without opening anything (a page that switches its own view)."""
    window.history.replaceState(None, "", href(name, *args))


def after_sign_in():
    """Where to go once someone signs in: the page they were heading for, or home."""
    target = _r["after"]
    _r["after"] = ""
    if target and target != window.location.hash and not target.startswith("#auth"):
        window.location.hash = target
    else:
        go("home")


def remember_after(target):
    _r["after"] = target


def _on_hash(event):
    show()


def start():
    if not _r["listening"]:
        window.addEventListener("hashchange", anvil.js.report_exceptions(_on_hash))
        _r["listening"] = True
    show()
