"""Server logic tests against a strict mock of Anvil's data tables (tools/testing/mock).

    python tools/testing/test_server.py          -> ends with ALL OK   (no -I: the mock reads anvil.yaml with PyYAML)

The mock takes its tables from anvil.yaml's db_schema, so a column typo fails here like it would live.
Ported from the old project (Guild/anvil-quiz) unchanged, plus a check that every callable the pages use still exists.
"""
import os, pathlib, shutil, sys, tempfile
HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
_tmp = pathlib.Path(tempfile.mkdtemp())
shutil.copytree(PROJECT / "server_code", _tmp / "app")
(_tmp / "app" / "__init__.py").write_text("")
os.environ["ANVIL_APP_YAML"] = str(PROJECT / "anvil.yaml")
sys.path[:0] = [str(HERE / "mock"), str(_tmp)]
import json, datetime as dt
import anvil.users
from anvil.tables import app_tables as T
from app import QuizService as S
from app.DemoData import DEMO_QUIZZES
OLD_PROJECT = PROJECT.parent / "Guild" / "anvil-quiz"  # the learning-module files live in the old project (read only)

# Every server function the pages call keeps its name (the Forms version calls the same callables).
for _n in ("start_guest end_guest get_me guest_get_me update_profile guest_update_profile get_home guest_get_home "
           "get_collection guest_get_collection get_study guest_get_study rate_card guest_rate_card finish_session "
           "guest_finish_session get_profile guest_get_profile import_quiz_json seed_demo admin_curriculum admin_part_cards "
           "admin_save_module admin_save_part admin_save_card admin_delete admin_export legal_state legal_accept").split():
    assert hasattr(S, _n) or _n.startswith("legal_"), _n

UTC = dt.datetime.now(dt.timezone.utc).date()
D = lambda n: (UTC + dt.timedelta(days=n)).isoformat()
now = dt.datetime.now(dt.timezone.utc)
u1 = T.users.add_row(email='ana.smith@example.com', signed_up=now)
u2 = T.users.add_row(email='bob@example.com', signed_up=now)
anvil.users.CURRENT[0] = u1
assert S.get_me(D(0))['is_admin']
print(S.seed_demo()['message'])
DEMO = json.loads(json.dumps(DEMO_QUIZZES))
NQ = sum(len(q['questions']) for q in DEMO); N1 = len(DEMO[0]['questions'])
NC1 = sum(len(q['questions']) for q in DEMO if q.get('collection') == DEMO[0]['collection'])
assert len(T.quizzes.rows) == len(DEMO) and len(T.questions.rows) == NQ

home = S.get_home(D(0))
st = home['stats']
assert st['total_cards'] == NQ and st['learned'] == 0 and st['due'] == 0, st
assert home['continue']['kind'] == 'quiz' and not home['continue']['started'], home['continue']
col = home['collections'][0]; assert col['card_count'] == NC1 and col['new'] == NC1, col
qid = S.get_collection(col['id'], D(0))['quizzes'][0]['id']

study = S.get_study(qid, 'due', D(0))
cards = study['cards']; assert len(cards) == N1 and all(c['is_new'] for c in cards) and cards[0]['answer'], study['counts']
# session: 3 got it, 2 still learning, then those 2 again -> got it
ratings = []
for i, c in enumerate(cards):
    knew = i < 3
    r = S.rate_card(c['id'], knew, D(0)); ratings.append({'question_id': c['id'], 'knew': knew})
    assert r['box'] == (1 if knew else 0) and r['due'] == (D(1) if knew else D(0)), r
mid = S.get_study(qid, 'due', D(0))
assert len(mid['cards']) == N1 - 3 and not mid['cards'][0]['is_new'], 'two still-learning cards stay due'
for c in cards[3:]:
    S.rate_card(c['id'], True, D(0)); ratings.append({'question_id': c['id'], 'knew': True})
res = S.finish_session(qid, ratings, D(0))
print('session1', {k: v for k, v in res.items() if k != 'me'})
assert res['xp_gained'] == 2 * (N1 + N1 - 3) + 3 * N1 and res['streak'] == 1 and res['next_due'] == D(1)
c = S.get_collection(col['id'], D(0))['quizzes'][0]
assert (c['learned'], c['due'], c['new']) == (N1, 0, 0), c
assert S.get_study(qid, 'due', D(0))['cards'] == [] and len(S.get_study(qid, 'all', D(0))['cards']) == N1

# next day: all 5 due in daily review (mixed), box 1 -> 2 => due in 3 days
home = S.get_home(D(1))
assert home['continue']['kind'] == 'review' and home['stats']['due'] == N1, home['continue']
rev = S.get_study(None, 'due', D(1))
assert len(rev['cards']) == N1 and rev['cards'][0]['quiz_title'] == DEMO[0]['title'] and rev['quiz']['title'] == 'Daily review'
r = S.rate_card(rev['cards'][0]['id'], True, D(1)); assert r['box'] == 2 and r['due'] == D(4), r
r = S.rate_card(rev['cards'][1]['id'], False, D(1)); assert r['box'] == 0 and r['due'] == D(1), r
res = S.finish_session(None, [{'question_id': rev['cards'][0]['id'], 'knew': True}, {'question_id': rev['cards'][1]['id'], 'knew': False}], D(1))
assert res['streak'] == 2, res
st_row = T.card_state.get(user=u1, question=T.questions.get_by_id(rev['cards'][1]['id']))
assert st_row['lapses'] >= 1 and st_row['reviews'] in (2, 3), (st_row['lapses'], st_row['reviews'])
assert S.finish_session(qid, [], D(1))['xp_gained'] == 0

p = S.get_profile(D(1))
print('profile', p['stats'], p['progress'][0], p['history'][0])
assert p['stats']['sessions'] == 2 and p['stats']['reviews'] == N1 + (N1 - 3) + 2 and any(h['title'] == 'Daily review' for h in p['history'])

# re-import keeps progress for unchanged cards, drops removed ones
demo = json.loads(json.dumps(DEMO_QUIZZES))
first = demo[0]; first['questions'] = first['questions'][:4] + [{'question': 'Brand new?', 'answer': 'Yes'}]
first['questions'][0]['answer'] = 'Edited answer'
print(S.import_quiz_json(json.dumps(first)))
c = S.get_collection(col['id'], D(1))['quizzes'][0]
assert c['card_count'] == 5 and c['new'] == 1 and len([s for s in T.card_state.rows if s['quiz'].get_id() == qid]) == 4, c
assert any(q['answer'] == 'Edited answer' for q in T.questions.rows)

# Quizbook multiple-choice file -> flashcards
_qb = PROJECT.parent / 'quizbook' / 'Quizbook Data' / '01-Canadian-Army-at-a-Glance' / 'quizzes' / '01.json'
if _qb.exists():
    print(S.import_quiz_json(_qb.read_text(encoding='utf-8')))
print(S.import_quiz_json(json.dumps({'title': 'x', 'questions': [{'question': 'no answer'}]})))
for f in (S.get_home(D(1)), S.get_profile(D(1)), S.get_study(None, 'due', D(1)), S.get_collection(col['id'], D(1))): json.dumps(f)
anvil.users.CURRENT[0] = u2
h = S.get_home(D(0)); assert h['stats']['learned'] == 0 and h['stats']['due'] == 0

# Guest mode: same flow, but nothing reaches the data tables; progress lives in anvil.server.session.
import anvil.server
anvil.users.CURRENT[0] = None
counts_before = {t: len(getattr(T, t).rows) for t in ('users', 'card_state', 'sessions')}
try:
    S.guest_get_home(D(0)); raise AssertionError('guest calls need start_guest first')
except anvil.users.AuthenticationFailed:
    pass
g = S.start_guest(D(0)); assert g['guest'] and g['display_name'] == 'Guest' and g['xp'] == 0 and not g['is_admin'], g
assert S.get_me.__name__ == 'get_me'  # signed-in endpoints are unchanged
gh = S.guest_get_home(D(0)); assert gh['stats']['learned'] == 0 and gh['me']['guest'] and gh['recent'] == []
gcol = gh['collections'][0]
gq = S.guest_get_collection(gcol['id'], D(0))['quizzes'][0]['id']
gcards = S.guest_get_study(gq, 'due', D(0))['cards']
gr = []
for i, c in enumerate(gcards):
    r = S.guest_rate_card(c['id'], i > 0, D(0)); gr.append({'question_id': c['id'], 'knew': i > 0})
    assert r['box'] == (1 if i else 0), r
res = S.guest_finish_session(gq, gr, D(0)); assert res['xp_gained'] > 0 and res['streak'] == 1 and res['me']['guest'], res
gc = S.guest_get_collection(gcol['id'], D(0))['quizzes'][0]
assert gc['learned'] == len(gcards) - 1 and gc['due'] == 1, gc
mod = S.guest_get_study(None, 'due', D(0), gcol['id']); assert mod['quiz']['module_id'] == gcol['id']
S.guest_finish_session(None, [{'question_id': gcards[0]['id'], 'knew': True}], D(0), gcol['id'])
rev = S.guest_get_study(None, 'due', D(1)); assert len(rev['cards']) == len(gcards) and rev['cards'][0]['quiz_title'], rev['counts']
gp = S.guest_get_profile(D(1))
assert gp['stats']['sessions'] == 2 and gp['stats']['reviews'] == len(gcards) and gp['history'][0]['title'] == 'Whole module', gp['history']
assert S.guest_update_profile(display_name='Visitor')['me']['display_name'] == 'Visitor'
assert S.start_guest(D(1))['display_name'] == 'Visitor'  # resuming in the same session keeps progress
json.dumps(gp); json.dumps(S.guest_get_home(D(1)))
assert {t: len(getattr(T, t).rows) for t in counts_before} == counts_before, 'guest wrote to the tables'
try:
    S.import_quiz_json('{}'); raise AssertionError('guest is not an admin')
except anvil.users.AuthenticationFailed:
    pass
S.end_guest()
try:
    S.guest_get_profile(D(1)); raise AssertionError('ended guest session')
except anvil.users.AuthenticationFailed:
    pass
assert S.start_guest(D(1))['xp'] == 0  # a new guest starts fresh
S.end_guest()

# Manage curriculum (admin): preview, edit, add, delete, hide, download.
anvil.users.CURRENT[0] = u2
for call in (lambda: S.admin_curriculum(), lambda: S.admin_delete('module', col['id']), lambda: S.admin_export(None)):
    try:
        call(); raise AssertionError('non-admins cannot manage the curriculum')
    except PermissionError:
        pass
anvil.users.CURRENT[0] = u1
cur = S.admin_curriculum(); json.dumps(cur)
m1 = next(m for m in cur['modules'] if m['id'] == col['id'])
p1 = next(p for p in m1['parts'] if p['id'] == qid)
assert p1['card_count'] == 5 and m1['card_count'] == sum(p['card_count'] for p in m1['parts']), m1
pc = S.admin_part_cards(qid); assert pc['ok'] and len(pc['cards']) == 5 and pc['cards'][0]['question'], pc
assert not S.admin_part_cards('nope')['ok']
c0 = pc['cards'][0]
had = T.card_state.get(user=u1, question=T.questions.get_by_id(c0['id']))
assert had is not None
r = S.admin_save_card(qid, c0['id'], dict(c0, answer='Fixed answer', concept='Edited'))
assert r['ok'] and r['card']['answer'] == 'Fixed answer' and r['card_count'] == 5, r
assert T.card_state.get(user=u1, question=T.questions.get_by_id(c0['id'])) is had, 'editing keeps progress'
assert not S.admin_save_card(qid, c0['id'], dict(c0, question=pc['cards'][1]['question']))['ok'], 'duplicate question'
assert not S.admin_save_card(qid, c0['id'], dict(c0, answer='  '))['ok'], 'answer required'
r = S.admin_save_card(qid, None, {'question': 'Added by admin?', 'answer': 'Yes'})
assert r['ok'] and r['card_count'] == 6 and r['card']['number'] > pc['cards'][-1]['number'], r
new_ids = [c['id'] for c in S.get_study(qid, 'all', D(1))['cards'] if c['is_new']]
assert r['card']['id'] in new_ids
r = S.admin_save_part(qid, {'title': 'Renamed part', 'description': 'd', 'number': '7', 'source': 'https://x.ca', 'published': True})
assert r['ok'] and r['part']['title'] == 'Renamed part' and r['part']['number'] == 7, r
assert not S.admin_save_part(qid, {'title': '', 'number': 1})['ok'] and not S.admin_save_part(qid, {'title': 'x', 'number': 'two'})['ok']
other = next(m for m in cur['modules'] if m['id'] != col['id'])
assert not S.admin_save_module(col['id'], dict(m1, title=other['title']))['ok'], 'module titles stay unique'
assert not S.admin_save_module(col['id'], dict(m1, color='red'))['ok']
r = S.admin_save_module(col['id'], dict(m1, number=12, published=False)); assert r['ok'] and r['module']['number'] == 12, r
assert col['id'] not in [c['id'] for c in S.get_home(D(1))['collections']], 'hidden module is gone for learners'
assert any(m['id'] == col['id'] for m in S.admin_curriculum()['modules']), 'but still listed for admins'
S.admin_save_module(col['id'], dict(m1, published=True))
assert col['id'] in [c['id'] for c in S.get_home(D(1))['collections']]

ex = S.admin_export(col['id']); json.dumps(ex)
assert ex['ok'] and ex['filename'].endswith('.json') and len(ex['items']) == len(m1['parts']), ex['filename']
assert ex['items'][-1]['title'] == 'Renamed part' and ex['items'][-1]['position'] == 7, 'renumbered part sorts last'
assert any(q['answer'] == 'Fixed answer' for q in ex['items'][-1]['questions']) and ex['items'][0]['collection_position'] == 1
assert S.import_quiz_json(json.dumps(ex['items']))['ok'] and len(S.admin_part_cards(qid)['cards']) == 6, 're-importing the download changes nothing'
assert S.admin_export(None)['ok'] and len(S.admin_export(None)['items']) == len(T.quizzes.rows)

# A guest studying a card that an admin then deletes
S.start_guest(D(0))
S.guest_rate_card(c0['id'], False, D(0))
n_states = len(T.card_state.rows)
r = S.admin_delete('card', c0['id']); assert r['ok'] and r['card_count'] == 5, r
assert len(T.card_state.rows) < n_states and T.questions.get_by_id(c0['id']) is None
assert c0['id'] not in [c['id'] for c in S.guest_get_study(None, 'due', D(0))['cards']]
S.end_guest()
assert not S.admin_delete('card', c0['id'])['ok'] and not S.admin_delete('thing', 'x')['ok']

r = S.admin_delete('part', qid); assert r['ok'], r
assert T.quizzes.get_by_id(qid) is None and not any(s['quiz'] is not None and s['quiz'].get_id() == qid for s in T.card_state.rows)
p = S.get_profile(D(1)); json.dumps(p)
assert any(h['title'] == 'Renamed part' for h in p['history']), 'history keeps the deleted part by name'
r = S.admin_delete('module', col['id']); assert r['ok'], r
assert T.collections.get_by_id(col['id']) is None and col['id'] not in [m['id'] for m in S.admin_curriculum()['modules']]
for f in (S.get_home(D(1)), S.get_profile(D(1)), S.get_study(None, 'due', D(1))): json.dumps(f)
print('ALL OK')

# Every module file in modules/ must import cleanly
import glob
anvil.users.CURRENT[0] = u1
for f in sorted((OLD_PROJECT / "modules").glob("*.json")):
    for item in json.loads(f.read_text(encoding="utf-8")):
        r = S.import_quiz_json(json.dumps(item))
        assert r["ok"], (f.name, r)
print("modules import OK:", len(T.collections.rows), "collections,", len(T.questions.rows), "cards in mock")
