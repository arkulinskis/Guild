/* Shared helpers for the CAF Guide UI scripts. tools/ui_test.py puts this in front of every script (flow.js, phone.js,
   admin.js, a11y.js, design.js, seed.js), so they can all use window.GL.

   The local database starts empty. The very first account becomes the admin (QuizService._ensure_defaults), so every
   script first calls GL.ensureContent(): it signs in (or signs up) the fixed local admin and, when the learning path is
   empty, loads the 27 sample cards from Profile. Then each script carries on with its own accounts. */
window.GL = (function () {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function until(fn, what, ms) {
    const end = Date.now() + (ms || 30000);
    while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(150); }
    throw new Error('timed out waiting for: ' + what);
  }
  const $ = (s) => document.querySelector(s), $$ = (s) => Array.from(document.querySelectorAll(s));
  const vis = (e) => !!(e && e.getClientRects().length);
  function type(input, value) {
    input.focus(); input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));
  }
  async function page(hash, ready, ms) {
    if (location.hash !== hash) window.UI_READY = false;  // the old page stays until the router runs
    location.hash = hash;
    await until(() => window.UI_READY && location.hash === hash && (!ready || ready()), hash, ms || 40000);
    await sleep(300);
  }
  const ADMIN = { name: 'Local Admin', email: 'admin@caf-guide.test', password: 'Gd-local-admin-Kq7-2026x' };
  const inputs = () => $$('.au-card input[type=text], .au-card input[type=email], .au-card input[type=password]').filter(vis);
  const btn = (re) => $$('.au-card .anvil-role-btn-block button').filter(vis).find((b) => re.test(b.textContent));

  async function signOut() {
    if (!$('.qb-header') || !vis($('.qb-header'))) return;
    $('.me-btn').click();
    await until(() => vis($('.qb-menu')), 'account menu');
    $$('.qb-menu button').find((b) => /Sign out|Exit guest mode/.test(b.textContent)).click();
    await until(() => location.hash.startsWith('#auth') && window.UI_READY && inputs().length >= 2, 'signed out', 30000);
    await sleep(300);
  }
  async function signIn(email, password) {
    await signOut();
    await page('#auth', () => inputs().length >= 2);
    type(inputs()[0], email); type(inputs()[1], password);
    btn(/^\s*Sign in\s*$/).click();
    await until(() => (location.hash === '#home' && window.UI_READY) || vis($('.au-card .anvil-role-msg-error')), 'sign in', 40000);
    return location.hash === '#home';
  }
  async function signUp(name, email, password) {
    await signOut();
    await page('#auth/signup', () => inputs().length >= 3);
    const i = inputs(); type(i[0], name); type(i[1], email); type(i[2], password);
    const tick = $('.au-card input[type=checkbox]'); if (tick && !tick.checked) tick.click();
    btn(/Create account/).click();
    await until(() => !location.hash.startsWith('#auth') && window.UI_READY, 'signed up', 40000);
    await sleep(300);
  }
  async function newLearner(name) {
    await signUp(name, name.toLowerCase().replace(/\W+/g, '') + Date.now() + '@example.com', 'Hb-' + Math.random().toString(36).slice(2) + '-Kq7');
  }
  async function asAdmin() {
    if (!(await signIn(ADMIN.email, ADMIN.password))) await signUp(ADMIN.name, ADMIN.email, ADMIN.password);
    await until(() => location.hash === '#home' && window.UI_READY, 'admin home', 40000);
  }
  async function ensureContent() {
    await asAdmin();
    await page('#home', () => $('.qb-home'));
    if (!$$('.qb-home .mod').length) {
      await page('#profile', () => $('.qb-prof'));
      const sum = $$('.qb-prof details summary').find(vis); if (sum) sum.click();
      await sleep(200);
      $$('button').find((b) => /Load 27 sample cards/.test(b.textContent)).click();
      await until(() => /Imported|updated|Loaded|sample/i.test(($('.qb-prof .anvil-role-msg-note') || {}).textContent || ''), 'sample cards loaded', 60000);
      await page('#home', () => $$('.qb-home .mod').length);
    }
  }
  /* The member pages worth checking, with real ids: home, a module, a part's study intro, the daily review, profile. */
  async function memberPages(admin) {
    await page('#home', () => $$('.qb-home .mod').length);
    const col = $('.qb-home .mod').getAttribute('href');
    await page(col, () => $$('.qb-col .item').length);
    const quiz = $('.qb-col .item').getAttribute('href');
    const list = ['#home', col, quiz, col.replace('#collection/', '#module/'), '#review', '#profile'];
    if (admin) list.push('#curriculum');
    return list;
  }
  return { sleep, until, $, $$, vis, type, page, signIn, signUp, signOut, newLearner, asAdmin, ensureContent, memberPages, ADMIN };
})();
