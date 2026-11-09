/* Manage curriculum (admins), with tools/ui/_lib.js in front: open a module and a part, preview the cards, edit a
   card, add one and delete it again, a bad module edit shows its error in the dialog, filter, download.
   Resolves to {ok, log}. */
(async function () {
  const log = [];
  const { sleep, until, $, $$, vis, type, page } = GL;
  const ok = (c, m) => { if (!c) throw new Error('FAILED: ' + m); log.push('ok   ' + m); };
  const text = (e) => ((e || {}).textContent || '').replace(/\s+/g, ' ').trim();
  const btnIn = (root, re) => Array.from((root || document).querySelectorAll('button')).filter(vis).find((b) => re.test(b.textContent));
  const dialog = () => $$('.modal-dialog, .anvil-modal-dialog').filter(vis).pop();
  async function closed() { await until(() => !dialog(), 'dialog closed'); await sleep(300); }
  try {
    await GL.ensureContent();
    ok(vis($('.qb-header .qb-menu a[href="#curriculum"]')) || $('.qb-header a[href="#curriculum"]'), 'admin: the account menu has Manage curriculum');
    await page('#profile', () => $('.qb-prof'));
    ok($$('.qb-prof section').filter(vis).some((s) => /Import learning modules/.test(s.textContent)) && $$('.qb-prof .badge').some((b) => /admin/.test(b.textContent)), 'profile: admin badge and the import tools');
    await page('#curriculum', () => $$('.qb-cur .mod').length);
    ok(/\d+ modules? · \d+ parts? · \d+ cards?/.test(text($('.qb-cur .anvil-role-muted-small'))), 'curriculum: totals');

    // open the first module, then its first part
    $('.qb-cur .mod .tog').click();
    await until(() => $$('.qb-cur .part').length, 'parts');
    ok($('.qb-cur .mod .tog').getAttribute('aria-expanded') === 'true', 'module opens (aria-expanded)');
    $('.qb-cur .part .tog').click();
    await until(() => $$('.qb-cur .crd').length, 'cards', 30000);
    const nCards = $$('.qb-cur .crd').length;
    ok(nCards >= 1 && text($('.qb-cur .crd .q')).length, 'part opens with its cards (' + nCards + ')');

    // preview
    btnIn($('.qb-cur .part'), /^Preview$/).click();
    await until(() => dialog() && $('.cur-pv'), 'preview');
    ok(!vis($('.cur-pv .aa')), 'preview: question first');
    btnIn(dialog(), /Show answer/).click(); await sleep(300);
    ok(vis($('.cur-pv .aa')), 'preview: Show answer');
    btnIn(dialog(), /^Close$/).click(); await closed();

    // edit a card
    btnIn($('.qb-cur .crd'), /^Edit$/).click();
    await until(() => dialog() && $('.cur-edit'), 'edit card');
    const areas = $$('.cur-edit textarea').filter(vis);
    type(areas[1], 'Edited by the admin test');
    btnIn(dialog(), /Save card/).click(); await closed();
    await until(() => /Edited by the admin test/.test(text($('.qb-cur .crd .a'))), 'card updated');
    ok(true, 'edit card: saved and shown');

    // add a card, then delete it
    btnIn($('.qb-cur .part'), /Add a card/).click();
    await until(() => dialog() && $('.cur-edit'), 'new card');
    const a2 = $$('.cur-edit textarea').filter(vis);
    type(a2[0], 'Admin test question ' + Date.now() + '?'); type(a2[1], 'Yes');
    btnIn(dialog(), /Add card/).click(); await closed();
    await until(() => $$('.qb-cur .crd').length === nCards + 1, 'card added');
    ok(true, 'add card: it appears at the end');
    const last = $$('.qb-cur .crd').pop();
    btnIn(last, /^Delete$/).click();
    await until(() => dialog() && btnIn(dialog(), /^Delete$/), 'confirm');
    ok(/Delete this card/.test(text(dialog())), 'delete: asks first');
    btnIn(dialog(), /^Delete$/).click(); await closed();
    await until(() => $$('.qb-cur .crd').length === nCards, 'card deleted');
    ok(true, 'delete card: gone');

    // a module edit the server refuses shows inside the dialog
    btnIn($('.qb-cur .mod'), /^Edit$/).click();
    await until(() => dialog() && $('.cur-edit'), 'edit module');
    const title = $$('.cur-edit input').filter(vis).find((i) => i.type === 'text' && i.value.length > 3);
    type(title, '');
    btnIn(dialog(), /Save module/).click();
    await until(() => vis($('.cur-edit .anvil-role-msg-error')), 'error shown');
    ok(/empty/.test(text($('.cur-edit .anvil-role-msg-error'))), 'edit module: "The module title can\'t be empty" in the dialog');
    btnIn(dialog(), /^Cancel$/).click(); await closed();

    // filter and download
    type($('.qb-cur .tools input'), 'zzzz-nothing'); await sleep(500);
    ok(!$$('.qb-cur .mod').length && /No module matches/.test(text($('.qb-cur .ui-empty'))), 'filter: nothing matches');
    type($('.qb-cur .tools input'), ''); await sleep(500);
    btnIn($('.qb-cur .head'), /Download all/).click();
    await until(() => /Downloaded .*\.json/.test(text(document.body)), 'download toast', 30000);
    ok(true, 'download: all modules as JSON');
    log.push('PASSED');
    return { ok: true, log: log };
  } catch (e) {
    log.push(String(e && e.message || e));
    return { ok: false, log: log };
  }
})();
