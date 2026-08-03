/* filehl — #351: /file highlights source, runs wider, and does not wrap.

   His words, typed from /file?p=lint.py: "syntax highlighting for source
   code files, and a bit wider of a body + no line wrapping." Three claims,
   each asserted in the one form that can fail on the bug it names:

     - **The markup is the server's #339 scanner, and the bytes are still
       the file.** tok- spans are counted (not "present"), the distinct
       token KINDS are derived from the fixture's own bytes and asserted
       (a fixture that stopped exercising the scanner must not pass), and
       pre.textContent is compared to the bytes on disk — the same
       byte-fidelity bar #252 set for the Source pane, held on the
       highlighted pane too.
     - **The colours are colours.** At least three DISTINCT computed
       colours among the token kinds on screen, and a comment is italic —
       a palette that collapsed to one colour is the pane #339 was asked
       to replace, and an end-state "spans exist" check cannot see it.
     - **Wider body, no wrap, no sideways page.** `.wrap` on /file is
       measurably wider than the SAME browser's dashboard column (derived,
       never a literal); the pane's scrollWidth exceeds its clientWidth
       because the fixture's long line is longer than the column (that
       precondition is derived from the bytes on disk, not hoped); and
       the DOCUMENT does not scroll sideways at desktop or at 390px —
       watch-design.md's contract is that wide content scrolls inside its
       own container.

   The #252 collision is guarded at the source: a markdown file's Source
   mode holds NO tok- spans even on a server that highlights, because that
   pane's bytes are the point of the mode. An unknown extension renders
   plain with zero element children — never guessed (#339's rule).

   The width GLIDE onto the route is deliberately not re-traced here: it is
   body.wsliding, the review route's own mechanism, reused verbatim and
   guarded by headertravel/reviewsplit; what this guard owes is that a
   DIRECT load arrives already wide (no first-paint animation), which is a
   static read. Reduced motion is parity: same spans, same bytes, same
   layout, no ghost and no wsliding.

   THIS GUARD BUILDS ITS OWN TARGET and takes its own ephemeral port: the
   shared fixture has no source file whose longest line provably overflows
   the widened column, and that overflow is a precondition here, not a
   nice-to-have.

   usage: node filehl.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync, readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';
import { serveVerified } from './serve.mjs';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv);
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
const { ok, present, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: 'a python file at /file (desktop 1000px and phone 390px, normal ' +
          'and reduced motion), the dashboard beside it for the width ' +
          'comparison, a .txt for the never-guess plain path, and a ' +
          'markdown file in Source mode for the #252 collision',
  traceWindow: 'no motion trace: this surface is static content — the ' +
               'highlight is server-built markup and the wide column is a ' +
               'direct load (body.wsliding, the glide, is the review ' +
               'route\'s guarded mechanism reused verbatim). Every check ' +
               'is a settled-state read.',
});
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
// OWN-SERVER GUARD: the port is ALWAYS ephemeral; argv[3] is deliberately
// ignored (fileview.mjs carries the #461/#471 reasoning verbatim).
const PORT = await freePort();

/* ── the target ───────────────────────────────────────────────────────────
   The python file must do THREE jobs at once: tokenise into several kinds
   (so "it coloured something" is not one fallback class), carry bytes a
   naive path would mangle (< & "), and hold ONE LINE longer than the
   widened column is wide — because horizontal overflow inside the pane is
   the whole nowrap claim, and a guard whose fixture fits never tests it. */
const LONG = '    return compute_the_thing(' +
  'alpha_value, beta_value, gamma_value, delta_value, epsilon_value, ' +
  'zeta_value, eta_value)  # this line is deliberately far too long to fit';
const PY = [
  '# tool.py — a small source file for the highlighter',
  'import os',
  '',
  'LIMIT = 42  # a number and a comment, side by side',
  '',
  'def compute_the_thing(alpha_value, beta_value, gamma_value, delta_value,',
  '                      epsilon_value, zeta_value, eta_value):',
  '    """Return the <tagged> & "quoted" result, or None."""',
  LONG,
  '',
  'class Tool:',
  '    def run(self) -> bool:',
  '        return compute_the_thing(1, 2, 3, 4, 5, 6, 7) > LIMIT',
  '',
].join('\n');
const PY_PATH = 'tool.py';
const TXT_PATH = 'notes.txt';
// a .txt whose bytes WOULD tokenise if anyone guessed — the never-guess
// check is only meaningful against content that wants colouring
const TXT = 'def f():\n    return "not python, whatever it looks like"\n';
const MD_PATH = 'doc.md';
const MD = '# doc\n\n```python\ndef f():\n    pass\n```\n';

const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
writeFileSync(join(DIR, PY_PATH), PY);
writeFileSync(join(DIR, TXT_PATH), TXT);
writeFileSync(join(DIR, MD_PATH), MD);
// the bytes as the guard compares them: read back off disk, so the
// comparison is against the file rather than against the string above
const ON_DISK = readFileSync(join(DIR, PY_PATH), 'utf8');

const srv = await serveVerified(DIR, PORT);
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
const BASE = `http://127.0.0.1:${PORT}`;
const URL_PY = `${BASE}/file?p=${encodeURIComponent(PY_PATH)}`;

/* one read of everything the pane claims, so the assertions below are about
   the page and not about six round-trips' worth of timing */
const READ = `(() => {
  const pre = document.querySelector('#filebody > pre');
  const wrap = document.querySelector('.wrap');
  const de = document.documentElement;
  const spans = pre ? [...pre.querySelectorAll('[class*="tok-"]')] : [];
  const kinds = {};
  for (const s of spans) {
    const k = [...s.classList].find(c => c.startsWith('tok-'));
    if (!kinds[k]) kinds[k] = { n: 0, colour: null, italic: false };
    kinds[k].n++;
    const cs = getComputedStyle(s);
    kinds[k].colour = cs.color;
    kinds[k].italic = kinds[k].italic || cs.fontStyle === 'italic';
  }
  return {
    hasPre: !!pre,
    code: pre ? !!pre.querySelector(':scope > code.language-python') : false,
    nTok: spans.length,
    kinds,
    text: pre ? pre.textContent : null,
    preKids: pre ? pre.children.length : null,
    preWS: pre ? getComputedStyle(pre).whiteSpace : null,
    preScrollW: pre ? pre.scrollWidth : 0,
    preClientW: pre ? pre.clientWidth : 0,
    wrapW: wrap ? wrap.getBoundingClientRect().width : 0,
    pageOverflowX: de.scrollWidth - de.clientWidth,
    bodyFile: document.body.classList.contains('file'),
    bodyWsliding: document.body.classList.contains('wsliding'),
  };
})()`;

const browser = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-webgl'],
  ignoreDefaultArgs: ['--hide-scrollbars'],
});

/* Refuse to grade horizontal geometry through Playwright's normally hidden
   scrollbar. Both halves matter: a zero-width reading on a page with no
   vertical overflow means the instrument could not run, not that it passed. */
{
  const pctx = await browser.newContext({ viewport: { width: 1000, height: 900 } });
  const ppage = await pctx.newPage();
  await ppage.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  const sb = await ppage.evaluate(() => ({
    width: window.innerWidth - document.documentElement.clientWidth,
    scrollH: document.documentElement.scrollHeight,
    innerH: window.innerHeight,
  }));
  notes.push('scrollbar precondition: ' + JSON.stringify(sb));
  ok(`scrollbar precondition: dashboard genuinely overflows vertically `
   + `(${sb.scrollH} > ${sb.innerH}) — else scrollbar width could not be tested`,
     sb.scrollH > sb.innerH);
  ok(`scrollbar precondition: this browser's scrollbar consumes width `
   + `(sb=${sb.width}px) — else --hide-scrollbars survived ignoreDefaultArgs `
   + `and every horizontal-overflow verdict below is blind`,
     sb.scrollH > sb.innerH && sb.width > 0);
  await pctx.close();
}

const ctx = await browser.newContext({ viewport: { width: 1000, height: 900 } });
const page = await ctx.newPage();
page.on('pageerror', e => errs.push(String(e)));
await page.goto(URL_PY, { waitUntil: 'networkidle' });
await page.waitForSelector('#filebody > pre', { timeout: 15000 });
await sleep(600);

if (!(await present(page, '#filebody > pre', 'the highlighted source pane'))) {
  try { srv.kill(); } catch (e) {}
  await browser.close(); finish();
} else {

const r = await page.evaluate(READ);
await page.screenshot({ path: `${OUT}/filehl-desktop.png` });

// ── the highlight ─────────────────────────────────────────────────────────
ok(`the pane carries the server's scanner output (${r.nTok} tok- spans ` +
   `inside a <code class="language-python">), not a second tokeniser`,
   r.hasPre && r.code && r.nTok >= 10);
const kindNames = Object.keys(r.kinds).sort();
ok(`...in SEVERAL token kinds (${kindNames.join(' ')}), so "it coloured ` +
   `something" cannot pass on a lone fallback class`,
   kindNames.length >= 4);
ok('...and the fixture really exercised the scanner, else the count above ' +
   'is vacuous (the bytes on disk hold a comment, a string, a keyword, ' +
   'a number and a call)',
   ON_DISK.includes('# tool.py') && ON_DISK.includes('"""') &&
   ON_DISK.includes('def ') && ON_DISK.includes('42') &&
   ON_DISK.includes('compute_the_thing('));
ok(`the bytes are STILL the file (textContent ${(r.text || '').length} of ` +
   `${ON_DISK.length} chars) — the #252 fidelity bar, held on the ` +
   `highlighted pane`,
   r.text === ON_DISK);
const colours = new Set(Object.values(r.kinds).map(k => k.colour));
ok(`the kinds are DISTINCTLY coloured (${colours.size} colours across ` +
   `${kindNames.length} kinds) — spans that all compute to one colour are ` +
   `the unhighlighted pane with extra markup`,
   colours.size >= 3);
ok(`a comment reads as a comment (italic: ` +
   `${(r.kinds['tok-com'] || {}).italic})`,
   r.kinds['tok-com'] && r.kinds['tok-com'].italic === true);

// ── wider, nowrap, and the sideways contract ─────────────────────────────
ok(`the route widens the column (body.file, .wrap ${r.wrapW.toFixed(0)}px)`,
   r.bodyFile && r.wrapW > 0);
ok('...and a DIRECT load arrives already wide — no wsliding, no first-paint ' +
   'animation (the glide is for route changes only)',
   !r.bodyWsliding);
const dash = await ctx.newPage();
await dash.goto(BASE + '/', { waitUntil: 'networkidle' });
await sleep(600);
const dashW = await dash.evaluate(() =>
  document.querySelector('.wrap').getBoundingClientRect().width);
await dash.close();
ok(`...wider than the SAME browser's dashboard column ` +
   `(${r.wrapW.toFixed(0)}px vs ${dashW.toFixed(0)}px — a derived ` +
   `comparison, never a literal)`,
   r.wrapW > dashW + 50);
ok(`the pane declares nowrap (white-space: ${r.preWS})`, r.preWS === 'pre');
const longest = Math.max(...ON_DISK.split('\n').map(l => l.length));
ok(`the fixture really overflows the column, else "scrolls inside itself" ` +
   `is vacuous (longest line ${longest} chars; pane ${r.preClientW}px ` +
   `client vs ${r.preScrollW}px scroll)`,
   longest > 100 && r.preScrollW > r.preClientW);
ok(`...and the overflow stays INSIDE the pane: the document does not ` +
   `scroll sideways (${r.pageOverflowX}px)`,
   r.pageOverflowX <= 0);

// ── narrow viewport: the wrap trade, measured where it bites ─────────────
const phone = await browser.newContext({ viewport: { width: 390, height: 844 } });
const pp = await phone.newPage();
pp.on('pageerror', e => errs.push(String(e)));
await pp.goto(URL_PY, { waitUntil: 'networkidle' });
await pp.waitForSelector('#filebody > pre', { timeout: 15000 });
await sleep(600);
const rp = await pp.evaluate(READ);
await pp.screenshot({ path: `${OUT}/filehl-390.png` });
ok(`390px: the pane still scrolls inside itself (scroll ${rp.preScrollW}px ` +
   `vs client ${rp.preClientW}px)`,
   rp.preScrollW > rp.preClientW);
ok(`390px: ...and the PAGE still does not scroll sideways ` +
   `(${rp.pageOverflowX}px overflow; wrap ${rp.wrapW.toFixed(0)}px in a ` +
   `390px viewport)`,
   rp.pageOverflowX <= 0 && rp.wrapW <= 390);
ok(`390px: the highlight and the bytes survive the narrow viewport ` +
   `(${rp.nTok} spans)`,
   rp.nTok === r.nTok && rp.text === ON_DISK);
await phone.close();

// ── never guess, and the #252 collision ──────────────────────────────────
const pt = await ctx.newPage();
await pt.goto(`${BASE}/file?p=${encodeURIComponent(TXT_PATH)}`, { waitUntil: 'networkidle' });
await pt.waitForSelector('#filebody > pre', { timeout: 15000 });
await sleep(400);
const plain = await pt.evaluate(READ);
ok('a .txt whose bytes WOULD tokenise renders plain, so "no spans" is the ' +
   'never-guess rule and not an easy fixture',
   TXT.includes('def ') && plain.hasPre && plain.nTok === 0 &&
   plain.preKids === 0 && plain.text === TXT);
await pt.close();

const ms = await ctx.newPage();
/* OFFER highlighted markup for a markdown file. The server's extension map
   never would — but #252's note about this collision makes the render-plain
   condition EXPLICIT precisely so the guarantee does not depend on what the
   server chose to send, so this check must not depend on it either. The
   production line this reds on is buildFile's renderPlain gate (proved:
   deleting it renders the shimmed markup below and this check fails). The
   shim delivers `hl`; only the production gate decides whether it shows. */
await ms.route('**/filedata*', async route => {
  const res = await route.fetch();
  const j = await res.json();
  j.hl = '<pre><code class="language-python">' +
         '<span class="tok-kw">def</span></code></pre>';
  route.fulfill({ status: 200, contentType: 'application/json',
                  body: JSON.stringify(j) });
});
await ms.goto(`${BASE}/file?p=${encodeURIComponent(MD_PATH)}&view=source`,
              { waitUntil: 'networkidle' });
await ms.waitForSelector('#filebody > pre', { timeout: 15000 });
await sleep(400);
const msrc = await ms.evaluate(READ);
ok('a markdown file in SOURCE mode shows no tokeniser output even when the ' +
   'server OFFERED it (#252: those bytes are the point of the mode)',
   msrc.hasPre && msrc.nTok === 0 && msrc.preKids === 0 && msrc.text === MD);
await ms.close();

// ── reduced motion: parity, not degradation ──────────────────────────────
const rc = await browser.newContext({
  viewport: { width: 1000, height: 900 }, reducedMotion: 'reduce' });
const rm = await rc.newPage();
rm.on('pageerror', e => errs.push(String(e)));
await rm.goto(URL_PY, { waitUntil: 'networkidle' });
await rm.waitForSelector('#filebody > pre', { timeout: 15000 });
await sleep(600);
const rr = await rm.evaluate(READ);
ok(`reduced motion: identical surface — same ${rr.nTok} spans, same bytes, ` +
   `same width, no wsliding, no ghost`,
   rr.nTok === r.nTok && rr.text === ON_DISK &&
   Math.abs(rr.wrapW - r.wrapW) < 1 && !rr.bodyWsliding &&
   !(await rm.evaluate(() => !!document.querySelector('.ghost'))));
await rc.close();

try { srv.kill(); } catch (e) {}
await browser.close();
ok('no page errors on any phase', errs.length === 0);
notes.push(`token kinds: ${kindNames.map(k => `${k}×${r.kinds[k].n}`).join(' ')}`);
notes.push(`colours: ${[...colours].join(' ')}`);
notes.push(`wrap widths: file ${r.wrapW.toFixed(0)}px vs dashboard ${dashW.toFixed(0)}px`);
notes.push(`pane overflow: ${r.preScrollW - r.preClientW}px at desktop, ` +
           `${rp.preScrollW - rp.preClientW}px at 390px`);
finish();
}
