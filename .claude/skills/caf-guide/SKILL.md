---
name: caf-guide
description: Context, workflow and recipes for CAF Guide (folder Guild-forms), the user's live Anvil flashcard app about the Canadian Armed Forces at caf-guide.anvil.app, built as native Anvil Forms (Python + HTML templates, a layout, RepeatingPanels). Load this before any feature request, bug fix, restyle, content change or deploy for that app ("add a feature", "change the study page", "make more cards", "push it live").
---

# CAF Guide: working on the app

**What it is:** CAF Guide is an active-recall flashcard app about the Canadian Armed Forces.
- Each card shows a question. The learner clicks to reveal the answer, then rates it **Still learning** or **Got it**.
- Leitner boxes schedule the cards, and there is a daily review of due cards.
- The content is a numbered learning path of 29 modules (about 2,000 cards). Header button **Lookup** = acronym
  dictionary (`theme/assets/acronyms.js`) with a Google search fallback.

**Where it lives:**
- Folder `C:\Users\arkvi\Documents\CLAUDE\Guild-forms\` = the git clone of **github.com/arkulinskis/Guild**. "git"
  layout: the folder *is* the Anvil app. Anvil pulls `master`; pushing master is the deploy. Live: https://caf-guide.anvil.app/
- Native Anvil Forms since 2026-11-09 (branch `forms`, merged at the user's request). The old JavaScript source
  `Guild\anvil-quiz` is retired (its deploy.py refuses to run) but still holds the **card content pipeline**
  (`cards_src/`, `materials/`, `tools/build_modules.py`, `modules/*.json`): see *Content* below.
- **APP_MAP.md** is the code map: read it first, then open only the files it points to.

**What the user wants:**
- No multiple choice, ever. Active recall is the point.
- The site must say clearly that it is an unofficial project by a civilian (footer of `Layouts/Shell`). Keep that wording whenever you change text.
- Claude deploys; never ask the user to paste code into Anvil.
- They're happy with the navy/red/olive look. Mobile-first (390 px), light and dark.

## Workflow for any change

**The app has real users (since Oct 2026). Never push a feature straight to `master`.** Push it to a branch
(`git push origin HEAD:<name>`), let the user test it, and merge to master only when they say so.

1. `git pull --ff-only` (Anvil commits "Edited ..." when the user changes something in the IDE; read those commits).
2. Edit a page's template and Python side by side (`client_code/Pages/X/form_template.html` + `__init__.py`).
3. `python tools/check.py` (no -I) -> **ALL CHECKS PASSED** (Anvil validator, JS syntax, asset hashes, server tests, design check).
4. `python -I tools/ui_test.py` (Docker Desktop running) -> **ALL UI TESTS PASSED** (flow, phone 390 px, admin, a11y,
   design). `--shots DIR` = screenshots of every page: Read them.
5. Commit only your files as `arkulinskis <arkulinskis@gmail.com>` ending with
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; push the branch.
   New tables/columns: tell the user to accept the **Schema Mismatch** alert ("The schema of the source code is correct");
   until they do, the app errors with `NoSuchColumnError`.

## Architecture

```
anvil.yaml            startup module; db_schema (single source of truth); head_html (SEO, legal kit, theme assets ?v=)
client_code/
  startup.py          get_me, Privacy & Terms kit, router.start()
  router.py           PAGES (who may open each page), _form (page -> Form), go/href; NAV = [] (header has Lookup + account menu)
  state.py            me(), call() (adds the guest_ prefix in guest mode; {"ok": False} -> toast), toast(), dates
  auth.py, legal.py   sign in/up/reset/Google; Privacy & Terms (from APP_MAKER/legal-kit, don't edit here)
  Layouts/Shell       header + account menu + Lookup + footer (disclaimer + the four standard links)
  Pages/              Auth, Home (learning path), Collection (= module page), Study (study session + daily review),
                      Profile, Curriculum (admin: manage modules/parts/cards; also serves #admin)
  Items/              ModuleRow, PartRow, SessionRow, HistoryRow, ProgressRow, StillCard, Cur*, Acronym, Seg, Swatch
  Dialogs/            Edit, Preview
server_code/          QuizService.py (ALL data access, scheduling, XP/streak, import, guest twins), DemoData.py,
                      legal_server.py, SchemaCheck
theme/assets/         app.css (tokens + pages), app-kit.js, acronyms.js, legal-kit.js, theme.css (spinner)
tools/                check.py, assets.py, build_icons.py, ui_test.py + ui/, testing/ (server tests + mock), live/
```

Patterns (pages, lists, dialogs, buttons, a11y, design kit) are those of
`C:\Users\arkvi\Documents\CLAUDE\APP_MAKER\template-forms\.claude\skills\__APP_KEY__\SKILL.md`: follow that guide's
"How things are done here" section.

## Product rules the code depends on

- **Server API** (`QuizService.py`): `get_me`, `update_profile`, `get_home`, `get_collection`, `get_study`,
  `rate_card(question_id, knew, today)`, `finish_session(quiz_id, ratings, today, collection_id)`, `get_profile`.
  Admin-only (`_require_admin()`, return `{ok, error}`): `import_quiz_json`, `seed_demo`, `admin_curriculum`,
  `admin_part_cards`, `admin_save_module|part|card`, `admin_delete(kind, id)`, `admin_export`. Deleting a part keeps
  its sessions with `quiz=None` and `ratings={"removed": {...}}`.
- **Guest mode** ("Try it without signing in"): `start_guest` / `end_guest` plus a `guest_<name>` twin of every
  learner call; signed-in callables keep `require_user=True`. Both call one internal `_<name>(user, ...)`; guest data
  lives in `anvil.server.session`, never in tables. A new learner function needs both versions and a guest test in
  `tools/testing/test_server.py`.
- The browser sends `today`; `_client_today` accepts it only within ±1 day of UTC.
- Scheduling: "Got it" -> `box + 1`, due after `BOX_INTERVALS = [0,1,3,7,16,35,90]` days; "Still learning" -> box 0,
  due today. Learned = box ≥ 1, mastered = box ≥ 4, module complete = all its cards learned.
- Tables: `users` (+ display_name, bio, avatar_color, is_admin, xp, streak, last_active, legal_*), `collections`
  (= modules, `position`), `quizzes` (= parts: position, card_count, source), `questions` (text, answer,
  explanation, concept), `card_state` (user × card: box, due, reviews, lapses), `sessions`.

## Content (cards)

- Edit `Guild\anvil-quiz\cards_src\NN-name.txt` (`@module` / `@part` / `## concept` / `Q:` / `A:` / `E:`), then in
  `Guild\anvil-quiz` run `python -I tools/build_modules.py` -> `modules/*.json`.
- The user uploads them at **Profile → Import learning modules** (or Curriculum). Re-importing updates cards and keeps
  progress on unchanged questions.
- Material is in `Guild\anvil-quiz\materials\`, 01–30 with **06 missing**. Questions stand alone, short answers, no crude content.

## Gotchas

- **Live test account:** `claude-test@example.com`; password in `Guild\anvil-quiz\tools\live\.test-account-password.txt`.
  Not an admin; the user's own account is the admin.
- No `gh` CLI: pushes go over HTTPS through Git Credential Manager; if it asks for sign-in, tell the user.
- Heredocs in the Bash tool mangle quotes: write files with the Write tool.
- The template guide's gotchas (local App Server lag, alert widths, headless Chrome) apply here too.

## Privacy & Terms (legal kit)

From `C:/Users/arkvi/Documents/CLAUDE/APP_MAKER/legal-kit`: change `apps/guild.json`, then there
`python -I build.py guild && python -I install.py guild`, then `python tools/assets.py` here and deploy.
Sign-up keeps the consent tick box. Consent lives in `users.legal_version`, `legal_accepted_at`, `legal_source`.
Feedback = Prepsto only ("Submit feedback").
