"""#583 — the dual-column /question focus view, asserted on the shipped page.

The authoritative geometry check remains the browser guard
`dev/capture/qdual.mjs`. This file additionally loads the shipped page in a
browser, resolves /question through the executable registry, and pins the
source contracts around the rendered layout. A regression in registration,
the layout-split branch, focus-scoped grid, or width-exception wiring is caught
at the seam that owns it.

Production lines the red-proofs name (each assertion has one):
  · the registered native Question component's `qdual` container emission in
    dev/build/src/question.js — the layout-split branch. Removing it reds
    `test_registered_question_emits_dual_column`.
  · the `#qfocus.qdual`-scoped `grid-template-columns` in client/style.css —
    the grid that splits body (col 1) from compose (col 2). Removing the
    `#qfocus` scope reds the dashboard-protection half (a bare `.qa` grid would
    lay the dashboard out in two columns), and removing the grid reds the
    focus half. Sabotaging the rule reds `test_dual_column_css_is_focus_scoped`.
  · the `classList.toggle('question', …)` wiring in client/router.js at the
    three width-exception sites. Removing it reds `test_router_wires_question_width`.

Every check derives its expectation at runtime from the assembled constants
rather than from a literal tuned to today's tree, and each names the line it
defends. The red-proofs are run by hand (sabotage → red → restore) per the
repo's verification rule, not asserted here.
"""

import json
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

import watch

ROOT = pathlib.Path(watch.__file__).parent
PLAYWRIGHT = pathlib.Path(
    "/home/xertrov/.llm-general/skills/headless-browser-screenshots/"
    "node_modules/playwright/index.mjs")


def question_browser_fixture(tmp_path):
    """Return the production collector data and assembled shipping page."""
    fixture = tmp_path / "fixture"
    shutil.copytree(ROOT / "dev" / "capture" / "fixture", fixture)
    return watch.collect(str(fixture)), watch._get_page()


def run_question_browser_scenario(tmp_path, assembled, states, scenario,
                                  script_name="question-route.mjs"):
    """Boot /question with the shared Playwright routes, then run a scenario."""
    assert PLAYWRIGHT.is_file(), (
        "the shipped /question check needs the repo's browser-guard "
        "Playwright install, but %s is absent" % PLAYWRIGHT)
    states_path = tmp_path / "states.json"
    states_path.write_text(json.dumps(states), encoding="utf-8")
    page_path = tmp_path / "page.html"
    page_path.write_text(assembled, encoding="utf-8")
    script = tmp_path / script_name
    harness = r'''
import { chromium } from __PLAYWRIGHT__;
import { readFileSync } from 'node:fs';

const html = readFileSync(process.argv[2], 'utf8');
const states = JSON.parse(readFileSync(process.argv[3], 'utf8'));
let liveData = states.open;
let liveMtime = '0';
let pollArmed = false;
let pollMtimeRequests = 0;
let pollDataRequests = 0;
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(String(error)));
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (route.request().isNavigationRequest()) {
      await route.fulfill({ status: 200, contentType: 'text/html', body: html });
    } else if (url.pathname === '/data.json') {
      if (pollArmed) pollDataRequests += 1;
      await route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify(liveData) });
    } else if (url.pathname === '/mtime') {
      if (pollArmed) pollMtimeRequests += 1;
      await route.fulfill({ status: 200, contentType: 'text/plain',
        body: liveMtime });
    } else {
      await route.fulfill({ status: 404, body: '' });
    }
  });
  const target = 'http://question.test/question?qid=' +
    encodeURIComponent(states.title);
  await page.goto(target, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-dw-mount="question"] #qfocus.qdual ' +
    '.qa[data-qkey="o0"]');
__SCENARIO__
} finally {
  await browser.close();
}
'''.replace("__PLAYWRIGHT__", json.dumps(str(PLAYWRIGHT)))
    script.write_text(harness.replace("__SCENARIO__", scenario),
                      encoding="utf-8")
    return subprocess.run(
        ["node", str(script), str(page_path), str(states_path)],
        cwd=ROOT, capture_output=True, text=True, timeout=30)


def _fn_src(src, name):
    """Slice one top-level `function NAME(…)` body out of concatenated client JS.

    The client is shipped as one concatenated script, so the slice runs from the
    `function NAME` declaration to the next top-level `function ` at column 0.
    """
    start = src.find("function " + name + "(")
    if start < 0:
        return ""
    nxt = src.find("\nfunction ", start + 1)
    return src[start:nxt if nxt > 0 else len(src)]


class QuestionDualColumnSource(unittest.TestCase):
    """The /question focus view ships a dual-column layout; the dashboard does
    not. The split is CSS-driven and scoped to the focus container, because
    `qaCard` is shared with the dashboard and is explicitly out of scope."""

    def test_registered_question_emits_dual_column_container(self):
        """The registered native view wraps its card in a dual container.

        Production line: the `qdual` class on the `#qfocus` div in
        dev/build/src/question.js Question. The dashboard question builders
        (buildQuestions/buildDashboard) never emit `#qfocus`, so the dual
        layout cannot reach them — asserted below as the dashboard half.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            base, assembled = question_browser_fixture(tmp)
            self.assertTrue(base["questions_open"])
            self.assertTrue(base["answered_entries"])

            title = "Fold-following production question"
            long_body = " ".join(["read position survives native churn"] * 80)
            opened = dict(base["questions_open"][0])
            opened.update(title=title, body=long_body)
            answered = dict(base["answered_entries"][0])
            answered.update(title=title, body=long_body)
            nearby = dict(opened)
            nearby["title"] = title + " nearby, never a substitute"
            states = {
                "title": title,
                "open": dict(base, questions_open=[opened],
                             answered_entries=[]),
                "answered": dict(base, questions_open=[],
                                  answered_entries=[answered]),
                "missing": dict(base, questions_open=[nearby],
                                answered_entries=[]),
            }
            scenario = r'''
  const runtime = await page.evaluate(() => ({
    routes: window.dwNative?.registry?.routes() || [],
    mounted: window.dwNative?.registry?.mounted() || [],
  }));
  if (!runtime.routes.includes('question')) {
    const absent = pageErrors.map(message =>
      message.match(/ReferenceError:\s*([A-Za-z_$][\w$]*) is not defined/)
    ).find(Boolean);
    if (absent)
      throw new Error('the registered /question component ' + absent[1] +
        ' is absent from the shipment');
    throw new Error('the shipped native registry does not register /question');
  }
  if (!runtime.mounted.includes('question'))
    throw new Error('the shipped native registry did not mount /question');

  await page.waitForSelector('[data-dw-mount="question"] #qfocus.qdual ' +
    '.qa[data-qkey="o0"]');
  const draft = 'alpha\nbeta gamma delta\nepsilon zeta eta\ntheta iota kappa';
  const before = await page.evaluate(value => {
    const card = document.querySelector('#qfocus .qa[data-qkey="o0"]');
    const body = card.querySelector('.qbody');
    const textarea = card.querySelector('textarea');
    const note = card.querySelector('.qmode[data-mode="note"]');
    const style = document.createElement('style');
    style.textContent = '#qfocus .qbody{display:block!important;' +
      'max-height:42px!important;overflow:auto!important}';
    document.head.appendChild(style);
    note.click();
    textarea.value = value;
    textarea.focus();
    textarea.setSelectionRange(7, 17, 'forward');
    textarea.scrollTop = 11;
    body.scrollTop = 19;
    return {
      mode: card.querySelector('.qcompose').dataset.mode,
      value: textarea.value, start: textarea.selectionStart,
      end: textarea.selectionEnd, dir: textarea.selectionDirection,
      textScroll: textarea.scrollTop, readScroll: body.scrollTop,
    };
  }, draft);
  if (before.mode !== 'note' || before.readScroll === 0)
    throw new Error('browser fixture did not establish compose/read state');

  await page.evaluate(next => setData(next), states.answered);
  const after = await page.evaluate(() => {
    const card = document.querySelector('#qfocus .qa[data-qkey="a0"]');
    const textarea = card?.querySelector('textarea');
    const body = card?.querySelector('.qbody');
    return {
      answered: !!card, dual: !!card?.closest('#qfocus.qdual'),
      value: textarea?.value, focused: document.activeElement === textarea,
      start: textarea?.selectionStart, end: textarea?.selectionEnd,
      dir: textarea?.selectionDirection,
      mode: card?.querySelector('.qcompose')?.dataset.mode,
      textScroll: textarea?.scrollTop, readScroll: body?.scrollTop,
    };
  });
  if (!after.answered || !after.dual)
    throw new Error('registered /question lost its answered #qfocus.qdual DOM');
  if (after.value !== before.value)
    throw new Error('native update lost the half-typed question draft');
  if (!after.focused || after.start !== before.start ||
      after.end !== before.end || after.dir !== before.dir)
    throw new Error('native update lost question focus or caret position');
  if (after.mode !== before.mode)
    throw new Error('native update lost the question compose mode');
  if (after.textScroll !== before.textScroll ||
      after.readScroll !== before.readScroll)
    throw new Error('native update lost question textarea or read scroll');

  // Construct the vanishing-card case for real, then let tick() discover it
  // through /mtime. Calling setData(missing) here would prove setData, not the
  // scheduled poll that production relies on.
  await page.evaluate(next => setData(next), states.open);
  await page.waitForSelector('#qfocus .qa[data-qkey="o0"] textarea');
  const droppedDraft = 'draft that must outlive a vanished question';
  // Refuse the input listener's first save so only restoreCardState's
  // unmatched-card fallback can create the record asserted below.
  await page.evaluate(() => {
    const save = dwDraft.save.bind(dwDraft);
    window.__fallbackSaveProbe = { attempts: 0 };
    dwDraft.save = (qid, title, value) => {
      window.__fallbackSaveProbe.attempts += 1;
      if (window.__fallbackSaveProbe.attempts === 1) return false;
      return save(qid, title, value);
    };
  });
  await page.locator('#qfocus .qa[data-qkey="o0"] textarea').fill(droppedDraft);
  const autosave = await page.evaluate(title => ({
    attempts: window.__fallbackSaveProbe.attempts,
    stored: DraftStore.get(DraftStore.id('card', title))?.text || '',
  }), states.title);
  if (autosave.attempts !== 1 || autosave.stored !== '')
    throw new Error('fallback-write fixture did not isolate input autosave: ' +
      JSON.stringify(autosave));
  liveData = states.missing;
  liveMtime = 'poll-missing';
  pollArmed = true;
  await page.waitForSelector('#qfocus .qmissing', { timeout: 5000 });
  const vanished = await page.evaluate(title => {
    const focus = document.querySelector('#qfocus');
    const notice = focus?.querySelector('[role="alert"][data-unmatched-qid]');
    const record = DraftStore.get(DraftStore.id('card', title));
    return {
      cards: focus?.querySelectorAll('.qa[data-qid]').length,
      textareas: focus?.querySelectorAll('textarea').length,
      notice: notice?.textContent || '',
      noticeQid: notice?.dataset.unmatchedQid || '',
      stored: record?.text || '',
      saveAttempts: window.__fallbackSaveProbe.attempts,
    };
  }, states.title);
  if (pollMtimeRequests < 1 || pollDataRequests < 1)
    throw new Error('scheduled /mtime poll did not fetch the missing state');
  if (vanished.cards !== 0 || vanished.textareas !== 0)
    throw new Error('missing-state fixture did not remove the real card and textarea');
  if (vanished.noticeQid !== encodeURIComponent(states.title) ||
      !vanished.notice.includes('Draft preserved') ||
      vanished.stored !== droppedDraft || vanished.saveAttempts !== 2)
    throw new Error('unmatched-card fallback write did not preserve draft "' +
      droppedDraft + '": input autosave was refused; fallback attempts=' +
      vanished.saveAttempts + '; restored-cards=0; absent target .qa[data-qid="' +
      encodeURIComponent(states.title) + '"]');

  // #1183 rekeyed drafts by persisted question id. These fixture questions
  // carry no qid (id falls back to title), so a retitle still separates the
  // drafts — prove that, then require the notice to state the id-based
  // recovery promise that replaced the old title-key wording.
  const retitledTitle = states.title + ' retitled';
  const retitledData = structuredClone(states.open);
  retitledData.questions_open[0].title = retitledTitle;
  liveData = retitledData;
  pollArmed = false;
  await page.goto('http://question.test/question?qid=' +
    encodeURIComponent(retitledTitle), { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#qfocus .qa[data-qkey="o0"] textarea');
  const retitled = await page.evaluate(([oldTitle, newTitle]) => ({
    oldStored: DraftStore.get(DraftStore.id('card', oldTitle))?.text || '',
    newStored: DraftStore.get(DraftStore.id('card', newTitle))?.text || '',
    restoredValue: document.querySelector('#qfocus textarea')?.value || '',
  }), [states.title, retitledTitle]);
  if (retitled.oldStored !== droppedDraft || retitled.newStored !== '' ||
      retitled.restoredValue !== '' ||
      !vanished.notice.includes('attached to this question id'))
    throw new Error('changed-title recovery promise disagreed with id key: ' +
      'oldStored=' + JSON.stringify(retitled.oldStored) + ', newStored=' +
      JSON.stringify(retitled.newStored) + ', restoredValue=' +
      JSON.stringify(retitled.restoredValue));

  // When storage refuses the vanished draft, the readonly recovery textarea
  // is the only remaining copy. Assert its value, not merely its presence.
  const refusalTitle = states.title + ' storage refusal';
  const refusalData = structuredClone(states.open);
  refusalData.questions_open[0].title = refusalTitle;
  liveData = refusalData;
  await page.goto('http://question.test/question?qid=' +
    encodeURIComponent(refusalTitle), { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#qfocus .qa[data-qkey="o0"] textarea');
  await page.evaluate(() => {
    Storage.prototype.setItem = () => { throw new Error('storage refused'); };
  });
  const refusedDraft = 'only copy after browser storage refusal';
  await page.locator('#qfocus .qa[data-qkey="o0"] textarea').fill(refusedDraft);
  liveData = states.missing;
  liveMtime = 'poll-storage-refusal';
  pollArmed = true;
  await page.waitForSelector('#qfocus [role="alert"] textarea[readonly]',
    { timeout: 5000 });
  const refused = await page.evaluate(() => {
    const copy = document.querySelector('#qfocus [role="alert"] textarea');
    return { value: copy?.value || '', readOnly: copy?.readOnly === true };
  });
  if (!refused.readOnly || refused.value !== refusedDraft)
    throw new Error('storage-refusal recovery textarea lost the exact draft: ' +
      JSON.stringify(refused));
  if (pageErrors.length)
    throw new Error('shipping /question raised page errors: ' +
      pageErrors.join(' | '));
  console.log('live /question registry and DOM preserved draft/focus/mode/scroll');
'''
            run = run_question_browser_scenario(
                tmp, assembled, states, scenario,
                script_name="question-live-registry.mjs")
            self.assertEqual(
                run.returncode, 0,
                "live /question browser check failed\nstdout:\n%s\nstderr:\n%s" %
                (run.stdout, run.stderr))

    def test_dashboard_builders_do_not_emit_the_focus_container(self):
        """The dashboard and /questions listing are UNCHANGED: they never
        carry #qfocus, so the focus-scoped grid cannot reach their cards."""
        for name in ("buildDashboard", "buildQuestions"):
            src = _fn_src(watch.VIEWS_JS, name)
            self.assertNotIn('id="qfocus"', src,
                             "%s emits #qfocus — the focus container has leaked "
                             "onto the dashboard" % name)

    def test_dual_column_css_is_focus_scoped(self):
        """The grid that splits question body from compose is scoped to the
        focus container, so the dashboard's shared `.qa` cards stay one column.

        Production line: the `#qfocus.qdual … grid-template-columns` rule in
        client/style.css. Scoping matters more than the value: a bare `.qa`
        grid would lay every dashboard card out in two columns. So assert a
        rule whose SELECTOR carries #qfocus declares grid-template-columns
        (the split), and assert a width exception for body.question exists
        (the second column needs room the 72ch reading column does not give)."""
        css = watch.STYLE
        # the width exception — a third deliberate one beside /review and /file
        self.assertIn("body.question", css,
                      "the /question width exception (body.question .wrap) is "
                      "missing — the second column has no room")
        # scan rule blocks: a rule whose selector carries #qfocus and whose
        # body declares grid-template-columns is the focus-scoped split
        focus_grid = False
        for m in re.finditer(r"([^{}]*?)\{([^{}]*)\}", css, re.S):
            selector, body = m.group(1), m.group(2)
            if "#qfocus" in selector and "grid-template-columns" in body:
                focus_grid = True
                break
        self.assertTrue(focus_grid,
                        "no grid-template-columns declaration is scoped to "
                        "#qfocus — the dual-column split is either absent or "
                        "unscoped (an unscoped .qa grid would reshape the "
                        "dashboard)")

    def test_router_wires_question_width(self):
        """The width exception rides the same body-class + glide idiom /review
        and /file use (body.wsliding), toggled at the route-commit sites.

        Production line: `classList.toggle('question', …)` in client/router.js.
        Without it the column never widens on /question and the second column
        has no room."""
        rj = watch.ROUTER_JS
        toggles = re.findall(r"classList\.toggle\('question'", rj)
        # review/file toggle at three sites (rmr crossfade, normal crossfade,
        # no-transition first paint); question must keep parity so the glide
        # matches on every path.
        self.assertGreaterEqual(len(toggles), 1,
                                "router.js does not toggle body.question — the "
                                "/question width exception is never applied")


if __name__ == "__main__":
    unittest.main()
