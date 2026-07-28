/* #462 — the staleness row's remedy: a copyable `just deploy` appears when the
   page falls behind, arrives atmospherically (one-shot .dreamin), and is
   absent when current.

   The row already named the fault (#140); the missing thing was the action.
   This guard covers the three behaviours that decide whether the affordance
   is usable:

     1. ONLY WHEN TRUE — present when behind, absent when current.
     2. ARRIVES, DOES NOT POP — the current→behind transition eases the
        remedy in through the .dreamin start pose, sampled mid-transition
        (never an end-state assert), with reduced-motion parity.
     3. ACTS — a click copies the deploy command and confirms on the page's
        one confirmation lifecycle.

   IT BUILDS ITS OWN TARGET (like serving.mjs) because the state under test is
   a relationship between the RUNNING bytes and a repo's watch.py history, and
   it drives the arrival through a real TICK (a target commit bumps
   .git/logs/HEAD mtime → /mtime changes → tick re-renders →
   revealStaleAction), because a full reload SETTLES first paint and would
   never show the arrival. The server is started with serveVerified (#461) so
   the responder is provably ours — two orphaned servers made a correct change
   read as broken tonight.

   usage: node staleremedy.mjs <outdir> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';
import { serveVerified } from './serve.mjs';
import { midFrames, transitionWindow, framesInWindow } from './dom.mjs';

const OUT = process.argv[2];
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
    actionCopy: act ? act.dataset.copy : '',
  };
})()`;

/* A rAF trace of .gservact's opacity from before the arrival through its
   settle, plus the transition events for opacity ON the affordance (captured
   at the document with capture, since transitionstart's target is the node
   itself). transitionstart is the load-independent snap detector (#442): a
   compositor-driven opacity transition can draw zero rAF samples inside its
   window under load, so `ran` asks the browser whether it animated, and
   midFrames is the motion evidence only when the sampler caught the window. */
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
  await sleep(900);
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
  // install the trace, then evolve to behind: a target commit bumps
  // .git/logs/HEAD mtime, the next tick re-renders, revealStaleAction fires
  // the arrival (knownStaleAction was false from this page's first paint).
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
  // PRECONDITION, derived at runtime — never a literal tuned to this tree: a
  // genuine current→behind transition. Without it the arrival check below is
  // vacuous (settling on a page that was already behind never poses).
  ok('...the state really moved current→behind (or the arrival is vacuous)',
     beforeState === 'current' && after.state === 'behind' &&
     (after.missing || []).length >= 1);
  ok('behind: the remedy is present and names the deploy command',
     present.length > 0 && (await p.evaluate(READ)).actionCopy === 'just deploy');
  // #442 SNAP DETECTOR: the browser registered a CSS opacity transition for
  // the arrival. A snap (.dreamin never removed, or the pose baked in) fires
  // none. This line cannot be defeated by frame rate.
  ok('behind: the remedy arrives via a CSS transition, not a snap', win.ran);
  // MOTION: when the trace sampled inside the window, an intermediate opacity
  // is direct evidence; under contention transitionstart already proved it.
  ok('behind: the arrival eases through intermediate opacity',
     win.ran && (sampled ? midFrames(ops) >= 1 : true));
  await ctx.close();
}

// ── 3. a click copies the command and confirms on the one lifecycle ──────
{
  const ctx = await br.newContext({
    viewport: { width: 1100, height: 1000 },
    permissions: ['clipboard-read', 'clipboard-write'],
  });
  const p = await ctx.newPage();
  p.on('pageerror', e => errs.push(String(e)));
  await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await p.waitForSelector('.gservact');
  await p.click('.gservact');
  await sleep(300);
  const note = (await p.locator('#fmsg').textContent()) || '';
  const clip = await p.evaluate(() => navigator.clipboard.readText().catch(() => ''));
  notes.push(`copy: note=${JSON.stringify(note)} clip=${JSON.stringify(clip)}`);
  ok('click copies the deploy command to the clipboard', clip === 'just deploy');
  ok('click confirms on the page\'s one lifecycle', /copied/.test(note) && /update/.test(note));
  await ctx.close();
}

// ── 4. reduced motion — the remedy still appears, never ramps ────────────
{
  // reset to current so the same transition can run under reduced motion
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
  // reduced-motion is a hard contract: timing changes, never function or
  // legibility. The pose is never applied, so no opacity transition fires and
  // every frame is at the settled value.
  ok('reduced: the remedy never ramps opacity', !win.ran &&
     ops.every(o => o >= 95));
  await ctx.close();
}

ok('no page errors', errs.length === 0);
finished = true;
await br.close();
try { srv.kill(); } catch (e) {}
process.exit(checks.some(c => c.startsWith('FAIL')) ? 1 : 0);
