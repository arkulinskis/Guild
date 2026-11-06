/* For screenshots of member pages (with tools/ui/_lib.js in front): the local admin with the sample cards.
   Resolves to window.SEED = {pages: [...]} (home, a module, a part's study intro, whole module, review, profile, curriculum). */
(async function () {
  try {
    await GL.ensureContent();
    window.SEED = { pages: await GL.memberPages(true) };
    return window.SEED;
  } catch (e) {
    return { error: String(e && e.message || e) };
  }
})();
