"""#653 — P1 of the #630 component transition: the build step, and the two
things that make a committed build artifact safe.

P1's claim was small and checkable: **`just build-client` exists,
`client/dist/` is committed, and the served page does not change by one byte.**
P3 deliberately ends that phase by embedding native.js. The lasting property
this file pins is the distinction between the two outputs: the native runtime
reaches PAGE once, while the design bundle that concatenates client assets
never does.

The other half is staleness. dist is committed (deploy ships committed state,
`justfile:418-423`, and the dashboard must come up with no node), so it can be
built from bytes that are no longer here. That cannot be made *impossible*
without a serve-time build, which the no-node requirement refuses — so it is
made impossible to MISS, and these checks are what say so.

Two rules from #397 govern every check below, and both are about checks that
pass for the wrong reason:

  1. **Every comparison asserts its own preconditions.** A byte-comparison
     passes vacuously on two empty sides; a containment check passes when the
     thing it looks for was never there to find. Each floor here is derived at
     runtime from the tree being measured, never a literal tuned to today's.
  2. **Every detector is proved able to detect.** Each red-proof below is a
     test, not a ceremony — and where the obvious red-proof would still admit
     a broken input, the test for THAT input is written too (the manifest that
     records nine hashes that all match while the tenth file is missing; the
     asset list that is reordered without one byte changing).
"""

import json
import http.server
import os
import pathlib
import re
import shutil
import subprocess
import threading
import types

import pytest

import client_dist
import watch
from test_question_dual_column import (
    question_browser_fixture,
    run_question_browser_scenario,
)

ROOT = pathlib.Path(__file__).resolve().parent
CLIENT = ROOT / "client"


def _clone(tmp_path, name="root"):
    """A whole checkout's worth of the build's subject, in tmp_path.

    The red-proofs mutate build inputs and manifests. They do it HERE, never
    in the repo: `client_dist.check` takes a root precisely so a proof cannot
    reach the tree it is run from. (`lessons.md:757` — the #348 incident that
    #349 tracks — sharpened by #652, where a lane found ANOTHER lane's
    snapshot in the shared scratchpad. The safest snapshot is the one that
    never has to be taken.)
    """
    dst = tmp_path / name
    dst.mkdir()
    shutil.copy(ROOT / "watch.py", dst / "watch.py")
    shutil.copytree(CLIENT, dst / "client")
    wrap = dst / client_dist.WRAPPER_EXPORTS_REL
    wrap.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / client_dist.WRAPPER_EXPORTS_REL, wrap)
    shutil.copytree(ROOT / client_dist.DS_SOURCE_DIR,
                    dst / client_dist.DS_SOURCE_DIR)
    # #630 P2: the native runtime's sources are build inputs too, so a clone
    # without them is not a faithful copy of the build's subject — every hash
    # comparison below would be run against a tree missing four of thirteen
    # inputs, and the OK assertion at the end of this function would be the
    # thing that failed rather than anything a proof injected.
    shutil.copytree(ROOT / client_dist.NATIVE_SRC_DIR,
                    dst / client_dist.NATIVE_SRC_DIR)
    # The clone must start CLEAN, or every proof below could be reading a
    # defect the clone introduced rather than the one it injected.
    reading = client_dist.check(str(dst))
    assert reading["state"] == client_dist.OK, (
        "the fixture clone is not a faithful copy — %r; every injection below "
        "would then be proving nothing" % (reading,))
    return dst


def _manifest(root):
    with open(os.path.join(str(root), client_dist.MANIFEST_REL),
              encoding="utf-8") as f:
        return json.load(f)


def _write_manifest(root, obj):
    with open(os.path.join(str(root), client_dist.MANIFEST_REL), "w",
              encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


# ── the phase's own claim ────────────────────────────────────────────────


def test_dist_delivery_matches_phase_authority():
    """The tool bundle stays contained; the native runtime reaches the page.

    P3 deliberately ends P1/P2's byte-identity phase by serving native.js.
    The design-tool bundle remains off-page because it concatenates the
    client assets and would run their top-level side effects a second time.

    Non-vacuous by construction: each probe string is asserted PRESENT in the
    built bundle first. A check that looks in the page for something that does
    not exist anywhere passes forever and means nothing — which is exactly how
    a containment check goes false-green.
    """
    index = (ROOT / client_dist.DS_DIR / "index.js").read_bytes().decode("utf-8")
    assert len(index) > 1000, (
        "client/dist/ds/index.js is %d chars — too small to be a bundle, and "
        "every probe below would be looking for nothing" % len(index))

    # Strings that exist ONLY in build output: the generated banner, esbuild's
    # entry marker, and the package's global name.
    probes = ["GENERATED by `just build-client`", "// entry.mjs",
              "DreamworkDesign"]
    for probe in probes:
        assert probe in index, (
            "%r is not in the built bundle, so its absence from the page "
            "would prove nothing" % probe)

    # #630 P2 emitted this bundle but loaded nothing. P3 serves the same
    # committed bytes inline, rather than copying or fetching them.
    native = (ROOT / client_dist.NATIVE_REL).read_bytes().decode("utf-8")
    assert len(native) > 50_000, (
        "%s is %d chars — too small to be React plus a runtime, and every "
        "probe below would be looking for nothing"
        % (client_dist.NATIVE_REL, len(native)))
    native_probes = ["dwNative", "data-dw-mount", "data-dw-probe"]
    for probe in native_probes:
        assert probe in native, (
            "%r is not in %s, so its absence from the page would prove "
            "nothing" % (probe, client_dist.NATIVE_REL))
    page = watch._get_page()
    floor = sum((CLIENT / n).stat().st_size for n in watch._CLIENT_ASSETS)
    assert floor > 0, "no client assets to derive a floor from"
    assert len(page) > floor, (
        "the assembled page is %d chars against %d chars of client assets — "
        "an asset is missing from the page, so this is not the dashboard and "
        "the containment checks below are meaningless" % (len(page), floor))

    # The generated banner is deliberately shared by both outputs, so it is a
    # build precondition but cannot distinguish the forbidden design bundle
    # from the required native one.
    for probe in ("// entry.mjs", "DreamworkDesign"):
        assert probe not in page, (
            "%r reached the served page — ds/index.js concatenates the "
            "client assets and would execute their top-level effects a "
            "second time on the dashboard" % probe)

    assert native in page, (
        "%s is not embedded byte-for-byte in the page — P3's registry is "
        "unreachable, so no route can flip to native authority"
        % client_dist.NATIVE_REL)

    # FALSE-GREEN VECTOR, constructed and then closed in P2. Content probes
    # alone pass on a page that fetches the runtime instead of inlining it:
    #
    #     <script src="/client/dist/native.js"></script>
    #
    # P3 preserves the closure: the page is still one response and fetches no
    # external script or stylesheet.
    #
    # Non-vacuous by construction: the page must contain inline <script> and
    # <style> first, or this would be asserting the absence of external assets
    # from a document that has no assets at all.
    assert "<script>" in page and "<style>" in page, (
        "the assembled page has no inline <script>/<style> — this is not the "
        "dashboard, and the single-response assertions below would hold "
        "vacuously")
    for ref in ("<script src", "<script  src", "<link rel=\"stylesheet\""):
        assert ref not in page, (
            "the page references an external asset (%r). The dashboard is one "
            "HTML response by design; native.js must be inline, not a fetch "
            "that content containment cannot distinguish"
            % ref)


def test_question_route_follows_the_fold_through_the_shipping_registry(tmp_path):
    """The registered /question component owns all three states and the move.

    This loads the assembled page, lets routeOf/isNativeRoute mount the
    production registry entry, and drives the production setData ->
    registry.update seam. No component is imported or constructed by the
    test, so deleting the registered production symbol makes this red.
    """
    base, assembled = question_browser_fixture(tmp_path)
    assert "function buildQuestion(" not in assembled, (
        "the converted route still ships its legacy buildQuestion authority")
    assert "return buildQuestion(view.param, d)" not in assembled, (
        "the router still dispatches /question to the deleted legacy builder")

    assert base["questions_open"] and base["answered_entries"], (
        "the production collector fixture needs both question shapes; a "
        "fabricated card would not exercise the shipping qaCard path")

    title = "Fold-following production question"
    opened = dict(base["questions_open"][0])
    opened.update(title=title, body="Read the live `DREAMWORK.md` link.")
    answered = dict(base["answered_entries"][0])
    answered["title"] = title
    nearby = dict(opened)
    nearby["title"] = title + " nearby, never a substitute"

    open_data = dict(base)
    open_data.update(questions_open=[opened], answered_entries=[])
    answered_data = dict(base)
    answered_data.update(questions_open=[], answered_entries=[answered])
    missing_data = dict(base)
    missing_data.update(questions_open=[nearby], answered_entries=[])

    states = {
        "title": title,
        "open": open_data,
        "answered": answered_data,
        "missing": missing_data,
    }
    scenario = r'''
  const initialUrl = page.url();
  const open = await page.evaluate(() => ({
    routes: window.dwNative.registry.routes(),
    mounted: window.dwNative.registry.mounted(),
    oldBuilder: typeof buildQuestion,
    missing: !!document.querySelector('#qfocus .qmissing'),
    knownLink: document.querySelector('#qfocus .mdfile a')?.getAttribute('href'),
    surface: document.querySelector('#qfocus .qa')?.dataset.qsurface,
  }));
  if (!open.routes.includes('question') || open.mounted[0] !== 'question')
    throw new Error('OPEN state did not arrive through the shipping question registry');
  if (open.oldBuilder !== 'undefined')
    throw new Error('OPEN state retained the deleted buildQuestion symbol');
  if (open.missing)
    throw new Error('OPEN state collapsed into qmissing');
  if (open.surface !== 'focus')
    throw new Error('OPEN state did not call qaCard with the focus surface');
  if (open.knownLink !== '/file?p=DREAMWORK.md')
    throw new Error('OPEN state qaCard did not read the live data binding');

  await page.evaluate(next => setData(next), states.answered);
  const moved = await page.evaluate(() => ({
    url: location.href,
    answered: !!document.querySelector(
      '#qfocus.qdual .qa[data-qkey="a0"]'),
    open: !!document.querySelector('#qfocus .qa[data-qkey="o0"]'),
    missing: !!document.querySelector('#qfocus .qmissing'),
  }));
  if (moved.url !== initialUrl || !moved.answered || moved.open || moved.missing)
    throw new Error('OPEN-TO-ANSWERED MOVE lost Fold-following production question under its stationary URL');

  await page.evaluate(next => setData(next), states.missing);
  const missing = await page.evaluate(() => {
    const focus = document.querySelector('#qfocus');
    return {
      url: location.href,
      dual: focus?.classList.contains('qdual'),
      head: focus?.querySelector('.qmisshead')?.textContent,
      back: focus?.querySelector('.qmissback a')?.getAttribute('href'),
      warned: !!focus?.querySelector('.--warn') ||
        !!focus?.classList.contains('--warn'),
      cards: focus?.querySelectorAll('.qa').length,
    };
  });
  if (missing.url !== initialUrl || missing.dual ||
      missing.head !== 'not found' || missing.back !== '/questions' ||
      missing.warned || missing.cards !== 0)
    throw new Error('NOT-FOUND state lost its neutral qmissing markup or substituted the near title');
  if (pageErrors.length)
    throw new Error('shipping /question raised page errors: ' + pageErrors.join(' | '));
  console.log('question shipping path: open o0; stationary move a0; neutral missing');
'''
    run = run_question_browser_scenario(
        tmp_path, assembled, states, scenario,
        script_name="question-route.mjs")
    assert run.returncode == 0, (
        "shipping /question browser check failed\nstdout:\n%s\nstderr:\n%s"
        % (run.stdout, run.stderr))


def test_ds_styles_is_a_byte_copy_of_the_stylesheet_the_page_serves():
    """The design package ships the dashboard's own stylesheet, not a fork.

    A second, editable copy of the visual language is a second authority for
    it — the thing Q1 refuses. So it is a copy, and this is what keeps it one.

    Precondition derived at runtime: both sides must carry the first custom
    property client/style.css actually declares. Two empty files are
    byte-equal, and a check that cannot tell that case from success is not a
    check.
    """
    served = (CLIENT / "style.css").read_bytes()
    shipped = (ROOT / client_dist.DS_DIR / "styles.css").read_bytes()
    text = served.decode("utf-8")
    tokens = [ln.split(":")[0].strip() for ln in text.splitlines()
              if ln.strip().startswith("--") and ":" in ln]
    assert tokens, (
        "client/style.css declares no custom property, so this test has no "
        "runtime-derived sentinel and would pass on two empty files")
    token = tokens[0]
    assert token.encode() in served and token.encode() in shipped, (
        "%s is not in both stylesheets — the comparison below could be "
        "comparing two blanks" % token)
    assert served == shipped, (
        "client/dist/ds/styles.css has drifted from client/style.css — the "
        "design package would ship a stylesheet the dashboard does not use")


def test_wrapper_exports_states_no_markup_of_its_own():
    """#630 §2b's "no restatement", enforced rather than reviewed.

    The one hand-written build input may CALL a builder; it may never restate
    its markup, because a second statement is the only place divergence could
    live. Today the file exports nothing, so this passes trivially — and that
    is the point of landing it now: the rule is in place before the first
    wrapper is written, not argued about afterwards.

    The detector proves itself first: it must find tag literals in
    client/components.js, which is FULL of them. A regex that had stopped
    matching anything would otherwise clear this file forever.
    """
    import re
    tag = re.compile(r"<\s*/?\s*(div|span|a|button|p|ul|li|table|tr|td|h[1-6]|"
                     r"section|header|footer|input|textarea|form|img|svg)\b",
                     re.I)
    builders = (CLIENT / "components.js").read_text(encoding="utf-8")
    found = tag.findall(builders)
    assert len(found) > 20, (
        "the tag-literal detector found %d tags in client/components.js, "
        "which is built entirely out of them — the detector is broken, and a "
        "broken detector clears the file below by finding nothing"
        % len(found))

    # #630 P2 widens this from one file to every hand-written build input.
    # The native runtime is where the temptation actually lives: a component
    # that "just needs a wrapper div" is one JSX tag away from being a second
    # statement of a builder's markup, and the first one nobody notices is the
    # one that makes "derived" a story rather than a property.
    #
    # This is also why the runtime is written with `React.createElement` and
    # not JSX (`dev/build/src/delegate.js` says so at its head): createElement
    # states an element NAME, so a component can still create elements while
    # this rule forbids markup outright. Under JSX the rule would have to
    # distinguish `<div>` the markup from `<div>` the call — which a regex
    # cannot do, and which would therefore fall to a reviewer every time.
    subjects = [client_dist.WRAPPER_EXPORTS_REL]
    native = client_dist.native_sources(str(ROOT))
    assert native, (
        "%s holds no source — this check would then be asserting the absence "
        "of markup from no files at all" % client_dist.NATIVE_SRC_DIR)
    subjects += native

    for rel in subjects:
        wrapper = (ROOT / rel).read_text(encoding="utf-8")
        # comments are prose about the rule, not markup subject to it
        code = "\n".join(ln for ln in wrapper.splitlines()
                         if not ln.lstrip().startswith(("//", "*", "/*")))
        hits = tag.findall(code)
        assert not hits, (
            "%s states markup of its own (%r). A wrapper must CALL the "
            "builder — a second statement of the same markup is the one "
            "thing that can diverge from it" % (rel, sorted(set(hits))))


def test_every_design_wrapper_has_one_complete_companion_triad_and_vice_versa():
    wrapper = (ROOT / client_dist.WRAPPER_EXPORTS_REL).read_text(
        encoding="utf-8")
    exports = re.findall(r"^export const ([A-Za-z_$][\w$]*)\s*=", wrapper,
                         re.MULTILINE)
    assert exports, "wrapper-exports.js exports no design wrappers"
    assert len(exports) == len(set(exports)), (
        "design wrapper export(s) are repeated: %r" % exports)

    companions = client_dist.ds_sources(str(ROOT))
    assert companions, "%s holds no companions" % client_dist.DS_SOURCE_DIR
    by_export = {}
    for rel in companions:
        name = pathlib.Path(rel).name
        suffix = next(s for s in client_dist.DS_SOURCE_SUFFIXES
                      if name.endswith(s))
        by_export.setdefault(name[:-len(suffix)], set()).add(suffix)

    required = set(client_dist.DS_SOURCE_SUFFIXES)
    for export in exports:
        missing = sorted(required - by_export.get(export, set()))
        assert not missing, "%s export is missing companion(s): %s" % (
            export, ", ".join(missing))
    for export, present in sorted(by_export.items()):
        missing = sorted(required - present)
        assert not missing, "%s companion set is missing companion(s): %s" % (
            export, ", ".join(missing))
        assert export in exports, (
            "%s companion triad has no matching wrapper export" % export)

    for rel in companions:
        source = ROOT / rel
        shipped = ROOT / client_dist.DS_DIR / source.name
        assert source.stat().st_size > 40, "%s is an empty-looking contract" % rel
        assert source.read_bytes() == shipped.read_bytes(), (
            "%s is not shipped byte-for-byte at %s" % (rel, shipped))

    fixture = json.loads((ROOT / client_dist.DS_SOURCE_DIR /
                          "QaCard.fixture.json").read_text(
        encoding="utf-8"))
    assert fixture["q"]["title"] and fixture["q"]["body"], (
        "QaCard fixture props do not exercise a real question")
    assert fixture["k"].startswith("o"), (
        "QaCard fixture does not exercise the open-card path")


def test_reviews_fixture_covers_loading_empty_and_distinct_multi_row_states():
    fixture = json.loads((ROOT / client_dist.DS_SOURCE_DIR /
                          "Reviews.fixture.json").read_text(encoding="utf-8"))
    assert set(fixture) == {"loading", "empty", "multi"}
    assert fixture["loading"]["data"] is None
    assert fixture["empty"]["data"]["reviews"] == []
    rows = fixture["multi"]["data"]["reviews"]
    assert len(rows) > 1, "Reviews multi fixture cannot exercise join with one row"
    assert len({row["decision"] for row in rows}) == len(rows), (
        "Reviews multi fixture rows need distinct decisions")
    assert len({row["question_title"] for row in rows}) == len(rows), (
        "Reviews multi fixture rows need distinct question links")


def test_reviews_wrapper_dom_strictly_equals_live_builder_for_every_state():
    """Both sides pass through one real DOM parser/serializer before equality."""
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        watch.make_handler(str(ROOT), journal_shadow=False))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:%d" % server.server_address[1]
    script = r"""
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { readFileSync } from 'node:fs';
const [base, designPath, nativePath, fixturePath] = process.argv.slice(1);
const cases = JSON.parse(readFileSync(fixturePath, 'utf8'));
const browser = await chromium.launch();
const page = await browser.newPage();
try {
  await page.goto(base + '/reviews', { waitUntil: 'networkidle' });
  await page.addScriptTag({ content: readFileSync(nativePath, 'utf8') });
  await page.evaluate(() => {
    delete document.getElementById('cmdpalette').dataset.composerMount;
  });
  await page.addScriptTag({ content: readFileSync(designPath, 'utf8') });
  const readings = [];
  for (const [state, props] of Object.entries(cases)) {
    const result = await page.evaluate(async ({ state, props }) => {
      const builder = buildReviews(props.data);
      const root = document.createElement('div');
      dwNative.ReactDOM.createRoot(root).render(
        dwNative.React.createElement(DreamworkDesign.Reviews, props));
      let mounted = null;
      for (let i = 0; i < 100; i++) {
        const host = root.querySelector('[data-dw-delegate="buildReviews"]');
        if (host) { mounted = host.innerHTML; break; }
        await new Promise(resolve => setTimeout(resolve, 10));
      }
      const serialize = raw => {
        const template = document.createElement('template');
        template.innerHTML = raw;
        const host = document.createElement('div');
        host.append(template.content.cloneNode(true));
        return host.innerHTML;
      };
      const expected = serialize(builder);
      const actual = serialize(mounted === null ? '' : mounted);
      let at = 0;
      while (expected[at] === actual[at] &&
             at < expected.length && at < actual.length) at++;
      return { state, expected, actual, at };
    }, { state, props });
    readings.push(result);
  }
  console.log(JSON.stringify(readings));
} finally {
  await browser.close();
}
"""
    try:
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script, base,
             str(ROOT / client_dist.DS_DIR / "index.js"),
             str(ROOT / client_dist.NATIVE_REL),
             str(ROOT / client_dist.DS_SOURCE_DIR / "Reviews.fixture.json")],
            text=True, capture_output=True, timeout=60)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert result.returncode == 0, (
        "Reviews wrapper equality browser failed before comparison:\n%s\n%s" %
        (result.stdout, result.stderr))
    readings = json.loads(result.stdout.strip().splitlines()[-1])
    assert {r["state"] for r in readings} == {"loading", "empty", "multi"}
    for reading in readings:
        assert reading["expected"], (
            "Reviews %s builder precondition: fixture output is non-empty" %
            reading["state"])
        assert reading["actual"], (
            "Reviews %s wrapper precondition: mounted output is non-empty" %
            reading["state"])
    mismatches = [
        "%s differs at %d: builder=%r wrapper=%r" %
        (r["state"], r["at"],
         r["expected"][r["at"]:r["at"] + 100],
         r["actual"][r["at"]:r["at"] + 100])
        for r in readings if r["expected"] != r["actual"]]
    assert not mismatches, (
        "Reviews wrapper serialization differs from live buildReviews after "
        "the same DOM parser/serializer: " + " | ".join(mismatches))


# ── #630 P2: the native runtime ──────────────────────────────────────────


def test_native_js_references_the_builders_and_does_not_contain_them():
    """"Consumed, never copied" as a property of the ARTIFACT.

    This is the check that separates the two bundles, and the separation is
    not stylistic. `ds/index.js` CONCATENATES `client/*.js` — it must, its
    consumer is a design tool with no dashboard — and it therefore carries
    their 40 top-level side effects: `setInterval(ages, 1e3)`,
    `document.addEventListener`, `window.dreambg = …`. #653 measured that
    count and flagged it as inert *for P1*. It stops being inert the moment a
    bundle containing it is loaded on the page, because the page is already
    running every one of them: a second `setInterval(ages, 1e3)` is a second
    timer mutating the same nodes forever.

    So `native.js` must reference the builders and never contain them. The
    detector is two-sided ON THE SAME PROBE, which is what makes it non-
    vacuous: each probe must be ABSENT from native.js and PRESENT in
    ds/index.js. A probe string that had gone stale — renamed builder, changed
    source — would fail the PRESENT half loudly instead of clearing the ABSENT
    half silently. Hunting for strings that exist nowhere is the exact
    false-green #653 recorded closing on its own containment check.
    """
    native = (ROOT / client_dist.NATIVE_REL).read_bytes().decode("utf-8")
    index = (ROOT / client_dist.DS_DIR / "index.js").read_bytes().decode(
        "utf-8")

    # Lifted verbatim from client/*.js: distinctive enough not to appear by
    # chance, and each one is a top-level SIDE EFFECT or a builder body — the
    # things that must not run twice.
    probes = ["setInterval(ages", "window.dreambg", "function artifactRow("]
    for probe in probes:
        assert probe in index, (
            "%r is not in the design bundle, which concatenates client/*.js. "
            "The probe is stale, so asserting its absence from native.js "
            "would prove nothing at all" % probe)
        assert probe not in native, (
            "%r is IN %s. The native runtime is loaded on a page that already "
            "runs the builders, so a copy of them there is a second set of "
            "top-level side effects against the same document — and a second "
            "statement of markup that can diverge from the served one"
            % (probe, client_dist.NATIVE_REL))

    # The other half of the claim: it references them. A bundle that neither
    # contains nor references a builder would pass every assertion above by
    # having nothing to do with the builders at all.
    assert "artifactRow" in native, (
        "%s does not name artifactRow — the delegating wrapper is supposed "
        "to CALL it, and a bundle that neither contains nor references the "
        "builders is not derived from anything" % client_dist.NATIVE_REL)


def test_native_js_bundles_reacts_production_build():
    """Which React the dashboard will run, asserted rather than assumed.

    React ships dev and production behind `process.env.NODE_ENV` and picks at
    bundle time. Getting this wrong is silent: the page works, and it is
    bigger, slower, and emits warnings to a console nobody has open. It is
    also not a size question — the dev build carries different code.

    Both directions, because either alone passes on a bundle that is not
    React at all: a production-only marker must be PRESENT, and the dev
    build's unmistakable string must be ABSENT.
    """
    native = (ROOT / client_dist.NATIVE_REL).read_bytes().decode("utf-8")
    assert "react-dom" in native.lower() or "ReactDOM" in native, (
        "%s does not look like it contains ReactDOM at all, so neither "
        "assertion below would be about React" % client_dist.NATIVE_REL)
    # esbuild folds `process.env.NODE_ENV !== "production"` to false and drops
    # the branch, so the dev build's warning text cannot survive.
    for dev_marker in ("Warning: React.createElement",
                       "react-dom.development.js",
                       "react.development.js"):
        assert dev_marker not in native, (
            "%r is in %s — the DEVELOPMENT build of React was bundled. It is "
            "bigger, slower, and warns into a console nobody has open; the "
            "fix is the --define:process.env.NODE_ENV=\"production\" flag in "
            "dev/build_client.build_native" % (dev_marker,
                                               client_dist.NATIVE_REL))
    manifest = _manifest(ROOT)
    assert manifest["tool"].get("react"), (
        "the manifest does not record which React was bundled — with React "
        "inside a minified artifact, that question is otherwise answered by "
        "grepping 143 KB of generated code")


RUNTIME_WEIGHT_BUDGET = 147_000
# Report migrated-component weight by default. Set this one line to the page
# ceiling Max chooses if component growth should become bounded.
COMPONENT_WEIGHT_BUDGET = None


def _native_weight(root=ROOT):
    res = subprocess.run(
        ["node", str(ROOT / "dev/build/measure-runtime.mjs"),
         "--root", str(root)], capture_output=True, text=True)
    assert res.returncode == 0, (
        "runtime-only measurement failed: %s" % res.stderr.strip())
    try:
        runtime = json.loads(res.stdout)["runtime_bytes"]
    except (KeyError, TypeError, ValueError) as exc:
        pytest.fail("runtime-only measurement emitted no byte count: %s (%s)"
                    % (res.stdout.strip(), exc))
    total = (pathlib.Path(root) / client_dist.NATIVE_REL).stat().st_size
    assert 50_000 < runtime <= total, (
        "runtime-only measurement is %r against %d total bytes — it is not "
        "a non-empty proper runtime/component split" % (runtime, total))
    return {"runtime": runtime, "components": total - runtime, "total": total}


def _enforce_native_weight(weight):
    assert weight["runtime"] <= RUNTIME_WEIGHT_BUDGET, (
        "runtime-only bundle is %d bytes, over its %d-byte budget; this "
        "measurement excludes migrated route components, so raising it is a "
        "React/runtime decision, not ordinary UI work"
        % (weight["runtime"], RUNTIME_WEIGHT_BUDGET))
    if COMPONENT_WEIGHT_BUDGET is not None:
        assert weight["components"] <= COMPONENT_WEIGHT_BUDGET, (
            "migrated components are %d bytes, over their %d-byte ceiling"
            % (weight["components"], COMPONENT_WEIGHT_BUDGET))


def test_runtime_measurement_matches_production_size_build_settings(
        tmp_path, monkeypatch):
    """The measurement build may differ in entry, never in size semantics."""
    import sys
    sys.path.insert(0, str(ROOT / "dev"))
    import build_client
    _configure_toolchain(build_client)

    root = tmp_path / "production-settings"
    src = root / client_dist.NATIVE_SRC_DIR
    src.mkdir(parents=True)
    shutil.copy(ROOT / client_dist.NATIVE_ENTRY_REL,
                root / client_dist.NATIVE_ENTRY_REL)
    captured = {}
    run = subprocess.run

    def capture(cmd, **kwargs):
        captured.update(cmd=cmd, kwargs=kwargs)
        return types.SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(build_client.subprocess, "run", capture)
    build_client.build_native(str(root))

    production = {
        "bundle": False,
        "define": {},
        "minify": False,
        "nodePaths": [captured["kwargs"]["env"]["NODE_PATH"]],
    }
    spellings = {
        "--format=": "format",
        "--global-name=": "globalName",
        "--target=": "target",
        "--charset=": "charset",
        "--line-limit=": "lineLimit",
        "--banner:js=": "banner",
    }
    for arg in captured["cmd"][2:]:
        if arg == "--bundle":
            production["bundle"] = True
        elif arg == "--minify":
            production["minify"] = True
        elif arg.startswith("--define:"):
            key, value = arg[len("--define:"):].split("=", 1)
            production["define"][key] = value
        elif arg.startswith("--outfile="):
            continue
        else:
            matches = [(prefix, key) for prefix, key in spellings.items()
                       if arg.startswith(prefix)]
            assert len(matches) == 1, (
                "production native build gained an unclassified esbuild "
                "setting %r; runtime-size parity must decide whether it "
                "belongs in the measurement" % arg)
            prefix, key = matches[0]
            value = arg[len(prefix):]
            production[key] = (int(value) if key == "lineLimit" else value)
    production["banner"] = {"js": production["banner"]}

    res = run(
        ["node", str(ROOT / "dev/build/measure-runtime.mjs"),
         "--print-build-config"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    measured = json.loads(res.stdout)
    assert measured == production, (
        "runtime measurement build settings drifted from production: "
        "measurement=%r production=%r" % (measured, production))


def test_the_native_runtime_stays_inside_a_chosen_page_weight_budget():
    """#630 plan §5-P2(ii), corrected by #1190 after its premise changed.

    The plan asks for a bound on PAGE. A bound on PAGE would be the wrong
    check HERE and would become a liability: the page is 604 KB and grows with
    every ordinary UI commit, so a PAGE budget fires on work that has nothing
    to do with this phase — the false red that trains a reader to raise the
    number without looking. Native.js used to isolate the runtime, but the
    React migration falsified that premise: route components now enter it as
    ordinary UI work. The strict subject is therefore rebuilt separately as
    React + ReactDOM + the registry + one probe; component weight is reported
    independently and is bounded only when COMPONENT_WEIGHT_BUDGET is set.

    IGC context: preserve the P2 human decision while routes keep migrating.

      Idea                         All  G1  G2  G3  G4
      runtime-only measurement     yes  yes yes yes yes
      esbuild per-input manifest   no   no  no  yes no
      split production chunks      no   yes yes no  yes

    G1 measures the semantic runtime; G2 stays true when the next component
    lands without editing a number; G3 leaves native.js unchanged; G4 needs no
    hand-classification of future component files. Per-input attribution is
    refuted because a component can make esbuild retain new React code and the
    compiler's byte allocation is not a semantic boundary. Production chunks
    are refuted because this task changes measurement, not shipped contents.
    """
    weight = _native_weight()
    print("native weight: runtime=%d, components=%d, total=%d"
          % (weight["runtime"], weight["components"], weight["total"]))
    _enforce_native_weight(weight)


def test_runtime_growth_reds_while_larger_component_growth_stays_green(
        tmp_path):
    """The separating pair: runtime RED, ordinary component growth GREEN."""
    root = _clone(tmp_path, "subject")
    src = root / client_dist.NATIVE_SRC_DIR
    dist = root / client_dist.NATIVE_REL
    baseline = _native_weight(root)

    probe = src / "probe.js"
    probe_original = probe.read_text(encoding="utf-8")
    probe.write_text(
        probe_original + "\nglobalThis.__probeWeightProof = %r;\n" %
        ("p" * 1_000), encoding="utf-8")
    assert _native_weight(root)["runtime"] > baseline["runtime"] + 500, (
        "the real coexistence probe is absent from the runtime measurement")
    probe.write_text(probe_original, encoding="utf-8")

    registry = src / "registry.js"
    original = registry.read_text(encoding="utf-8")
    runtime_padding = "x" * 2_000
    registry.write_text(
        original + "\nglobalThis.__runtimeWeightProof = %r;\n" %
        runtime_padding, encoding="utf-8")
    runtime_growth = _native_weight(root)
    assert runtime_growth["runtime"] > baseline["runtime"] + 1_000, (
        "runtime injection did not materially enter the measured bundle")
    with pytest.raises(AssertionError, match="runtime-only bundle is"):
        _enforce_native_weight(runtime_growth)

    registry.write_text(original, encoding="utf-8")
    component_padding = "y" * 4_000
    (src / "ordinary-component.js").write_text(
        "import React from 'react';\n"
        "export const Ordinary = () => React.createElement('div', null, %r);\n"
        % component_padding, encoding="utf-8")
    entry = src / "native-entry.js"
    entry.write_text(
        entry.read_text(encoding="utf-8") +
        "\nimport { Ordinary } from './ordinary-component.js';\n"
        "registry.register('__weight_proof', { component: Ordinary });\n",
        encoding="utf-8")
    import sys
    sys.path.insert(0, str(ROOT / "dev"))
    import build_client
    _configure_toolchain(build_client)
    build_client.build_native(str(root))
    component_growth = _native_weight(root)
    assert component_growth["total"] > baseline["total"], (
        "registering an ordinary component and rebuilding native.js did not "
        "grow the shipped bundle (%d bytes before and after)"
        % baseline["total"])
    assert component_growth["runtime"] == baseline["runtime"], (
        "an ordinary registered component changed the runtime-only reading")
    print("component rebuild: native.js %d -> %d; runtime %d -> %d"
          % (baseline["total"], component_growth["total"],
             baseline["runtime"], component_growth["runtime"]))
    _enforce_native_weight(component_growth)  # report-only component policy


def test_native_sources_are_all_build_inputs(tmp_path):
    """Every file in `dev/build/src/` is hashed, by GLOB rather than by list.

    The native runtime grows a file per converted surface from P3 on. A
    hand-maintained list of its sources would be a second truth that goes
    stale on the first addition — and stale in the silent direction: the new
    file simply would not be hashed, so editing it would never read as stale.

    Non-vacuous by construction: a file is CREATED here and the input set must
    grow to include it. A glob that had stopped matching anything would fail
    this, where merely listing today's four files would not.
    """
    root = _clone(tmp_path)
    before = client_dist.expected_inputs(str(root))
    assert before, "the clone's input set is empty"

    added = root / client_dist.NATIVE_SRC_DIR / "zz_p3_surface.js"
    added.write_text("export const later = 1;\n", encoding="utf-8")
    after = client_dist.expected_inputs(str(root))
    new = sorted(set(after) - set(before))
    assert new == [client_dist.NATIVE_SRC_DIR + "/zz_p3_surface.js"], (
        "a new file in %s did not become a build input (%r) — the input set "
        "is not derived from the tree" % (client_dist.NATIVE_SRC_DIR, new))


def _goals_source():
    source = ROOT / client_dist.NATIVE_SRC_DIR / "goals.js"
    text = source.read_text(encoding="utf-8")
    assert "function GoalPage" in text, (
        "dev/build/src/goals.js no longer contains GoalPage — this check did "
        "not examine the /goals renderer")
    return text


def test_goals_dom_order_and_common_exact_selector_css_declarations():
    """Check DOM order plus three common declarations in four exact blocks."""
    source = _goals_source()
    page = source[source.index("function GoalPage"):
                  source.index("export function registerGoals")]
    tree_heading = page.index("'goal tree'")
    editor = page.index("React.createElement(GoalWrites")
    assert tree_heading < editor, (
        "GoalPage renders the editing UI before the goal tree — the tree must "
        "be the page subject above every add/edit control")

    css = (CLIENT / "style.css").read_text(encoding="utf-8")
    for selector in (".goalpage", ".goaltree-section", ".goaltree",
                     ".goalwrites"):
        start = css.index(selector + " {")
        rule = css[start:css.index("}", start)]
        reordering = re.search(
            r"(?:^|[;{]\s*)(?:(?:order|grid-row)\s*:|"
            r"(?:flex-direction|flex-flow)\s*:[^;}]*reverse)", rule)
        assert reordering is None, (
            f"{selector}'s first exact CSS block uses order/grid-row or "
            "reverse flex; this static check does not cover other selectors, "
            "declarations, inline styles, or rendered geometry")


def test_goals_editor_source_exposes_required_controls_and_messages():
    """Usability controls stay explicit; browser behaviour is guarded separately."""
    source = _goals_source()
    required = {
        "Goal title": "Goal title is required",
        "Done when": "Done when is required",
        "edit escape": "Cancel edit",
        "draft escape": "Clear draft",
        "child shortcut": "Add child",
    }
    for subject, marker in required.items():
        assert marker in source, (
            f"the goals editor lost its {subject} control/message: {marker!r}")


def test_expected_inputs_accepts_a_tree_without_wrapper_companions(tmp_path):
    root = _clone(tmp_path)
    companions = client_dist.ds_sources(str(root))
    shutil.rmtree(root / client_dist.DS_SOURCE_DIR)

    inputs = client_dist.expected_inputs(str(root))
    assert inputs is not None, (
        "repo without dev/build/ds-src must report an empty companion set, "
        "not unknown inputs")
    expected = (["client/" + name for name in client_dist.asset_order(str(root))]
                + [client_dist.WRAPPER_EXPORTS_REL]
                + client_dist.native_sources(str(root)))
    assert inputs == expected
    assert not set(companions) & set(inputs)


def test_readable_empty_wrapper_companion_directory_is_an_empty_set(tmp_path):
    root = _clone(tmp_path)
    shutil.rmtree(root / client_dist.DS_SOURCE_DIR)
    (root / client_dist.DS_SOURCE_DIR).mkdir()

    assert client_dist.ds_sources(str(root)) == []
    assert client_dist.expected_inputs(str(root)) is not None


def test_unreadable_wrapper_companion_directory_refuses(tmp_path, monkeypatch):
    root = _clone(tmp_path)
    real_scandir = os.scandir
    companion_dir = str(root / client_dist.DS_SOURCE_DIR)

    def refuse_companion_dir(path):
        if os.fspath(path) == companion_dir:
            raise PermissionError("wrapper companion directory is unreadable")
        return real_scandir(path)

    monkeypatch.setattr(client_dist.os, "scandir", refuse_companion_dir)
    assert client_dist.ds_sources(str(root)) is None
    assert client_dist.expected_inputs(str(root)) is None


def test_build_names_an_unreadable_wrapper_companion_directory(
        tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(ROOT / "dev"))
    import build_client
    _configure_toolchain(build_client)

    root = _clone(tmp_path)
    real_scandir = os.scandir
    companion_dir = str(root / client_dist.DS_SOURCE_DIR)

    def refuse_companion_dir(path):
        if os.fspath(path) == companion_dir:
            raise PermissionError("wrapper companion directory is unreadable")
        return real_scandir(path)

    monkeypatch.setattr(client_dist.os, "scandir", refuse_companion_dir)
    with pytest.raises(build_client.BuildError) as exc:
        build_client.build(str(root))
    message = str(exc.value)
    assert message == (
        "%s could not be read — refusing to guess the design bundle's "
        "wrapper companion inputs" % client_dist.DS_SOURCE_DIR)


def test_a_new_native_source_that_the_manifest_never_saw_is_stale(tmp_path):
    """RED PROOF: the P3-shaped mistake, exactly.

    Someone adds a component file to the native runtime and does not rebuild.
    Every hash the manifest records still matches its file, so a detector
    keyed on the MANIFEST's own key set is green while native.js was built
    without the new component in it.
    """
    root = _clone(tmp_path)
    (root / client_dist.NATIVE_SRC_DIR / "future-surface.js").write_text(
        "export const Research = null;\n", encoding="utf-8")

    manifest = _manifest(root)
    for rel, digest in manifest["inputs"].items():
        assert client_dist.sha256_file(os.path.join(str(root), rel)) == digest, (
            "the injection disturbed a recorded file; the false-green it is "
            "demonstrating would not be demonstrated")

    reading = client_dist.check(str(root))
    assert reading["state"] == client_dist.STALE, (
        "a native source the build never saw read as %r" % (reading["state"],))
    assert any("future-surface.js" in s for s in reading["stale"]) or \
        "future-surface.js" in (reading["note"] or ""), (
        "the reading does not NAME the unbuilt source: %r" % (reading,))


def test_an_edited_native_source_reds_the_detector(tmp_path):
    """RED PROOF, the plain direction, on the new input class."""
    root = _clone(tmp_path)
    target = root / client_dist.NATIVE_SRC_DIR / "registry.js"
    target.write_bytes(target.read_bytes() + b"\n// drift\n")
    reading = client_dist.check(str(root))
    assert reading["state"] == client_dist.STALE, (
        "an edited native source did not read as stale (%r)" % (reading,))
    assert any("registry.js" in s for s in reading["stale"]), reading


def test_an_edited_native_bundle_reds_the_detector(tmp_path):
    """RED PROOF: the output side. `native.js` is committed and right there —
    hand-editing a committed artifact is the temptation the manifest is for."""
    root = _clone(tmp_path)
    out = root / client_dist.NATIVE_REL
    out.write_bytes(out.read_bytes() + b"\n/* hand-edited */\n")
    reading = client_dist.check(str(root))
    assert reading["state"] == client_dist.STALE, (
        "a hand-edited native bundle read as %r" % (reading["state"],))
    assert any("native.js" in s for s in reading["stale"]), reading


def test_an_emptied_native_src_dir_is_unreadable_and_never_green(tmp_path):
    """FALSE-GREEN VECTOR, closed: the input class that vanishes.

    `native_sources` globs, and a glob over an empty directory returns an
    empty list, not an error. Fold that into the input set and the four native
    hashes simply stop being compared — the check goes green over a native.js
    built from files that are no longer here.

    So an empty source directory is UNREADABLE, not "a build with fewer
    inputs". And the note must name the DIRECTORY: the sibling failure (an
    unparseable watch.py) reaches the same branch, and a note that named
    watch.py for a missing build directory sends the reader to the wrong file.
    """
    root = _clone(tmp_path)
    for path in (root / client_dist.NATIVE_SRC_DIR).glob("*.js"):
        path.unlink()
    assert client_dist.native_sources(str(root)) is None, (
        "an emptied source directory still produced an input list")

    reading = client_dist.check(str(root))          # must not raise
    assert reading["state"] == client_dist.UNREADABLE, (
        "an emptied %s read as %r — the native inputs would silently stop "
        "being compared" % (client_dist.NATIVE_SRC_DIR, reading["state"]))
    assert client_dist.NATIVE_SRC_DIR in (reading["note"] or ""), (
        "the reading does not name the directory that is empty, and the "
        "other cause of this state points at watch.py: %r" % (reading,))


# ── the staleness detector, and the ways it could pass while wrong ───────


def test_the_committed_dist_is_built_from_the_committed_tree():
    """The standing check, in pytest as well as in lint.

    Its own precondition first: the input set must be the whole asset list
    plus the hand-written file. A check over an empty input set is green
    forever.
    """
    want = client_dist.expected_inputs(str(ROOT))
    assert want is not None, "watch._CLIENT_ASSETS is not AST-readable"
    native = client_dist.native_sources(str(ROOT))
    assert native, (
        "%s holds no source — the native runtime's inputs would be an empty "
        "set, and an empty set is what every vacuous check looks like"
        % client_dist.NATIVE_SRC_DIR)
    companions = client_dist.ds_sources(str(ROOT))
    assert companions, (
        "%s holds no companions — the design contract inputs would be "
        "an empty set" % client_dist.DS_SOURCE_DIR)
    # Derived on both sides rather than a literal count: #630 P2 took this
    # from 9 to 13 and P3 will take it further, and a hard-coded total makes
    # every later phase edit a number here to make an unrelated test pass —
    # which is how a check stops being read and starts being satisfied.
    expected = (len(watch._CLIENT_ASSETS) + 1 + len(companions)
                + len(native))
    assert len(want) == expected, (
        "expected %d inputs (%d assets + wrapper-exports + %d companions "
        "+ %d native sources), derived %d"
        % (expected, len(watch._CLIENT_ASSETS), len(companions),
           len(native), len(want)))
    reading = client_dist.check(str(ROOT))
    assert reading["state"] == client_dist.OK, (
        "client/dist is %s: %s — run `just build-client`"
        % (reading["state"], reading["note"]))


def test_an_edited_input_reds_the_detector(tmp_path):
    """RED PROOF, the plain direction: touch one byte of a builder.

    This is the defect the whole mechanism exists for — a design bundle
    compiled from yesterday's `components.js`.
    """
    root = _clone(tmp_path)
    target = root / "client" / "components.js"
    raw = target.read_bytes()
    target.write_bytes(raw + b"\n// one byte of drift\n")

    reading = client_dist.check(str(root))
    assert reading["state"] == client_dist.STALE, (
        "an edited builder did not read as stale (%r) — every client edit "
        "from here on would ship a dist built from something else"
        % (reading,))
    assert any("components.js" in s for s in reading["stale"]), (
        "the reading does not NAME the file that drifted: %r" % (reading,))
    assert reading["fix"], "a red with no fix named is a red nobody can clear"


def test_an_edited_output_reds_the_detector(tmp_path):
    """RED PROOF: the other side of the manifest. A hand-edited artifact is
    the temptation a committed build creates — the file is right there."""
    root = _clone(tmp_path)
    out = root / client_dist.DS_DIR / "index.js"
    out.write_bytes(out.read_bytes() + b"\n/* hand-edited */\n")
    reading = client_dist.check(str(root))
    assert reading["state"] == client_dist.STALE, (
        "a hand-edited build artifact read as %r" % (reading["state"],))
    assert any("index.js" in s for s in reading["stale"]), reading


def test_a_manifest_that_forgot_an_input_is_stale_though_every_hash_matches(
        tmp_path):
    """FALSE-GREEN VECTOR, closed.

    Construct the input that is genuinely broken but that the obvious check
    passes on: drop one asset from the manifest's `inputs` map and change
    nothing else. Every hash the manifest still records matches its file
    exactly, so a detector that iterates the MANIFEST's keys reports green —
    while the dist was in fact built without that asset.

    This is the shape a real ninth asset would take: someone adds
    `client/foo.js` to `_CLIENT_ASSETS`, never rebuilds, and the manifest
    simply does not mention it. The check must derive its key set from the
    TREE, which is why `expected_inputs` reads `_CLIENT_ASSETS` rather than
    the manifest.
    """
    root = _clone(tmp_path)
    manifest = _manifest(root)
    dropped = "client/components.js"
    assert dropped in manifest["inputs"], "fixture assumption broken"
    del manifest["inputs"][dropped]
    _write_manifest(root, manifest)

    # the vector is real: every hash still recorded is still correct, so a
    # manifest-keyed detector has nothing to report.
    for rel, digest in manifest["inputs"].items():
        assert client_dist.sha256_file(os.path.join(str(root), rel)) == digest, (
            "the injection changed a file it should not have; the false-green "
            "it is demonstrating would not be demonstrated")

    reading = client_dist.check(str(root))
    assert reading["state"] == client_dist.STALE, (
        "a dist built without client/components.js read as %r — the detector "
        "is trusting the manifest's own key set" % (reading["state"],))
    assert dropped in reading["note"], reading


def test_a_reordered_asset_list_is_stale_though_no_byte_changed(tmp_path):
    """FALSE-GREEN VECTOR, closed.

    The page concatenates the assets in `_CLIENT_ASSETS` order, and the bundle
    is generated in that same order. Swap two entries and every file on disk is
    byte-identical — so a hash-only detector, over the correct key set, is
    still green, while the bundle now means something different from the page.

    Order is an input. This is the check that says so.
    """
    root = _clone(tmp_path)
    src = (root / "watch.py").read_text(encoding="utf-8")
    order = client_dist.asset_order(str(root))
    a, b = order[2], order[3]
    assert a.endswith(".js") and b.endswith(".js"), (
        "fixture wants two JS assets to swap, got %r/%r" % (a, b))
    swapped = src.replace('    "%s",\n    "%s",\n' % (a, b),
                          '    "%s",\n    "%s",\n' % (b, a), 1)
    assert swapped != src, "the asset-list swap did not apply"
    (root / "watch.py").write_text(swapped, encoding="utf-8")
    assert client_dist.asset_order(str(root))[2:4] == [b, a], (
        "the swap did not change what the AST reads — nothing was injected")

    # every hash is still correct; only the ORDER moved.
    manifest = _manifest(root)
    for rel, digest in list(manifest["inputs"].items()) + \
            list(manifest["outputs"].items()):
        assert client_dist.sha256_file(os.path.join(str(root), rel)) == digest

    reading = client_dist.check(str(root))
    assert reading["state"] == client_dist.STALE, (
        "reordering the page's assets left dist reading %r — the bundle would "
        "silently disagree with the page about load order"
        % (reading["state"],))


def test_an_empty_manifest_does_not_pass_by_having_nothing_to_compare(
        tmp_path):
    """FALSE-GREEN VECTOR, closed: the vacuous manifest.

    `{"inputs": {}, "outputs": {}}` satisfies every hash comparison there is,
    by supplying none. This is the shape a half-written or truncated manifest
    takes, and it must not read as a clean build.
    """
    root = _clone(tmp_path)
    _write_manifest(root, {"schema": client_dist.SCHEMA, "tool": {},
                           "asset_order": client_dist.asset_order(str(root)),
                           "inputs": {}, "outputs": {}})
    reading = client_dist.check(str(root))
    assert reading["state"] != client_dist.OK, (
        "a manifest recording nothing read as a current build")


def test_a_manifest_with_inputs_but_no_outputs_is_not_clean(tmp_path):
    """The same vacuity one level in: recording every input correctly while
    claiming no outputs would leave the artifact half of the check with
    nothing to iterate."""
    root = _clone(tmp_path)
    manifest = _manifest(root)
    manifest["outputs"] = {}
    _write_manifest(root, manifest)
    assert client_dist.check(str(root))["state"] != client_dist.OK


# ── the states where the check's own subjects are absent ─────────────────


def test_a_missing_manifest_is_a_named_state_and_never_a_raise(tmp_path):
    """lessons.md:580 / :622 — a guard assertion whose subject may not exist
    must RETURN a reading, never throw. The absent case is precisely the one
    this check was written for; a traceback there reads like the check being
    broken and starts the diagnosis in the wrong place."""
    root = _clone(tmp_path)
    os.remove(os.path.join(str(root), client_dist.MANIFEST_REL))
    reading = client_dist.check(str(root))          # must not raise
    assert reading["state"] == client_dist.MISSING, reading
    assert client_dist.MANIFEST_REL in reading["note"], reading


def test_an_unparseable_manifest_is_a_named_state_and_never_a_raise(tmp_path):
    root = _clone(tmp_path)
    with open(os.path.join(str(root), client_dist.MANIFEST_REL), "w") as f:
        f.write("{ this is not json")
    reading = client_dist.check(str(root))          # must not raise
    assert reading["state"] in (client_dist.MISSING, client_dist.UNREADABLE)
    assert reading["state"] != client_dist.OK


def test_an_unreadable_watch_py_reports_rather_than_crashing(tmp_path):
    """The input set is derived from watch.py by AST. If that read fails the
    check knows nothing — and must SAY so, not pass and not explode."""
    root = _clone(tmp_path)
    (root / "watch.py").write_text("def (: not python\n", encoding="utf-8")
    reading = client_dist.check(str(root))          # must not raise
    assert reading["state"] == client_dist.UNREADABLE, reading


def test_a_missing_input_file_is_stale_not_a_crash(tmp_path):
    root = _clone(tmp_path)
    os.remove(str(root / "client" / "shader.js"))
    reading = client_dist.check(str(root))          # must not raise
    assert reading["state"] == client_dist.STALE, reading
    assert any("shader.js" in s for s in reading["stale"]), reading


def test_serving_report_carries_the_dist_reading_on_its_EARLY_return(tmp_path):
    """The serving-time surface, checked where it is most likely to be lost.

    `serving_report` has several early returns — a target that is not a git
    checkout leaves on the first one. A reading attached at the bottom of the
    happy path would be absent from exactly those answers, which is the
    "a comparison that could not run must not look like one that ran and found
    nothing" rule the function's own docstring states, one field over.

    The precondition is the point: assert the git half really did bail early,
    or this passes on the ordinary path and proves nothing about the others.
    """
    rep = watch.serving_report(str(tmp_path))       # an empty dir, no .git
    assert rep["state"] == watch.SERVE_NOREPO, (
        "fixture did not take the early return (%r), so this says nothing "
        "about whether the reading survives one" % rep["state"])
    assert "client_dist" in rep, (
        "serving_report dropped the client/dist reading on its early return — "
        "the serving-time half of the staleness signal is missing exactly "
        "where the rest of the report could not be computed")
    assert rep["client_dist"]["state"] == client_dist.OK, rep["client_dist"]


# ── shipping: the half that has bricked the dashboard twice ──────────────


def test_deploy_declares_and_tracks_every_file_the_dist_check_reads(tmp_path):
    """#425/#480 — `just deploy` ships DATA_SIBLINGS, and it TREE-FILTERS at
    the rev (`dev/deploy_state.py:374`). So a path that is declared but
    untracked is dropped in silence: the deployed instance would simply not
    have it, and the staleness reading there would be red forever with no
    edit to explain it.

    Two assertions, because declaring and tracking fail differently and both
    fail quietly.
    """
    declared = set(watch.DATA_SIBLINGS)
    # DERIVED from the check's own input set, not listed again here. #630 P2
    # made DATA_SIBLINGS a second statement of "which files the build reads"
    # — unavoidably, because `just deploy` AST-parses that tuple and an
    # `ast.literal_eval` cannot run a glob. This is the assertion that keeps
    # the two in step: add `dev/build/src/foo.js` without adding a line to
    # DATA_SIBLINGS and this goes red HERE, at commit time, instead of on the
    # deployed instance as a staleness reading that never clears.
    inputs = client_dist.expected_inputs(str(ROOT))
    assert inputs, "the build's input set could not be derived"
    # Only the non-`client/` inputs: the client assets ship by their own
    # DATA_SIBLINGS lines already and are asserted by test_client_assets.
    want = ([client_dist.MANIFEST_REL]
            + [p for p in inputs if not p.startswith("client/")]
            + list(client_dist.OUTPUT_RELS))
    assert client_dist.NATIVE_ENTRY_REL in want, (
        "the native entry is not among the derived inputs — this check would "
        "pass while the runtime's own source went unshipped")
    missing = sorted(p for p in want if p not in declared)
    assert not missing, (
        "DATA_SIBLINGS does not declare %r — deploy would ship a snapshot "
        "whose client/dist check can never come back clean" % missing)

    for rel in want:
        assert (ROOT / rel).is_file(), "%s is declared but not on disk" % rel
        res = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(ROOT), "ls-files",
             "--error-unmatch", "--", rel],
            capture_output=True)
        assert res.returncode == 0, (
            "%s is not tracked by git. deploy ships COMMITTED state and "
            "tree-filters DATA_SIBLINGS at the rev, so an untracked entry is "
            "discarded without a word" % rel)


def test_deploy_stages_the_dist_subdirectory_for_real(tmp_path):
    """Not "the tuple looks right" — actually run the shipper.

    `client/dist/ds/` is the first two-deep data sibling in this repo, and the
    belief that `ship_siblings` makes parent directories is exactly the kind of
    belief that has bricked this dashboard twice. Verified against a scratch
    destination; never against the live deployment.

    Shipped from the INDEX tree, not `HEAD`, and the difference is the whole
    finding. Written against HEAD this went red on its first run — deploy
    tree-filters at the rev (`deploy_state.py:374`), so a path that is not
    in the rev is discarded without a word, which is precisely the silent drop
    the test exists to catch. Against HEAD it could also never go green in the
    commit that first adds dist, and a check that cannot pass until after the
    thing it gates has landed gates nothing. The index is what is about to
    become HEAD; in any committed checkout the two trees agree.
    """
    import sys
    sys.path.insert(0, str(ROOT / "dev"))
    import deploy_state

    res = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(ROOT), "write-tree"],
        capture_output=True, text=True)
    assert res.returncode == 0, (
        "cannot read the index as a tree: %s" % res.stderr.strip())
    rev = res.stdout.strip()
    assert rev, "git write-tree produced no object"
    # Precondition: the tree being shipped must actually carry the files, or
    # the shipper would be asked to move nothing and this would fail for a
    # reason that has nothing to do with subdirectories.
    listing = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(ROOT), "ls-tree", "-r",
         "--name-only", rev, "--", client_dist.DIST_DIR],
        capture_output=True, text=True).stdout.split()
    assert client_dist.MANIFEST_REL in listing, (
        "%s is not in the index — stage it before this can say anything"
        % client_dist.MANIFEST_REL)

    dest = tmp_path / "snap"
    dest.mkdir()
    written = deploy_state.ship_siblings(rev, str(dest), repo=ROOT)
    assert written, "ship_siblings staged nothing at all"
    for rel in [client_dist.MANIFEST_REL] + list(client_dist.OUTPUT_RELS):
        staged = dest / rel
        assert staged.is_file(), (
            "%s was not staged into the deploy snapshot — the deployed "
            "dashboard would not carry it" % rel)
        assert staged.read_bytes() == (ROOT / rel).read_bytes(), (
            "%s shipped with different bytes than the tree holds" % rel)


def test_autoreload_sees_a_rebuild(tmp_path):
    """`just build-client` must clear the startup red without a manual restart.

    The WARNING is read once per process, so a dev who rebuilds to fix a red
    would keep seeing the red until they restarted by hand — #397's
    "edit and see nothing" loop, one layer out.
    """
    watched = set(watch._autoreload_sources())
    for rel in (client_dist.MANIFEST_REL,) + client_dist.OUTPUT_RELS:
        assert os.path.join(watch.SELF_DIR, rel) in watched, (
            "%s is not in the autoreload watch set" % rel)
    # #630 P2 — and the INPUT side, which is the mirror case: watching the
    # outputs is what lets a rebuild CLEAR a red without a restart; watching
    # the sources is what lets an edit RAISE one. Editing the registry and
    # reloading otherwise gives a page reporting "dist is current" when it is
    # not, which is worse than no reading at all.
    native = client_dist.native_sources(str(ROOT))
    assert native, "no native sources to assert the watch set against"
    for rel in native:
        assert os.path.join(watch.SELF_DIR, rel) in watched, (
            "%s is a build input but is not watched — a dev editing the "
            "native runtime would see a stale dist reported as current" % rel)
    assert all(os.path.isabs(p) for p in watched), (
        "relative paths in the watch set survive until someone chdirs, and "
        "_sources_mtime's OSError handling would then hide that a file had "
        "stopped being watched at all")


def test_derived_output_is_not_counted_as_a_presentation_change():
    """`client/dist/` is under `client/`, and the styleguide audit classifies
    a commit as UI by that prefix — so without an exclusion every rebuild
    would demand a styleguide entry for a file nobody authored.

    Both directions asserted: a real asset must still classify as UI, or this
    would pass on a predicate that had stopped recognising anything.
    """
    import sys
    sys.path.insert(0, str(ROOT / "dev"))
    import styleguide_audit

    for rel in ("client/style.css", "client/components.js"):
        assert styleguide_audit.is_ui_asset(rel), (
            "%s stopped classifying as a UI asset — the audit would go green "
            "over real presentation changes" % rel)
    for rel in [client_dist.MANIFEST_REL] + list(client_dist.OUTPUT_RELS):
        assert not styleguide_audit.is_ui_asset(rel), (
            "%s classifies as a presentation change; a rebuild would demand "
            "a styleguide entry for generated output" % rel)


# ── the build itself ─────────────────────────────────────────────────────


def _node_modules():
    """Find this checkout's install, or the shared main-worktree install."""
    local = ROOT / "dev" / "build" / "node_modules"
    candidates = [local]
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=ROOT, capture_output=True, text=True)
    if common.returncode == 0:
        candidates.append(pathlib.Path(common.stdout.strip()).parent /
                          "dev" / "build" / "node_modules")
    return next((path for path in candidates
                 if (path / ".bin" / "esbuild").exists()), None)


def _configure_toolchain(build_client):
    node_modules = _node_modules()
    if node_modules is None:
        pytest.skip("dev/build/node_modules absent in this checkout and its "
                    "main worktree — `just build-client` installs it; the "
                    "reading this check needs is the toolchain's own output")
    build_client.NODE_MODULES = str(node_modules)
    build_client.ESBUILD = str(node_modules / ".bin" / "esbuild")
    return node_modules


def test_the_build_is_reproducible_and_the_committed_output_is_its_output(
        tmp_path):
    """Rebuild from a clean clone; the bytes must match what is committed.

    This is the check that caught the design's one real defect: esbuild writes
    the entry file's path into the bundle as a comment, and building from a
    randomly-named temp directory made every rebuild emit a different artifact.
    A committed artifact that changes on a no-op rebuild makes its own hash
    manifest churn — and a staleness signal that fires when nothing is stale
    is the false red that trains you to ignore the real one (lessons.md:157).
    Production line: `cwd=tmp` with a relative entry name in
    `dev/build_client.py`. Pass the absolute path instead and this goes red.
    """
    import sys
    sys.path.insert(0, str(ROOT / "dev"))
    import build_client
    toolchain = _configure_toolchain(build_client)

    root_a = _clone(tmp_path, "build-a")
    root_b = _clone(tmp_path, "build-from-a-different-absolute-path")
    # Exercise both resolution routes. The first checkout has its own local
    # node_modules path; the second has none and uses the invoking checkout's
    # fallback. Pointing both builds at one external path would let that path
    # leak into both outputs and make their equality a false green.
    local_node_modules = root_a / "dev" / "build" / "node_modules"
    shutil.copytree(toolchain, local_node_modules, symlinks=True)
    build_client.NODE_MODULES = str(local_node_modules)
    manifest_a = build_client.build(str(root_a))
    build_client.NODE_MODULES = str(toolchain)
    manifest_b = build_client.build(str(root_b))
    assert manifest_a["outputs"], "the first build recorded no outputs"
    assert manifest_b["outputs"], "the second build recorded no outputs"
    assert manifest_a["outputs"].keys() == manifest_b["outputs"].keys(), (
        "the two builds did not produce the same output inventory")
    for rel, digest in manifest_a["outputs"].items():
        assert digest == manifest_b["outputs"][rel], (
            "building %s from two different absolute paths, with and without "
            "local node_modules, produced different bytes — the artifact "
            "leaks its build location" % rel)
        committed = client_dist.sha256_file(str(ROOT / rel))
        assert committed is not None, "%s is not committed" % rel
        assert digest == committed, (
            "rebuilding %s produced different bytes than the committed "
            "artifact — either the build is not reproducible, or dist is "
            "stale and `just build-client` was not run" % rel)


def test_the_build_refuses_an_empty_asset_rather_than_bundling_a_blank(
        tmp_path):
    """The `_read_client` discipline (`watch.py:497`), one layer out: an empty
    input bundles to a valid, silent nothing, and the manifest would then
    faithfully record the hash of a blank."""
    import sys
    sys.path.insert(0, str(ROOT / "dev"))
    import build_client
    _configure_toolchain(build_client)

    root = _clone(tmp_path)
    (root / "client" / "shader.js").write_bytes(b"")
    with pytest.raises(build_client.BuildError) as exc:
        build_client.build(str(root))
    assert "shader.js" in str(exc.value), (
        "the refusal does not name the empty asset: %s" % exc.value)
