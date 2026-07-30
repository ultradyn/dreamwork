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
   - #553: the cooldown-end setTimeout does NOT clobber a live arm —
     press remind, then arm a posture override mid-cooldown, advance past
     the cooldown (page.clock); the slot stays 'arming override…', never
     the resurrected button

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
          'button returns after cooldown; #553: the cooldown-end setTimeout ' +
          'does not clobber a live arm (page.clock interleaving)',
  traceWindow: 'POST observation via ctx request listener; cooldown is the ' +
               'real 10s (REMIND_COOLDOWN_MS); re-render survival sampled by ' +
               'waiting through 2s ticks inside the cooldown; #553 advances ' +
               'virtual time past the cooldown via page.clock runFor while a ' +
               'posture arm is live',
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

// ── #553: the cooldown-end setTimeout must not clobber a live arm ──────
// The defect: sendRemind's setTimeout(paintRemindSlot, REMIND_COOLDOWN_MS)
// repaints #posture-src unconditionally when the cooldown ends. If the human
// armed a posture override DURING that window the armed state
// ('arming override…') is live, and the timer's repaint resurrects the
// remind button — hiding the armed copy until the next data tick (≤2s,
// morphdom self-heals). The fix: paintRemindSlot early-returns on
// pendingPostIsLive(readPostPending()), the same predicate the armed state
// itself uses (paintSlot at watch.py:~5548). No second test of arm-ness.
//
// page.clock (bdinput (d)/(e) is the landed idiom) fakes the production
// timers. clock.install is called BEFORE the second remind so the cooldown
// setTimeout is created AFTER install — provably faked, firing at the
// exact virtual time (not real time), which is what makes the interleaving
// deterministic rather than load-dependent: a timer scheduled before
// install fires on REAL wall time, so the real-time delta between the
// remind and the install decides whether the clobber lands before or after
// the arm — and under load that delta crosses 7s and the check goes green
// over the bug. The arm is started 3s into virtual time, so its RUN_ARM_MS
// (10s) outlives the remind cooldown's fire point by ≥3s: when the
// cooldown-end repaint runs the arm is live by construction. The fixture's
// content is unchanged across this phase, so the /mtime tick's hash-skip
// holds — a re-render here would self-heal the bug and the red-run would
// stay green over it (the exact failure mode the repo warns about: a check
// that launders the value it was written to catch). The test's own sleep/poll
// uses Node timers, which page.clock does NOT fake.
const postsBefore553 = posts.length;
// Install page.clock BEFORE the remind so the cooldown setTimeout is faked
// (created after install). Virtual time freezes at T0 = real-now; runFor
// fires due fake timers exactly. The page's fetch (real network I/O) and
// the test's Node sleep/poll are unaffected by clock faking.
await p.clock.install();
// Press remind again for a fresh cooldown (the first expired in the rearm
// phase above). The click triggers sendRemind → real fetch (resolves on
// real I/O) → remindCooldownUntil = Date.now()+10000 = T0+10000 (virtual
// Date) → setTimeout(paintRemindSlot, 10000) at virtual T0+10000 (FAKE).
// Exactly one more POST expected.
try {
  await p.click('#remind-btn', { timeout: 5000 });
} catch (e) {
  errs.push('#553 click #remind-btn: ' + e.message.split('\n')[0]);
}
let confirmed553 = false;
for (let i = 0; i < 40; i++) {
  const st = await p.evaluate(() => {
    const src = document.getElementById('posture-src');
    return {
      text: src ? src.textContent.trim() : '',
      hasBtn: !!document.getElementById('remind-btn'),
    };
  });
  if (posts.length === postsBefore553 + 1 && /sent/i.test(st.text) && !st.hasBtn) {
    confirmed553 = true; break;
  }
  await sleep(100);
}
notes.push('#553 fresh remind: confirmed=' + confirmed553 +
           ' posts=' + posts.length);
ok('#553 precondition: a fresh remind started (one more POST, confirming)',
   confirmed553 && posts.length === postsBefore553 + 1);
// Advance 3s of virtual time — still inside the 10s cooldown (the fake
// cooldown setTimeout fires at virtual T0+10000). This gives the arm a 3s
// head-start so it is live for ≥3s PAST the cooldown-end repaint.
await p.clock.runFor(3000);
// Precondition: the cooldown is still active at this virtual time — the
// setTimeout has NOT fired yet. If it already fired the interleaving is
// vacuous and the check cannot catch the bug; fail loudly, never silently.
const preArm553 = await p.evaluate(() => {
  const src = document.getElementById('posture-src');
  return {
    text: src ? src.textContent.trim() : '',
    hasBtn: !!document.getElementById('remind-btn'),
  };
});
notes.push('#553 pre-arm slot (cooldown still active): ' +
           JSON.stringify(preArm553));
ok('#553 precondition: cooldown still active when arming (sent, no button)',
   /sent/i.test(preArm553.text) && !preArm553.hasBtn);
// Arm a posture override: pick a DIFFERENT pace stop ('steady' vs the
// committed default 'idle'). This writes a live pending entry (until =
// virtual-now + RUN_ARM_MS = T0+13000) and paints 'arming override…' in
// the slot. Production line: pickPostureAxis → armPostureDraft → writePostPending.
await p.evaluate(() => pickPostureAxis('pace', 'steady'));
const armedSlot553 = await p.evaluate(() => {
  const src = document.getElementById('posture-src');
  return {
    text: src ? src.textContent.trim() : '',
    hasBtn: !!document.getElementById('remind-btn'),
    pendingLive: pendingPostIsLive(readPostPending()),
  };
});
notes.push('#553 armed slot (the arm took the slot): ' +
           JSON.stringify(armedSlot553));
ok('#553 precondition: the arm is live and the slot reads "arming override…"',
   armedSlot553.pendingLive && /arming override/i.test(armedSlot553.text));
// Advance to virtual T0+10000: fires the fake cooldown setTimeout
// (paintRemindSlot) while the arm is still live (until T0+13000, 3s margin).
// The arm's own commit setTimeout (T0+13000) does NOT fire.
await p.clock.runFor(7000);
const afterCooldown553 = await p.evaluate(() => {
  const src = document.getElementById('posture-src');
  const btn = document.getElementById('remind-btn');
  return {
    text: src ? src.textContent.trim() : '',
    hasBtn: !!btn,
    btnLabel: btn ? btn.textContent.trim() : '',
    pendingLive: pendingPostIsLive(readPostPending()),
  };
});
notes.push('#553 after cooldown setTimeout fired: ' +
           JSON.stringify(afterCooldown553));
// The fix: paintRemindSlot early-returns on pendingPostIsLive, so the armed
// copy survives the timer. The bug: the timer resurrects the remind button,
// visually withdrawing a state the human created.
ok('#553 cooldown-end repaint does not clobber a live arm (slot still armed)',
   afterCooldown553.pendingLive
   && /arming override/i.test(afterCooldown553.text)
   && !afterCooldown553.hasBtn);
await p.clock.resume();

await br.close();
stop();
finish();
