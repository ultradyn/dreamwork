/* plugcmd — #86: the commands a plugin declares, in the composer that has to
   offer them.

   THE GAP THIS CLOSES WAS BETWEEN A CONTRACT AND A UI. `writing-plugins.md`
   has granted plugins their own command namespace in prose since there were
   plugins; the loop has written the declaration into
   `.dreamwork/plugin-commands.json`; `lint.py` has policed that file. Nothing
   rendered it. The human re-raised it twice.

   WHAT IT ASSERTS THAT A SCREENSHOT WOULD NOT:

     - ABSENCE COSTS NOTHING, and this runs FIRST. Almost every target loads
       no plugin that declares a command, so the composer with no file is the
       common case and it must render exactly as it did before any of this
       existed. A check that only ever sees the populated page passes on a
       build that requires the file.
     - the declared commands reach the page AT ALL, which is the feature, and
       reach it on a page that was already open — the set is a property of the
       machine, so it can change under him.
     - they ARRIVE rather than appearing, when they land under his eye. The
       menu's items had no opacity transition of their own and `.cmdmenuitem`
       declares one LATER in the sheet at the same specificity, so `.qreveal`
       lost and the fade was silently a no-op — #154 one component over, which
       is why this measures intermediate opacities and not the end state.
     - ...and the SURVIVING items neither move nor re-arrive: the menu is
       reconciled by kind, not rebuilt, so an arrival is legible as an arrival.
     - a plugin CANNOT promote itself into the main row. Loading one may add
       to the composer and may never degrade it; the row is the composer's
       most valuable real estate and there is deliberately no way to ask.
     - the server ACCEPTS what the composer offers. A menu entry that 400s is
       worse than no menu entry, and the two halves live in different files.
     - unloading is the absence of a write, so the entries go — and his
       selection falls back rather than being left pointing at a kind the
       server now refuses.
     - reduced motion changes the timing and not the function.

   SHOWN RED FIVE WAYS, each break reddening only the checks that name it:

     - `plugin_commands` taken back out of `collect()` — three checks, all
       saying the commands never arrived, and none of them a timeout.
     - `renderMenu` rebuilding with `innerHTML` — the survivors' nodes are
       gone and all four core items "re-arrive".
     - the `.cmdmenuitem.qreveal` rule deleted — 1 distinct part-way opacity
       and 2 distinct transforms. Note what stayed GREEN through that:
       "starts from nothing" and "finishes at full opacity". The bug is
       entirely in the middle, which is why the count of intermediate values
       is the assertion and the end state is not.
     - `common` honoured from the file — the row grows to five.
     - `watched_mtime` back to statting only files — the unload checks, which
       is how that bug was found in the first place: absence has to be
       observable or "unloading is the absence of a write" is not a contract.

   usage: node plugcmd.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, writeFileSync, rmSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
const OUT = process.argv[2], PORT = process.argv[3] || '39899';
const BASE = `http://127.0.0.1:${PORT}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });

const checks = []; const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
const notes = [];
const errs = [];
let finished = false;
process.on('exit', () => {
  if (!finished) checks.push('FAIL the guard threw before finishing its checks');
  console.log(notes.join('\n'));
  console.log('----');
  console.log(checks.join('\n'));
  if (errs.length) console.log(errs.join('\n'));
});

/* The guard drives the FILE, because the file is the interface. It learns
   where the target is from the page itself rather than being told: every
   script here takes (OUT, PORT) and nothing else, and the server already
   answers the question. */
const target = await (await fetch(`${BASE}/data.json`)).json()
  .then(d => d.target).catch(() => null);
if (!target) { ok('the server answered /data.json (nothing below can run)', false);
               process.exit(1); }
const DECL = join(target, '.dreamwork', 'plugin-commands.json');
const DECLARED = JSON.parse(readFileSync(DECL, 'utf8'));
const unload = () => rmSync(DECL, { force: true });
const load = (doc = DECLARED) => writeFileSync(DECL, JSON.stringify(doc));
const TICK = 2600;              // the page polls at 2000ms

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

const menu = p => p.evaluate(`[...document.querySelectorAll('.cmdmenuitem')].map(n => ({
  kind: n.dataset.kind,
  label: n.querySelector('.cmk').textContent,
  plugin: (n.querySelector('.cmpl') || {}).textContent || null,
  colour: n.querySelector('.cmpl')
    ? getComputedStyle(n.querySelector('.cmpl')).color : null,
}))`);
const row = p => p.evaluate(`[...document.querySelectorAll('.cmdkind')].map(n => ({
  kind: n.dataset.kind, title: n.title }))`);

async function openComposer(p) {
  if (!await p.evaluate(`!!document.querySelector('#cmdpalette.open')`)) {
    await p.click('#cmdplus'); await sleep(700);
  }
}
/* The menu opens on hover in CSS, which is the real gesture — there is no
   click that opens it, so automating one would be checking a door nobody
   uses. It re-opens the PANEL first every time, because the panel closes
   itself 1425ms after a send (#131's courtesy) and a phase that reopened it
   two lines earlier can still be hovering at a `visibility:hidden` menu by
   the time it gets here — which costs a 30s timeout reported as a throw. */
const openMenu = async p => {
  await openComposer(p);
  await p.hover('#cmdmore');
  await sleep(500);
};

/* ── 1. against nothing, FIRST ────────────────────────────────────────────
   Absence is the common case and the one a populated fixture hides. */
unload();
const p = await br.newPage({ viewport: { width: 1100, height: 1000 } });
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
await sleep(1200);
await openComposer(p);

/* the subject, before anything drives it: a build without the composer costs
   a 30s Playwright timeout reported as "the guard threw", which says nothing
   about the page (dev/capture/README.md) */
const HAVE = await p.evaluate(`!!document.querySelector('#cmdmenu')`);
ok('the composer has a command menu (else every check below is about a page ' +
   'that has none)', HAVE);

let CORE = [];
/* Everything from §3 down DRIVES a plugin command — clicks it, sends it,
   watches it go. On a build where none arrived those are clicks at a selector
   that will never resolve: thirty seconds each, reported as "the guard threw",
   which says nothing about the page (dev/capture/README.md). §2 sets this, and
   the phases below skip rather than repeat the timeout. */
let LANDED = false;
if (HAVE) {
  await openMenu(p);
  const m = await menu(p);
  CORE = m.map(x => x.kind);
  notes.push(`no file: menu ${JSON.stringify(CORE)}, row ${
    JSON.stringify((await row(p)).map(r => r.kind))}`);
  ok('with no plugin-commands.json the menu still lists the core commands',
     m.length >= 3);
  // the failure this names: a composer that needs the file to render at all
  ok('...and none of them claims a plugin', m.every(x => x.plugin === null));
  const r = await row(p);
  ok('...and the main row is the common kinds, unchanged',
     r.length >= 3 && r.every(x => CORE.indexOf(x.kind) >= 0));
  const ind = await p.evaluate(
    `(document.querySelector('#cmdind') || {}).offsetWidth || 0`);
  ok('...and the selection indicator has landed on a button', ind > 10);
}

/* ── 2. it arrives, and it arrives rather than appearing ──────────────────
   The menu is OPEN in front of him while the set changes: that is the case
   that needs a gesture, and it is the case this drives. The window is bounded
   to the arrival itself — 800ms from the frame the item first exists — so a
   later tick cannot supply the movement the assertion is about. */
if (HAVE) {
  await openMenu(p);
  // mark the survivors by NODE, so "was it replaced" is answerable afterwards
  await p.evaluate(`document.querySelectorAll('.cmdmenuitem')
    .forEach((n, i) => { n.__survivor = 'core' + i; })`);
  const trace = p.evaluate(`new Promise(res => {
    const seen = []; const t0 = performance.now();
    (function step() {
      seen.push({ t: performance.now() - t0,
        items: [...document.querySelectorAll('.cmdmenuitem')].map(n => ({
          kind: n.dataset.kind,
          op: +getComputedStyle(n).opacity,
          tr: getComputedStyle(n).transform,
          survivor: n.__survivor || null })) });
      if (performance.now() - t0 < 4200) requestAnimationFrame(step); else res(seen);
    })();
  })`);
  await sleep(100);
  load();
  const seen = await trace;
  const declared = DECLARED.commands.map(c => c.kind);

  const arrivedAt = k => seen.findIndex(f => f.items.some(i => i.kind === k));
  const missing = declared.filter(k => arrivedAt(k) < 0);
  LANDED = missing.length === 0;
  ok('the declared commands reach a page that was ALREADY OPEN (the feature; ' +
     `missing: ${JSON.stringify(missing)})`, LANDED);

  if (LANDED) {
    for (const k of declared) {
      const at = arrivedAt(k), t0 = seen[at].t;
      const win = seen.slice(at).filter(f => f.t - t0 <= 800);
      const ops = win.map(f => f.items.find(i => i.kind === k).op);
      const mid = [...new Set(ops.filter(o => o > 0.02 && o < 0.98))];
      const last = ops[ops.length - 1];
      notes.push(`${k}: first at ${Math.round(t0)}ms, ${ops.length} frames, ` +
        `${mid.length} distinct part-way opacities, first ${ops[0]}, last ${last}`);
      // AN END-STATE CHECK CANNOT FAIL ON THIS. `.qreveal` losing to
      // `.cmdmenuitem`'s own later transition produces an item that is fully
      // opaque on its first frame and correct forever after.
      ok(`${k} EASES IN rather than blinking on (distinct part-way opacities)`,
         mid.length >= 3);
      ok(`${k} starts from nothing rather than animating toward it`,
         ops[0] < 0.15);
      ok(`${k} finishes at full opacity and never overshoots on the way`,
         last > 0.98 && ops.every(o => o <= 1.001));
      const trs = [...new Set(win.map(f =>
        f.items.find(i => i.kind === k).tr))];
      ok(`${k} drifts as well as fades (${trs.length} distinct transforms)`,
         trs.length >= 3);
    }
    /* THE SURVIVORS. A rebuild would look identical at the end and would drop
       any hover or focus he was holding — and would make every item an
       arrival, so the fade above would be meaningless. */
    const end = seen[seen.length - 1].items;
    const kept = end.filter(i => CORE.indexOf(i.kind) >= 0);
    ok('the core items were RECONCILED, not re-created (their nodes survived)',
       kept.length === CORE.length && kept.every(i => i.survivor));
    const flickered = CORE.filter(k => seen.some(f => {
      const i = f.items.find(x => x.kind === k); return i && i.op < 0.98; }));
    ok(`...and none of them re-arrived (${JSON.stringify(flickered)})`,
       flickered.length === 0);
    ok('the declared commands come AFTER the core ones, appended',
       end.slice(0, CORE.length).map(i => i.kind).join() === CORE.join());
  }
}

/* ── 3. attributed, quietly, and never promoted ──────────────────────────── */
if (HAVE && LANDED) {
  await openMenu(p);
  const m = await menu(p);
  const plugged = m.filter(x => x.plugin);
  notes.push(`attributed: ${JSON.stringify(plugged)}`);
  ok('a plugin command names the plugin that answers it, on the item',
     plugged.length === DECLARED.commands.length &&
     plugged.every(x => x.plugin === 'ud-dreamwork-github'));
  // QUIETLY: --dimmer, the same step as the history's ages. Provenance is not
  // an errand, and the accent on this page means "this needs you".
  const dimmer = await p.evaluate(
    `getComputedStyle(document.documentElement).getPropertyValue('--dimmer').trim()`);
  const want = 'rgb(' + [1, 3, 5].map(i => parseInt(dimmer.slice(i, i + 2), 16))
    .join(', ') + ')';
  ok(`...at the quietest step of the ramp, not the accent (${want})`,
     plugged.every(x => x.colour === want));
  const r = await row(p);
  notes.push(`row after load: ${JSON.stringify(r.map(x => x.kind))}`);
  // there is deliberately no way for a plugin to ask for this
  ok('a plugin CANNOT promote itself into the main row',
     r.every(x => CORE.indexOf(x.kind) >= 0));
  /* Keyboard-only: focus the dots button, then Tab into the first declared
     plugin command. `focus-within` is the menu's actual open state; a click
     here would prove only the pointer path and leave #209 untouched. Do this
     AFTER checking non-promotion: selecting an uncommon kind deliberately
     gives it a row seat for the indicator. */
  await p.focus('.cmdmorebtn');
  let keyboard = { kind: null, visible: false };
  for (let i = 0; i < CORE.length + 2; i++) {
    await p.keyboard.press('Tab');
    keyboard = await p.evaluate(`({
      kind: (document.activeElement.dataset || {}).kind || null,
      visible: !!(document.activeElement.closest &&
        document.activeElement.closest('#cmdmenu')) &&
        getComputedStyle(document.activeElement).visibility === 'visible'
    })`);
    if (keyboard.kind === 'gh-sync') break;
  }
  notes.push(`keyboard reached ${JSON.stringify(keyboard)}`);
  ok('a keyboard-only path reaches a visible plugin command',
     keyboard.kind === 'gh-sync' && keyboard.visible);
  if (keyboard.kind === 'gh-sync') await p.keyboard.press('Enter');
  ok('...and Enter selects it through the same command path',
     await p.evaluate(`document.querySelector('.cmdkind.on').dataset.kind`) ===
       'gh-sync');
}

/* ── 4. the server accepts what the composer offers ───────────────────────
   The two halves are in different files and a menu entry that 400s is worse
   than no menu entry: he sends a thought and gets `rejected (400)`. */
if (HAVE && LANDED) {
  await openComposer(p); await openMenu(p);
  await p.click('.cmdmenuitem[data-kind="gh-sync"]');
  await sleep(300);
  const r = await row(p);
  notes.push(`row with a plugin kind selected: ${JSON.stringify(r)}`);
  ok('a selected plugin kind gets a button, so the indicator has a seat',
     r.some(x => x.kind === 'gh-sync'));
  const seat = r.find(x => x.kind === 'gh-sync');
  ok('...whose title names the plugin, for the choice he made an hour ago',
     !!seat && /ud-dreamwork-github/.test(seat.title));
  // Wait for the confirmation rather than sampling at a fixed offset, and
  // read it from `#cmdmsg` — the node `confirmationFor` (#255) writes on a
  // successful POST. `querySelector('.cmdmsg')` resolves to `#fmsg` (the
  // FILE message shares the class and sits earlier in the DOM, watch.py:1562),
  // which is always empty here; reading it returned `""` over a product that
  // was working and kept this check red for the wrong reason. `confirmation.mjs`
  // uses this same `cmdmsg.textContent === 'sent to the dream'` condition; the
  // page exposes `cmdmsg` as the autoglobal for id=cmdmsg.
  await p.evaluate(() => {
    document.getElementById('cmdtext').value = 'a plugin steer ' + Date.now();
    document.getElementById('cmdform').requestSubmit();
  });
  let said = '';
  try {
    await p.waitForFunction(
      () => (cmdmsg.textContent || '').trim() !== '',
      { timeout: 4000 });
  } catch (_) { /* bounded timeout: leave said empty, the message reports it */ }
  said = await p.evaluate(() => cmdmsg.textContent || '');
  notes.push(`sending gh-sync said ${JSON.stringify(said)}`);
  ok('POST /command ACCEPTS a plugin kind — confirmation on #cmdmsg (saw '
     + JSON.stringify(said) + '; a menu entry that 400s is worse than no '
     + 'menu entry)', /sent to the dream/.test(said));
  const log = readFileSync(join(target, '.dreamwork', 'watch-events.log'), 'utf8');
  ok('...and it reaches the loop by the same transport as a core command',
     /gh-sync/.test(log));
}

/* ── 5. unloading is the absence of a write ───────────────────────────────
   And the half that only bites later: his selection is now a kind that no
   longer exists, and the row would go on offering it. */
if (HAVE && LANDED) {
  await openComposer(p);
  unload();
  await sleep(TICK);
  await openMenu(p);
  const m = await menu(p);
  const r = await row(p);
  notes.push(`after unload: menu ${JSON.stringify(m.map(x => x.kind))}, ` +
             `row ${JSON.stringify(r.map(x => x.kind))}`);
  ok('unloading takes the commands out of the menu with nobody deleting them',
     m.every(x => x.plugin === null) && m.length === CORE.length);
  ok('...and his selection falls back to a core kind rather than pointing at ' +
     'one the server now refuses', r.every(x => CORE.indexOf(x.kind) >= 0) &&
     await p.evaluate(`!!document.querySelector('.cmdkind.on')`));
}

/* ── 6. landing while the menu is SHUT is not an appearance ───────────────
   Nothing was on screen, so nothing appeared; the menu's own reveal is what
   brings these in when he next opens it. The risk in saying that is a stuck
   half-faded item, so that is what this looks for. */
if (HAVE) {
  await p.evaluate(`document.getElementById('cmdmore').dispatchEvent(
    new PointerEvent('pointerleave', { bubbles: true }))`);
  await p.mouse.move(5, 5);
  await sleep(500);
  load();
  await sleep(TICK);
  await openMenu(p);
  const state = await p.evaluate(`[...document.querySelectorAll('.cmdmenuitem')]
    .map(n => ({ kind: n.dataset.kind, cls: n.className,
                 op: +getComputedStyle(n).opacity }))`);
  notes.push(`landed while shut: ${JSON.stringify(state)}`);
  ok('commands that landed while the menu was shut are simply there when it ' +
     'opens', state.length === CORE.length + DECLARED.commands.length);
  ok('...fully visible, with no enter class left stuck on them',
     state.every(s => s.op > 0.98 && !/dreamin|qreveal/.test(s.cls)));
}

await openComposer(p); await openMenu(p);
await p.screenshot({ path: `${OUT}/plugcmd.png`, fullPage: false });

/* ── 7. reduced motion: the timing goes, the function does not ───────────── */
if (HAVE) {
  unload();
  const rp = await br.newPage({ viewport: { width: 1100, height: 1000 },
                                reducedMotion: 'reduce' });
  rp.on('pageerror', e => errs.push('reduced: ' + String(e)));
  await rp.goto(`${BASE}/questions`, { waitUntil: 'networkidle' });
  await sleep(1200);
  await openComposer(rp); await openMenu(rp);
  const trace = rp.evaluate(`new Promise(res => {
    const seen = []; const t0 = performance.now();
    (function step() {
      seen.push({ t: performance.now() - t0,
        items: [...document.querySelectorAll('.cmdmenuitem')].map(n => ({
          kind: n.dataset.kind, op: +getComputedStyle(n).opacity })) });
      if (performance.now() - t0 < 4200) requestAnimationFrame(step); else res(seen);
    })();
  })`);
  await sleep(100);
  load();
  const seen = await trace;
  const end = seen[seen.length - 1].items.map(i => i.kind);
  const partial = seen.flatMap(f => f.items.filter(i => i.op > 0.02 && i.op < 0.98));
  notes.push(`reduced: ends with ${JSON.stringify(end)}, ` +
             `${partial.length} part-way frames`);
  ok('reduced motion still gets the commands (timing, never function)',
     DECLARED.commands.every(c => end.indexOf(c.kind) >= 0));
  ok('...and they are simply there, with no fade', partial.length === 0);
  await rp.screenshot({ path: `${OUT}/plugcmd-reduced.png` });
  await rp.close();
}

ok('no page errors', errs.length === 0);
await br.close();
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
