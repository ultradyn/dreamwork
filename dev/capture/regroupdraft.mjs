/* #540 — a card being typed into is the SAME element after a DIFFERENT card's
   answer-regroup. This is the binding scenario the #505 keyed reconciler
   exists to defend: the user is mid-edit in card B when card A is answered,
   the tick regroups the list, and B's card must survive untouched.

   Without the qid key, positional morphdom pairing shuffles ALL cards by
   position — not just the answered one. B's card div is morphed to a
   DIFFERENT question's content (its data-qid changes), corrupting a card the
   user was actively editing. (The draft text itself survives either way: the
   textarea has its own stable id — `qi${key}` — that morphdom matches
   independently, so it is repositioned correctly even when the card div is
   mis-paired. That is why the decisive assertion here is the CARD NODE, not
   the text: a JS reference to B's card div, held in the page across the tick,
   must still be in the DOM with B's qid. The draft-leak check is a companion
   that catches the text-lost failure mode.)

   Distinct from regroup.mjs's sameNode (Gap 1): that tests the ANSWERED card
   (the one that MOVES and must hold identity while travelling); this tests a
   NEIGHBOUR card (the one that STAYS and must hold identity while untouched).
   Both fail under positional fallback, but for different cards in different
   roles — answering A need not disrupt B, and the guard proves it.

   The decisive red: delete viewNodeKey's `if (d.qid) return 'qid:' + d.qid`
   (watch.py ~7188) and the node-identity check fails — B's stashed card ends
   up with a different question's qid. Baseline green on the keyed tree.

   usage: node regroupdraft.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
import { outdir } from './outdir.mjs';
import { mkdirSync } from 'node:fs';
const OUT = outdir(process.argv), PORT = process.argv[3] || '39887';
mkdirSync(OUT, { recursive: true });
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));

const { ok, declare, finish, checks, notes } = makeReporter();
declare({
  drives: '/questions, typing a draft into open card B (answer mode), answering a ' +
          'DIFFERENT open card A through the real UI (qmode + qsend), then waiting ' +
          'for the /mtime tick that regroups the list through morphdom',
  traceWindow: 'the 2s /mtime poll past sendAnswer\'s 1.25s MORPH_HOLD_MS; the guard ' +
               'waits for window.__dwViewRenderGen to advance (the tick committed a ' +
               're-render) rather than a fixed sleep',
});

// distinctive enough that no fixture body could contain it
const DRAFT = '540keydraft-B-only';

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const ctx = await br.newContext({ viewport: { width: 1100, height: 950 } });
const p = await ctx.newPage();
const errs = []; p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
// #536 render readiness — wait for the .qa.open cards, not a fixed sleep (#428)
await waitFor(p, '.qa.open');

// absence-first: need two open cards (A to answer, B to draft into)
const setup = await p.evaluate(() => {
  const open = [...document.querySelectorAll('.qa.open[data-qid]')];
  // A is the first open card (same choice regroup.mjs answers); B is the next
  // open card in DOM order — answering A shifts B's position, the condition
  // positional pairing corrupts.
  return { openCount: open.length,
           aQid: open[0] ? open[0].dataset.qid : null,
           bQid: open[1] ? open[1].dataset.qid : null };
});
ok('fixture has >=2 open questions (A to answer, B to draft into, else vacuous)',
   setup.openCount >= 2);

if (setup.openCount < 2) {
  notes.push('only ' + setup.openCount + ' open question(s) — reset the scratch target');
  await br.close(); finish(); process.exit(1);
}

// record the render generation and STASH a JS reference to B's card div — the
// node-identity probe. morphdom strips data-* attrs (server HTML lacks them),
// so like regroup.mjs's sameNode the probe holds a JS REFERENCE in the page
// closure, not an attribute. After the tick we check the reference is still in
// the DOM and still carries B's qid — positional fallback morphs it to a
// different question's qid (the identity theft the qid key prevents).
const gen0 = await p.evaluate(({ bQid }) => {
  const bCard = [...document.querySelectorAll('.qa[data-qid]')]
    .find(c => c.dataset.qid === bQid);
  window.__540bCard = bCard;   // JS reference — survives morphdom's attribute patch
  return window.__dwViewRenderGen || 0;
}, { bQid: setup.bQid });

// type a draft into B (answer mode + focus) then answer A through the real UI.
// The draft is set WITHOUT an input event: it lives in the DOM node only, so
// restoreAnswerDrafts (the post-morph belt that restores SAVED drafts by qid)
// cannot mask the node-identity failure. The draft check below is a companion;
// the decisive assertion is the card-node identity.
await p.evaluate(({ aQid, bQid, draft }) => {
  const find = qid => [...document.querySelectorAll('.qa[data-qid]')]
    .find(c => c.dataset.qid === qid);
  // 1. draft into B — click answer mode, type, focus
  const bCard = find(bQid);
  bCard.querySelector('.qmode[data-mode=answer]').click();
  const bTa = bCard.querySelector('textarea');
  bTa.value = draft;
  bTa.focus();
  // 2. answer A through the real UI (qmode + textarea + qsend = sendAnswer)
  const aCard = find(aQid);
  aCard.querySelector('.qmode[data-mode=answer]').click();
  aCard.querySelector('textarea').value = 'regroupdraft answers A';
  aCard.querySelector('.qsend').click();
}, { aQid: setup.aQid, bQid: setup.bQid, draft: DRAFT });

// let sendAnswer's async POST + local morph land before waiting for the tick
await sleep(700);

// wait for the tick's re-render (the keyed-reconcile path); the tick polls
// /mtime every 2s, and sendAnswer holds the re-render for MORPH_HOLD_MS (1.25s)
let ticked = false;
for (let i = 0; i < 50; i++) {
  await sleep(150);
  const gen = await p.evaluate(() => window.__dwViewRenderGen || 0);
  if (gen > gen0) { ticked = true; break; }
}
ok('the tick re-rendered after the answer (else the reconcile check is vacuous)',
   ticked);
// give the post-morph belts a frame to land
if (ticked) await sleep(200);

await p.screenshot({ path: `${OUT}/after-regroup.png`, fullPage: true });

// assert: B's stashed card node is still in the DOM with B's qid (the identity
// check positional fallback breaks), the draft is in B's card by qid (the
// companion), and the draft leaked nowhere.
const result = await p.evaluate(({ bQid, draft }) => {
  const stashed = window.__540bCard;
  const cards = [...document.querySelectorAll('.qa[data-qid]')];
  // the decisive check: same JS node, same qid
  const bNodeSame = !!(stashed && document.contains(stashed) &&
                       stashed.dataset.qid === bQid);
  let bHas = false, leak = [];
  for (const c of cards) {
    const ta = c.querySelector('textarea');
    if (!ta) continue;
    if (c.dataset.qid === bQid) bHas = ta.value.includes(draft);
    else if (ta.value.includes(draft)) leak.push(c.dataset.qid.slice(0, 30));
  }
  return { bNodeSame, bHas, leak, cardCount: cards.length };
}, { bQid: setup.bQid, draft: DRAFT });

ok('no page errors', errs.length === 0);
ok('#540 the typing card (B) is the SAME node after a different card (A) is answered '
 + '(keyed reconcile preserves the neighbour, not just the mover)',
   result.bNodeSame);
ok('#540 a draft typed into B is still in B after the regroup', result.bHas);
ok('#540 the draft leaked into no other card '
 + `(leaked into ${result.leak.length}: ${JSON.stringify(result.leak)})`,
   result.leak.length === 0);

notes.push('draft marker : ' + DRAFT);
notes.push('A (answered) : ' + String(setup.aQid).slice(0, 50));
notes.push('B (drafted)  : ' + String(setup.bQid).slice(0, 50));
notes.push('card count   : ' + result.cardCount);
notes.push('tick re-render: ' + (ticked ? 'yes' : 'NO — timed out'));
if (errs.length) notes.push('errors: ' + errs.join(' | '));
await br.close();
finish();
