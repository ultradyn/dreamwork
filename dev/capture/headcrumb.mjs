/* headcrumb — #491: the head's version crumb sits beside the freshness age,
   and a bare migration filename in that slot read to him as "this file
   changed Ns ago". It is not — it is the target's RECORDED skill version
   (.dreamwork/skill-version, written by orient), a deliberately different
   source from the skill tree's latest migration (skill_identity). The value
   is honest; the defect was the adjacency implying an age the value does not
   carry, because the crumb named nothing about what it IS.

   THE CHECK THAT CANNOT EXIST AS A PYTEST SUBSTRING. The crumb is built in
   JS (crumbsFor), so the rendered adjacency is invisible to Python. The
   bug is one of reading, not data shape: `files['skill-version']` is correct
   and stays. What changed is the crumb says what its value IS (a skill
   version), so the neighbour "updated Ns ago" no longer supplies the meaning.

   TWO ASSERTIONS, AND ONLY THE SECOND REDS ON THE BUG:

     - the crumb carries the recorded version name. A guard that only checked
       "a label word is present" would pass against a crumb that dropped the
       name entirely, so the name is derived from /data.json (never a literal
       tuned to today's fixture) and required in the rendered text.
     - the crumb is LABELED — its text contains a word naming it as a skill
       version, so it is not a bare filename that the adjacent freshness age
       can attach to. This is the assertion the bare-filename bug fails.

   Ordinary (OUT, PORT) on the shared server: the datum is the fixture's own
   skill-version, read through the real crumb. usage: node headcrumb.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';

const OUT = process.argv[2];
const PORT = process.argv[3];
const sleep = ms => new Promise(r => setTimeout(r, ms));
const BASE = `http://127.0.0.1:${PORT}`;

const { ok, present, declare, finish, notes, errs } = makeReporter();
declare({
  drives: '/ on the shared server; reads the head crumb row (#meta)',
  traceWindow: 'one settled read after load (~1.2s); no motion — the claim is '
             + 'the crumb\'s text, not its arrival',
});

// the recorded version name, derived from the server (never a literal). The
// fixture carries a real skill-version; a guard that hard-coded today's name
// would pass against a crumb showing a different one.
const data = await (await fetch(`${BASE}/data.json`)).json();
const recorded = (data.files && data.files['skill-version']) || '';
notes.push(`recorded skill-version: ${recorded || '<none>'}`);
ok('the fixture carries a recorded skill-version (else this guard is hollow)',
   recorded.length > 0);

const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });
const ctx = await br.newContext({ viewport: { width: 1100, height: 900 } });
const p = await ctx.newPage();
p.on('pageerror', e => errs.push(String(e)));
await p.goto(`${BASE}/`, { waitUntil: 'networkidle' });
// #536 render readiness — wait for the #meta crumbs area the guard reads first, not a fixed sleep (#428 class)
await waitFor(p, '#meta');


// the version crumb is keyed 'version' in crumbsFor. Absence-first: name the
// holder before reading it, so a build without the crumb is a named FAIL and
// not a selector timeout reported as "the guard threw".
const hasVersion = await present(p, '#meta [data-k="version"]', 'the version crumb');
const crumbText = hasVersion ? await p.evaluate(
  () => (document.querySelector('#meta [data-k="version"]') || {}).textContent || '') : '';
notes.push(`version crumb text: ${crumbText.trim() || '<empty>'}`);

ok('the crumb carries the recorded version name (derived, not a literal)',
   recorded && crumbText.includes(recorded));

/* THE BUG: a bare filename in this slot reads, beside "updated Ns ago", as
   "this file changed Ns ago". The crumb must NAME what its value is — a skill
   version — so the adjacent freshness age no longer supplies the meaning. The
   assertion is on a label WORD, not on exact prose: the contract is "says
   what it IS", and pinning the wording would freeze copy this guard has no
   stake in. A bare migration filename (YYYY-MM-DD-NN-slug.md) contains no
   space and no identifying word, so it fails this. */
ok('the crumb labels itself as a skill version, not a bare filename '
   + '(else the adjacent freshness age implies an age it does not carry)',
   hasVersion && /\b(skill|version|ran)\b/i.test(crumbText) && /\s/.test(crumbText));

ok('no page errors', errs.length === 0);
finish();
await br.close();
