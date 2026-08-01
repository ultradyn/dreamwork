/* drawmode — #738: the per-browser draw preference follows across tabs.

   Two pages in ONE BrowserContext are two tabs of the same browser profile:
   they share localStorage and receive one another's storage events. This is
   the distinction a single-page check cannot make.

   Production seams red-proved:
     - pickDrawMode's direct setDrawModePreference call: the writing tab must
       apply because storage never fires there;
     - adoptDrawModePreferenceFromStorage's key branch: the already-open
       sibling must adopt the change without a reload or server round trip.

   usage: node drawmode.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { waitFor } from './dom.mjs';
import { makeReporter } from './report.mjs';
import { mkdirSync } from 'node:fs';
import { outdir } from './outdir.mjs';

const OUT = outdir(process.argv), PORT = process.argv[3] || '39899';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });
const { ok, declare, finish, notes } = makeReporter();
declare({
  drives: '/ dashboard draw-mode controls in two already-open tabs sharing one browser context',
  traceWindow: 'event-driven state; waitFor observes the radio state in each tab',
});

const browser = await chromium.launch({
  args: ['--use-gl=swiftshader', '--enable-webgl'],
});
const context = await browser.newContext({ viewport: { width: 1100, height: 950 } });
const writer = await context.newPage();
const sibling = await context.newPage();
const errs = [];
writer.on('pageerror', e => errs.push('writer: ' + String(e)));
sibling.on('pageerror', e => errs.push('sibling: ' + String(e)));

for (const page of [writer, sibling]) {
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await waitFor(page, '.drawpick');
  await page.evaluate(() => {
    const real = window.dreambg.setDrawMode.bind(window.dreambg);
    window.__drawModeCalls = [];
    window.dreambg.setDrawMode = mode => {
      window.__drawModeCalls.push(mode);
      return real(mode);
    };
  });
}

const choose = async (page, mode) => {
  await page.click(`.drawpick [data-drawmode="${mode}"]`);
  await waitFor(page, `.drawpick [data-drawmode="${mode}"][aria-checked="true"]`);
};
const adopted = async (page, mode) => {
  for (let i = 0; i < 20; i++) {
    const yes = await page.evaluate(want =>
      document.querySelector('.drawpick [aria-checked="true"]')?.dataset.drawmode
        === want, mode);
    if (yes) return true;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  return false;
};
const observed = page => page.evaluate(() => ({
  mode: window.dreambg.drawMode,
  checked: document.querySelector('.drawpick [aria-checked="true"]')?.dataset.drawmode,
  calls: window.__drawModeCalls.slice(),
  stored: localStorage.getItem('dw:draw-mode'),
}));

await choose(writer, 'paused');
const siblingAdoptedPaused = await adopted(sibling, 'paused');
const w1 = await observed(writer), s1 = await observed(sibling);
notes.push('writer -> paused: ' + JSON.stringify({ writer: w1, sibling: s1 }));
ok('the writing tab applied its own change exactly once (storage does not fire there)',
   w1.mode === 'paused' && w1.checked === 'paused' &&
   JSON.stringify(w1.calls) === JSON.stringify(['paused']));
ok('the sibling tab adopted the writer change exactly once without a reload',
   siblingAdoptedPaused && s1.mode === 'paused' && s1.checked === 'paused' &&
   JSON.stringify(s1.calls) === JSON.stringify(['paused']));

await choose(sibling, 'light');
const writerAdoptedLight = await adopted(writer, 'light');
const w2 = await observed(writer), s2 = await observed(sibling);
notes.push('sibling -> light: ' + JSON.stringify({ writer: w2, sibling: s2 }));
ok('sync is bidirectional: the first tab adopted the sibling change once',
   writerAdoptedLight && w2.mode === 'light' && w2.checked === 'light' &&
   JSON.stringify(w2.calls) === JSON.stringify(['paused', 'light']));
ok('the second writing tab also applied locally exactly once',
   s2.mode === 'light' && s2.checked === 'light' &&
   JSON.stringify(s2.calls) === JSON.stringify(['paused', 'light']));
ok('both tabs expose the same per-browser persisted value',
   w2.stored === 'light' && s2.stored === 'light');
ok('the two-tab exercise raised no page errors', errs.length === 0);

await browser.close();
finish();
