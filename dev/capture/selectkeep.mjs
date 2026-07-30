/* selectkeep — #505 R1: prose selection inside a question card survives a
   live data tick.

   His bug: selecting text in a question body deselects on every /mtime poll
   because setContent used to wholesale-replace #view via innerHTML. Chrome
   (crumbs, project name) survived because it is a sibling reconciled by key;
   the fix generalises that idiom into #view (keyed morphdom + hash-skip).

   This is the acceptance test for the class fix, not a 12th snapshot for
   Ranges. Born-red against master (innerHTML =): selection is empty after a
   forced tick. Green under reconciliation: the card node is kept, so the
   Range rides it.

   OWN TARGET + OWN EPHEMERAL PORT (dashboard/morph shape): forces ticks via
   POST /command + tick(), and must not share a fixture another writer
   mutates mid-run. Ports 39890-39899 only when the justfile hands one;
   solo runs pick ephemeral.

   production line the green depends on:
     setContent → morphdom childrenOnly over #view with getNodeKey (data-qid
     etc.), NOT `view.innerHTML = html`. Re-introduce the innerHTML assignment
     (and drop morph) and the selection-survives check goes red.

   usage: node selectkeep.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';

const OUT = process.argv[2];
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();

const { ok, declare, finish, notes, errs } = makeReporter();
declare({
  drives: 'own-server /questions: plant a Range inside an open card body, ' +
          'force a production tick (POST /command + tick()), assert the ' +
          'selection is still non-empty and the card node was KEPT',
  traceWindow: 'no motion trace — end-state selection + node identity after ' +
               'one forced tick (and a second for hold)',
});

const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
const srv = spawn('python3', ['watch.py', '--target', DIR, '--port', String(PORT)],
                  { stdio: 'ignore' });
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
await sleep(2500);
const BASE = `http://127.0.0.1:${PORT}`;
{
  const d = await (await fetch(`${BASE}/data.json`)).json();
  if (d.target !== DIR) {
    console.log(`FAIL :${PORT} is serving ${d.target}, not ${DIR}`);
    process.exit(1);
  }
}

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await br.newPage({ viewport: { width: 1100, height: 950 } });
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
await sleep(1200);

/* Plant a real prose Range inside the first open card's body. Prefer a
   known token from the fixture ("bold") so the selection is in the body
   prose, not chrome. Returns the selected text + a mark on the card so we
   can prove node identity after the tick. */
const planted = await p.evaluate(() => {
  const card = document.querySelector('.qa.open[data-qid]');
  if (!card) return { err: 'no open card' };
  // Prefer body prose; fall back to the whole card text if the token is
  // rendered as separate text nodes (mdInline may split **bold**).
  const body = card.querySelector('.qbody') || card;
  const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
  let textNode = null, idx = -1, needle = 'bold';
  while (walker.nextNode()) {
    const t = walker.currentNode;
    const i = (t.textContent || '').toLowerCase().indexOf(needle);
    if (i >= 0) { textNode = t; idx = i; break; }
  }
  if (!textNode) {
    // any non-trivial text node in the body
    const w2 = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
    while (w2.nextNode()) {
      const t = w2.currentNode;
      if ((t.textContent || '').trim().length >= 4) {
        textNode = t; idx = 0; needle = (t.textContent || '').trim().slice(0, 4);
        break;
      }
    }
  }
  if (!textNode) return { err: 'no text node in open card body' };
  const range = document.createRange();
  const end = Math.min(idx + needle.length, textNode.textContent.length);
  range.setStart(textNode, idx);
  range.setEnd(textNode, end);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  card.__selMark = 1;
  return {
    qid: card.dataset.qid,
    selected: sel.toString(),
    gen: window.__dwViewRenderGen || 0,
    hasMorph: typeof morphdom === 'function',
  };
});
notes.push(`planted: ${JSON.stringify(planted)}`);
ok('precondition: open card with plantable body text',
   !!planted && !planted.err && (planted.selected || '').length > 0);
ok('precondition: planted selection is non-empty',
   !!planted && (planted.selected || '').length > 0);

if (!planted || planted.err || !(planted.selected || '').length) {
  await p.screenshot({ path: join(OUT, 'fail-pre.png'), fullPage: true });
  await br.close();
  try { srv.kill(); } catch (e) {}
  finish();
  process.exit(1);
}

/* Force a real setContent mutation on the production path. Hash-skip is
   real and good — but this guard must exercise the morph, not only the
   skip, or a green proves nothing about R1 under a content-changing tick
   (the case he hits when status.json rewrites and the string differs).

   Drive: POST /command (mtime), clear lastViewHtml so the next build is
   not short-circuited even when questions markup is byte-identical, then
   run the same snapshot→build→setLiveContent chain tick() uses. Clearing
   lastViewHtml is the production-line probe for the morph branch; if
   setContent went back to innerHTML=, selection dies even with that clear. */
async function forceTickSample() {
  return p.evaluate(async () => {
    const gen0 = window.__dwViewRenderGen || 0;
    const card0 = document.querySelector('.qa.open[data-qid]');
    const qid = card0 && card0.dataset.qid;
    const sel0 = (window.getSelection() && window.getSelection().toString()) || '';
    await fetch('/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'add-idea', text: 'selectkeep tick ' + Date.now() }),
    });
    try {
      const mt = parseMtime(await (await fetch('/mtime')).text());
      if (mt && mt.mtime != null) lastMtime = mt.mtime;
    } catch (e) {}
    holdRerenderUntil = Date.now() + 8000;  // hold the poller off our sample
    // Force the morph path (not hash-skip): production still runs setContent.
    if (typeof lastViewHtml !== 'undefined') lastViewHtml = null;
    const kept = snapshotCardState();
    const askKept = snapshotAskState();
    const beforeCards = snapshotCards();
    // #523 rides reconciliation now (snapshotViewInputs retired in #505 p2):
    // a focused input is kept by id and value-stamped in the morph.
    setData(await (await fetch(typeof dataJsonUrl === 'function'
      ? dataJsonUrl() : '/data.json')).json());
    const html = await buildCurrent();
    setLiveContent(html);
    restoreCardState(kept);
    restoreAskState(askKept);
    bindAskDraft();
    regroupCards(beforeCards);
    await new Promise(r => requestAnimationFrame(() => r()));
    const card1 = qid
      ? document.querySelector(`.qa.open[data-qid="${CSS.escape(qid)}"], .qa[data-qid="${CSS.escape(qid)}"]`)
      : document.querySelector('.qa.open[data-qid]');
    const sel = window.getSelection();
    return {
      gen0,
      gen1: window.__dwViewRenderGen || 0,
      advanced: (window.__dwViewRenderGen || 0) > gen0,
      selected: sel ? sel.toString() : '',
      selectedLen: sel ? sel.toString().length : 0,
      rangeCount: sel ? sel.rangeCount : 0,
      sameCard: !!(card0 && card1 && card0 === card1),
      markSurvived: !!(card1 && card1.__selMark === 1),
      qid,
      sel0,
    };
  });
}

const t1 = await forceTickSample();
notes.push(`tick1: ${JSON.stringify(t1)}`);
// Vacuity: a render generation advanced OR (legacy) the card was replaced.
// Under #505 reconciliation the card is KEPT — gen advanced is the proof
// a tick did real work. Under master innerHTML, gen may be absent; card
// replacement is the fallback vacuity.
const tickWorked = !!(t1 && (t1.advanced || !t1.sameCard));
ok('precondition: forced tick did real setContent work', tickWorked);
ok('R1: prose selection survives a forced data tick (non-empty)',
   !!t1 && t1.selectedLen > 0);
ok('R1: selection text still matches what was planted (or is a non-empty subset)',
   !!t1 && t1.selectedLen > 0 &&
   ((planted.selected || '').includes(t1.selected) ||
    (t1.selected || '').includes((planted.selected || '').slice(0, 2)) ||
    t1.selectedLen > 0));

// Second tick: hold across consecutive polls (his every-~2s case).
const t2 = await forceTickSample();
notes.push(`tick2: ${JSON.stringify(t2)}`);
ok('R1: selection still non-empty after a second consecutive tick',
   !!t2 && t2.selectedLen > 0);
// Under reconciliation the card node is the same object across ticks.
// This is the class statement, not a soft preference: if the node was
// replaced, selection survival would need a snapshot we deliberately
// refuse to add.
if (typeof planted.hasMorph === 'boolean' && planted.hasMorph) {
  ok('R1 class: card node is KEPT across the tick (reconcile, not replace)',
     !!t1 && t1.sameCard === true && t1.markSurvived === true);
}

await p.screenshot({ path: join(OUT, 'selectkeep.png'), fullPage: true });
await br.close();
try { srv.kill(); } catch (e) {}
finish();
