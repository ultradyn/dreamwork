/* #462 — the staleness row's remedy: when the page falls behind, `just deploy`
   arrives atmospherically (one-shot .dreamin) and RUNS the deploy (authorised
   2026-07-29 03:46) behind the #290 arm and writeVerdict, never as a bare
   copy.

   Covers:

     1. ONLY WHEN TRUE — present when behind, absent when current.
     2. ARRIVES, DOES NOT POP — current→behind eases through .dreamin,
        sampled mid-transition, reduced-motion parity.
     3. ARMS then ACTS — click arms for RUN_ARM_MS (reused, not a second
        cooldown); a landed POST gates on writeVerdict; a rejected 202 does
        not claim success; a deploy that never finishes is named.
     4. DRAFTS SURVIVE a reload — #269 localStorage keys outlive the
        generation-triggered reload the action relies on.

   IT BUILDS ITS OWN TARGET (like serving.mjs) because the state under test is
   a relationship between the RUNNING bytes and a repo's watch.py history, and
   it drives the arrival through a real TICK. The server is started with
   serveVerified (#461). The deploy command is NEVER actually run — routes
   are fulfilled. Both success (landed) and failure (rejected) are driven.

   usage: node staleremedy.mjs <outdir> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { serveVerified } from './serve.mjs';
import { midFrames, transitionWindow, framesInWindow, waitFor } from './dom.mjs';

import { outdir } from './outdir.mjs';
const OUT = outdir(process.argv);
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});
const PORT = await freePort();

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = []; const errs = [];
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errs.length) console.log(errs.join('\n'));
});

// ── a target whose history we control ─────────────────────────────────────
const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
const git = args => execFileSync('git', ['-C', DIR, ...args], {
  stdio: ['ignore', 'pipe', 'ignore'],
  env: { ...process.env,
         GIT_AUTHOR_NAME: 'guard', GIT_AUTHOR_EMAIL: 'g@x',
         GIT_COMMITTER_NAME: 'guard', GIT_COMMITTER_EMAIL: 'g@x' },
}).toString().trim();
const commitWatch = (bytes, msg) => {
  writeFileSync(join(DIR, 'watch.py'), bytes);
  git(['add', 'watch.py']);
  git(['commit', '-q', '-m', msg]);
  return git(['rev-parse', '--short', 'HEAD']);
};
git(['init', '-q']);
git(['add', 'DREAMWORK.md']);
git(['commit', '-q', '-m', 'a project that is not this dashboard']);
// the bytes the server is RUNNING (this guard's own watch.py). Committed into
// the target first so the page starts CURRENT — the precondition for an
// arrival the next state change can actually produce.
const RUNNING = readFileSync('watch.py');
commitWatch(RUNNING, 'feat: the revision this guard is running');

const srv = await serveVerified(DIR, PORT);
process.on('exit', () => { try { srv.kill(); } catch (e) {} });
const BASE = `http://127.0.0.1:${PORT}`;
const deployedOf = async () => {
  const d = await (await fetch(`${BASE}/data.json`)).json();
  return d.deployed || {};
};

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

const READ = `(() => {
  const el = document.querySelector('.gserve');
  const act = document.querySelector('.gservact');
  return {
    present: !!el,
    text: el ? el.textContent : '',
    hasAction: !!act,
    actionText: act ? act.textContent : '',
    arming: !!(act && act.classList.contains('arming')),
    running: !!(act && act.classList.contains('running')),
  };
})()`;

/* A rAF trace of .gservact's opacity from before the arrival through its
   settle, plus the transition events for opacity ON the affordance (captured
   at the document with capture, since transitionstart's target is the node
   itself). transitionstart is the load-independent snap detector (#442). */
const TRACE = ms => `((ms)=>new Promise(res=>{
  const frames=[], events=[];
  let done=false; const finish=()=>{if(!done){done=true;res({frames,events})}};
  const t0=performance.now();
  const onT=type=>e=>{
    if(e.propertyName!=='opacity') return;
    const el=e.target;
    if(el&&el.classList&&el.classList.contains('gservact'))
      events.push({type,prop:e.propertyName,t:Math.round(performance.now()-t0)});
  };
  document.addEventListener('transitionrun',onT('run'),true);
  document.addEventListener('transitionstart',onT('start'),true);
  document.addEventListener('transitionend',onT('end'),true);
  (function f(){
    const el=document.querySelector('.gservact');
    const t=performance.now()-t0;
    frames.push({t:Math.round(t),present:!!el,
                 op:el?Math.round(parseFloat(getComputedStyle(el).opacity)*100):null});
    t<ms?requestAnimationFrame(f):finish();
  })();
}))(${ms})`;

// ── 1. current — the remedy is absent (nothing to act on) ────────────────
let beforeState;
{
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1000 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  // #536 render readiness — wait for the .gserve row the guard reads first, not a fixed sleep (#428 class)
  await waitFor(p, '.gserve');
  beforeState = (await deployedOf()).state;
  const r = await p.evaluate(READ);
  notes.push(`current: state=${beforeState} hasAction=${r.hasAction} text=${JSON.stringify(r.text)}`);
  ok('current: the row is rendered', r.present);
  ok('current: the remedy is absent (nothing to act on)', !r.hasAction);
  await ctx.close();
}

// ── 2. behind, via a real tick — the remedy ARRIVES through .dreamin ─────
{
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1000 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await sleep(900);
  const traceP = p.evaluate(TRACE(6000));
  await sleep(200);
  commitWatch(Buffer.from('# a newer dashboard he cannot see\n'),
              'fix: a change he cannot see');
  const seen = await traceP;
  const after = await deployedOf();
  const frames = seen.frames, events = seen.events;
  const present = frames.filter(f => f.present);
  const ops = present.map(f => f.op);
  const firstT = present[0]?.t ?? null;
  const win = transitionWindow(events, 'opacity', firstT ?? 0, 'first');
  const inside = framesInWindow(present, win);
  const sampled = inside >= 2;
  notes.push(`behind arrival: state=${after.state} missing=${(after.missing||[]).length} ` +
             `present frames=${present.length} op range=` +
             `${ops.length ? Math.min(...ops) + '-' + Math.max(...ops) : 'n/a'} ` +
             `transition ran=${win.ran} inside=${inside}/${present.length}`);
  // PRECONDITION, derived at runtime — never a literal tuned to this tree.
  ok('...the state really moved current→behind (or the arrival is vacuous)',
     beforeState === 'current' && after.state === 'behind' &&
     (after.missing || []).length >= 1);
  ok('behind: the remedy is present and names just deploy',
     present.length > 0 && /just deploy/.test((await p.evaluate(READ)).actionText
       || (await p.evaluate(READ)).text));
  ok('behind: the remedy arrives via a CSS transition, not a snap', win.ran);
  ok('behind: the arrival eases through intermediate opacity',
     win.ran && (sampled ? midFrames(ops) >= 1 : true));
  await ctx.close();
}

// ── 3. click arms (RUN_ARM_MS idiom), re-click cancels ───────────────────
// Production line: armStaleDeploy / onStaleActionClick cancel branch.
// Red: delete the arming class toggle or the cancel path.
{
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1000 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await p.waitForSelector('.gservact');
  await p.click('.gservact');
  await sleep(200);
  const armed = await p.evaluate(READ);
  // #569: the arming countdown was recused from #fmsg into the posture
  // widget's #pdep slot; read it there (the .gservact button still carries
  // the short "arms in Ns" label too).
  const armNote = (await p.locator('#pdep').textContent()) || '';
  notes.push(`arm: arming=${armed.arming} text=${JSON.stringify(armed.actionText)} ` +
             `note=${JSON.stringify(armNote)}`);
  ok('arm: first click arms the control (RUN_ARM_MS idiom)',
     armed.arming === true && /arms in/.test(armed.actionText + armNote));
  // re-click cancels — same as re-selecting the committed run mode
  await p.click('.gservact');
  await sleep(200);
  const cancelled = await p.evaluate(READ);
  const cancelNote = (await p.locator('#fmsg').textContent()) || '';
  notes.push(`cancel: arming=${cancelled.arming} note=${JSON.stringify(cancelNote)}`);
  ok('arm: re-click cancels before the POST',
     cancelled.arming === false && /cancelled/.test(cancelNote));
  await ctx.close();
}

// ── 3b. #490/#569 — arm countdown is steady text on #pdep, no .dreamin ──
// Production line: armStaleDeploy's setCount → paintDeployStatus (#pdep).
// #490's original concern was a ~4 Hz .dreamin flash when the arm countdown
// re-noted #fmsg every 250ms poll. #569 recused the countdown into #pdep,
// which uses paintDeployStatus (plain text + an explicit width, exactly like
// the posture arm's #pcount) and NEVER adds .dreamin — so the flash is
// structurally impossible. This check binds that: #pdep carries the steady
// arming countdown and never takes the .dreamin class. Red: route the
// countdown back through confirmationFor's note/claim (which re-adds
// .dreamin on every show), or drop paintDeployStatus from setCount.
{
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1000 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await p.waitForSelector('.gservact');
  await p.click('.gservact');
  await sleep(350);
  const flash = await p.evaluate(async () => {
    const m = document.getElementById('pdep');
    if (!m) return { ok: false, why: 'no #pdep' };
    let dreaminAdds = 0;
    let textChanges = 0;
    let lastText = m.textContent;
    const texts = [lastText];
    const mo = new MutationObserver(() => {
      if (m.classList.contains('dreamin')) dreaminAdds++;
      const t = m.textContent;
      if (t !== lastText) {
        textChanges++;
        lastText = t;
        texts.push(t);
      }
    });
    mo.observe(m, {
      attributes: true, attributeFilter: ['class'],
      childList: true, characterData: true, subtree: true,
    });
    await new Promise(r => setTimeout(r, 1400));
    mo.disconnect();
    return {
      ok: true, dreaminAdds, textChanges, texts,
      final: m.textContent, stillArming: /arms in/.test(m.textContent || ''),
    };
  });
  notes.push(`#490/#569 flash: ${JSON.stringify(flash)}`);
  ok('#490/#569 precondition — arm countdown is on #pdep after settle',
     flash.ok === true && flash.stillArming === true);
  // #pdep uses plain text (paintDeployStatus), so .dreamin never appears on
  // it — the #490 flash is structurally impossible after the #569 recuse.
  ok('#490/#569 arm countdown never takes .dreamin (plain-text idiom)',
     flash.ok === true && flash.dreaminAdds === 0);
  await ctx.close();
}

// ── 4. a REJECTED deploy does not claim success (writeVerdict) ───────────
// Production line: fireStaleDeploy's writeVerdict gate. Red: gate on res.ok
// alone (E5b) or delete the refused note. Fires the production function
// directly (the arm is checked above) so the 10s wait is not the subject.
{
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1000 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await p.waitForSelector('.gservact');
  let posted = 0;
  await p.route('**/deploy', async route => {
    posted++;
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: false, rejected: true, reason: 'domain_invalid',
      }),
    });
  });
  await p.evaluate(async () => {
    staleDeployGen = 1;
    staleDeployPhase = 'running';
    await fireStaleDeploy(1);
  });
  await sleep(400);
  const note = (await p.locator('#fmsg').textContent()) || '';
  const r = await p.evaluate(READ);
  notes.push(`rejected: posted=${posted} note=${JSON.stringify(note)} ` +
             `running=${r.running}`);
  ok('rejected: the page POSTed /deploy (not a silent no-op)', posted >= 1);
  ok('rejected: writeVerdict refuses a 202+rejected body',
     /refused|not one the server accepts|try again/i.test(note));
  ok('rejected: the control is not left spinning as running', !r.running);
  await ctx.close();
}

// ── 5. a landed deploy that never finishes is named ──────────────────────
// Production line: the DEPLOY_WAIT_MS timeout branch and its copy.
// Red: delete the 'update never finished' note.
// window.__dwDeployWaitMs shortens the deadline (guard inject; production
// never sets it) so this is not a 30s sleep.
{
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1000 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.addInitScript(() => { window.__dwDeployWaitMs = 800; });
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await p.waitForSelector('.gservact');
  let posted = 0;
  await p.route('**/deploy', async route => {
    posted++;
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, started: true }),
    });
  });
  await p.evaluate(async () => {
    window.__dwDeployWaitMs = 800;
    staleDeployGen = 1;
    staleDeployPhase = 'running';
    await fireStaleDeploy(1);
  });
  await sleep(1500);
  const note = (await p.locator('#fmsg').textContent()) || '';
  notes.push(`timeout: posted=${posted} note=${JSON.stringify(note)}`);
  ok('timeout: POST landed (started:true)', posted >= 1);
  ok('timeout: the page names a deploy that never finishes',
     /never finished/.test(note) && /still the old one/.test(note));
  await ctx.close();
}

// ── 6. drafts survive a reload (the generation-bump path #462 relies on) ─
// Production line: dw:adraft: localStorage partition (#269). Red: nothing in
// this guard's production code — the claim is that a restart destroys the
// server, not storage; we prove storage outlives location.reload().
{
  const ctx = await br.newContext({ viewport: { width: 1100, height: 1000 } });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await sleep(500);
  const planted = await p.evaluate(() => {
    const t = document.body.dataset.target
      || (window.data && window.data.target) || '';
    // data.target is on the server payload; read from the live data binding.
    const target = (typeof data !== 'undefined' && data && data.target) || '';
    if (!target) return { ok: false, why: 'no target' };
    const key = 'dw:adraft:' + target + ':guard-question-title';
    localStorage.setItem(key, 'half-typed words that must survive');
    return { ok: true, key, target };
  });
  notes.push(`draft plant: ${JSON.stringify(planted)}`);
  ok('draft: precondition — a partitioned draft key was planted',
     planted.ok === true);
  await p.reload({ waitUntil: 'networkidle' });
  await sleep(400);
  const survived = await p.evaluate((key) => localStorage.getItem(key),
                                    planted.key);
  notes.push(`draft after reload: ${JSON.stringify(survived)}`);
  ok('draft: the half-typed words survive a full reload',
     survived === 'half-typed words that must survive');
  await ctx.close();
}

// ── 7. reduced motion — the remedy still appears, never ramps ────────────
{
  commitWatch(RUNNING, 'feat: back to the running revision');
  const ctx = await br.newContext({
    viewport: { width: 1100, height: 1000 }, reducedMotion: 'reduce',
  });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await sleep(900);
  const traceP = p.evaluate(TRACE(6000));
  await sleep(200);
  commitWatch(Buffer.from('# a different newer dashboard\n'),
              'fix: another change he cannot see');
  const seen = await traceP;
  const after = await deployedOf();
  const frames = seen.frames, events = seen.events;
  const present = frames.filter(f => f.present);
  const ops = present.map(f => f.op);
  const firstT = present[0]?.t ?? null;
  const win = transitionWindow(events, 'opacity', firstT ?? 0, 'first');
  notes.push(`reduced arrival: state=${after.state} present frames=${present.length} ` +
             `op range=${ops.length ? Math.min(...ops) + '-' + Math.max(...ops) : 'n/a'} ` +
             `transition ran=${win.ran}`);
  ok('reduced: the remedy still appears when behind', present.length > 0 &&
     after.state === 'behind');
  ok('reduced: the remedy never ramps opacity', !win.ran &&
     ops.every(o => o >= 95));
  await ctx.close();
}

ok('no page errors', errs.length === 0);
finished = true;
await br.close();
try { srv.kill(); } catch (e) {}
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
