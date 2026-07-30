/* pip83 — the popout-pip (Picture-in-Picture / window.open affordance) on
   review artifacts and on the file/review views. Clicking a review's pip
   floats the artifact in an identity-headed window that stays put while the
   main tab navigates.

   HARNESS-CONTRACT REPAIR (#538): the guard died at `p.click('#sections
   .pipbtn')` with a Playwright timeout — `#sections .pipbtn` matches the FIRST
   pip in the dashboard, which is a file-LINK pip inside the questions
   `<details class="qsec">` (may be collapsed, and never opens a review popout),
   not the review popout pip the guard means to drive. The popout identity
   check was the same class of expiry: `/dreamwork|vtarget/` matched the
   project BASENAME when the target was the live repo, but against any other
   target (a fixture, a worktree) the basename differs and the check reddens
   on a correct popout.

   Both are derived now: the pip driven is the one whose `data-pipurl` is the
   REVIEW artifact's `/reviewraw?p=<name>` (derived from data.reviews), and the
   popout identity is checked against data.target (the `.ppath`) and the review
   name (the `.ptitle`) — not a literal. A dashboard without a review pip, or a
   popout that does not carry the project path / embed the artifact, is a named
   FAIL in seconds (absence-first via present()), not a thirty-second timeout.

   usage: node pip83.mjs <outdir> [port] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { outdir } from './outdir.mjs';
import { makeReporter } from './report.mjs';
import { mkdirSync } from 'node:fs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`; const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, present, declare, finish, checks, notes, errs } = makeReporter();
declare({
  drives: '/ (dashboard) — click a REVIEW artifact pip to float its popout; ' +
          'then /file and /review views carry a #meta pip',
  traceWindow: 'static reads after ~400ms popout settle; no motion trace',
});

/* ── derive the review popout target from data, never assume a positional
   `#sections .pipbtn`. The first `.pipbtn` in #sections is a file-link pip in
   the questions section, not the review popout; clicking it reddens on a
   hidden element and never proves the review popout. The review pip's
   data-pipurl is `/reviewraw?p=<name>` (watch.py pipBtn + the reviews row). */
const d = await (await fetch(`${BASE}/data.json`)).json();
const reviews = Array.isArray(d.reviews) ? d.reviews : [];
const review = reviews[0] || null;
const reviewName = review ? review.name : null;
const target = typeof d.target === 'string' ? d.target : null;
// popoutShell derives base from the target path the same way (watch.py openPopout)
const base = target ? (target.split('/').filter(Boolean).pop() || 'dreamwork') : null;
ok('precondition: the fixture ships a review artifact to pop out', !!reviewName);
ok('precondition: data carries a served target path (the popout identity)', !!target);

if (!reviewName || !target) { finish(); process.exit(1); }

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1000, height: 820 } });
p.on('pageerror', e => errs.push(String(e)));

await p.goto(BASE + '/', { waitUntil: 'networkidle' });
// #536 render readiness — wait for the .pipbtn affordance the guard reads first (#428 class)
await waitFor(p, '.pipbtn');

/* Find the REVIEW popout pip in the dashboard by its data-pipurl (the review
   artifact's /reviewraw), and prove it is the one that opens a popout — not
   the file-link pip that happens to be first in #sections. */
const dash = await p.evaluate(reviewName => {
  const pips = [...document.querySelectorAll('#sections .pipbtn')].map(b => ({
    url: b.getAttribute('data-pipurl') || '',
    label: b.getAttribute('data-piplabel') || '',
  }));
  const reviewPip = pips.find(b =>
    b.url.includes('/reviewraw') &&
    (b.label === reviewName || b.url.includes(encodeURIComponent(reviewName)) || b.url.includes(reviewName)));
  return { pipCount: pips.length, reviewPipUrl: reviewPip ? reviewPip.url : null,
    hasFileLinkPip: pips.some(b => b.url.startsWith('/file?')) };
}, reviewName);
notes.push('dash: ' + JSON.stringify(dash));
ok('a REVIEW artifact pip renders on the dashboard (data-pipurl=/reviewraw, derived)',
   !!dash.reviewPipUrl);
ok('pip buttons render on the dashboard (>=1)', dash.pipCount >= 1);
await p.screenshot({ path: `${OUT}/dashboard-pip.png` });

// absence-first: a dashboard without the review popout pip is a named FAIL,
// not a click timeout on a hidden file-link pip.
const reviewPipSel = '#sections .pipbtn[data-pipurl*="reviewraw"]';
if (!(await present(p, reviewPipSel, 'the review popout pip (data-pipurl*="reviewraw")'))) {
  await br.close(); finish(); process.exit(1);
}

/* click the REVIEW pip -> popout. The popout is a floated window (Document PiP
   or window.open) carrying the project identity (.ptitle/.ppath) and an iframe
   of the artifact at its data-pipurl. */
const popupP = p.waitForEvent('popup', { timeout: 3000 }).catch(() => null);
await p.locator(reviewPipSel).first().click();
const popup = await popupP;
let popInfo = '(none)';
if (popup) {
  await popup.waitForLoadState('domcontentloaded').catch(() => {});
  await sleep(400);
  popInfo = await popup.evaluate(() => ({
    ident: (document.querySelector('.ptitle')?.textContent || '').trim(),
    path: (document.querySelector('.ppath')?.textContent || '').trim(),
    hasIframe: !!document.querySelector('iframe'),
    iframeSrc: document.querySelector('iframe')?.getAttribute('src') || '',
  }));
  await popup.screenshot({ path: `${OUT}/popout-doc.png` }).catch(() => {});
}
notes.push('popout: ' + JSON.stringify(popInfo));

// file view pip + review view pip present?
await p.goto(`${BASE}/file?p=.dreamwork/lessons.md`, { waitUntil: 'networkidle' }); await sleep(500);
const filePip = await p.evaluate(() => !!document.querySelector('#meta .pipbtn'));
await p.goto(`${BASE}/review?p=${encodeURIComponent(reviewName)}`, { waitUntil: 'networkidle' }); await sleep(500);
const reviewViewPip = await p.evaluate(() => !!document.querySelector('#meta .pipbtn'));
notes.push(`filePip=${filePip}  reviewViewPip=${reviewViewPip}`);

ok('the file view carries a #meta pip button', filePip);
ok('the review view carries a #meta pip button', reviewViewPip);
if (popup) {
  // identity checked against data, not a project-basename literal: the popout's
  // .ppath IS data.target, and .ptitle names the artifact it floats.
  ok('popout carries the project target path (.ppath = data.target)',
     popInfo.path === target);
  ok('popout names the artifact in its header (.ptitle includes the review name)',
     (popInfo.ident || '').includes(reviewName));
  ok('popout embeds the artifact in a /reviewraw iframe',
     popInfo.hasIframe && (popInfo.iframeSrc || '').includes('/reviewraw'));
} else {
  ok('the review pip opened a popout window', false);
}
ok('no page errors', errs.length === 0);

await br.close();
finish();
