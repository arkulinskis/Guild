# QuizPage — Custom HTML form. HTML: forms/QuizPage.html
# An active-recall study session for one part (quiz_id), a whole module (collection_id),
# or, with neither, the daily review of due cards from every module.
from ._anvil_designer import QuizPageTemplate
from anvil import *
import anvil.server

from .. import qb_ui


class QuizPage(QuizPageTemplate):
    def __init__(self, quiz_id=None, collection_id=None, **properties):
        super().__init__(**properties)
        self.quiz_id = quiz_id
        self.collection_id = None if quiz_id else collection_id
        self.data = self._load("due")
        self.add_event_handler("show", self._on_show)

    def _load(self, scope):
        return anvil.server.call("get_study", self.quiz_id, scope, qb_ui.today(), self.collection_id)

    def _on_show(self, **event_args):
        qb_ui.mount(self, "quiz", self.data, self._on_event)

    def _on_event(self, event, p):
        if event == "rate":
            return anvil.server.call("rate_card", p["question_id"], bool(p.get("knew")), qb_ui.today())
        if event == "finish":
            result = anvil.server.call("finish_session", self.quiz_id, p.get("ratings", []), qb_ui.today(),
                                       self.collection_id)
            get_open_form().refresh_user(result.get("me"))  # updates XP / streak in the header
            return result
        if event == "load":
            self.data = self._load(p.get("scope", "due"))
            return self.data
        if event == "back":
            collection_id = self.data["quiz"].get("collection_id")
            if collection_id:
                get_open_form().go("collection", collection_id=collection_id)
            else:
                get_open_form().go("home")
