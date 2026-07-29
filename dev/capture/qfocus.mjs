/* qfocus — #452: focus ONE question on its own page (/question?qid=<title>).

   The route exists because the loop rewrites questions.md while he is
   reading it: a list re-sorts and shifts under him mid-answer, and a
   focused page is a surface that churn cannot move. The key is the
   question's own title identity — the same one `data-qid` already uses to
   survive regrouping — so body rewrites, re-sorts and the open→answered
   fold keep the page resolved. A RETITLE breaks it, and that case must
   render an explicit missing notice, never a blank page and never a
   different question.

   Production lines the red-proofs name (watch.py):
     · the `a.qfocus` link emission in qaInner — removing it reds the
       way-in checks;
     · buildQuestion's `d.answered_entries.find` fallback — removing it
       reds the fold-follow check (the tick would report a live, folded
       question as missing);
     · the `.qmissing` branch — removing it reds the missing-key check;
     · the crossfade path itself — the route-arrival evidence asks the
       browser (transitionstart, #442) whether the existing dissolve ran,
       so a snap navigation reds it.

   usage: node qfocus.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { makeReporter } from './report.mjs';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
const OUT = process.argv[2], PORT = process.argv[3] || '39886';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, notes } = makeReporter();
declare({
  drives: '/questions focus affordance → /question?qid=… (real click), the ' +
          'answer gesture on the focused surface, the missing-key notice, ' +
          'a reduced-motion route swap, and a fixture fold the tick follows',
  traceWindow: 'settle reads after ~1.4s per navigation; tick-following ' +
               'phases poll to 12s (tick is 2s; morph hold 1.25s). No ' +
               'frame traces: route-transition evidence is transitionstart ' +
               'on #view, the load-independent snap detector (#442).',
});

const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await b.newPage({ viewport: { width: 1100, height: 950 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));

/* ── preconditions, derived from served data, never literals ────────────── */
const d = await (await fetch(`${BASE}/data.json`)).json();
const openQ = d.questions_open.find(x => !x.answer);
const foldQ = d.answered_entries[0];
ok('precondition: an unanswered open question and a folded entry both exist',
   !!openQ && !!foldQ);
ok('precondition: their titles differ (identity cannot collide)',
   !!openQ && !!foldQ && openQ.title !== foldQ.title);
const target = d.target;
ok('precondition: server named its target (fold phase rewrites the fixture)',
   !!target);
if (!openQ || !foldQ || !target) { await b.close(); finish(); }
const enc = encodeURIComponent(openQ.title);

/* ── the way in: a per-card focus affordance on /questions ──────────────── */
await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
await sleep(900);
const links = await p.evaluate(() =>
  [...document.querySelectorAll('.qa')].map(card => {
    const a = card.querySelector('a.qfocus');
    return { qid: card.dataset.qid || null, state: card.className,
             href: a ? a.getAttribute('href') : null,
             tag: a ? a.tagName : null };
  }));
notes.push('focus links: ' + JSON.stringify(links));
ok('every card carries a focus affordance', links.every(l => l.href));
ok('the affordance is a real link (keyboard-operable natively, deep-linkable)',
   links.every(l => l.tag === 'A'));
ok('the link key IS the card identity (href qid === data-qid)',
   links.every(l => l.href === '/question?qid=' + l.qid));
ok('a folded card is focusable too (a settled entry can be found again)',
   links.some(l => l.state.includes('folded') && l.href));

/* ── the real gesture: click it, arrive on the focused page ─────────────── */
await p.evaluate(() => {
  window.__qft = [];
  document.addEventListener('transitionstart', e => {
    if (e.target && e.target.id === 'view') window.__qft.push(e.propertyName);
  });
});
await p.click(`.qa[data-qid="${enc}"] a.qfocus`);
await sleep(1600);                       // the dissolve is ~1.15s
const arrived = await p.evaluate(() => ({
  path: location.pathname,
  qid: new URLSearchParams(location.search).get('qid'),
  cards: [...document.querySelectorAll('#view .qa')].map(c => ({
    qid: c.dataset.qid, cls: c.className,
    canAnswer: !!c.querySelector('.qcompose textarea') })),
  transitions: window.__qft,
}));
notes.push('arrived: ' + JSON.stringify(arrived));
ok('the click navigated to /question with the question as key',
   arrived.path === '/question' && arrived.qid === openQ.title);
ok('the focused page shows exactly ONE card, and it is that question',
   arrived.cards.length === 1 && arrived.cards[0].qid === enc);
ok('the focused open question keeps its answer box (the page is for answering)',
   arrived.cards.length === 1 && arrived.cards[0].canAnswer);
ok('the arrival used the existing route dissolve (transitionstart on #view)',
   arrived.transitions.includes('opacity') ||
   arrived.transitions.includes('transform'));
await p.screenshot({ path: `${OUT}/focused.png`, fullPage: true });

/* ── answering ON the focused surface resolves the right entry ──────────── */
await p.click('#view .qa textarea');
await p.type('#view .qa textarea', 'qfocus guard answer — the page held still');
await p.keyboard.press('Control+Enter');
let st = null;
for (let i = 0; i < 24; i++) {
  await sleep(500);
  st = await p.evaluate(() => {
    const c = document.querySelector('#view .qa');
    return c ? { cls: c.className, qid: c.dataset.qid } : null;
  });
  if (st && st.cls.includes('awaiting')) break;
}
notes.push('after answer: ' + JSON.stringify(st));
ok('an answer sent from the focused page lands on the SAME question ' +
   '(awaiting, same identity, still one card)',
   !!st && st.cls.includes('awaiting') && st.qid === enc);

/* ── the fold: the entry moves to ## Answered and the page FOLLOWS ──────── */
{
  const qfile = join(target, '.dreamwork', 'questions.md');
  const text = readFileSync(qfile, 'utf8');
  const lines = text.split('\n');
  const head = lines.findIndex(l =>
    l.startsWith('- **') && openQ.title.startsWith(l.slice(4, 34).trimEnd()));
  ok('precondition: the focused entry was found as one file block',
     head >= 0);
  if (head >= 0) {
    let end = lines.findIndex((l, i) =>
      i > head && (l.startsWith('- **') || l.startsWith('## ')));
    if (end < 0) end = lines.length;
    const block = lines.splice(head, end - head);
    const answeredAt = lines.findIndex(l => l.startsWith('## Answered'));
    ok('precondition: ## Answered still exists after the cut',
       answeredAt >= 0);
    lines.splice(answeredAt + 1, 0, '', ...block);
    writeFileSync(qfile, lines.join('\n'));
    let fol = null;
    for (let i = 0; i < 24; i++) {
      await sleep(500);
      fol = await p.evaluate(() => {
        const c = document.querySelector('#view .qa');
        return c ? { cls: c.className, qid: c.dataset.qid,
                     key: c.dataset.qkey } : null;
      });
      if (fol && fol.cls.includes('folded')) break;
    }
    notes.push('after fold: ' + JSON.stringify(fol));
    ok('the open→answered fold does NOT lose the focused page: same ' +
       'question, now folded (a<n> key), still exactly one card',
       !!fol && fol.cls.includes('folded') && fol.qid === enc &&
       /^a\d+$/.test(fol.key || ''));
    await p.screenshot({ path: `${OUT}/followed-fold.png`, fullPage: true });
  } else {
    ok('the fold phase ran (entry block found)', false);
  }
}

/* ── a key that resolves nothing renders a SAID missing, never a blank ──── */
{
  const ghost = openQ.title + ' · RETITLED sentinel';
  const absent = !d.questions_open.concat(d.answered_entries)
    .some(x => x.title === ghost);
  ok('precondition: the sentinel title genuinely resolves nowhere', absent);
  await p.goto(`${BASE}/question?qid=${encodeURIComponent(ghost)}`,
               { waitUntil: 'networkidle' });
  await sleep(900);
  const miss = await p.evaluate(() => ({
    notice: !!document.querySelector('.qmissing'),
    cards: document.querySelectorAll('#view .qa').length,
    text: (document.querySelector('.qmissing') || {}).textContent || '',
    back: !!(document.querySelector('.qmissing a[href="/questions"]')),
  }));
  notes.push('missing: ' + JSON.stringify(miss));
  ok('an unresolvable key renders the missing notice, and NO card',
     miss.notice && miss.cards === 0);
  ok('the notice says the question may have been re-titled (never renders ' +
     '"I could not tell" as "nothing")',
     /re-?title|renamed|moved|no longer/i.test(miss.text));
  ok('the notice offers the way back to the list', miss.back);
  await p.screenshot({ path: `${OUT}/missing.png`, fullPage: true });
}

/* ── reduced motion: same function, no dissolve ─────────────────────────── */
{
  await p.emulateMedia({ reducedMotion: 'reduce' });
  await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  await sleep(600);
  await p.evaluate(() => {
    window.__qft2 = [];
    document.addEventListener('transitionstart', e => {
      if (e.target && e.target.id === 'view') window.__qft2.push(e.propertyName);
    });
  });
  await p.click(`.qa[data-qid="${enc}"] a.qfocus`);
  await sleep(500);
  const rm = await p.evaluate(() => ({
    path: location.pathname,
    ghost: !!document.querySelector('.ghost'),
    enter: document.getElementById('view').classList.contains('enter'),
    transitions: window.__qft2,
    cards: document.querySelectorAll('#view .qa').length,
  }));
  notes.push('reduced-motion arrival: ' + JSON.stringify(rm));
  ok('reduced motion: the swap is instant (no ghost, no enter pose, no ' +
     'transition on #view) and the same one card is there',
     rm.path === '/question' && !rm.ghost && !rm.enter &&
     rm.transitions.length === 0 && rm.cards === 1);
}

ok('no page errors', errs.length === 0);
if (errs.length) notes.push('page errors: ' + errs.join(' | '));
await b.close();
finish();
