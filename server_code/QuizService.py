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
    }


def _user():
    user = anvil.users.get_user()
    if user is None:
        raise anvil.users.AuthenticationFailed("Please sign in again.")
    _ensure_defaults(user)
    return user


def _require_admin():
    user = _user()
    if not user["is_admin"]:
        raise PermissionError("Only admins can do this.")
    return user


def _published_quizzes():
    """Published quizzes in published collections, in display order."""
    return [q for q in app_tables.quizzes.search(tables.order_by("position"), published=True)
            if q["collection"] is not None and q["collection"]["published"]]


def _states(user):
    """{question_id: card_state_row} for this user."""
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
        out.append({
            "id": col.get_id(), "title": col["title"], "description": col["description"] or "",
            "kind": col["kind"] or "Collection", "color": col["color"] or COLLECTION_COLORS[0],
            "quiz_count": len(items), "card_count": sum(c["total"] for c in cs),
            "learned": sum(c["learned"] for c in cs), "due": sum(c["due"] for c in cs),
            "new": sum(c["new"] for c in cs), "started": any(c["seen"] for c in cs),
        })
    return out


def _session_dict(row):
    quiz = row["quiz"]
    col = quiz["collection"] if quiz else None
    return {
        "quiz_id": quiz.get_id() if quiz else None,
        "title": quiz["title"] if quiz else "Daily review",
        "collection_title": col["title"] if col else "All collections",
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
@anvil.server.callable(require_user=True)
def get_me(today=None):
    return _me_dict(_user(), _client_today(today))


@anvil.server.callable(require_user=True)
def update_profile(display_name=None, bio=None, avatar_color=None):
    user = _user()
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
@anvil.server.callable(require_user=True)
def get_home(today=None):
    user = _user()
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
                "subtitle": "Cards from all your collections that are due today"}
    else:
        for qz in quizzes:
            c = counts[qz.get_id()]
            if c["new"]:
                cont = {"kind": "quiz", "quiz_id": qz.get_id(), "title": qz["title"],
                        "subtitle": "%s · %d new card%s" % (qz["collection"]["title"], c["new"], "" if c["new"] == 1 else "s"),
                        "started": bool(c["seen"])}
                break
    next_due = min((c["next_due"] for c in counts.values() if c["next_due"]), default=None)

    recent = [_session_dict(r) for r in
              app_tables.sessions.search(tables.order_by("finished", ascending=False), user=user)[:5]]
    return {
        "me": _me_dict(user, today),
        "stats": {
            "learned": sum(c["learned"] for c in counts.values()),
            "total_cards": sum(c["total"] for c in counts.values()),
            "due": due, "next_due": _iso(next_due),
            "mastered": sum(c["mastered"] for c in counts.values()),
            "xp": user["xp"] or 0, "streak": _current_streak(user, today),
        },
        "continue": cont,
        "collections": collections,
        "recent": [r for r in recent if r["quiz_id"] is None or r["quiz_id"] in live],
    }


@anvil.server.callable(require_user=True)
def get_collection(collection_id, today=None):
    user = _user()
    today = _client_today(today)
    col = app_tables.collections.get_by_id(collection_id) if collection_id else None
    if col is None or not col["published"]:
        raise ValueError("That collection was not found.")
    quizzes = list(app_tables.quizzes.search(tables.order_by("position"), collection=col, published=True))
    counts = _quiz_counts(quizzes, _states(user), today)
    return {
        "collection": {"id": col.get_id(), "title": col["title"], "description": col["description"] or "",
                       "kind": col["kind"] or "Collection", "color": col["color"] or COLLECTION_COLORS[0]},
        "quizzes": [dict(id=q.get_id(), title=q["title"], description=q["description"] or "",
                         difficulty=q["difficulty"] or "", card_count=counts[q.get_id()]["total"],
                         learned=counts[q.get_id()]["learned"], due=counts[q.get_id()]["due"],
                         new=counts[q.get_id()]["new"], last_studied=_iso(counts[q.get_id()]["last"]))
                    for q in quizzes],
    }


@anvil.server.callable(require_user=True)
def get_study(quiz_id=None, scope="due", today=None):
    """Cards for one study session.

    quiz_id given: that quiz. scope "due" = due + new cards, "all" = every card (study ahead).
    quiz_id None:  daily review = due cards from every published quiz (no new cards).
    """
    user = _user()
    today = _client_today(today)
    states = _states(user)

    if quiz_id:
        qz = app_tables.quizzes.get_by_id(quiz_id)
        if qz is None or not qz["published"]:
            raise ValueError("That quiz was not found.")
        quizzes = [qz]
        cards = list(app_tables.questions.search(tables.order_by("position"), quiz=qz))
        col = qz["collection"]
        info = {"id": qz.get_id(), "title": qz["title"], "description": qz["description"] or "",
                "collection_id": col.get_id() if col else None, "collection_title": col["title"] if col else ""}
    else:
        quizzes = _published_quizzes()
        live = {q.get_id() for q in quizzes}
        cards = [s["question"] for s in states.values()
                 if s["quiz"] is not None and s["quiz"].get_id() in live and (s["due"] is None or s["due"] <= today)]
        info = {"id": None, "title": "Daily review", "description": "Due cards from all your collections.",
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
    return {
        "quiz": info, "scope": scope,
        "cards": [_card_dict(q, states.get(q.get_id()), titles) for q in chosen],
        "counts": dict(total, next_due=_iso(next_due), limit=SESSION_LIMIT),
    }


@anvil.server.callable(require_user=True)
@tables.in_transaction
def rate_card(question_id, knew, today=None):
    """Save one self-rating. Called after every card, so leaving mid-session loses nothing."""
    user = _user()
    today = _client_today(today)
    q = app_tables.questions.get_by_id(question_id) if question_id else None
    if q is None:
        raise ValueError("That card was not found.")
    state = app_tables.card_state.get(user=user, question=q)
    box = (state["box"] or 0) if state else 0
    if knew:
        box = min(box + 1, len(BOX_INTERVALS) - 1)
        due = today + timedelta(days=BOX_INTERVALS[box])
    else:
        box, due = 0, today
    fields = dict(box=box, due=due, last_reviewed=_now())
    if state is None:
        app_tables.card_state.add_row(user=user, question=q, quiz=q["quiz"], reviews=1, lapses=0 if knew else 1, **fields)
    else:
        state.update(reviews=(state["reviews"] or 0) + 1,
                     lapses=(state["lapses"] or 0) + (0 if knew else 1), **fields)
    return {"box": box, "due": _iso(due)}


@anvil.server.callable(require_user=True)
@tables.in_transaction
def finish_session(quiz_id, ratings, today=None):
    """Record a finished session (ratings were already saved one by one) and award XP + streak."""
    user = _user()
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
    app_tables.sessions.add_row(user=user, quiz=qz, finished=_now(), reviewed=len(cards), got=got, again=again,
                                xp=xp, ratings=ratings[:500])

    # When does this learner next have something due?
    states = [s for s in app_tables.card_state.search(user=user) if s["due"] is not None]
    future = [s["due"] for s in states if s["due"] > today]
    return {"xp_gained": xp, "streak": streak, "next_due": _iso(min(future) if future else None),
            "due_tomorrow": sum(1 for s in states if s["due"] <= today + timedelta(days=1)),
            "me": _me_dict(user, today)}


@anvil.server.callable(require_user=True)
def get_profile(today=None):
    user = _user()
    today = _client_today(today)
    quizzes = _published_quizzes()
    states = _states(user)
    counts = _quiz_counts(quizzes, states, today)
    sessions = list(app_tables.sessions.search(tables.order_by("finished", ascending=False), user=user))
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
        "progress": [{"title": c["title"], "color": c["color"], "learned": c["learned"], "total": c["card_count"],
                      "due": c["due"]} for c in _collection_summaries(quizzes, counts)],
        "history": [_session_dict(r) for r in sessions[:HISTORY_LIMIT]],
        "colors": AVATAR_COLORS,
    }


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
    if col is None:
        n = len(app_tables.collections.search())
        col = app_tables.collections.add_row(
            title=col_title, description=str(item.get("collection_description") or ""),
            kind=str(item.get("kind") or "Collection"), color=COLLECTION_COLORS[n % len(COLLECTION_COLORS)],
            position=n + 1, published=True, created=_now())

    qz = app_tables.quizzes.get(collection=col, title=title)
    replaced = qz is not None
    fields = dict(description=str(item.get("description") or ""), difficulty=str(item.get("difficulty") or ""),
                  card_count=len(cards), published=True, source=str(item.get("format") or "import"))
    if qz is None:
        qz = app_tables.quizzes.add_row(collection=col, title=title, created=_now(),
                                        position=len(app_tables.quizzes.search(collection=col)) + 1, **fields)
        existing = []
    else:
        qz.update(**fields)
        existing = list(app_tables.questions.search(tables.order_by("position"), quiz=qz))

    # Re-importing: cards with the same question text are updated in place, so learners keep their progress.
    by_text = {}
    for row in existing:
        by_text.setdefault(row["text"], row)
    keep = set()
    for i, c in enumerate(cards):
        row = by_text.pop(c["text"], None)
        if row is None:
            app_tables.questions.add_row(quiz=qz, position=i + 1, **c)
        else:
            row.update(position=i + 1, **c)
            keep.add(row.get_id())
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
