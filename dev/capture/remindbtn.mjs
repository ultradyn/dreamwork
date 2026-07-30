/* remindbtn — #551 the posture slot's 'remind' link-btn.

   Contract under test (the ambient #posture-src slot — both file and derived
   sources — replaced by a link-styled 'remind' button; the armed
   'arming override…' state is OUT of scope here, covered by posture.mjs):
   - ambient slot shows the 'remind' button (no posture file → derived source)
   - click → exactly ONE POST /remind observed
   - on 202 ok: confirmation visible in the slot ('sent · …')
   - the control cannot be retriggered for ≥10s: no button during cooldown,
     and no second request after a second click attempt
   - the cooldown state is module-scope JS, so a live re-render (the 2s tick)
     mid-cooldown repaints the confirmation, never a clickable button
   - after the cooldown the control is armed again (button returns)

   usage: node remindbtn.mjs <outdir> <port>   (own server; port ignored,
          a free one is taken — see posture.mjs for the port-collision why) */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, existsSync, readFileSync, writeFileSync, appendFileSync } from 'node:fs';
import { serveVerified } from './serve.mjs';
import { waitFor } from './dom.mjs';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { makeReporter } from './report.mjs';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv);
/* Own server on a free port (#475/#461): the guards recipe passes {{port}} to
   every guard, and a guard that reuses it dies "address in use" silently and
   grades the recipe's target. Take a free port; ignore argv[3]. */
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const { ok, present, declare, finish, notes, errs } = makeReporter();
declare({
  drives: 'scratch target on / — ambient remind button, one POST on click, ' +
          'confirmation visible, no retrigger for 10s across live re-renders, ' +
          'button returns after cooldown',
  traceWindow: 'POST observation via ctx request listener; cooldown is the ' +
               'real 10s (REMIND_COOLDOWN_MS); re-render survival sampled by ' +
               'waiting through 2s ticks inside the cooldown',
});

// Redirect the spawned server's /remind relay away from the real shared
// coordinator inbox (DREAMWORK_REMIND_INBOX_DIR → a scratch dir) so a guard
// run never appends a fake reminder the live coordinator would act on.
const inboxDir = join(OUT, 'coord-inbox');
process.env.DREAMWORK_REMIND_INBOX_DIR = inboxDir;

// Own target — no posture file, so the slot is the derived ambient state.
const dir = join(OUT, 'target');
rmSync(dir, { recursive: true, force: true });
cpSync('dev/capture/fixture', dir, { recursive: true });
const server = await serveVerified(dir, PORT);
const stop = () => { try { server.kill(); } catch (e) {} };
process.on('exit', stop);

const br = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-webgl'],
});
const ctx = await br.newContext({ viewport: { width: 1100, height: 900 } });
const p = await ctx.newPage();
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await waitFor(p, '#posture');

if (!(await present(p, '#posture', 'posture section'))) {
  await br.close();
  finish();
  process.exit(1);
}

// ── ambient slot shows the remind button ───────────────────────────────
const slotAmbient = await p.evaluate(() => {
  const src = document.getElementById('posture-src');
  const btn = document.getElementById('remind-btn');
  return {
    hasSrc: !!src,
    text: src ? src.textContent.trim() : '',
    hasBtn: !!btn,
    btnLabel: btn ? btn.textContent.trim() : '',
    btnDisabled: btn ? btn.disabled : null,
  };
});
notes.push('ambient slot: ' + JSON.stringify(slotAmbient));
ok('ambient #posture-src shows the remind button',
   slotAmbient.hasBtn && slotAmbient.btnLabel === 'remind');
ok('ambient button is not disabled (ready)',
   slotAmbient.hasBtn && slotAmbient.btnDisabled === false);
// Precondition: the old ambient text is gone — the slot no longer carries the
// useless 'derived from run mode' / 'override · .dreamwork/posture' note.
ok('ambient slot dropped the old override/derived note',
   !/derived from run mode|override ·/i.test(slotAmbient.text));

// ── click → exactly one POST /remind; confirmation visible ─────────────
const posts = [];
ctx.on('request', req => {
  if (req.method() === 'POST' && req.url().includes('/remind'))
    posts.push({ t: Date.now() });
});

// Guard the click so a missing button reports FAIL rather than throwing past
// the reporter (a thrown guard still fails, but loses its verdict lines).
try {
  await p.click('#remind-btn', { timeout: 5000 });
} catch (e) {
  errs.push('click #remind-btn: ' + e.message.split('\n')[0]);
}
// Poll for the POST + the confirmation text (the fetch is async).
let confirmed = false;
for (let i = 0; i < 40; i++) {
  const st = await p.evaluate(() => {
    const src = document.getElementById('posture-src');
    const btn = document.getElementById('remind-btn');
    return {
      text: src ? src.textContent.trim() : '',
      hasBtn: !!btn,
    };
  });
  if (posts.length >= 1 && /sent/i.test(st.text) && !st.hasBtn) {
    confirmed = true; break;
  }
  await sleep(100);
}
notes.push('after click: posts=' + posts.length + ' confirmed=' + confirmed);
ok('click sent exactly one POST /remind', posts.length === 1);
ok('confirmation visible after click (sent · …)',
   confirmed || await p.evaluate(
     () => /sent/i.test(document.getElementById('posture-src')?.textContent || '')));

const afterClick = await p.evaluate(() => {
  const src = document.getElementById('posture-src');
  const btn = document.getElementById('remind-btn');
  return { text: src ? src.textContent.trim() : '', hasBtn: !!btn };
});
notes.push('after click slot: ' + JSON.stringify(afterClick));
ok('no clickable remind button during cooldown (control at rest)',
   !afterClick.hasBtn);

// ── a second click inside the cooldown sends NO second request ──────────
// The button is gone, so a slot click must not POST. Then FORCE a real
// DATA-driven re-render during the cooldown: append a question so collect()
// returns different content and the built html differs from lastViewHtml —
// which is the only way past setContent's hash-skip so morphdom actually
// runs. A bare mtime bump does NOT suffice: if posturePicker ignored the
// cooldown it would rebuild the same button html, the hash would match, and
// morphdom would never run — the bug self-masks behind the skip (the first
// version of this check used an mtime-only bump and stayed green over the
// sabotage: a green red-run, reported). The production line this depends on
// is posturePicker reading remindCooldownUntil via remindSlotInner.
await p.evaluate(() => {
  const src = document.getElementById('posture-src');
  if (src) src.click();   // a slot click must not POST (no button lives here)
});
const qPath = join(dir, '.dreamwork', 'questions.md');
const qOrig = readFileSync(qPath, 'utf8');
appendFileSync(qPath,
  '\n- **remind render probe · 2026-07-30 — forces a re-render mid-cooldown.**' +
  ' → resolved (2026-07-30): a data change so morphdom runs past the hash-skip.\n');
await sleep(2600);        // >1 tick: the 2s /mtime poll + morphdom reconcile
const midCooldown = await p.evaluate(() => {
  const src = document.getElementById('posture-src');
  const btn = document.getElementById('remind-btn');
  return {
    text: src ? src.textContent.trim() : '',
    hasBtn: !!btn,
    stillSent: src ? /sent/i.test(src.textContent) : false,
  };
});
notes.push('mid-cooldown (post re-render): ' + JSON.stringify(midCooldown));
// Restore the fixture so the rearm phase grades the original layout.
writeFileSync(qPath, qOrig);
ok('cooldown survives a live re-render (still confirming, no button)',
   midCooldown.stillSent && !midCooldown.hasBtn);
ok('no second POST inside the cooldown', posts.length === 1);

// ── after the cooldown the control is armed again ──────────────────────
// Wait out the real 10s cooldown (REMIND_COOLDOWN_MS), then poll for the
// button to return — via the module-scope setTimeout repaint and/or the next
// posturePicker re-render reading the expired remindCooldownUntil.
let rearmed = false;
for (let i = 0; i < 60; i++) {
  const has = await p.evaluate(
    () => !!document.getElementById('remind-btn'));
  if (has) { rearmed = true; break; }
  await sleep(250);
}
notes.push('rearmed after cooldown: ' + rearmed);
ok('button returns after the cooldown (control armed again)', rearmed);
// And it did not fire a third request by reappearing.
ok('no extra POST from rearming', posts.length === 1);

await br.close();
stop();
finish();
