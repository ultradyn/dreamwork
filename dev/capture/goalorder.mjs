/* goalorder — #1006: rendered geometry, not stylesheet text, owns the claim
   that the goal tree is the page subject above its controls and editor.

   The static pytest deliberately catches only order/grid-row/reverse-flex in
   four first exact selector blocks. This guard asks Chromium for rectangles,
   so position, transforms, compound selectors, inline styles, and future CSS
   mechanisms cannot visually reorder the boxes without changing the result.

   It also drives Cancel edit through the shipping React page: replace the
   selected goal's details, click Cancel, then assert the saved value and
   selected goal are restored while both tree rows survive.

   usage: node dev/capture/goalorder.mjs <outdir> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { execFileSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { outdir } from './outdir.mjs';
import { makeReporter } from './report.mjs';
import { waitFor } from './dom.mjs';

const OUT = outdir(process.argv);
const PORT = process.argv[3] || '39895';
const BASE = `http://127.0.0.1:${PORT}`;
mkdirSync(OUT, { recursive: true });

const { ok, present, declare, finish, notes, errs } = makeReporter();
declare({
  drives: 'the shared fixture server GET /goals; first-row Edit; replace ' +
          'details; click Cancel edit; no POST',
  traceWindow: 'static getBoundingClientRect reads after goal rows mount, ' +
               'then immediate React state reads after the Cancel click',
});

const target = await (await fetch(`${BASE}/data.json`)).json()
  .then(data => data.target).catch(() => null);
if (!target) {
  ok('the server answered /data.json (nothing below can run)', false);
  finish();
} else {
  execFileSync('python3', ['dev/capture/goalfault_fixture.py', target, 'current'],
    { stdio: ['ignore', 'pipe', 'pipe'] });

  const browser = await chromium.launch({
    args: ['--use-gl=swiftshader', '--enable-webgl'],
  });
  const page = await browser.newPage({ viewport: { width: 1100, height: 1400 } });
  page.on('pageerror', error => errs.push(String(error)));
  await page.goto(`${BASE}/goals`, { waitUntil: 'networkidle' });
  await waitFor(page, '.goaltree-row');

  const subjectsExist = await present(
    page, '.goaltree-section', 'the rendered goal-tree section');
  if (subjectsExist) {
    const measured = await page.evaluate(() => {
      const rect = selector => {
        const box = document.querySelector(selector).getBoundingClientRect();
        return { top: Math.round(box.top), bottom: Math.round(box.bottom) };
      };
      const section = document.querySelector('.goaltree-section');
      const actions = document.querySelector('.goaltree-actions');
      const editor = document.querySelector('.goalwrites');
      return {
        dom: {
          actionDom: section.contains(actions),
          editorDom: !!(section.compareDocumentPosition(editor) &
            Node.DOCUMENT_POSITION_FOLLOWING),
        },
        tree: rect('.goaltree-section'),
        actions: rect('.goaltree-actions'),
        editor: rect('.goalwrites'),
      };
    });
    const rendered = measured.tree.top < measured.actions.top &&
      measured.actions.bottom <= measured.tree.bottom &&
      measured.tree.bottom < measured.editor.top;
    notes.push(`DOM actionDom=${measured.dom.actionDom} ` +
      `editorDom=${measured.dom.editorDom}`);
    notes.push(`rectangles tree=${measured.tree.top}-${measured.tree.bottom} ` +
      `actions=${measured.actions.top}-${measured.actions.bottom} ` +
      `editor=${measured.editor.top}-${measured.editor.bottom}`);
    ok('DOM keeps row actions inside the tree and the editor after it',
      measured.dom.actionDom && measured.dom.editorDom);
    ok(`rendered order keeps actions inside tree ` +
       `[${measured.tree.top},${measured.tree.bottom}] / ` +
       `[${measured.actions.top},${measured.actions.bottom}] and tree above ` +
       `editor [${measured.editor.top},${measured.editor.bottom}]`, rendered);

    await page.getByRole('link', { name: 'Edit details for Healthy goal' }).click();
    await page.locator('#goal-details-text').waitFor();
    const originalDetails = await page.locator('#goal-details-text').inputValue();
    const originalGoal = await page.locator('#goal-details-goal').inputValue();
    await page.locator('#goal-details-text').fill('unsaved replacement from goalorder');
    await page.getByRole('button', { name: 'Cancel edit' }).click();

    const restoredDetails = await page.locator('#goal-details-text').inputValue();
    const restoredGoal = await page.locator('#goal-details-goal').inputValue();
    const rows = await page.locator('.goaltree-title').allTextContents();
    notes.push(`Cancel restored details=${JSON.stringify(restoredDetails)} ` +
      `goal=${JSON.stringify(restoredGoal)} rows=${JSON.stringify(rows)}`);
    ok('Cancel edit restores the saved details value and selected goal',
      restoredDetails === originalDetails && restoredGoal === originalGoal);
    ok('Cancel edit preserves both goal-tree rows',
      rows.length === 2 && rows.includes('Healthy goal') && rows.includes('Broken goal'));
  }

  await browser.close();
  finish();
}
