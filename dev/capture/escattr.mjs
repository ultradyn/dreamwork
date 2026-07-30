/* escattr — #374: `esc()` does not escape the double quote, so three
   attribute interpolations in the pip-button builder (pipBtn) are
   injectable. `esc = textContent → innerHTML` serialises TEXT, which
   escapes `&`, `<`, `>` but NOT `"` (the HTML serialiser only quotes
   inside attribute values). pipBtn interpolates that output into three
   `"`-delimited attributes: `aria-label="pop out ${esc(label)}"`,
   `data-pipurl="${esc(url)}"`, `data-piplabel="${esc(label)}"`. The file
   route passes the raw `/file?p=` query param as `label`, so a `"` in
   the query string closes the attribute early — `<`/`>` stay escaped so
   no new tag opens, but `onfocus=` on that same focusable button is
   enough. The fix is an `escA()` for attribute position (esc PLUS
   `"` → `&quot;`); `esc` keeps producing readable `"` for text.

   This guard is BORN-RED: against the unfixed `esc` the parsed DOM gains
   an injected `onfocus` attribute and the label attributes carry only the
   text before the first `"`; against `escA` the attribute set is exactly
   the six the builder emits and each label attribute carries the whole
   payload as ONE value. The assertion is about the PARSED DOM's attribute
   set — never the HTML string, which looks plausible either way (the
   filing named this form).

   #556 — the SECOND hop. #374 escA-locked the pip button's own attributes,
   but clicking it hands the payload to `popoutDoc`, which rebuilt
   `<iframe src title>` from `pip.dataset.pipurl` / `pip.dataset.piplabel`.
   Those dataset reads parse escA's `&quot;` BACK to a raw `"`, so the whole
   payload re-enters as one value and `esc` (no `"` escape) on `title` let
   the quote break the attribute open a second time — `onfocus` rode in on
   the popout window's iframe, one hop past the fix. The same `escA` closes
   it: popoutDoc now escA-encodes both `src` and `title`. This guard drives
   the click and reads the PARSED iframe attribute set on the popout
   document (absence-first: the popout opened AND holds an iframe, else the
   phase is named-vacuous). Capture mechanism: Document Picture-in-Picture
   (openPopout's first choice) is a window a Playwright context cannot reach
   via waitForEvent('page'), so the phase neutralises
   `window.documentPictureInPicture` up front to force openPopout's
   `window.open` fallback — a real, tracked popup page — and reads the parsed
   iframe there (never the HTML string).

   usage: node escattr.mjs <outdir> [port]   (recipe-driven: connects to
          the watch server the `just guards` recipe already holds on <port>) */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { outdir } from './outdir.mjs';
import { makeReporter } from './report.mjs';
import { mkdirSync } from 'node:fs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39891';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });

const { ok, present, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: '/file?p=<quote payload> — the file-view pip button (pipBtn) renders ' +
          'the raw query param as its label across three `"`-delimited attributes, ' +
          'then a CLICK of that button opens the popout whose iframe re-interpolates ' +
          'the same payload (two hops, one payload)',
  traceWindow: 'static read of the parsed DOM after render readiness; the popout ' +
               'phase also reads the popup document after the click — no motion trace',
});

// The payload carries a `"` to break the attribute and an `onfocus="…" ` to
// inject a second attribute. It is the test INPUT, not a fixture-derived
// literal: deriving the expected label from PAYLOAD below means the check
// cannot expiry-date on a fixture change. `=` and the token make the injected
// attribute name+value crisp to assert on.
const PAYLOAD = 'x" onfocus="window.__pwned=1';
// The six attributes the builder emits, in order. Anything else on the parsed
// button is an injection (unfixed `esc` adds `onfocus`).
const EXPECTED = ['class', 'type', 'title', 'aria-label', 'data-pipurl', 'data-piplabel'];

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1000, height: 820 } });
p.on('pageerror', e => errs.push(String(e)));

// encodeURIComponent the payload for the URL: the browser sends the encoded
// form, URLSearchParams.get('p') decodes it back, so v.param (the label) is
// the raw payload — the `"` reaches esc/escA exactly as a crafted link would.
await p.goto(`${BASE}/file?p=${encodeURIComponent(PAYLOAD)}`, { waitUntil: 'networkidle' });
await waitFor(p, '.pipbtn');

/* absence-first: a build without the pip button is a named FAIL in seconds,
   not a thrown evaluate over a null subject. */
if (!(await present(p, '#meta .pipbtn', 'the file-view pip button (#meta .pipbtn)'))) {
  await br.close(); finish(); process.exit(1);
}

/* Read the PARSED DOM — the attribute set the browser actually built — never
   the HTML string. This is the decision the guard is named for: `esc` leaves
   `"` raw, so the parsed button carries an injected `onfocus` and the label
   attributes stop at the first `"`. Capture the FULL attribute map so a value
   scan (the injected token) is over every attribute, not just the three the
   builder means to emit. */
const btn = await p.evaluate(() => {
  const b = document.querySelector('#meta .pipbtn');
  if (!b) return null;
  const attrs = b.getAttributeNames();
  const values = {};
  for (const a of attrs) values[a] = b.getAttribute(a);
  return { attrs, values };
});
notes.push('parsed button: ' + JSON.stringify(btn));

// (c) precondition — the button really rendered AND carries the label
// attribute the payload targets, else every check below is about a button
// that has no label interpolation to poison (vacuous). This is the rule the
// repo states: assert in the check the precondition the check depends on.
ok('precondition: the pip button rendered with a data-piplabel (else vacuous)',
   !!btn && Object.prototype.hasOwnProperty.call(btn.values, 'data-piplabel'));

if (!btn || !Object.prototype.hasOwnProperty.call(btn.values, 'data-piplabel')) {
  await br.close(); finish(); process.exit(1);
}

// (a) the attribute set contains NO injected attribute. The set difference
// against the builder's six is the injection; unfixed `esc` yields `onfocus`.
// This is the definitive detector the filing names (the attribute SET), not a
// value scan: data-pipurl legitimately echoes the payload as the popout URL
// (`/file?p=<encoded payload>`), so a value scan for any payload token would
// false-positive on the FIXED code. Attribute injection always adds an
// ATTRIBUTE NAME, so the set difference is both necessary and sufficient.
const injected = btn.attrs.filter(a => !EXPECTED.includes(a));
ok('no injected attribute on the pip button (attribute set = builder six)',
   injected.length === 0);
ok('no `onfocus` attribute (the quote broke the attribute open)',
   !btn.attrs.includes('onfocus'));

// (b) the label attributes carry the WHOLE payload as ONE value. Unfixed
// `esc` truncates both at the first `"`; `escA` keeps the `"` inside as &quot;
// so the parsed value is the literal payload. aria-label is "pop out " + label.
ok('data-piplabel carries the whole payload as one value (not truncated at ")',
   btn.values['data-piplabel'] === PAYLOAD);
ok('aria-label carries "pop out " + the whole payload as one value',
   btn.values['aria-label'] === 'pop out ' + PAYLOAD);
// the url side is also attribute-position; assert it survived intact too
ok('data-pipurl survived (also attribute position, now escA)',
   typeof btn.values['data-pipurl'] === 'string' && btn.values['data-pipurl'].length > 0);

ok('no page errors', errs.length === 0);

/* ── popout phase (#556): the SECOND hop. #374 escA-locked the pip button's
   own attributes, but the click hands the payload to popoutDoc, which
   rebuilt `<iframe src title>` from `pip.dataset.pipurl`/`pip.dataset.piplabel`.
   Those dataset reads parse escA's `&quot;` BACK to a raw `"`, so the whole
   payload re-enters as one value — and `esc` on `title` (no `"` escape) let
   the quote break the attribute open again, `onfocus` riding in on the
   popout's iframe. Read the PARSED iframe attribute set on the popout
   document, never the HTML string (the filing named this form for the
   first hop; the second hop is the same decision on a different document). */

// Capture mechanism: Document Picture-in-Picture (openPopout's first choice)
// is a window a Playwright context CANNOT reach via waitForEvent('page'), so
// neutralise it up front to force openPopout's `window.open` fallback — a
// real, tracked popup page. This is deterministic regardless of whether the
// headless build exposes documentPictureInPicture, and it is the path the
// brief sanctions ("driving the window.open fallback").
await p.evaluate(() => {
  if (window.documentPictureInPicture) delete window.documentPictureInPicture;
});

// Set up the popup listener BEFORE the click: openPopout is async (awaits
// ensureData), so window.open fires a tick after the click — but the
// 'page' event must be subscribed first or it races.
const popupP = p.context().waitForEvent('page', { timeout: 15000 });
await p.click('#meta .pipbtn');
const popup = await popupP;
const iframeReady = await waitFor(popup, 'iframe', 15000);

// (c) absence-first precondition: a build where the popout did not open, or
// opened without an iframe, is a named FAIL — every check below else judges
// a popup with no iframe interpolation to read (vacuous). This is the rule:
// assert in the check the precondition the check depends on.
ok('precondition: the popout opened and contains an iframe (else vacuous)',
   iframeReady && !!(await popup.evaluate(() => document.querySelector('iframe'))));
if (!iframeReady) {
  await popup.close().catch(() => {}); await br.close(); finish(); process.exit(1);
}

// Read the PARSED iframe's attribute set on the popout document — what the
// browser actually built there. Unfixed `esc` on title yields an injected
// `onfocus` and truncates title at the first `"`; escA keeps the `"` inside
// so the set is exactly {src,title} and title carries the whole payload as
// ONE value. Capture the FULL attribute map so a value scan (the injected
// token) is over every attribute, mirroring the first hop.
const ifr = await popup.evaluate(() => {
  const f = document.querySelector('iframe');
  if (!f) return null;
  const attrs = f.getAttributeNames();
  const values = {};
  for (const a of attrs) values[a] = f.getAttribute(a);
  return { attrs, values };
});
notes.push('parsed popout iframe: ' + JSON.stringify(ifr));

// derive the expected src at runtime from PAYLOAD, not a literal: data-pipurl
// was '/file?p=' + encodeURIComponent(payload) at pipBtn time, escA/esc leave
// %22 intact, so a fixture change cannot expiry-date this check.
const IFR_EXPECTED = ['src', 'title'];
const EXPECTED_SRC = '/file?p=' + encodeURIComponent(PAYLOAD);

// (a) the attribute set contains NO injected attribute — the definitive
// detector (an injection always adds an ATTRIBUTE NAME). Unfixed esc yields
// `onfocus` here.
const ifrInjected = ifr ? ifr.attrs.filter(a => !IFR_EXPECTED.includes(a)) : ['<no iframe>'];
ok('no injected attribute on the popout iframe (set = {src,title})',
   !!ifr && ifrInjected.length === 0);
ok('no `onfocus` on the popout iframe (the quote broke title open)',
   !!ifr && !ifr.attrs.includes('onfocus'));

// (b) title carries the WHOLE payload as ONE value. Unfixed esc truncates at
// the first `"`; escA keeps it inside as &quot; so the parsed value is the
// literal payload. This is the live vector the brief names.
ok('popout iframe title carries the whole payload as one value (not truncated at ")',
   !!ifr && ifr.values['title'] === PAYLOAD);

// src is also attribute position; it survives because encodeURIComponent
// quoted the `"` as %22, but escA is correct-by-position there regardless —
// assert the exact value (derived from PAYLOAD) so the check holds if the
// file route's URL shape ever changes.
ok('popout iframe src survived (attribute position; " arrived as %22)',
   !!ifr && ifr.values['src'] === EXPECTED_SRC);

await popup.close().catch(() => {});
await br.close();
finish();
