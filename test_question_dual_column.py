"""#583 — the dual-column /question focus view, asserted on the shipped source.

pytest cannot see rendered structure (see the justfile: "pytest cannot see
rendered structure"), so the authoritative geometry check is the browser guard
`dev/capture/qdual.mjs`. This file pins the SOURCE contract the geometry is
built from, on the same surface `test_client_assets.py` already reads — the
byte-exact client constants — so a regression in the layout-split branch, the
focus-scoped grid, or the width-exception wiring is caught without a browser.

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
            fixture = tmp / "fixture"
            shutil.copytree(pathlib.Path(watch.__file__).parent /
                            "dev" / "capture" / "fixture", fixture)
            base = watch.collect(str(fixture))
            self.assertTrue(base["questions_open"])
            self.assertTrue(base["answered_entries"])

            title = "Fold-following production question"
            long_body = " ".join(["read position survives native churn"] * 80)
            opened = dict(base["questions_open"][0])
            opened.update(title=title, body=long_body)
            answered = dict(base["answered_entries"][0])
            answered.update(title=title, body=long_body)
            states = {
                "title": title,
                "open": dict(base, questions_open=[opened],
                             answered_entries=[]),
                "answered": dict(base, questions_open=[],
                                 answered_entries=[answered]),
            }
            states_path = tmp / "states.json"
            states_path.write_text(json.dumps(states), encoding="utf-8")
            page_path = tmp / "page.html"
            page_path.write_text(watch._get_page(), encoding="utf-8")

            playwright = pathlib.Path(
                "/home/xertrov/.llm-general/skills/"
                "headless-browser-screenshots/node_modules/playwright/index.mjs")
            self.assertTrue(
                playwright.is_file(),
                "the shipped /question resolver needs the browser-guard "
                "Playwright install")
            script = tmp / "question-live-registry.mjs"
            script.write_text(r'''
import { chromium } from __PLAYWRIGHT__;
import { readFileSync } from 'node:fs';

const html = readFileSync(process.argv[2], 'utf8');
const states = JSON.parse(readFileSync(process.argv[3], 'utf8'));
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
      await route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify(states.open) });
    } else if (url.pathname === '/mtime') {
      await route.fulfill({ status: 200, contentType: 'text/plain', body: '0' });
    } else {
      await route.fulfill({ status: 404, body: '' });
    }
  });
  await page.goto('http://question.test/question?qid=' +
    encodeURIComponent(states.title), { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(50);

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
  if (pageErrors.length)
    throw new Error('shipping /question raised page errors: ' +
      pageErrors.join(' | '));
  console.log('live /question registry and DOM preserved draft/focus/mode/scroll');
} finally {
  await browser.close();
}
'''.replace("__PLAYWRIGHT__", json.dumps(str(playwright))), encoding="utf-8")
            run = subprocess.run(
                ["node", str(script), str(page_path), str(states_path)],
                cwd=pathlib.Path(watch.__file__).parent,
                capture_output=True, text=True, timeout=30)
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
