# QuizService — Server Module (Anvil IDE: Server Code → + Add Server Module → "QuizService").
# All Data Table access happens here, so every table can stay "No access" for client code.
#
# Active recall with spaced repetition (Leitner boxes):
#   every card a user has seen has a row in card_state with a box number and a due date.
#   "Got it"         → box + 1, due again after BOX_INTERVALS[box] days
#   "Still learning" → box 0, due today (stays in circulation)
import json
import re
from datetime import date, datetime, timedelta, timezone

import anvil.server
import anvil.users
import anvil.tables as tables
from anvil.tables import app_tables

from .DemoData import DEMO_QUIZZES

# Navy, Canada red, army olive, air force blue, khaki, slate, sea green, maroon
AVATAR_COLORS = ["#2e4a70", "#c8102e", "#556b2f", "#3b6ea5", "#8a7a4f", "#5c6470", "#2f7a78", "#7a2e3b"]
COLLECTION_COLORS = ["#2e4a70", "#556b2f", "#c8102e", "#3b6ea5", "#8a7a4f", "#5c6470"]
BOX_INTERVALS = [0, 1, 3, 7, 16, 35, 90]  # days until due again, by box after "Got it"
MASTERED_BOX = 4                          # survived a 7-day gap → counts as mastered
SESSION_LIMIT = 50                        # most cards in one study session
XP_PER_REVIEW = 2
XP_PER_GOT_IT = 3
HISTORY_LIMIT = 30


# ---------------------------------------------------------------- helpers
def _iso(value):
    return value.isoformat() if value else None


def _now():
    return datetime.now(timezone.utc)


def _client_today(value):
    """Trust the browser's local date for streaks and due dates, but only within a day of UTC."""
    utc_today = _now().date()
    try:
        d = date.fromisoformat(str(value))
        if abs((d - utc_today).days) <= 1:
            return d
    except (TypeError, ValueError):
        pass
    return utc_today


def _default_name(email):
    local = (email or "learner").split("@")[0]
    return re.sub(r"[._\-]+", " ", local).strip().title() or "Learner"


def _current_streak(user, today):
    last = user["last_active"]
    if not last or (today - last).days > 1:
        return 0
    return user["streak"] or 0


def _ensure_defaults(user):
    """Fill in profile columns for new users. The very first user becomes the admin."""
    changes = {}
    if not user["display_name"]:
        changes["display_name"] = _default_name(user["email"])
    if not user["avatar_color"]:
        changes["avatar_color"] = AVATAR_COLORS[sum(map(ord, user["email"] or "")) % len(AVATAR_COLORS)]
    if user["xp"] is None:
        changes["xp"] = 0
    if user["streak"] is None:
        changes["streak"] = 0
    if user["is_admin"] is None:
        changes["is_admin"] = len(app_tables.users.search(is_admin=True)) == 0
    if changes:
        user.update(**changes)


def _me_dict(user, today):
    return {
        "email": user["email"],
        "display_name": user["display_name"],
        "default_name": user["display_name"] == _default_name(user["email"]),
        "bio": user["bio"] or "",
        "avatar_color": user["avatar_color"],
        "xp": user["xp"] or 0,
        "streak": _current_streak(user, today),
        "is_admin": bool(user["is_admin"]),
        "signed_up": _iso(user["signed_up"]),
        "guest": _is_guest(user),
    }


def _user():
    user = anvil.users.get_user()
    if user is None:
        raise anvil.users.AuthenticationFailed("Please sign in again.")
    _ensure_defaults(user)
    return user


# ---------------------------------------------------------------- guest mode
# "Try without signing in": progress lives only in anvil.server.session (this browser session),
# never in the data tables. The guest_* callables run the same logic as the signed-in ones,
# with a _Guest standing in for the users row and its card states / sessions.
GUEST_KEY = "guest"


class _Ref(object):
    """Stands in for a row link where only get_id() is needed."""
    def __init__(self, row_id):
        self._id = row_id

    def get_id(self):
        return self._id


class _GuestState(object):
    """A card_state-like view of one guest card: [quiz_id, box, due, reviews, lapses, last_reviewed]."""
    def __init__(self, qid, v):
        self._qid, self._v = qid, v

    def __getitem__(self, key):
        v = self._v
        if key == "box":
            return v[1]
        if key == "due":
            return date.fromisoformat(v[2]) if v[2] else None
        if key == "reviews":
            return v[3]
        if key == "lapses":
            return v[4]
        if key == "last_reviewed":
            return datetime.fromisoformat(v[5]) if v[5] else None
        if key == "quiz":
            return _Ref(v[0])
        if key == "question":
            return app_tables.questions.get_by_id(self._qid)
        raise KeyError(key)


class _GuestSession(object):
    """A sessions-row-like view of one finished guest session."""
    def __init__(self, d):
        self._d = d

    def __getitem__(self, key):
        d = self._d
        if key == "quiz":
            return app_tables.quizzes.get_by_id(d["quiz_id"]) if d.get("quiz_id") else None
        if key == "ratings":
            return {"module": d["module"]} if d.get("module") else []
        if key == "finished":
            return datetime.fromisoformat(d["finished"])
        return d.get(key)


class _Guest(object):
    """A users-row-like guest whose data is a dict in anvil.server.session."""
    def __init__(self, data):
        self.data = data

    def __getitem__(self, key):
        d = self.data
        if key == "last_active":
            return date.fromisoformat(d["last_active"]) if d.get("last_active") else None
        if key in ("email", "signed_up"):
            return None
        if key == "is_admin":
            return False
        return d.get(key)

    def update(self, **changes):
        for k, v in changes.items():
            self.data[k] = v.isoformat() if isinstance(v, date) else v
        self.save()

    def save(self):
        anvil.server.session[GUEST_KEY] = self.data  # reassign so Anvil stores the change


def _new_guest():
    return {"display_name": "Guest", "bio": "", "avatar_color": AVATAR_COLORS[0], "xp": 0, "streak": 0,
            "last_active": None, "cards": {}, "sessions": []}


def _guest():
    data = anvil.server.session.get(GUEST_KEY)
    if data is None:
        raise anvil.users.AuthenticationFailed("Your guest session has ended. Start a new one from the sign-in page.")
    return _Guest(data)


def _is_guest(user):
    return isinstance(user, _Guest)


def _sessions(user):
    """This learner's finished sessions, newest first."""
    if _is_guest(user):
        return [_GuestSession(d) for d in reversed(user.data["sessions"])]
    return list(app_tables.sessions.search(tables.order_by("finished", ascending=False), user=user))


@anvil.server.callable
def start_guest(today=None):
    """Begin (or resume, in the same browser session) trying the app without an account."""
    if anvil.server.session.get(GUEST_KEY) is None:
        anvil.server.session[GUEST_KEY] = _new_guest()
    return _me_dict(_guest(), _client_today(today))


@anvil.server.callable
def end_guest():
    anvil.server.session[GUEST_KEY] = None  # the session object has no pop(); None means "no guest"


def _require_admin():
    user = _user()
    if not user["is_admin"]:
        raise PermissionError("Only admins can do this.")
    return user


def _published_quizzes():
    """Published quizzes in published collections, in learning order (module, then part)."""
    rows = [q for q in app_tables.quizzes.search(published=True)
            if q["collection"] is not None and q["collection"]["published"]]
    return sorted(rows, key=lambda q: (q["collection"]["position"] or 0, q["position"] or 0))


def _source_url(quizzes):
    """The source link of a module, taken from its parts (when it is a web address)."""
    for q in quizzes:
        if str(q["source"] or "").startswith("http"):
            return q["source"]
    return ""


def _states(user):
    """{question_id: card_state_row} for this user."""
    if _is_guest(user):
        return {qid: _GuestState(qid, v) for qid, v in user.data["cards"].items()}
    return {s["question"].get_id(): s for s in app_tables.card_state.search(user=user) if s["question"] is not None}


def _quiz_counts(quizzes, states, today):
    """Per quiz: total cards, learned (last rating "Got it"), due now, new (never seen), mastered."""
    counts = {q.get_id(): {"total": q["card_count"] or 0, "seen": 0, "learned": 0, "due": 0, "mastered": 0,
                           "next_due": None, "last": None} for q in quizzes}
    for s in states.values():
        c = counts.get(s["quiz"].get_id()) if s["quiz"] is not None else None
        if c is None:
            continue
        c["seen"] += 1
        if (s["box"] or 0) >= 1:
            c["learned"] += 1
        if (s["box"] or 0) >= MASTERED_BOX:
            c["mastered"] += 1
        if s["due"] is None or s["due"] <= today:
            c["due"] += 1
        elif c["next_due"] is None or s["due"] < c["next_due"]:
            c["next_due"] = s["due"]
        if s["last_reviewed"] and (c["last"] is None or s["last_reviewed"] > c["last"]):
            c["last"] = s["last_reviewed"]
    for c in counts.values():
        c["new"] = max(0, c["total"] - c["seen"])
    return counts


def _collection_summaries(quizzes, counts):
    by_col = {}
    for qz in quizzes:
        by_col.setdefault(qz["collection"].get_id(), []).append(qz)
    out = []
    for col in app_tables.collections.search(tables.order_by("position"), published=True):
        items = by_col.get(col.get_id(), [])
        if not items:
            continue
        cs = [counts[q.get_id()] for q in items]
        total = sum(c["total"] for c in cs)
        learned = sum(c["learned"] for c in cs)
        out.append({
            "id": col.get_id(), "number": col["position"] or 0, "title": col["title"],
            "description": col["description"] or "",
            "kind": col["kind"] or "Collection", "color": col["color"] or COLLECTION_COLORS[0],
            "quiz_count": len(items), "card_count": total,
            "learned": learned, "due": sum(c["due"] for c in cs), "mastered": sum(c["mastered"] for c in cs),
            "new": sum(c["new"] for c in cs), "started": any(c["seen"] for c in cs),
            "complete": total > 0 and learned >= total, "source": _source_url(items),
        })
    return out


def _session_dict(row):
    quiz = row["quiz"]
    col = quiz["collection"] if quiz else None
    title = quiz["title"] if quiz else "Daily review"
    module = row["ratings"].get("module") if isinstance(row["ratings"], dict) else None
    removed = row["ratings"].get("removed") if isinstance(row["ratings"], dict) else None
    col_title = None
    if quiz is None and module:
        col = app_tables.collections.get_by_id(module)
        title = "Whole module" if col else title
        if col is None:
            title, col_title = "Whole module", "Removed module"
    if quiz is None and removed:  # its part was deleted by an admin
        title, col_title = removed.get("title") or "Removed part", removed.get("module") or "Removed module"
    return {
        "quiz_id": quiz.get_id() if quiz else None,
        "collection_id": col.get_id() if (col and module) else None,
        "title": title,
        "collection_title": col_title or (col["title"] if col else "All collections"),
        "finished": _iso(row["finished"]),
        "reviewed": row["reviewed"] or 0, "got": row["got"] or 0, "again": row["again"] or 0,
    }


def _card_dict(q, state, quiz_titles=None):
    d = {"id": q.get_id(), "text": q["text"], "answer": q["answer"] or "", "explanation": q["explanation"] or "",
         "concept": q["concept"] or "", "box": (state["box"] or 0) if state else 0, "is_new": state is None}
    if quiz_titles is not None:
        d["quiz_title"] = quiz_titles.get(q["quiz"].get_id(), "")
    return d


# ---------------------------------------------------------------- profile
def _update_profile(user, display_name=None, bio=None, avatar_color=None):
    changes = {}
    if display_name is not None:
        name = " ".join(str(display_name).split())[:60]
        if not name:
            return {"ok": False, "error": "Please enter a display name."}
        changes["display_name"] = name
    if bio is not None:
        changes["bio"] = str(bio).strip()[:400]
    if avatar_color is not None:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(avatar_color)):
            return {"ok": False, "error": "That colour isn't valid."}
        changes["avatar_color"] = avatar_color
    if changes:
        user.update(**changes)
    return {"ok": True, "me": _me_dict(user, _now().date())}


# ---------------------------------------------------------------- pages
def _get_home(user, today=None):
    today = _client_today(today)
    quizzes = _published_quizzes()
    states = _states(user)
    counts = _quiz_counts(quizzes, states, today)
    collections = _collection_summaries(quizzes, counts)
    live = {q.get_id() for q in quizzes}
    due = sum(c["due"] for c in counts.values())

    # "Continue": due reviews first, else the next quiz that still has new cards.
    cont = None
    if due:
        cont = {"kind": "review", "due": due, "title": "Review %d due card%s" % (due, "" if due == 1 else "s"),
                "subtitle": "Cards from all your modules that are due today"}
    else:
        for qz in quizzes:
            c = counts[qz.get_id()]
            if c["new"]:
                cont = {"kind": "quiz", "quiz_id": qz.get_id(), "title": qz["title"],
                        "module": qz["collection"]["position"] or 0,
                        "subtitle": "%s · %d new card%s" % (qz["collection"]["title"], c["new"], "" if c["new"] == 1 else "s"),
                        "started": bool(c["seen"])}
                break
    next_due = min((c["next_due"] for c in counts.values() if c["next_due"]), default=None)

    recent = [_session_dict(r) for r in _sessions(user)[:5]]
    return {
        "me": _me_dict(user, today),
        "stats": {
            "learned": sum(c["learned"] for c in counts.values()),
            "total_cards": sum(c["total"] for c in counts.values()),
            "due": due, "next_due": _iso(next_due),
            "mastered": sum(c["mastered"] for c in counts.values()),
            "modules_total": len(collections), "modules_complete": sum(1 for c in collections if c["complete"]),
            "modules_started": sum(1 for c in collections if c["started"]),
            "xp": user["xp"] or 0, "streak": _current_streak(user, today),
        },
        "continue": cont,
        "collections": collections,
        "recent": [r for r in recent if r["quiz_id"] is None or r["quiz_id"] in live],
    }


def _get_collection(user, collection_id, today=None):
    today = _client_today(today)
    col = app_tables.collections.get_by_id(collection_id) if collection_id else None
    if col is None or not col["published"]:
        raise ValueError("That collection was not found.")
    quizzes = list(app_tables.quizzes.search(tables.order_by("position"), collection=col, published=True))
    counts = _quiz_counts(quizzes, _states(user), today)
    all_modules = [c for c in app_tables.collections.search(tables.order_by("position"), published=True)]
    return {
        "collection": {"id": col.get_id(), "number": col["position"] or 0, "title": col["title"],
                       "description": col["description"] or "", "modules_total": len(all_modules),
                       "kind": col["kind"] or "Collection", "color": col["color"] or COLLECTION_COLORS[0],
                       "source": _source_url(quizzes)},
        "quizzes": [dict(id=q.get_id(), title=q["title"], description=q["description"] or "",
                         difficulty=q["difficulty"] or "", card_count=counts[q.get_id()]["total"],
                         learned=counts[q.get_id()]["learned"], due=counts[q.get_id()]["due"],
                         new=counts[q.get_id()]["new"], last_studied=_iso(counts[q.get_id()]["last"]))
                    for q in quizzes],
    }


def _get_study(user, quiz_id=None, scope="due", today=None, collection_id=None):
    """Cards for one study session.

    quiz_id given:       that quiz (part). scope "due" = due + new cards, "all" = every card (study ahead).
    collection_id given: every part of that module, in order.
    neither:             daily review = due cards from every published quiz (no new cards).
    """
    today = _client_today(today)
    states = _states(user)

    if collection_id and not quiz_id:
        col = app_tables.collections.get_by_id(collection_id)
        if col is None or not col["published"]:
            raise ValueError("That module was not found.")
        quizzes = list(app_tables.quizzes.search(tables.order_by("position"), collection=col, published=True))
        cards = []
        for qz in quizzes:
            cards += list(app_tables.questions.search(tables.order_by("position"), quiz=qz))
        info = {"id": None, "module_id": col.get_id(), "number": col["position"] or 0,
                "title": col["title"], "description": "Every part of this module, in order.",
                "collection_id": col.get_id(), "collection_title": col["title"], "source": _source_url(quizzes)}
    elif quiz_id:
        qz = app_tables.quizzes.get_by_id(quiz_id)
        if qz is None or not qz["published"]:
            raise ValueError("That quiz was not found.")
        quizzes = [qz]
        cards = list(app_tables.questions.search(tables.order_by("position"), quiz=qz))
        col = qz["collection"]
        info = {"id": qz.get_id(), "title": qz["title"], "description": qz["description"] or "",
                "collection_id": col.get_id() if col else None, "collection_title": col["title"] if col else "",
                "number": col["position"] if col else None,
                "source": qz["source"] if str(qz["source"] or "").startswith("http") else ""}
    else:
        quizzes = _published_quizzes()
        live = {q.get_id() for q in quizzes}
        cards = [s["question"] for s in states.values()
                 if s["quiz"] is not None and s["quiz"].get_id() in live and (s["due"] is None or s["due"] <= today)]
        cards = [q for q in cards if q is not None]  # a guest's card may have been deleted by an admin
        info = {"id": None, "title": "Daily review", "description": "Due cards from all your modules.",
                "collection_id": None, "collection_title": "Home"}

    def is_due(q):
        s = states.get(q.get_id())
        return s is None or s["due"] is None or s["due"] <= today

    if scope != "all":
        cards = [q for q in cards if is_due(q)]
    # Due reviews first (most overdue first), then new cards in their quiz order.
    far = date.max
    reviews = sorted((q for q in cards if q.get_id() in states), key=lambda q: states[q.get_id()]["due"] or far)
    new = [q for q in cards if q.get_id() not in states]
    chosen = (reviews + new)[:SESSION_LIMIT]

    counts = _quiz_counts(quizzes, states, today)
    total = {k: sum(c[k] for c in counts.values()) for k in ("total", "learned", "due", "new")}
    next_due = min((c["next_due"] for c in counts.values() if c["next_due"]), default=None)
    titles = None if quiz_id else {q.get_id(): q["title"] for q in quizzes}
    if collection_id and not quiz_id and len(quizzes) == 1:
        titles = None
    return {
        "quiz": info, "scope": scope,
        "cards": [_card_dict(q, states.get(q.get_id()), titles) for q in chosen],
        "counts": dict(total, next_due=_iso(next_due), limit=SESSION_LIMIT),
    }


def _rate_card(user, question_id, knew, today=None):
    """Save one self-rating. Called after every card, so leaving mid-session loses nothing."""
    today = _client_today(today)
    q = app_tables.questions.get_by_id(question_id) if question_id else None
    if q is None:
        raise ValueError("That card was not found.")
    if _is_guest(user):
        old = user.data["cards"].get(q.get_id())
        state = _GuestState(q.get_id(), old) if old else None
    else:
        state = app_tables.card_state.get(user=user, question=q)
    box = (state["box"] or 0) if state else 0
    if knew:
        box = min(box + 1, len(BOX_INTERVALS) - 1)
        due = today + timedelta(days=BOX_INTERVALS[box])
    else:
        box, due = 0, today
    fields = dict(box=box, due=due, last_reviewed=_now())
    if _is_guest(user):
        reviews, lapses = (old[3], old[4]) if old else (0, 0)
        user.data["cards"][q.get_id()] = [q["quiz"].get_id() if q["quiz"] else None, box, due.isoformat(),
                                          reviews + 1, lapses + (0 if knew else 1), fields["last_reviewed"].isoformat()]
        user.save()
    elif state is None:
        app_tables.card_state.add_row(user=user, question=q, quiz=q["quiz"], reviews=1, lapses=0 if knew else 1, **fields)
    else:
        state.update(reviews=(state["reviews"] or 0) + 1,
                     lapses=(state["lapses"] or 0) + (0 if knew else 1), **fields)
    return {"box": box, "due": _iso(due)}


def _finish_session(user, quiz_id, ratings, today=None, collection_id=None):
    """Record a finished session (ratings were already saved one by one) and award XP + streak."""
    today = _client_today(today)
    ratings = [r for r in (ratings or []) if isinstance(r, dict) and r.get("question_id")]
    if not ratings:
        return {"xp_gained": 0, "streak": _current_streak(user, today), "me": _me_dict(user, today)}
    qz = app_tables.quizzes.get_by_id(quiz_id) if quiz_id else None
    cards = {r["question_id"] for r in ratings}
    got = len({r["question_id"] for r in ratings if r.get("knew")})
    again = len({r["question_id"] for r in ratings if not r.get("knew")})
    xp = XP_PER_REVIEW * len(ratings) + XP_PER_GOT_IT * got

    last = user["last_active"]
    if last is not None and today <= last:  # same day (or the device clock went back a day)
        streak, today = user["streak"] or 1, last
    elif last is not None and (today - last).days == 1:
        streak = (user["streak"] or 0) + 1
    else:
        streak = 1
    user.update(xp=(user["xp"] or 0) + xp, streak=streak, last_active=today)
    if _is_guest(user):
        user.data["sessions"] = (user.data["sessions"] + [{
            "quiz_id": qz.get_id() if qz else None, "module": collection_id if (collection_id and not qz) else None,
            "finished": _now().isoformat(), "reviewed": len(cards), "got": got, "again": again}])[-HISTORY_LIMIT:]
        user.save()
    else:
        stored = {"module": collection_id, "ratings": ratings[:500]} if (collection_id and not qz) else ratings[:500]
        app_tables.sessions.add_row(user=user, quiz=qz, finished=_now(), reviewed=len(cards), got=got, again=again,
                                    xp=xp, ratings=stored)

    # When does this learner next have something due?
    states = [s for s in _states(user).values() if s["due"] is not None]
    future = [s["due"] for s in states if s["due"] > today]
    return {"xp_gained": xp, "streak": streak, "next_due": _iso(min(future) if future else None),
            "due_tomorrow": sum(1 for s in states if s["due"] <= today + timedelta(days=1)),
            "me": _me_dict(user, today)}


def _get_profile(user, today=None):
    today = _client_today(today)
    quizzes = _published_quizzes()
    states = _states(user)
    counts = _quiz_counts(quizzes, states, today)
    sessions = _sessions(user)
    return {
        "me": _me_dict(user, today),
        "stats": {
            "learned": sum(c["learned"] for c in counts.values()),
            "mastered": sum(c["mastered"] for c in counts.values()),
            "total_cards": sum(c["total"] for c in counts.values()),
            "reviews": sum(s["reviews"] or 0 for s in states.values()),
            "sessions": len(sessions),
            "due": sum(c["due"] for c in counts.values()),
        },
        "progress": [{"id": c["id"], "number": c["number"], "title": c["title"], "color": c["color"],
                      "learned": c["learned"], "total": c["card_count"], "due": c["due"], "complete": c["complete"]}
                     for c in _collection_summaries(quizzes, counts)],
        "history": [_session_dict(r) for r in sessions[:HISTORY_LIMIT]],
        "colors": AVATAR_COLORS,
    }


# ---------------------------------------------------------------- learner API
# Each call has a signed-in version and a guest_ version (guest progress stays in the browser session).
@anvil.server.callable(require_user=True)
def get_me(today=None):
    return _me_dict(_user(), _client_today(today))


@anvil.server.callable
def guest_get_me(today=None):
    return _me_dict(_guest(), _client_today(today))


@anvil.server.callable(require_user=True)
def update_profile(display_name=None, bio=None, avatar_color=None):
    return _update_profile(_user(), display_name, bio, avatar_color)


@anvil.server.callable
def guest_update_profile(display_name=None, bio=None, avatar_color=None):
    return _update_profile(_guest(), display_name, bio, avatar_color)


@anvil.server.callable(require_user=True)
def get_home(today=None):
    return _get_home(_user(), today)


@anvil.server.callable
def guest_get_home(today=None):
    return _get_home(_guest(), today)


@anvil.server.callable(require_user=True)
def get_collection(collection_id, today=None):
    return _get_collection(_user(), collection_id, today)


@anvil.server.callable
def guest_get_collection(collection_id, today=None):
    return _get_collection(_guest(), collection_id, today)


@anvil.server.callable(require_user=True)
def get_study(quiz_id=None, scope="due", today=None, collection_id=None):
    return _get_study(_user(), quiz_id, scope, today, collection_id)


@anvil.server.callable
def guest_get_study(quiz_id=None, scope="due", today=None, collection_id=None):
    return _get_study(_guest(), quiz_id, scope, today, collection_id)


@anvil.server.callable(require_user=True)
@tables.in_transaction
def rate_card(question_id, knew, today=None):
    return _rate_card(_user(), question_id, knew, today)


@anvil.server.callable
def guest_rate_card(question_id, knew, today=None):
    return _rate_card(_guest(), question_id, knew, today)


@anvil.server.callable(require_user=True)
@tables.in_transaction
def finish_session(quiz_id, ratings, today=None, collection_id=None):
    return _finish_session(_user(), quiz_id, ratings, today, collection_id)


@anvil.server.callable
def guest_finish_session(quiz_id, ratings, today=None, collection_id=None):
    return _finish_session(_guest(), quiz_id, ratings, today, collection_id)


@anvil.server.callable(require_user=True)
def get_profile(today=None):
    return _get_profile(_user(), today)


@anvil.server.callable
def guest_get_profile(today=None):
    return _get_profile(_guest(), today)


# ---------------------------------------------------------------- admin: importing cards
def _clean_card(q, n):
    """Accepts a flashcard {question, answer} or a multiple-choice question (its right option becomes the answer)."""
    if not isinstance(q, dict):
        raise ValueError("card %d is not an object" % n)
    text = str(q.get("question") or q.get("text") or q.get("front") or "").strip()
    answer = str(q.get("answer") or q.get("back") or "").strip()
    options = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
    ci = q.get("correctIndex", q.get("correct_index"))
    if isinstance(ci, str) and ci.isdigit():
        ci = int(ci)
    if not answer and isinstance(ci, int) and 0 <= ci < len(options):
        answer = options[ci]
    if not text or not answer:
        raise ValueError("card %d needs a question and an answer" % n)
    return {"text": text, "answer": answer,
            "explanation": str(q.get("explanation") or "").strip(), "concept": str(q.get("concept") or "").strip()}


def _import_one(item):
    """Create or update one quiz. Accepts the Quizbook 'quizbook-quiz/1' format or the simple format."""
    col_title = str(item.get("collection") or item.get("book") or "General").strip()
    title = str(item.get("title") or item.get("chapterTitle") or "").strip()
    if not title:
        raise ValueError("a quiz has no title (use \"title\" or \"chapterTitle\")")
    cards = [_clean_card(q, i + 1) for i, q in enumerate(item.get("questions") or item.get("cards") or [])]
    if not cards:
        raise ValueError('"%s" has no cards' % title)

    col = app_tables.collections.get(title=col_title)
    col_fields = {}
    if item.get("collection_description"):
        col_fields["description"] = str(item["collection_description"])
    if item.get("kind"):
        col_fields["kind"] = str(item["kind"])
    if re.fullmatch(r"#[0-9a-fA-F]{6}", str(item.get("color") or "")):
        col_fields["color"] = item["color"]
    if isinstance(item.get("collection_position"), (int, float)):
        col_fields["position"] = item["collection_position"]
    if col is None:
        n = len(app_tables.collections.search())
        base = dict(description="", kind="Collection", color=COLLECTION_COLORS[n % len(COLLECTION_COLORS)], position=n + 1)
        base.update(col_fields)
        col = app_tables.collections.add_row(title=col_title, published=True, created=_now(), **base)
    elif col_fields:
        col.update(**col_fields)

    qz = app_tables.quizzes.get(collection=col, title=title)
    replaced = qz is not None
    fields = dict(description=str(item.get("description") or ""), difficulty=str(item.get("difficulty") or ""),
                  card_count=len(cards), published=True,
                  source=str(item.get("source") or item.get("format") or "import"))
    if isinstance(item.get("position"), (int, float)):
        fields["position"] = item["position"]
    if qz is None:
        fields.setdefault("position", len(app_tables.quizzes.search(collection=col)) + 1)
        qz = app_tables.quizzes.add_row(collection=col, title=title, created=_now(), **fields)
        existing = []
    else:
        qz.update(**fields)
        existing = list(app_tables.questions.search(tables.order_by("position"), quiz=qz))

    # Re-importing: cards with the same question text are updated in place, so learners keep their progress.
    by_text = {}
    for row in existing:
        by_text.setdefault(row["text"], row)
    keep, new_rows = set(), []
    for i, c in enumerate(cards):
        row = by_text.pop(c["text"], None)
        if row is None:
            new_rows.append(dict(quiz=qz, position=i + 1, **c))
        else:
            row.update(position=i + 1, **c)
            keep.add(row.get_id())
    add_rows = getattr(app_tables.questions, "add_rows", None)
    if add_rows and new_rows:
        add_rows(new_rows)
    else:
        for r in new_rows:
            app_tables.questions.add_row(**r)
    for row in existing:
        if row.get_id() not in keep:
            for s in app_tables.card_state.search(question=row):
                s.delete()
            row.delete()
    return replaced, len(cards)


@tables.in_transaction
def _import_items(items):
    added = updated = n = 0
    for item in items:
        was_replaced, count = _import_one(item)
        updated += was_replaced
        added += not was_replaced
        n += count
    return "Imported %d new quiz%s and updated %d (%d cards)." % (added, "" if added == 1 else "zes", updated, n)


@anvil.server.callable(require_user=True)
def import_quiz_json(text):
    _require_admin()
    try:
        data = json.loads(str(text or "").lstrip("﻿"))
    except ValueError as e:
        return {"ok": False, "error": "That isn't valid JSON: %s" % e}
    items = data if isinstance(data, list) else data.get("quizzes", [data]) if isinstance(data, dict) else []
    if not items:
        return {"ok": False, "error": "No quizzes found in that JSON."}
    try:
        return {"ok": True, "message": _import_items(items)}
    except ValueError as e:
        return {"ok": False, "error": "Nothing was imported: %s." % e}


@anvil.server.callable(require_user=True)
def seed_demo():
    _require_admin()
    return {"ok": True, "message": _import_items(DEMO_QUIZZES)}


# ---------------------------------------------------------------- admin: managing the curriculum
# Profile → Manage curriculum (admins only): browse every module (hidden ones too), preview its cards,
# edit or delete modules, parts and cards in place, and download modules as importable JSON.
# Edits keep the same rows, so learners keep their progress on edited cards.
def _num(value):
    """A position as an int when it is a whole number (Anvil may hand back 3.0)."""
    return int(value) if isinstance(value, float) and value.is_integer() else value


def _admin_part(qz):
    return {"id": qz.get_id(), "number": _num(qz["position"]) or 0, "title": qz["title"],
            "description": qz["description"] or "", "source": qz["source"] or "",
            "published": bool(qz["published"]), "card_count": qz["card_count"] or 0}


def _admin_module(col, parts):
    return {"id": col.get_id(), "number": _num(col["position"]) or 0, "title": col["title"],
            "description": col["description"] or "", "kind": col["kind"] or "",
            "color": col["color"] or COLLECTION_COLORS[0], "published": bool(col["published"]),
            "card_count": sum(p["card_count"] for p in parts), "parts": parts}


def _admin_card(q):
    return {"id": q.get_id(), "number": _num(q["position"]) or 0, "question": q["text"], "answer": q["answer"] or "",
            "explanation": q["explanation"] or "", "concept": q["concept"] or ""}


def _module_parts(col):
    return list(app_tables.quizzes.search(tables.order_by("position"), collection=col))


def _field(fields, key, label, limit, required=False):
    value = str(fields.get(key) or "").strip()
    if required and not value:
        raise ValueError("%s can't be empty." % label)
    if len(value) > limit:
        raise ValueError("%s is too long (%d characters at most)." % (label, limit))
    return value


def _position(fields, label):
    try:
        n = int(str(fields.get("number")).strip())
    except (TypeError, ValueError):
        raise ValueError("%s number must be a whole number." % label)
    if not 0 <= n <= 9999:
        raise ValueError("%s number must be between 0 and 9999." % label)
    return n


def _admin_call(fn, *args):
    _require_admin()
    try:
        return dict(fn(*args), ok=True)
    except ValueError as e:
        return {"ok": False, "error": str(e)}


def _delete_all(rows):
    """Delete every row of a search (one call on Anvil, row by row elsewhere)."""
    delete_all = getattr(rows, "delete_all_rows", None)
    if delete_all:
        delete_all()
    else:
        for r in list(rows):
            r.delete()


def _recount(qz):
    n = len(app_tables.questions.search(quiz=qz))
    qz.update(card_count=n)
    return n


@anvil.server.callable(require_user=True)
def admin_curriculum():
    """Every module with its parts (no cards, to keep it light), hidden ones included."""
    _require_admin()
    by_col = {}
    for qz in app_tables.quizzes.search(tables.order_by("position")):
        if qz["collection"] is not None:
            by_col.setdefault(qz["collection"].get_id(), []).append(_admin_part(qz))
    return {"modules": [_admin_module(col, by_col.get(col.get_id(), []))
                        for col in app_tables.collections.search(tables.order_by("position"))],
            "colors": COLLECTION_COLORS}


def _part_cards(quiz_id):
    qz = app_tables.quizzes.get_by_id(quiz_id) if quiz_id else None
    if qz is None:
        raise ValueError("That part was not found. It may have been deleted.")
    return {"cards": [_admin_card(q) for q in app_tables.questions.search(tables.order_by("position"), quiz=qz)]}


@anvil.server.callable(require_user=True)
def admin_part_cards(quiz_id):
    return _admin_call(_part_cards, quiz_id)


def _save_module(collection_id, fields):
    col = app_tables.collections.get_by_id(collection_id) if collection_id else None
    if col is None:
        raise ValueError("That module was not found. It may have been deleted.")
    title = _field(fields, "title", "The module title", 200, required=True)
    if any(c != col for c in app_tables.collections.search(title=title)):
        raise ValueError("Another module is already called that. Module titles must be unique, "
                         "because importing a file matches modules by title.")
    color = str(fields.get("color") or "").strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("The colour must look like #2e4a70.")
    number = _position(fields, "The module")
    changes = dict(title=title, description=_field(fields, "description", "The description", 2000),
                   color=color, position=number, published=bool(fields.get("published")))
    if re.fullmatch(r"Module \d+", col["kind"] or ""):  # keep the "Module N" label in step with the number
        changes["kind"] = "Module %d" % number
    col.update(**changes)
    return {"module": _admin_module(col, [_admin_part(q) for q in _module_parts(col)])}


@anvil.server.callable(require_user=True)
def admin_save_module(collection_id, fields):
    return _admin_call(_save_module, collection_id, fields or {})


def _save_part(quiz_id, fields):
    qz = app_tables.quizzes.get_by_id(quiz_id) if quiz_id else None
    if qz is None:
        raise ValueError("That part was not found. It may have been deleted.")
    title = _field(fields, "title", "The part title", 200, required=True)
    if any(q != qz for q in app_tables.quizzes.search(collection=qz["collection"], title=title)):
        raise ValueError("This module already has a part called that. Part titles must be unique within a module.")
    source = _field(fields, "source", "The source link", 1000)
    qz.update(title=title, description=_field(fields, "description", "The description", 2000),
              source=source or "import", position=_position(fields, "The part"),
              published=bool(fields.get("published")))
    return {"part": _admin_part(qz)}


@anvil.server.callable(require_user=True)
def admin_save_part(quiz_id, fields):
    return _admin_call(_save_part, quiz_id, fields or {})


def _save_card(quiz_id, card_id, fields):
    """Edit a card (card_id given) or add one to the end of a part."""
    qz = app_tables.quizzes.get_by_id(quiz_id) if quiz_id else None
    if qz is None:
        raise ValueError("That part was not found. It may have been deleted.")
    card = app_tables.questions.get_by_id(card_id) if card_id else None
    if card_id and (card is None or card["quiz"] != qz):
        raise ValueError("That card was not found. It may have been deleted.")
    values = dict(text=_field(fields, "question", "The question", 2000, required=True),
                  answer=_field(fields, "answer", "The answer", 2000, required=True),
                  explanation=_field(fields, "explanation", "The explanation", 4000),
                  concept=_field(fields, "concept", "The concept", 200))
    if any(q != card for q in app_tables.questions.search(quiz=qz, text=values["text"])):
        raise ValueError("This part already has a card with exactly that question.")
    if card is None:
        last = max([q["position"] or 0 for q in app_tables.questions.search(quiz=qz)] or [0])
        card = app_tables.questions.add_row(quiz=qz, position=_num(last) + 1, **values)
    else:
        card.update(**values)
    return {"card": _admin_card(card), "card_count": _recount(qz)}


@anvil.server.callable(require_user=True)
def admin_save_card(quiz_id, card_id, fields):
    return _admin_call(_save_card, quiz_id, card_id, fields or {})


def _delete_part_rows(qz):
    """Remove a part, its cards and everyone's progress on them. Study history stays, labelled by title."""
    col = qz["collection"]
    removed = {"title": qz["title"], "module": col["title"] if col else ""}
    for s in app_tables.sessions.search(quiz=qz):
        old = s["ratings"]
        s.update(quiz=None, ratings={"removed": removed, "ratings": old if isinstance(old, list) else []})
    _delete_all(app_tables.card_state.search(quiz=qz))
    _delete_all(app_tables.questions.search(quiz=qz))
    qz.delete()


@tables.in_transaction
def _delete(kind, item_id):
    if kind == "card":
        card = app_tables.questions.get_by_id(item_id) if item_id else None
        if card is None:
            raise ValueError("That card was not found. It may already be deleted.")
        qz = card["quiz"]
        _delete_all(app_tables.card_state.search(question=card))
        card.delete()
        return {"message": "Card deleted.", "card_count": _recount(qz) if qz else 0}
    if kind == "part":
        qz = app_tables.quizzes.get_by_id(item_id) if item_id else None
        if qz is None:
            raise ValueError("That part was not found. It may already be deleted.")
        title = qz["title"]
        _delete_part_rows(qz)
        return {"message": 'Deleted the part "%s".' % title}
    if kind == "module":
        col = app_tables.collections.get_by_id(item_id) if item_id else None
        if col is None:
            raise ValueError("That module was not found. It may already be deleted.")
        title = col["title"]
        for qz in _module_parts(col):
            _delete_part_rows(qz)
        col.delete()
        return {"message": 'Deleted the module "%s".' % title}
    raise ValueError("Unknown kind of item: %s" % kind)


@anvil.server.callable(require_user=True)
def admin_delete(kind, item_id):
    return _admin_call(_delete, kind, item_id)


def _export_part(col, qz, cards):
    item = {"collection": col["title"], "collection_description": col["description"] or "",
            "collection_position": _num(col["position"]), "kind": col["kind"] or "", "color": col["color"] or "",
            "title": qz["title"], "description": qz["description"] or "", "position": _num(qz["position"]),
            "source": qz["source"] or ""}
    if qz["difficulty"]:
        item["difficulty"] = qz["difficulty"]
    item["questions"] = [{"question": q["text"], "answer": q["answer"] or "", "explanation": q["explanation"] or "",
                          "concept": q["concept"] or ""}
                         for q in sorted(cards, key=lambda q: q["position"] or 0)]
    return item


def _export(collection_id=None):
    """Modules as the same JSON as modules/*.json, so the file can be imported again."""
    if collection_id:
        col = app_tables.collections.get_by_id(collection_id)
        if col is None:
            raise ValueError("That module was not found. It may have been deleted.")
        items = [_export_part(col, qz, list(app_tables.questions.search(quiz=qz))) for qz in _module_parts(col)]
        slug = re.sub(r"[^A-Za-z0-9]+", "-", col["title"]).strip("-") or "module"
        return {"items": items, "filename": "%02d-%s.json" % (_num(col["position"]) or 0, slug)}
    by_quiz = {}
    for q in app_tables.questions.search():
        if q["quiz"] is not None:
            by_quiz.setdefault(q["quiz"].get_id(), []).append(q)
    items = []
    for col in app_tables.collections.search(tables.order_by("position")):
        items += [_export_part(col, qz, by_quiz.get(qz.get_id(), [])) for qz in _module_parts(col)]
    return {"items": items, "filename": "caf-guide-curriculum-%s.json" % _now().date().isoformat()}


@anvil.server.callable(require_user=True)
def admin_export(collection_id=None):
    return _admin_call(_export, collection_id)
