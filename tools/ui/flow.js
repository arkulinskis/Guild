/* The main journeys, run inside the real app (Anvil App Server) by tools/ui_test.py through tools/live/drive.mjs,
   with tools/ui/_lib.js (window.GL) in front. Resolves to {ok, log}. Keep log lines ASCII (the Windows console). */
(async function () {
  const log = [], t0 = Date.now();
  const say = (m) => log.push(((Date.now() - t0) / 1000).toFixed(1) + 's ' + m);
  const { sleep, until, $, $$, vis, type, page } = GL;
  const ok = (cond, msg) => { if (!cond) throw new Error('FAILED: ' + msg); say('ok   ' + msg); };
  const text = (s) => (($(s) || {}).textContent || '').replace(/\s+/g, ' ').trim();
  const key = (k) => document.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true }));
  const button = (re, root) => $$((root || '') + ' button').filter(vis).find((b) => re.test(b.textContent));

  try {
    // ---- the front page (visitors): hero, form, Watch section, the four footer links, no header
    await GL.signOut();
    await page('#auth', () => $('.qb-auth'));
    ok(/Learn about the Canadian Armed Forces/.test(text('.qb-auth h1')), 'front page: the hero heading');
    ok(/unofficial/i.test(text('.qb-auth .side')) && /civilian/i.test(text('.qb-auth .civ')), 'front page: says it is unofficial, made by a civilian');
    ok($('#watch .ytf-cover') && !$('#watch iframe'), 'front page: Watch section (nothing loads from YouTube before the click)');
    ok(!vis($('.qb-header')), 'front page: no top bar while signed out (as before)');
    const foot = $('.qb-footer');
    ok(foot.querySelector('[data-prepsto-open][href*="prepsto.com/#f/jfr2n3p"]') && foot.querySelector('[data-lk-open]') &&
       foot.querySelector('a[href="https://arkvital.com"]') && foot.querySelector('a[href="https://addanapp.com"]'), 'footer: Submit feedback, Privacy & Terms, Contact developer, Parent company');
    ok(/independent study project by a civilian/.test(foot.textContent), 'footer: the civilian disclaimer');
    $('#watch .ytf-cover').click();
    await until(() => $('#watch iframe[src*="youtube-nocookie.com/embed/DHVV7YRVxX0"]'), 'the video player');
    ok(true, 'Watch: pressing play loads the privacy-enhanced player');

    // ---- the local admin and the sample cards (first account = admin)
    await GL.ensureContent();
    ok($$('.qb-home .mod').length >= 1, 'learning path has modules');
    await GL.signOut();

    // ---- members-only address sends visitors to sign in, then on to it
    await page('#profile', () => true).catch(() => {});
    await until(() => window.UI_READY && $('.au-card'), 'redirected to sign in');
    ok(location.hash === '#profile' && $('.au-card'), 'a members-only address asks visitors to sign in');
    $$('.au-card .ui-seg button').find((b) => /Create account/.test(b.textContent)).click();
    await until(() => $$('.au-card input').filter(vis).length >= 3, 'sign-up form');
    const ins = $$('.au-card input[type=text], .au-card input[type=email], .au-card input[type=password]').filter(vis);
    type(ins[0], 'Flow Tester'); type(ins[1], 'flow' + Date.now() + '@example.com'); type(ins[2], 'Hb-' + Math.random().toString(36).slice(2) + '-Kq7');
    $$('.anvil-role-btn-block button').find((b) => /Create account/.test(b.textContent)).click();
    await sleep(1200);
    ok($('.au-card') && !vis($('.qb-header')), 'sign-up: the Privacy & Terms tick box is required');
    const tick = $('.au-card input[type=checkbox]'); if (tick && !tick.checked) tick.click();
    $$('.anvil-role-btn-block button').find((b) => /Create account/.test(b.textContent)).click();
    await until(() => location.hash === '#profile' && window.UI_READY && $('.qb-prof'), 'back on the page they wanted', 40000);
    ok(/Flow Tester/.test(text('.qb-prof .anvil-role-page-title')), 'sign-up: signed in, sent on to their profile, with the name they typed');
    ok(vis($('.qb-header')) && /FT/.test(text('.qb-header .avatar')) && /0 XP/.test(text('.qb-header .xp')), 'header: avatar initials and XP');

    // ---- home: greeting, stats, continue card, path, filters
    await page('#home', () => $$('.qb-home .mod').length);
    ok(/Good (morning|afternoon|evening), Flow/.test(text('.qb-home .anvil-role-page-title')), 'home: greeting with the first name');
    ok($$('.qb-home .stat').length === 4, 'home: four stat tiles');
    ok(vis($('.qb-home a.continue')) && /^#quiz\//.test($('.qb-home a.continue').getAttribute('href')), 'home: "Start learning" card links to a part');
    ok($$('.qb-home .seg').length === $$('.qb-home .mod').length, 'home: one segment per module in the path bar');
    button(/^Complete$/, '.qb-home').click(); await sleep(400);
    ok(!$$('.qb-home .mod').filter(vis).length && $$('.qb-home .ui-empty').find(vis), 'home: the Complete filter (nothing yet)');
    button(/^All$/, '.qb-home').click(); await sleep(400);
    ok($$('.qb-home .mod').filter(vis).length >= 1, 'home: back to All');

    // ---- a module, then a part
    const colHref = $('.qb-home .mod').getAttribute('href');
    $('.qb-home .mod').click();
    await until(() => location.hash === colHref && window.UI_READY && $$('.qb-col .item').length, 'module page');
    ok(/^#collection\//.test(colHref) && text('.qb-col .anvil-role-page-title').length > 3, 'module page: #collection/<id> with its title');
    ok(/Module \d+ of \d+/.test(text('.qb-col .crumbs')) && button(/Study this module/), 'module page: its number, and "Study this module"');
    const quizHref = $('.qb-col .item').getAttribute('href');
    $('.qb-col .item').click();
    await until(() => location.hash === quizHref && window.UI_READY && vis($('.qb-study .intro-card')), 'study intro');
    ok(/^#quiz\//.test(quizHref) && /Start . \d+ cards?/.test((button(/^Start/) || {}).textContent || ''), 'study: intro with Start');
    ok($$('.qb-study .how li').length === 3, 'study: the three steps (recall, reveal, be honest)');

    // ---- a session: Space reveals, Got it, key 1 = still learning, Finish
    button(/^Start/).click();
    await until(() => vis($('.qb-study .flash')) && text('.qb-study .anvil-role-qtext').length, 'first card');
    ok(!vis($('.qb-study .back')) && !$$('.qb-study input[type=radio]').length, 'card: question only, no multiple choice');
    key(' ');
    await until(() => vis($('.qb-study .back')) && text('.qb-study .anvil-role-answer').length, 'answer shown');
    ok(/see it again in 1 day/.test(text('.qb-study .got')), 'card: Space shows the answer; "Got it" says when it comes back');
    $('.qb-study .got').click();
    await until(() => vis($('.qb-study .reveal')), 'next card');
    button(/Show answer/).click();
    await until(() => vis($('.qb-study .back')), 'second answer');
    key('1'); await sleep(300);
    ok(/Finish/.test(text('.qb-study .qhead')), 'card: key 1 = still learning; the button now says Finish');
    button(/Finish/).click();
    await until(() => vis($('.qb-study .summary-card')), 'summary');
    ok(text('.qb-study .big') === '2', 'summary: 2 cards reviewed');
    await until(() => /\+\d+ XP/.test(text('.qb-study .summary-card')), 'session saved', 40000);
    ok(/1 still learning/.test(text('.qb-study .summary-card')) && button(/Go again with the 1 card/), 'summary: XP, one still learning, "Go again"');
    ok(/[1-9]\d* XP/.test(text('.qb-header .xp')), 'header: XP went up');
    ok($$('.qb-study .still-card').length === 1, 'summary: the card still in rotation');

    // ---- the daily review has the still-learning card
    await page('#review', () => vis($('.qb-study .intro-card')));
    ok(/Daily review/.test(text('.qb-study .anvil-role-page-title')) && /Start . 1 card/.test((button(/^Start/) || {}).textContent || ''), 'daily review: the card still being learned is due');

    // ---- Lookup in the header
    $('.qb-header .look').click();
    await until(() => vis($('.qb-dict')), 'lookup panel');
    type($('.qb-dict input'), 'CAF');
    await until(() => $$('.qb-dict .hit').length, 'lookup hits');
    ok(/Canadian Armed Forces/.test(text('.qb-dict')) && /google\.com\/search\?q=CAF%20CAF/.test($('.qb-dict .google').getAttribute('href')), 'lookup: finds CAF, offers a web search');
    key('Escape'); await sleep(300);
    ok(!vis($('.qb-dict')), 'lookup: Escape closes it');

    // ---- profile: rename, colour, theme
    await page('#profile', () => $('.qb-prof'));
    const nameBox = $$('.qb-prof input').find((i) => i.value === 'Flow Tester');
    type(nameBox, 'Flow Renamed');
    $$('.qb-prof .swatch')[2].click(); await sleep(300);
    ok($$('.qb-prof .swatch')[2].getAttribute('aria-pressed') === 'true', 'profile: a colour swatch says it is chosen');
    button(/Save changes/).click();
    await until(() => /Flow Renamed/.test(text('.qb-prof .anvil-role-page-title')), 'saved');
    ok(/Flow Renamed/.test(text('.qb-menu .anvil-role-menu-name')), 'profile: saved, the header menu has the new name');
    button(/^Dark$/, '.qb-prof').click(); await sleep(200);
    ok(document.documentElement.getAttribute('data-theme') === 'dark', 'profile: Dark theme');
    button(/^Auto$/, '.qb-prof').click(); await sleep(200);
    ok(!document.documentElement.getAttribute('data-theme'), 'profile: back to Auto');
    ok(!$$('.qb-prof section').filter(vis).find((s) => /Import learning modules/.test(s.textContent)), 'profile: learners do not see the admin tools');

    // ---- learners can't open Manage curriculum
    await page('#curriculum', () => true).catch(() => {});
    await until(() => window.UI_READY && $('.qb-home'), 'sent home');
    ok($('.qb-home') && !$('.qb-cur'), 'Manage curriculum is for admins only');

    // ---- guest mode
    await GL.signOut();
    button(/Try it without signing in/, '.au-card').click();
    await until(() => location.hash === '#home' && window.UI_READY && $$('.qb-home .mod').length, 'guest home', 40000);
    ok(vis($('.qb-header .guest')) && /Guest mode/.test(text('.qb-header .guest')), 'guest: the guest strip under the header');
    await page(quizHref, () => vis($('.qb-study .intro-card')));
    button(/^Start/).click();
    await until(() => vis($('.qb-study .reveal')), 'guest card');
    key(' '); await until(() => vis($('.qb-study .back')), 'guest answer');
    key('2'); await sleep(300);
    button(/Finish|Stop/).click();
    await until(() => /\+\d+ XP/.test(text('.qb-study .summary-card')), 'guest session saved', 40000);
    ok(true, 'guest: studies a card, the session is saved for this tab');
    $$('.qb-header .guest button')[0].click();
    await until(() => location.hash.startsWith('#auth') && window.UI_READY, 'guest left');
    ok(!vis($('.qb-header')), 'guest: "Sign in or create an account" ends guest mode');

    // ---- unknown addresses go to the front page
    await page('#nowhere', () => true).catch(() => {});
    await until(() => window.UI_READY && $('.qb-auth'), 'front page');
    ok(true, 'an unknown address shows the front page');
    say('PASSED');
    return { ok: true, log: log };
  } catch (e) {
    say(String(e && e.message || e));
    return { ok: false, log: log };
  }
})();
