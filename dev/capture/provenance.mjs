/* provenance — #217: honest provenance coverage on the burndown panel.

   The panel draws who filed each task BY FIRST SIGHT (#216): human, loop,
   and the historical unknown remainder — drawn as itself, never folded
   into loop, never implied to be the loop's. The copy names the
   denominator (committed first sightings in recorded git history) and
   names incomplete coverage when the clone is shallow.

   THIS GUARD BUILDS ITS OWN TARGETS and takes ephemeral ports, for the
   reason burndown.mjs names: the shared fixture is not a git repository,
   so the datum under test could not exist there and every check would
   pass against nothing. The history here is PLANTED so the counts are
   known rather than read off the page and compared to themselves:

     c1  #1 origin: **human**      #2 (unmarked)
     c2  #2 gains origin: **human** (a LATER marker — first sight is
         final, so #2 stays unknown forever), #3 origin: **loop**
     c3  #4/#5 combined origin: **loop**, and #1 is DELETED (groomed —
         a first sight already happened and cannot be un-happened)

   …so the truthful answer is human 1 · loop 3 · historical unknown 1,
   five first sightings.

   RED-FIRST, for the failure this guard exists to name: with the
   classifier sabotaged to fail OPEN (`else "loop"` in entry_origins —
   the unknown remainder silently counted as the loop's), the load-bearing
   count assertion fails: the page reads `loop 4 · historical unknown 0`
   and the guard goes red. Restored, it is green. The sabotage is the
   exact lie #217 was filed against, which is why it is the one proven.

   usage: node provenance.mjs <outdir> [port, ignored] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { mkdirSync, rmSync, cpSync, writeFileSync } from 'node:fs';
import { spawn, execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { join } from 'node:path';

const OUT = process.argv[2];
const sleep = ms => new Promise(r => setTimeout(r, ms));
mkdirSync(OUT, { recursive: true });
/* deterministic evidence for the coordinator's visual review — the same
   plates on every run, so a diff is a change and not the weather */
const EVIDENCE = '.dreamwork/review/evidence/provenance-coverage-217';
mkdirSync(EVIDENCE, { recursive: true });
const freePort = () => new Promise(res => {
  const s = createServer();
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); });
});

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

// ── the planted ledger history ────────────────────────────────────────────
const DIR = join(OUT, 'target');
rmSync(DIR, { recursive: true, force: true });
cpSync('dev/capture/fixture', DIR, { recursive: true });
const T0 = 1784900000;   // pinned: the timestamps are data, not weather
const git = (dir, args, at) => execFileSync('git', ['-C', dir, ...args], {
  stdio: ['ignore', 'pipe', 'ignore'],
  env: { ...process.env,
         GIT_AUTHOR_NAME: 'guard', GIT_AUTHOR_EMAIL: 'g@x',
         GIT_COMMITTER_NAME: 'guard', GIT_COMMITTER_EMAIL: 'g@x',
         GIT_AUTHOR_DATE: `@${at} +0000`, GIT_COMMITTER_DATE: `@${at} +0000` },
}).toString().trim();
const HEAD_OF = '# Task ledger\n\nNext id: **99**\n\n## Open\n\n';
const commit = (text, at) => {
  writeFileSync(join(DIR, '.dreamwork', 'tasks.md'), text);
  git(DIR, ['add', '.dreamwork/tasks.md'], at);
  git(DIR, ['commit', '-q', '-m', `ledger at ${at}`], at);
};
git(DIR, ['init', '-q'], T0);
commit(HEAD_OF +
  '- **#1** — his steer · P2 · task · origin: **human**\n' +
  '- **#2** — filed before markers existed · P2 · task\n', T0);
commit(HEAD_OF +
  '- **#1** — his steer · P2 · task · origin: **human**\n' +
  '- **#2** — filed before markers existed · P2 · task · origin: **human**\n' +
  '- **#3** — the loop\'s own idea · P2 · task · origin: **loop**\n', T0 + 3600);
commit(HEAD_OF +
  '- **#2** — filed before markers existed · P2 · task · origin: **human**\n' +
  '- **#3** — the loop\'s own idea · P2 · task · origin: **loop**\n' +
  '- **#4/#5** — a combined filing · P2 · task · origin: **loop**\n', T0 + 7200);

const SERVERS = [];
const startServer = async (target) => {
  const port = await freePort();
  /* Pin the server's right-edge clock as well as the browser's Date.now.
     ledger_series extends its final bucket to time.time(); without this seam
     the screenshot's right label drifted with wall time even though every Git
     timestamp was fixed — evidence that changes by waiting is not deterministic. */
  const boot = `import sys, watch\nwatch.time.time = lambda: ${T0 + 8000}\nwatch.main(sys.argv[1:])`;
  const srv = spawn('python3', ['-c', boot, '--target', target,
                               '--port', String(port)], { stdio: 'ignore' });
  /* a live child holds the event loop open, so every server is killed
     before finishing (the exit handler is only the backstop) — the first
     version of this guard hung at the end over exactly this */
  SERVERS.push(srv);
  process.on('exit', () => { try { srv.kill(); } catch (e) {} });
  const base = `http://127.0.0.1:${port}`;
  for (let i = 0; i < 40; i++) {
    try {
      const d = await (await fetch(`${base}/data.json`)).json();
      if (d.target === target) return { srv, base };
    } catch (e) { /* not up yet */ }
    await sleep(250);
  }
  throw new Error(`server for ${target} never came up on :${port}`);
};

const { base: BASE } = await startServer(DIR);
{
  const d = await (await fetch(`${BASE}/data.json`)).json();
  notes.push(`served provenance: ${JSON.stringify(d.burndown.provenance)}`);
  ok('the server emits the provenance datum at all (else the page half ' +
     'of this guard is vacuous)',
     d.burndown && d.burndown.provenance &&
     d.burndown.provenance.human === 1 && d.burndown.provenance.loop === 3 &&
     d.burndown.provenance.unknown === 1 && d.burndown.provenance.total === 5 &&
     d.burndown.provenance.history_complete === true);
}

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

/* reads the whole datum back out of the DOM. Everything the guard asserts
   is measured here, never re-derived — a check that rebuilds its own
   expectation passes over an absent subject. */
const READ = `(() => {
  const prov = document.querySelector('.bd .bdprov');
  if (!prov) return { present: false };
  const bar = prov.querySelector('.provbar');
  const segs = [...prov.querySelectorAll('.provseg')];
  const barW = bar.getBoundingClientRect().width;
  const probe = document.createElement('span');
  probe.style.color = 'var(--accent)';
  document.body.appendChild(probe);
  const accent = getComputedStyle(probe).color;
  probe.remove();
  const paints = [prov, ...prov.querySelectorAll('*')].map(el =>
    getComputedStyle(el).color + '|' + getComputedStyle(el).backgroundColor +
    '|' + getComputedStyle(el).borderTopColor + '|' +
    getComputedStyle(el).borderBottomColor);
  const line = prov.querySelector('.provline');
  const docW = document.documentElement.clientWidth;
  const bdEl = document.querySelector('.bd');
  return {
    present: true,
    legend: (line.textContent || '').trim(),
    srcs: [...prov.querySelectorAll('.provsrc')].map(s => s.textContent.trim()),
    aria: bar.getAttribute('aria-label'),
    segClasses: segs.map(s => s.className.replace('provseg', '').trim()),
    segPcts: segs.map(s => barW ? s.getBoundingClientRect().width / barW : -1),
    segTitles: segs.map(s => s.getAttribute('title')),
    segBg: segs.map(s => getComputedStyle(s).backgroundImage),
    keyColors: [...line.querySelectorAll('span')].map(s => getComputedStyle(s).color),
    accentUsed: paints.some(p => p.includes(accent)),
    legendClipped: line.scrollWidth > line.clientWidth + 1,
    /* the datum's OWN overflow. The document-level scrollWidth is NOT the
       check here: the composer's ... menu overflows the 390px viewport by
       ~120px on d278b7b already (measured, pre-existing, not this
       surface), and folding that into this guard would report somebody
       else's bug as this feature's. What #217 owes is that ITS block —
       and the panel it lives in — never sticks out. */
    provOverflow: bdEl.getBoundingClientRect().right > docW + 1 ||
                  bar.getBoundingClientRect().right > docW + 1 ||
                  prov.scrollWidth > prov.clientWidth + 1 ||
                  line.scrollWidth > line.clientWidth + 1,
    pageOverflow: document.scrollingElement.scrollWidth >
                  document.documentElement.clientWidth,
    transitions: [...prov.querySelectorAll('*')].some(el =>
      getComputedStyle(el).transitionDuration !== '0s'),
  };
})()`;

/* the causal ready handshake: the datum is THERE, with the planted counts
   rendered — not a fixed sleep, which reports the poll's phase as the
   page's state. Plus document.fonts.ready, so the plates below are the
   settled type and not a mid-swap frame. */
const ready = async (page, legendBit) => {
  await page.waitForFunction((bit) => {
    const l = document.querySelector('.bd .provline');
    return l && l.textContent.includes(bit);
  }, legendBit, { timeout: 15000 });
  await page.evaluate('document.fonts.ready');
};
/* OUT is deliberately caller-owned and usually a fresh temp path. It is a
   useful server-isolation premise, but not visual data: normalise only the
   target crumb before capture so two equivalent runs do not differ by `a`
   versus `b` in `/tmp/prov-a/target`. The real target/path was already proven
   through /data.json and the provenance assertions above. */
const normaliseCaptureChrome = page => page.evaluate(() => {
  const target = document.querySelector('.crumb[data-k="target"]');
  if (target) target.textContent = '/fixture/provenance/target';
});
const shaderHealthy = page => page.evaluate(async () => {
  const cv = document.getElementById('dreambg');
  const gl = cv && cv.getContext('webgl');
  const before = window.dreambg && window.dreambg.frames;
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  return getComputedStyle(document.body).backgroundColor === 'rgb(11, 15, 25)' &&
    gl && !gl.isContextLost() && window.dreambg &&
    window.dreambg.frames > before;
});
const plateIsDark = (page, png) => page.evaluate(async b64 => {
  const image = new Image();
  image.src = 'data:image/png;base64,' + b64;
  await image.decode();
  const cv = document.createElement('canvas');
  cv.width = image.width; cv.height = image.height;
  const g = cv.getContext('2d'); g.drawImage(image, 0, 0);
  const points = [[5,5], [image.width - 6,5], [5,image.height - 6],
                  [image.width - 6,image.height - 6]];
  const luma = points.map(([x,y]) => {
    const p = g.getImageData(x,y,1,1).data;
    return (p[0] + p[1] + p[2]) / 3;
  });
  return luma.every(v => v < 80);
}, png.toString('base64'));
const capturePair = async (page, prefix) => {
  for (let attempt = 0; attempt < 3; attempt++) {
    if (!await shaderHealthy(page)) {
      await page.reload({ waitUntil:'networkidle' });
      await ready(page, 'historical unknown');
      continue;
    }
    await normaliseCaptureChrome(page);
    const panel = await (await page.$('.bd')).screenshot();
    const full = await page.screenshot();
    if (await shaderHealthy(page) && await plateIsDark(page, full)) {
      for (const root of [OUT, EVIDENCE]) {
        writeFileSync(`${root}/provenance-${prefix}-panel.png`, panel);
        writeFileSync(`${root}/provenance-${prefix}.png`, full);
      }
      return;
    }
    await page.reload({ waitUntil:'networkidle' });
    await ready(page, 'historical unknown');
  }
  throw new Error(`${prefix} capture never reached a dark, live shader frame`);
};

// ── desktop: 1440x1000 ────────────────────────────────────────────────────
const p = await br.newPage({ viewport: { width: 1440, height: 1000 } });
p.on('pageerror', e => errs.push(String(e)));
/* the shader's phase is the wall clock, so two runs are never the same
   pixels; the clock is frozen for the captures, the way worldspace.mjs
   does it, so the plates are evidence rather than weather */
await p.addInitScript(`Date.now = () => ${T0 + 8000}000;`);
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
await ready(p, 'historical unknown');

const rd = await p.evaluate(READ);
notes.push(`desktop: ${JSON.stringify(rd)}`);
ok('the burndown panel carries the provenance block (else everything ' +
   'here is vacuous)', rd.present);
/* THE LOAD-BEARING ASSERTION, and the one the red-first sabotage breaks:
   the exact counts, with the historical unknown stated as itself. #2 was
   marked human an hour AFTER it arrived and still reads unknown, because
   first sight is final; #1 was deleted and still counts, because first
   sight cannot be un-happened. */
ok('the counts are the planted first sightings, exactly — ' +
   'human 1 · loop 3 · historical unknown 1',
   rd.legend === 'human 1 · loop 3 · historical unknown 1');
ok('...and the unknown remainder is NOT rolled into loop (the sabotage ' +
   'this guard was shown red against)', !/loop 4/.test(rd.legend));
ok('the denominator names its source and its scope',
   rd.srcs.length === 1 &&
   rd.srcs[0] === '5 first sightings in recorded git history');
ok('a complete history does NOT claim to be incomplete',
   !rd.srcs.some(s => s.includes('incomplete')));
ok('the bar is three segments in human / loop / unknown order',
   rd.segClasses.join(',') === 'phuman,ploop,punknown');
ok('...and their geometry IS the counts: 20% / 60% / 20% of the bar',
   rd.segPcts.every(x => x >= 0) &&
   Math.abs(rd.segPcts[0] - 0.2) < 0.02 &&
   Math.abs(rd.segPcts[1] - 0.6) < 0.02 &&
   Math.abs(rd.segPcts[2] - 0.2) < 0.02 &&
   Math.abs(rd.segPcts.reduce((a, b) => a + b, 0) - 1) < 0.03);
ok('colour never carries the split alone: unknown is a HATCH, ' +
   'human and loop are solid',
   rd.segBg[2].includes('gradient') &&
   rd.segBg[0] === 'none' && rd.segBg[1] === 'none');
ok('...and the legend keys wear their segment\'s ramp step',
   new Set(rd.keyColors).size === 3);
ok('every segment states its count on hover (detail already summarised ' +
   'on screen — the hover idiom, not the only copy)',
   rd.segTitles.join('|') === 'human 1|loop 3|historical unknown 1');
ok('the aria-label is the whole datum in words',
   !!rd.aria && rd.aria.includes('human 1') && rd.aria.includes('loop 3') &&
   rd.aria.includes('historical unknown 1') &&
   rd.aria.includes('5 first sightings in recorded git history'));
ok('the accent is not spent here — nothing in this panel waits on him',
   rd.accentUsed === false);
ok('the datum has NO motion: a live tick commits its DOM instantly ' +
   '(transitions.md), so reduced-motion parity is the identical visual',
   rd.transitions === false);
ok('no horizontal overflow at 1440px, and the legend is not clipped',
   rd.pageOverflow === false && rd.provOverflow === false &&
   rd.legendClipped === false);

/* the plates. Element shots of the panel for the datum itself, page shots
   for the composition it lives in. */
await capturePair(p, 'desktop');
await p.close();

// ── mobile: 390x844 ───────────────────────────────────────────────────────
{
  const mp = await br.newPage({ viewport: { width: 390, height: 844 } });
  mp.on('pageerror', e => errs.push(String(e)));
  await mp.addInitScript(`Date.now = () => ${T0 + 8000}000;`);
  await mp.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await ready(mp, 'historical unknown');
  const rm = await mp.evaluate(READ);
  notes.push(`mobile: ${JSON.stringify(rm)}`);
  ok('mobile: the same datum, whole — labels, counts and denominator ' +
     'do not disappear at 390px',
     rm.present && rm.legend === 'human 1 · loop 3 · historical unknown 1' &&
     rm.srcs[0] === '5 first sightings in recorded git history');
  ok('mobile: the datum itself never sticks out of the viewport, and ' +
     'the legend is not clipped (the composer menu\'s 390px overflow is ' +
     'pre-existing — measured on d278b7b — and not this surface)',
     rm.provOverflow === false && rm.legendClipped === false);
  ok('mobile: the segments keep their proportions',
     rm.segPcts.every(x => x >= 0) &&
     Math.abs(rm.segPcts[1] - 0.6) < 0.02);
  await capturePair(mp, 'mobile');
  await mp.close();
}

// ── a shallow clone must NAME its incomplete coverage ─────────────────────
/* depth 1 sees only c3, so its walk reads #2 as human (the later marker is
   the only one visible), reports four sightings, and knows nothing of #1.
   That distortion is exactly what the incomplete line exists to confess —
   a quiet "human 1 · loop 3 · unknown 0" would read as fact. */
{
  const dst = join(OUT, 'shallow');
  rmSync(dst, { recursive: true, force: true });
  execFileSync('git', ['clone', '-q', '--depth', '1', 'file://' + DIR, dst]);
  const { base } = await startServer(dst);
  const sp = await br.newPage({ viewport: { width: 1440, height: 1000 } });
  sp.on('pageerror', e => errs.push(String(e)));
  await sp.goto(`${base}/`, { waitUntil: 'networkidle' });
  await ready(sp, 'historical unknown');
  const rs = await sp.evaluate(READ);
  notes.push(`shallow: ${JSON.stringify(rs)}`);
  ok('a shallow clone answers from what it can see (and no further)',
     rs.present && rs.legend === 'human 1 · loop 3 · historical unknown 0');
  ok('...and NAMES the incompleteness rather than reading as fact',
     rs.srcs.some(s => s.includes('coverage is incomplete')));
  ok('...in the aria-label too, because the label is the whole datum',
     !!rs.aria && rs.aria.includes('coverage is incomplete'));
  await sp.close();
}

ok('no page errors', errs.length === 0);
await br.close();
for (const s of SERVERS) { try { s.kill(); } catch (e) {} }
finished = true;
process.exitCode = checks.some(c => c.startsWith('FAIL')) ? 1 : 0;
