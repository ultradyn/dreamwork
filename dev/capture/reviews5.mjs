/* reviews5 — #545: the dashboard reviews panel caps at the most recent
   REVIEWS_DASH_CAP rows and links to /reviews; /reviews lists every
   artifact through the same artifactRow factory.

   Two contracts, both content (not motion — a live re-render commits its
   DOM instantly, transitions.md): (1) with more than the cap the panel
   shows exactly the cap and a link line naming the total; at or below the
   cap it renders exactly as before, no link, no "5 of 5" noise. (2) /reviews
   renders the full set, and the dashboard's capped rows are the same rows
   (same data-review identity, same factory).

   Own target/server because the shared fixture has no review artifacts and
   this guard needs more than the cap. The total is DERIVED from the
   filesystem (never a literal tuned to today); the cap value (5) is the
   spec constant the guard pins, so a drift in watch.py's REVIEWS_DASH_CAP
   fails here rather than passing silently.
   usage: node reviews5.mjs <outdir> [ignored-port] */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { cpSync, mkdirSync, readdirSync, rmSync, writeFileSync, renameSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';
import { outdir } from './outdir.mjs';
import { makeReporter } from './report.mjs';

const r = makeReporter();
const { ok, declare, finish } = r;
declare({ drives: 'dashboard (/) cap + link, and /reviews full listing',
          traceWindow: 'none — content counts, not motion (transitions.md: a ' +
                       'live re-render commits instantly; no gesture to trace)' });

const OUT = outdir(process.argv);
mkdirSync(OUT, { recursive: true });
const target = join(OUT, 'target');
cpSync(new URL('./fixture', import.meta.url), target, { recursive: true });
const rd = join(target, '.dreamwork', 'review');
mkdirSync(rd, { recursive: true });

/* atomic recreate gives a stable, distinct birth (review_artifact.py's
   write path; #463). */
const recreate = (name, body = null) => {
  const path = join(rd, name);
  const content = body ?? `<!doctype html><p>${name}`;
  const tmp = path + '.tmp';
  writeFileSync(tmp, content);
  renameSync(tmp, path);
};
const totalOnDisk = () =>
  readdirSync(rd).filter(n => n.endsWith('.html')).length;

// 7 artifacts — comfortably above the cap of 5.
for (let i = 1; i <= 7; i++) {
  recreate(`r0${i}.html`);
  await new Promise(res => setTimeout(res, 40));   // distinct birth resolution
}

const srv = spawn('python3', ['-u', 'watch.py', '--target', target, '--port', '0'],
  { stdio: ['ignore', 'pipe', 'inherit'] });
const line = await new Promise((resolve, reject) => {
  let s = '';
  srv.stdout.on('data', b => { s += b; const m = s.match(/http:\/\/[^:]+:(\d+)/); if (m) resolve(m[1]); });
  srv.on('exit', reject);
});
const base = `http://127.0.0.1:${line}`;

const rowsOn = async (p, path) => {
  await p.goto(base + path, { waitUntil: 'networkidle' });
  await p.waitForFunction(() => {
    const rows = document.querySelectorAll('[data-review]');
    return rows.length > 0;
  }, { timeout: 8000 }).catch(() => {});
  return await p.evaluate(() =>
    [...document.querySelectorAll('[data-review]')].map(n => ({
      name: n.dataset.review, })));
};

try {
  const br = await chromium.launch({ args: ['--use-gl=swiftshader'] });
  try {
    /* ── Phase A: more than the cap ─────────────────────────────────── */
    const total = totalOnDisk();
    ok(`COVERAGE #545: fixture has more reviews than the cap (total ${total} > 5)`,
       total > 5);

    const p = await br.newPage({ viewport: { width: 1000, height: 1100 } });
    const dash = await rowsOn(p, '/');
    const dashNames = dash.map(x => x.name);
    ok(`#545 dashboard caps at ${5} when total is ${total} (saw ${dash.length})`,
       dash.length === 5);
    // The link line names the total honestly and points at the full list.
    const link = await p.evaluate(() => {
      const a = document.querySelector('a[href="/reviews"]');
      return a ? { text: a.textContent.trim(), href: a.getAttribute('href') } : null;
    });
    ok(`#545 dashboard link names the total: "all ${total} reviews →"`,
       !!link && link.text === `all ${total} reviews →` && link.href === '/reviews');

    // /reviews lists every artifact.
    const all = await rowsOn(p, '/reviews');
    const allNames = all.map(x => x.name);
    ok(`#545 /reviews lists the full set (saw ${all.length}, expected ${total})`,
       all.length === total);
    // A row on the dashboard and a row on /reviews are the same row: the
    // capped set is a subset of the full listing (same data-review identity).
    ok(`#545 dashboard rows are a subset of /reviews (same factory, same rows)`,
       dashNames.length === 5 && dashNames.every(n => allNames.includes(n)));

    /* ── Phase B: at or below the cap ──────────────────────────────── */
    // Wipe and seed exactly 3 — under the cap, so the panel renders every
    // row and carries NO link line (no "3 of 3" noise).
    rmSync(rd, { recursive: true, force: true });
    mkdirSync(rd, { recursive: true });
    for (let i = 1; i <= 3; i++) {
      recreate(`s0${i}.html`);
      await new Promise(res => setTimeout(res, 40));
    }
    const few = totalOnDisk();
    ok(`COVERAGE #545: low fixture is at or below the cap (total ${few} <= 5)`,
       few > 0 && few <= 5);

    const dashFew = await rowsOn(p, '/');
    ok(`#545 dashboard shows all ${few} rows under the cap (saw ${dashFew.length})`,
       dashFew.length === few);
    const linkFew = await p.evaluate(() =>
      !!document.querySelector('a[href="/reviews"]'));
    ok(`#545 no link line when total (${few}) is within the cap`, linkFew === false);

    const allFew = await rowsOn(p, '/reviews');
    ok(`#545 /reviews lists all ${few} rows under the cap (saw ${allFew.length})`,
       allFew.length === few);

    await p.close();
  } finally { await br.close(); }
} finally { srv.kill(); }

finish();
console.log(r.checks.join('\n'));
process.exitCode = r.checks.some(x => x.startsWith('FAIL')) ? 1 : 0;
