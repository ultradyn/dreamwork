/* #105 — ONE question component. Proves every surface that shows a question
   renders the SAME card: /questions (all three states), the dashboard, and
   the review dock. Structural equality is the assertion — same tag path,
   same class vocabulary, same footer — because "looks the same" is exactly
   what a shared component buys and what a fork would quietly lose.
   usage: node qacard.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { makeReporter } from './report.mjs';
const OUT = process.argv[2], PORT = process.argv[3] || '39887';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });

const { ok, declare, finish, checks, notes } = makeReporter();
declare({
  drives: '/questions (all three states), the dashboard, and /review dock — ' +
          'one .qa card shape compared structurally across all four surfaces',
  traceWindow: 'static reads after ~0.9s settle per route, plus one #273 mode ' +
               'switch on /questions; no motion traced',
});

const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const p = await b.newPage({ viewport: { width: 1100, height: 950 } });
const errs = []; p.on('pageerror', e => errs.push(String(e)));

// the shape of a card, independent of its content — what a second
// implementation would drift on.
//
// `root` is the card, except for a FOLDED entry, whose contents sit one level
// down inside the `.qfold` disclosure (#111): collapsing IS that state's
// treatment, so it is the one structural difference between the three. Every
// assertion below still reads through the same probe at the same depth, and
// `.qt` is still the question line in all three states — the folded one just
// happens to be a <summary>.
//
// `.qbody` is looked THROUGH, not at (#326). It is the review dock's
// scrollport and generates no box anywhere else, so it is not part of a card's
// shape — but it IS a DOM level, and a `:scope >` probe would stop at it and
// report the title and the answer tag missing from every unfolded card. `kids`
// flattens it away, so `order` still lists what it listed before the wrapper
// existed and the two surfaces are still compared piece for piece. It also
// differs BY STATE (a folded entry's title is the summary and cannot be inside
// it), which is exactly why the flatten is the right shape here: the probe
// asks what the card contains, not how it is nested.
const SHAPE = `(card) => { const root = card.querySelector(':scope > .qfold') || card;
 const kids = [...root.children].flatMap(c =>
   c.classList.contains('qbody') ? [...c.children] : [c]);
 const kid = sel => kids.find(c => c.matches(sel)) || null;
 return {
  cls: card.className,
  key: card.dataset.qkey || null,
  folded: root !== card,
  hasTitle: !!kid('.qt'),
  titleTag: (kid('.qt') || {}).tagName || null,
  hasInput: !!root.querySelector(':scope > .qcompose .qfield textarea'),
  inputId: (root.querySelector(':scope > .qcompose textarea') || {}).id || null,
  // #273: accessible name + 44px send floor (dock and every card share qaCompose)
  inputAria: (root.querySelector(':scope > .qcompose textarea') || {})
               .getAttribute?.('aria-label') || null,
  sendAria: (root.querySelector(':scope > .qcompose .qsend') || {})
              .getAttribute?.('aria-label') || null,
  sendH: (() => { const b = root.querySelector(':scope > .qcompose .qsend');
    return b ? b.getBoundingClientRect().height : 0; })(),
  modes: [...root.querySelectorAll(':scope > .qcompose .qmode')]
           .map(b => b.dataset.mode),
  hasAnsTag: !!kid('.anstag'),
  when: (root.querySelector('.qwhen') || {}).textContent || null,
  order: kids.map(c => c.className || c.tagName.toLowerCase())
}; }`;

await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' }); await sleep(900);
const qs = await p.evaluate(`[...document.querySelectorAll('.qa')].map(${SHAPE})`);
await p.screenshot({ path: `${OUT}/questions.png`, fullPage: true });

const byState = s => qs.filter(c => c.cls.includes(s));
const open = byState('open'), awaiting = byState('awaiting'), folded = byState('folded');

// #273 mode rewrite while still on /questions (open card present)
let modeOk = { ok: false };
if (open[0]) {
  modeOk = await p.evaluate(async (key) => {
    const card = document.querySelector(`.qa[data-qkey="${key}"]`);
    if (!card) return { ok: false, why: 'no card' };
    const noteBtn = card.querySelector('.qmode[data-mode="note"]');
    const ta = card.querySelector('textarea');
    const send = card.querySelector('.qsend');
    if (!noteBtn || !ta) return { ok: false, why: 'no controls' };
    const before = ta.getAttribute('aria-label') || '';
    noteBtn.click();
    await new Promise(r => setTimeout(r, 50));
    const after = ta.getAttribute('aria-label') || '';
    const sendL = send ? (send.getAttribute('aria-label') || '') : '';
    return {
      ok: /note/i.test(after) && after !== before && /note/i.test(sendL),
      before, after, sendL
    };
  }, open[0].key);
}

await p.goto(`${BASE}/`, { waitUntil: 'networkidle' }); await sleep(900);
const dash = await p.evaluate(`[...document.querySelectorAll('.qa')].map(${SHAPE})`);

// the review dock: deep-load /review with a question title so it docks
const title = await p.evaluate(async () => {
  const d = await (await fetch('/data.json')).json();
  const q = d.questions_open.find(x => !x.answer) || d.questions_open[0];
  return q ? q.title : null;
});
let dock = [];
if (title) {
  const rev = await p.evaluate(async () => (await (await fetch('/data.json')).json()).reviews[0]);
  if (rev) {
    await p.goto(`${BASE}/review?p=${encodeURIComponent(rev.name)}&q=${encodeURIComponent(title)}`,
                 { waitUntil: 'networkidle' });
    await sleep(900);
    dock = await p.evaluate(`[...document.querySelectorAll('#qdock .qa')].map(${SHAPE})`);
    await p.screenshot({ path: `${OUT}/review-dock.png`, fullPage: true });
  }
}

const sameShape = (a, b2) => JSON.stringify(a.order) === JSON.stringify(b2.order) &&
  a.hasTitle === b2.hasTitle && a.hasInput === b2.hasInput &&
  JSON.stringify(a.modes) === JSON.stringify(b2.modes) && a.cls === b2.cls;

ok('no page errors', errs.length === 0);ok('all three states present on /questions',
   open.length > 0 && awaiting.length > 0 && folded.length > 0);
ok('every card is a .qa with a data-qkey', qs.every(c => c.key));
ok('every card carries ONE input, keyed to itself (#103)',
   qs.every(c => c.hasInput && c.inputId === 'qi' + c.key));
ok('a card that can be answered offers both modes; a folded one does not',
   qs.every(c => JSON.stringify(c.modes) ===
     (c.cls.includes('folded') ? '[]' : '["answer","note"]')));
ok('awaiting cards (and only awaiting) show the answered tag',
   qs.every(c => c.hasAnsTag === c.cls.includes('awaiting')));
ok('folded entries are keyed a<n>, open/awaiting o<n>',
   folded.every(c => /^a\d+$/.test(c.key)) &&
   [...open, ...awaiting].every(c => /^o\d+$/.test(c.key)));
// #111: the collapse is the folded state's treatment, and ONLY the folded
// state's — an entry still waiting on the loop stays visible
ok('folded entries collapse, open and awaiting do not',
   folded.every(c => c.folded) && [...open, ...awaiting].every(c => !c.folded));
ok('the question line is the summary when folded, so .qt still names it',
   folded.every(c => c.hasTitle && c.titleTag === 'SUMMARY') &&
   [...open, ...awaiting].every(c => c.hasTitle && c.titleTag === 'DIV'));
ok('a collapsed entry still says when it was answered',
   folded.every(c => /^answered \d{4}-\d{2}-\d{2}/.test(c.when || '')));
ok('dashboard renders the identical card as /questions',
   dash.length > 0 && dash.every(d => qs.some(q => sameShape(d, q))));
ok('the review dock renders the identical card as /questions',
   dock.length === 1 && qs.some(q => sameShape(dock[0], q)));

// #273 — review dock a11y: named field + 44px send (shared compose path)
const withInput = c => c.hasInput;
ok('every input card has an aria-label on the textarea (#273)',
   qs.filter(withInput).every(c => c.inputAria && c.inputAria.length > 2));
ok('open cards name "answer"; awaiting/folded name "note" (#273 mode)',
   open.every(c => /^answer\b/i.test(c.inputAria || '')) &&
   [...awaiting, ...folded].filter(withInput)
     .every(c => /note/i.test(c.inputAria || '')));
ok('send controls are named and at least 44px tall (#273)',
   qs.filter(withInput).every(c =>
     c.sendAria && /send/i.test(c.sendAria) && c.sendH + 0.01 >= 44));
if (dock[0] && dock[0].hasInput) {
  ok('review dock textarea has accessible name (#273)',
     !!(dock[0].inputAria && dock[0].inputAria.length > 2));
  ok('review dock send is ≥44px (#273)', dock[0].sendH + 0.01 >= 44);
}
ok('switching to note rewrites textarea + send aria-label (#273)',
   !!(modeOk && modeOk.ok));

/* ── #385: humanized age next to the date in the question headline ─────────
   The fixture's open titles all share one date, so two ages would be equal
   and a check that they differ would be vacuous. Plant two deliberately
   different title dates on the TARGET (runner reset copies the fixture
   fresh for this guard), then assert the ages differ at runtime. */
{
  const { readFileSync, writeFileSync } = await import('node:fs');
  const { join } = await import('node:path');
  const target = await (await fetch(`${BASE}/data.json`)).json()
    .then(d => d.target).catch(() => null);
  ok('#385 server answered with a target for age planting', !!target);
  if (target) {
    const QFILE = join(target, '.dreamwork', 'questions.md');
    let text = readFileSync(QFILE, 'utf8');
    // two different days inside Open — 40 days and 5 days before a fixed
    // anchor near "today" so the ladder lands on different big units.
    const day = 86400 * 1000;
    const t0 = Date.now();
    const iso = ms => {
      const d = new Date(ms);
      const p = n => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
    };
    const oldDate = iso(t0 - 40 * day);
    const youngDate = iso(t0 - 5 * day);
    // rewrite the first two YYYY-MM-DD title dates under ## Open only
    let n = 0;
    text = text.replace(
      /(## Open[\s\S]*?)(## Answered)/,
      (whole, openSec, answered) => {
        const next = openSec.replace(
          /(\*\*(?:P[123] · )?)(\d{4}-\d{2}-\d{2})( — )/g,
          (m, pre, _d, sep) => {
            const d = n === 0 ? oldDate : (n === 1 ? youngDate : _d);
            n += 1;
            return `${pre}${d}${sep}`;
          });
        return next + answered;
      });
    writeFileSync(QFILE, text);
    ok('#385 planted two distinct title dates in Open',
       n >= 2 && oldDate !== youngDate);
    notes.push(`#385 planted dates: old=${oldDate} young=${youngDate} (rewrote ${n})`);

    await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
    await sleep(1100); // ages() runs on setContent and once a second
    const ages = await p.evaluate(() => {
      const cards = [...document.querySelectorAll('.qa.open .qt')];
      return cards.map(qt => {
        const age = qt.querySelector('.age[data-ct], .qage[data-ct]');
        const date = (qt.textContent.match(/\d{4}-\d{2}-\d{2}/) || [])[0] || null;
        return {
          date,
          hasAge: !!age,
          ct: age ? age.dataset.ct : null,
          // #392a: `data-day="1"` marks a DAY-precision timestamp. The FIGURE
          // COUNT is the precision signal, so the guard has to read the signal
          // to check it -- see the assertion below.
          day: age ? (age.dataset.day === '1') : null,
          text: age ? age.textContent.trim() : null,
          // age sits after the date in the headline, not elsewhere
          afterDate: (() => {
            if (!age || !date) return false;
            const html = qt.innerHTML;
            const di = html.indexOf(date);
            const ai = html.indexOf('data-ct');
            return di >= 0 && ai > di;
          })(),
        };
      });
    });
    notes.push(`#385 ages: ${JSON.stringify(ages)}`);
    const withAge = ages.filter(a => a.hasAge);
    ok('#385 open question headlines carry a data-ct age next to the date',
       withAge.length >= 2 && withAge.every(a => a.afterDate && a.text));
    // anti-vacuity: the two ages MUST differ, derived at runtime from the
    // planted dates — equal ages would make the rest of this check hollow.
    // #474: pick the two cards this guard PLANTED, not the first two rendered.
    // The plant walks FILE order; the page sorts by priority and date, so the
    // first two cards are whichever entries sort highest -- here a P1 the plant
    // never touched, one day apart from its neighbour, which fails `gap >
    // 86400` deterministically while both planted dates sit further down. The
    // guard was asserting about a pair it had not arranged, so the fixture's
    // shape and the calendar decided whether it passed.
    const planted = [oldDate, youngDate]
      .map(d => withAge.find(x => x.date === d))
      .filter(Boolean);
    ok(`#385 precondition: both planted dates are on screen `
       + `(${planted.length} of 2: ${oldDate}, ${youngDate})`,
       planted.length === 2);
    if (planted.length === 2) {
      const [a, b2] = planted;
      const gap = Math.abs(parseFloat(a.ct) - parseFloat(b2.ct));
      ok(`#385 fixture ages differ (gap ${gap}s; dates ${a.date} vs ${b2.date})`,
         gap > 86400 && a.text !== b2.text);
      // #385 fixed the SHAPE (zero-padded two-digit figures + unit letter);
      // #392a fixed what the shape is allowed to CLAIM. Two figures means we
      // know the time, one figure means we know only the day, and `today` is
      // the same-day case. Asserting "always two units" -- which this line did
      // until #392a landed -- now asserts the bug: every questions entry is
      // date-only, so the old form could only pass by lying about precision.
      // Check the CORRESPONDENCE, per node, against the signal in the DOM.
      const TWO = /^\d{2}[a-z] \d{2}[a-z] ago$/, ONE = /^\d{2}[a-z] ago$/;
      const badForm = withAge.filter(a => !(TWO.test(a.text) || ONE.test(a.text)
                                            || a.text === 'today'));
      ok(`#385 every age is a known form (${badForm.length} unrecognised)`,
         badForm.length === 0);
      const mismatched = withAge.filter(a => a.day
        ? !(ONE.test(a.text) || a.text === 'today')
        : !TWO.test(a.text));
      ok('#392a figure count encodes precision (day-precision -> one figure or '
         + `today, timed -> two; ${mismatched.length} mismatched)`,
         mismatched.length === 0);
      // Anti-vacuity for the line above: it is satisfied trivially if NOTHING
      // is day-precision, and today every entry is. Assert the population the
      // assertion is about actually exists, derived at runtime rather than
      // assumed -- a fixture that loses its date-only entry would otherwise
      // turn this check green by emptying it.
      ok(`#392a precondition: a day-precision age is present to test `
         + `(${withAge.filter(a => a.day).length} of ${withAge.length})`,
         withAge.some(a => a.day));
    } else {
      ok('#385 fixture ages differ (planted dates not both on screen)', false);
      ok('#385 age text is the XXa YYb form (no ages to compare)', false);
    }
  }
}

notes.push('states: open=' + open.length + ' awaiting=' + awaiting.length +
           ' folded=' + folded.length + ' dash=' + dash.length +
           ' dock=' + dock.length);
if (dock[0]) notes.push('dock: ' + JSON.stringify(dock[0]));
await b.close();
finish();
