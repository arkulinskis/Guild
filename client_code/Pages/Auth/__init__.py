import re

from anvil import *

from ._anvil_designer import AuthTemplate
from ... import auth, legal, router, state

HEADINGS = {"login": ("Welcome back", "Sign in to continue where you left off.", "Sign in"),
            "signup": ("Create your account", "Your progress, streak and cards learned are saved to your profile.",
                       "Create account"),
            "reset": ("Reset your password", "We'll email you a link to choose a new one.", "Send reset link")}
EMAIL = re.compile(r"^\S+@\S+\.\S+$")
# The app's video on the Addanapp YouTube channel (APP_MAKER/youtube/manifest.json), shown in the Watch section.
YT_VIDEO = "DHVV7YRVxX0"


class Auth(AuthTemplate):
    """The front page (Persuade + a form): the navy hero with the civilian note, sign in (#auth), create an account
    (#auth/signup), reset the password (#auth/reset), "Try it without signing in" (guest mode), and the Watch
    section. Sign-up needs the Privacy & Terms tick box (the legal kit draws it)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.dom_nodes["consent"].innerHTML = legal.consent_field()
        self.dom_nodes["yt_cover"].addEventListener("click", self._play)
        self._mode = args[0] if args and args[0] in ("signup", "reset") else "login"
        state.heading(self.heading, 2)
        state.set_control_attr(self.name_box, "autocomplete", "name")
        state.set_control_attr(self.email_box, "autocomplete", "email")
        self._draw()

    def _draw(self, message=None, is_error=False):
        mode = self._mode
        heading, sub, action = HEADINGS[mode]
        self.heading.text, self.sub.text, self.submit_button.text = heading, sub, action
        self.mode_tabs.visible = mode != "reset"
        self.tab_login.classes["on"] = mode == "login"
        self.tab_signup.classes["on"] = mode == "signup"  # app-kit.js turns "on" into aria-pressed for .ui-seg buttons
        state.set_control_attr(self.password_box, "autocomplete", "new-password" if mode == "signup" else "current-password")
        self.name_field.visible = mode == "signup"
        self.password_field.visible = mode != "reset"
        self.pw_hint.visible = mode == "signup"
        self.forgot_row.visible = mode == "login"
        self.consent_box.visible = mode == "signup"
        self.back_row.visible = mode == "reset"
        self.guest_part.visible = mode != "reset"
        self._say(message, is_error)

    def _say(self, message, is_error=True):
        self.message.visible = bool(message)
        self.message.text = message or ""
        self.message.role = "msg-error" if is_error else "msg-note"

    def _play(self, event):
        """Swap the video's cover for YouTube's player (privacy-enhanced); nothing loads from YouTube before this click."""
        self.dom_nodes["yt_frame"].innerHTML = (
            '<iframe src="https://www.youtube-nocookie.com/embed/' + YT_VIDEO + '?autoplay=1&rel=0&playsinline=1" '
            'title="CAF Guide video" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen '
            'referrerpolicy="strict-origin-when-cross-origin"></iframe>')

    # ---- switching between Sign in / Create account / Reset
    def mode_click(self, event):
        event.preventDefault()
        self._mode = event.currentTarget.getAttribute("data-mode")
        router.replace("auth", "" if self._mode == "login" else self._mode)
        self._draw()
        (self.name_box if self._mode == "signup" else self.email_box).focus()

    @handle("show_button", "click")
    def show_button_click(self, **event_args):
        self.password_box.hide_text = not self.password_box.hide_text
        self.show_button.text = "Show" if self.password_box.hide_text else "Hide"

    # ---- submit (the button, or Enter in any box)
    @handle("name_box", "pressed_enter")
    def name_box_pressed_enter(self, **event_args):
        self.submit_button_click()

    @handle("email_box", "pressed_enter")
    def email_box_pressed_enter(self, **event_args):
        self.submit_button_click()

    @handle("password_box", "pressed_enter")
    def password_box_pressed_enter(self, **event_args):
        self.submit_button_click()

    @handle("submit_button", "click")
    def submit_button_click(self, **event_args):
        mode = self._mode
        name, email, password = (self.name_box.text or "").strip(), (self.email_box.text or "").strip(), self.password_box.text or ""
        problem = None
        if mode == "signup" and len(name) < 1:
            problem = "Please tell us your name."
        elif not EMAIL.match(email):
            problem = "Please enter a valid email address."
        elif mode == "signup" and len(password) < 8:
            problem = "Please choose a password of at least 8 characters."
        elif mode == "login" and not password:
            problem = "Please enter your password."
        if problem:
            self._say(problem)
            return
        if mode == "signup" and not legal.consent_ok(self.dom_nodes["consent"]):
            return  # the kit shows its own message next to the tick box
        self._say(None)
        self.submit_button.enabled = self.guest_button.enabled = False
        try:
            if mode == "login":
                r = auth.sign_in(email, password)
            elif mode == "signup":
                r = auth.sign_up(name, email, password)
            else:
                r = auth.reset(email)
        finally:
            self.submit_button.enabled = self.guest_button.enabled = True
        if not r["ok"]:
            self._say(r["error"])
        elif mode == "reset" or r.get("confirm"):
            self._mode = "login"
            router.replace("auth")
            self._draw(r["message"], False)
        else:
            state.toast("Welcome to CAF Guide!" if mode == "signup" else "Welcome back!", "ok")
            router.after_sign_in()

    @handle("guest_button", "click")
    def guest_button_click(self, **event_args):
        self.guest_button.enabled = False
        try:
            auth.try_as_guest()
        finally:
            self.guest_button.enabled = True
        router.after_sign_in()

    @handle("", "show")
    def form_show(self, **event_args):
        (self.name_box if self._mode == "signup" else self.email_box).focus()
