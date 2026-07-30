/* qgroup — #564: the dashboard's two questions parts are grouped under one
   visible "Q & A" section, with the section's own top margin as the real gap
   above them.

   His words (journal ord=61): *"the 2 questions parts should be under a
   'Q & A' section — currently there's no gap between the section above them
   and them."* Previously qSection (a bare <details>, .25rem margin) and the
   dim /answers link sat directly under the chats list with no separation.

   The fix is one section header — `label('Q & A')` — because label() IS the
   dashboard's section idiom and its margin-top (var(--space), the section-
   rhythm token) IS the gap. This guard pins the two halves of that claim
   against the REAL served page:

     GROUPING — a "Q & A" .label is a direct child of #sections, and BOTH
       questions parts (.qsec then the /answers link) follow it in DOM order.
     THE GAP — that label's computed margin-top equals every other section
       label's (it carries the same var(--space) rhythm as dreams), and is
       non-trivial. A Q&A header that lost its section class, or a gap that
       collapsed, reds here.

   This lane's gap is achieved ENTIRELY on the questions side; chatList is
   lane-562chat's live region. The shared fixture carries no chats, so this
   guard checks the grouping + gap against the section ABOVE (dreams) rather
   than against a chats region it must not depend on. The "after the chats
   region" ordering is pinned by the pytest render test through the real
   buildDashboard assembly, which stubs chatList to a sentinel on purpose.

   Production line the red-proof names (watch.py buildDashboard):
     the `h += label('Q & A');` statement between the chatList call and
     qSection. Removing it drops the header and the gap; the presence check
     and the margin check both red.

   usage: node qgroup.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
import { mkdirSync } from 'node:fs';
import { outdir } from './outdir.mjs';

const OUT = outdir(process.argv), PORT = process.argv[3] || '39893';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, notes, errs } = makeReporter();
declare({
  drives: '/ dashboard: the "Q & A" section header groups both questions ' +
          'parts (.qsec + the /answers link) and carries the section gap',
  traceWindow: 'static reads after the dashboard settles — no motion trace ' +
               '(the header is static structure under the settled tick re-render)',
});

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const ctx = await br.newContext({ viewport: { width: 1100, height: 900 } });
const p = await ctx.newPage();
p.on('pageerror', e => errs.push(String(e)));

await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
// #507 render readiness — wait for the questions section the guard reads
await waitFor(p, '.qsec');

/* One walk of #sections' direct children, in DOM order, with the computed
   margin-top of each .label. The margin is the load-bearing half: it is
   what makes the header a real section gap rather than a bare line. */
const read = await p.evaluate(() => {
  const root = document.getElementById('sections');
  if (!root) return { err: 'no #sections' };
  const children = [...root.children];
  const markers = children.map(c => {
    if (c.classList.contains('label'))
      return { kind: 'label', text: (c.textContent || '').trim() };
    if (c.classList.contains('qsec'))
      return { kind: 'qsec' };
    // the /answers dim link line
    const a = c.querySelector(':scope > a[href="/answers"]');
    if (a) return { kind: 'answers' };
    return { kind: 'other', tag: c.tagName, cls: c.className };
  });
  const margin = el => {
    if (!el) return null;
    return parseFloat(getComputedStyle(el).marginTop);
  };
  const find = (kind, text) =>
    children.find((c, i) =>
      markers[i].kind === kind && (!text || markers[i].text === text));
  const qa = find('label', 'Q & A');
  const dreams = children.find((c, i) =>
    markers[i].kind === 'label' && /^dreams/.test(markers[i].text));
  return {
    markers,
    qaMargin: margin(qa),
    dreamsMargin: margin(dreams),
    qaIsDirectChild: !!qa && qa.parentElement === root,
  };
});
notes.push('qgroup read: ' + JSON.stringify(read));

const present = read && !read.err && read.markers &&
  read.markers.some(m => m.kind === 'label' && m.text === 'Q & A');
if (!present) {
  ok('the dashboard has a "Q & A" section header (direct child of #sections)',
     false);
  notes.push('markers seen: ' + JSON.stringify(read && read.markers));
  await ctx.close();
  finish();
  process.exit(1);
}

const idx = {};
read.markers.forEach((m, i) => {
  if (m.kind === 'label' && m.text === 'Q & A' && idx.qa === undefined) idx.qa = i;
  if (m.kind === 'qsec' && idx.qsec === undefined) idx.qsec = i;
  if (m.kind === 'answers' && idx.answers === undefined) idx.answers = i;
  if (m.kind === 'label' && /^dreams/.test(m.text) && idx.dreams === undefined)
    idx.dreams = i;
});
notes.push('indices: ' + JSON.stringify(idx));

// ── GROUPING ─────────────────────────────────────────────────────────────
ok('a "Q & A" .label is a direct child of #sections', read.qaIsDirectChild);
ok('the questions block (.qsec) follows the "Q & A" header',
   idx.qa !== undefined && idx.qsec !== undefined && idx.qa < idx.qsec);
ok('the /answers link follows .qsec (both parts inside the group)',
   idx.qsec !== undefined && idx.answers !== undefined &&
   idx.qsec < idx.answers);
ok('the "Q & A" header sits below the section above (dreams)',
   idx.dreams !== undefined && idx.qa !== undefined && idx.dreams < idx.qa);

// ── THE GAP ──────────────────────────────────────────────────────────────
// The header carries the SAME section-rhythm margin-top as the established
// dreams label (both resolve var(--space)); a header that lost the section
// class, or a gap that collapsed, would diverge. And it is non-trivial.
ok('the "Q & A" header carries the section gap (margin-top == dreams label)',
   read.qaMargin !== null && read.dreamsMargin !== null &&
   read.qaMargin === read.dreamsMargin);
ok('...and that gap is real, not collapsed (margin-top well above zero)',
   read.qaMargin > 1);

ok('no page errors', errs.length === 0);
await ctx.close();
await br.close();
finish();
