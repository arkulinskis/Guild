"""The app starts here (anvil.yaml: startup module). Who is signed in (Anvil's loading spinner shows meanwhile), the
Privacy & Terms kit, then the page for the address in the browser bar.

get_me needs a signed-in user (require_user), so it is only called when there is one. A tab that was trying the app
as a guest before a reload resumes its guest session (start_guest resumes it while the browser session lasts)."""
import anvil.server
import anvil.users

from . import legal, router, state

LEGAL_THEME = {"accent": "#2e4a70"}  # colours for the Privacy & Terms page (match --c-brand in app.css)

legal.setup(LEGAL_THEME)
if anvil.users.get_user():
    state.set_me(anvil.server.call("get_me", state.today()))
    legal.refresh_soon()
elif state.guest_tab():
    try:
        state.set_me(anvil.server.call("start_guest", state.today()))
    except Exception:
        state.set_me(None)
router.start()
