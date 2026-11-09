import json

from anvil import *
import anvil.server
import anvil.users

from ._anvil_designer import ProfileTemplate
from ... import auth, router, state

THEMES = ("auto", "light", "dark")
DEFAULT_COLORS = ["#2e4a70", "#c8102e", "#556b2f", "#3b6ea5", "#8a7a4f", "#5c6470", "#2f7a78", "#7a2e3b"]


class Profile(ProfileTemplate):
    """#profile (Operate): who you are, your stats, progress per module, edit name/bio/avatar colour, the theme for
    this device, change password (members) or "save your progress" (guests), and for admins: Manage curriculum and
    Import learning modules (files, pasted JSON, 27 sample cards), then the recent sessions.
    Data: get_profile (or the guest twin)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.data = state.learn("get_profile", state.today())
        self.me = self.data.get("me") or {}
        self.color = self.me.get("avatar_color") or DEFAULT_COLORS[0]
        state.heading(self.name_label, 1)
        state.set_control_attr(self.name_box, "autocomplete", "name")
        state.set_control_attr(self.name_box, "maxlength", "60")
        state.set_control_attr(self.bio_box, "maxlength", "400")
        state.set_control_attr(self.old_box, "autocomplete", "current-password")
        state.set_control_attr(self.new_box, "autocomplete", "new-password")
        state.set_control_attr(self.new2_box, "autocomplete", "new-password")
        self.swatch_panel.add_event_handler("x-pick", self._pick)
        self.files_loader.add_event_handler("change", self._files_chosen)
        self._draw()

    def _draw(self):
        me, st = self.me, self.data.get("stats") or {}
        prog, hist = self.data.get("progress") or [], self.data.get("history") or []
        guest, admin = bool(me.get("guest")), bool(me.get("is_admin"))
        n = self.dom_nodes
        self._draw_avatar()
        self.name_label.text = me.get("display_name") or ""
        sub = "Guest · progress is kept only until you close this tab" if guest else (me.get("email") or "")
        if me.get("signed_up"):
            sub += " · member since " + state.fmt_date(me["signed_up"])
        n["sub_line"].textContent = sub
        self.admin_badge.visible = admin
        self.bio_label.text = me.get("bio") or ""
        self.bio_label.visible = bool(me.get("bio"))
        self.sign_out_button.text = "Exit guest mode" if guest else "Sign out"
        n["t_learned"].textContent = str(st.get("learned") or 0)
        n["t_total"].textContent = " / %d" % (st.get("total_cards") or 0)
        n["t_mastered"].textContent = str(st.get("mastered") or 0)
        n["t_due"].textContent = str(st.get("due") or 0)
        n["t_reviews"].textContent = str(st.get("reviews") or 0)
        n["t_sessions"].textContent = str(st.get("sessions") or 0)
        n["t_streak"].textContent = str(me.get("streak") or 0)
        n["prog_line"].textContent = "%d of %d modules complete" % (len([p for p in prog if p.get("complete")]), len(prog))
        n["prog_line"].hidden = not prog
        self.progress_panel.items = prog
        self.no_prog.visible = not prog
        self.name_box.text = me.get("display_name") or ""
        self.bio_box.text = me.get("bio") or ""
        self._draw_swatches()
        self._draw_theme()
        self.guest_card.visible = guest
        self.pw_card.visible = not guest
        self.cur_card.visible = self.import_card.visible = admin
        self.history_panel.items = hist
        self.hist_head.visible = bool(hist)
        self.no_hist.visible = not hist

    def _draw_avatar(self):
        av = self.dom_nodes["avatar"]
        av.textContent = state.initials(self.me.get("display_name") or self.me.get("email"))
        av.style.setProperty("--c", state.avatar_bg(self.color))

    def _draw_swatches(self):
        colors = self.data.get("colors") or DEFAULT_COLORS
        self.swatch_panel.items = [{"color": c, "on": c == self.color} for c in colors]

    def _pick(self, color, **event_args):
        key = state.focus_key()
        self.color = color
        self._draw_avatar()
        self._draw_swatches()
        state.refocus(self.swatch_panel, key)

    # ---- theme (this device only)
    def _draw_theme(self):
        t = state.theme()
        for name, el in zip(THEMES, (self.th_auto, self.th_light, self.th_dark)):
            el.classes["on"] = name == t

    def theme_click(self, event):
        state.set_theme(event.currentTarget.getAttribute("data-t"))
        self._draw_theme()

    # ---- profile
    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        self.save_button.enabled = False
        try:
            res = state.learn("update_profile", display_name=(self.name_box.text or "").strip(),
                              bio=(self.bio_box.text or "").strip(), avatar_color=self.color)
        finally:
            self.save_button.enabled = True
        if not res or not res.get("ok"):
            state.toast((res or {}).get("error") or "Could not save", "error")
            return
        self.me.update(res.get("me") or {})
        state.set_me(dict(state.me() or {}, **(res.get("me") or {})))
        shell = getattr(self, "layout", None)
        if shell is not None and hasattr(shell, "refresh"):
            shell.refresh("profile")
        self._draw()
        state.toast("Profile saved", "ok")

    @handle("sign_out_button", "click")
    def sign_out_button_click(self, **event_args):
        auth.sign_out()
        router.go("auth")

    @handle("join_button", "click")
    def join_button_click(self, **event_args):
        auth.sign_out()
        router.go("auth", "signup")

    # ---- password (members)
    def _pw_say(self, ok, text):
        self.pw_msg.visible = bool(text)
        self.pw_msg.text = text or ""
        self.pw_msg.role = "msg-note" if ok else "msg-error"

    @handle("pw_button", "click")
    def pw_button_click(self, **event_args):
        old, new, new2 = self.old_box.text or "", self.new_box.text or "", self.new2_box.text or ""
        if not old or not new:
            self._pw_say(False, "Fill in your current and your new password.")
            return
        if new != new2:
            self._pw_say(False, "The new passwords don't match.")
            return
        if new == old:
            self._pw_say(False, "The new password is the same as the current one.")
            return
        self.pw_button.enabled = False
        try:
            anvil.users.reset_password(old, new)
        except anvil.users.TooManyPasswordFailures:
            self._pw_say(False, "Too many wrong attempts. Wait a while, or email yourself a reset link.")
            return
        except Exception as e:
            if type(e).__name__ == "PasswordNotAcceptable":
                self._pw_say(False, str(e) or "Please choose a stronger password.")
            elif isinstance(e, anvil.users.AuthenticationFailed):
                self._pw_say(False, "Your current password is not right.")
            else:
                raise
            return
        finally:
            self.pw_button.enabled = True
        self.old_box.text = self.new_box.text = self.new2_box.text = ""
        self._pw_say(True, "Password changed. Use the new one next time you sign in.")
        state.toast("Password changed", "ok")

    @handle("reset_button", "click")
    def reset_button_click(self, **event_args):
        email = self.me.get("email") or ""
        try:
            anvil.users.send_password_reset_email(email)
        except anvil.users.AuthenticationFailed:
            self._pw_say(False, "Could not send a reset email for this account.")
            return
        self._pw_say(True, "A reset link is on its way to " + email + ".")

    # ---- admin: importing learning modules
    def _admin_say(self, ok, text):
        self.admin_msg.visible = bool(text)
        self.admin_msg.text = text or ""
        self.admin_msg.role = "msg-note" if ok else "msg-error"

    def _files_chosen(self, **event_args):
        files = self.files_loader.files or []
        self.dom_nodes["files_note"].textContent = (state.plural(len(files), "file") + " chosen") if files else "No files chosen"

    @handle("import_files_button", "click")
    def import_files_button_click(self, **event_args):
        """Import module files one part at a time, so no single server call gets too big."""
        files = sorted(self.files_loader.files or [], key=lambda f: f.name or "")
        if not files:
            self._admin_say(False, "Choose at least one .json file first.")
            return
        done, cards, errors = 0, 0, []
        self.import_files_button.enabled = False
        try:
            for fi, f in enumerate(files):
                try:
                    text = f.get_bytes().decode("utf-8").lstrip("﻿")
                    data = json.loads(text)
                except Exception:
                    errors.append("%s: not valid JSON" % f.name)
                    continue
                items = data if isinstance(data, list) else (data.get("quizzes") or [data])
                for ii, item in enumerate(items):
                    self._admin_say(True, "File %d of %d (%s) · part %d of %d…" % (fi + 1, len(files), f.name, ii + 1, len(items)))
                    try:
                        res = anvil.server.call("import_quiz_json", json.dumps(item))
                    except Exception as e:
                        res = {"ok": False, "error": str(e)}
                    if res and res.get("ok"):
                        done += 1
                        cards += len(item.get("questions") or item.get("cards") or []) if isinstance(item, dict) else 0
                    else:
                        errors.append("%s part %d: %s" % (f.name, ii + 1, (res or {}).get("error") or "failed"))
        finally:
            self.import_files_button.enabled = True
        summary = "Imported %s (%d cards) from %s." % (state.plural(done, "part"), cards, state.plural(len(files), "file"))
        self._admin_say(not errors, summary + (("\n" + "\n".join(errors)) if errors else " Open your learning path to see the modules."))

    def _admin(self, fn, *args):
        self._admin_say(True, "Working…")
        try:
            res = anvil.server.call(fn, *args) or {}
        except Exception as e:
            res = {"ok": False, "error": str(e)}
        self._admin_say(bool(res.get("ok")), res.get("message") if res.get("ok") else res.get("error"))

    @handle("import_json_button", "click")
    def import_json_button_click(self, **event_args):
        self._admin("import_quiz_json", self.json_box.text or "")

    @handle("seed_button", "click")
    def seed_button_click(self, **event_args):
        self._admin("seed_demo")
