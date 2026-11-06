/* Phone-width check (run at 390 px wide by tools/ui_test.py, with tools/ui/_lib.js in front): every page loads
   without errors and without sideways scrolling, signed out and signed in (as the admin, so Manage curriculum is
   checked too), plus a study card and its answer. Resolves to {ok, log}. */
(async function () {
  const log = [], bad = [];
  const { sleep, until, $, $$, vis, page } = GL;
  function measure(label) {
    const w = document.documentElement.scrollWidth, vw = screen.width;
    const wide = $$('body *').filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.right > vw + 1; })
      .slice(0, 3).map((e) => e.tagName.toLowerCase() + '.' + String(e.className).split(' ').slice(0, 2).join('.'));
    if (w > vw + 1) bad.push(label + ' scrolls sideways (' + w + ' > ' + vw + ') ' + wide.join(' '));
    log.push((w > vw + 1 ? 'WIDE ' : 'ok   ') + label + ' (' + w + ')');
  }
  async function check(hash, ready) { await page(hash, ready); await sleep(400); measure(hash); }
  try {
    await GL.signOut();
    for (const h of ['#auth', '#auth/signup', '#auth/reset']) await check(h, () => $('.au-card'));
    await GL.ensureContent();
    const pages = await GL.memberPages(true);
    for (const h of pages) await check(h);
    // a study card, question and answer
    await page(pages[2], () => vis($('.qb-study .intro-card')));
    $$('.qb-study button').filter(vis).find((b) => /^Start/.test(b.textContent)).click();
    await until(() => vis($('.qb-study .reveal')), 'card');
    await sleep(300); measure('study card');
    $$('.qb-study button').filter(vis).find((b) => /Show answer/.test(b.textContent)).click();
    await until(() => vis($('.qb-study .back')), 'answer');
    await sleep(300); measure('study answer');
    $('.qb-header .look').click();
    await until(() => vis($('.qb-dict')), 'lookup');
    measure('lookup panel');
    log.push(bad.length ? 'PROBLEMS: ' + bad.join(' | ') : 'PASSED');
    return { ok: !bad.length, log: log };
  } catch (e) {
    log.push(String(e && e.message || e));
    return { ok: false, log: log };
  }
})();
