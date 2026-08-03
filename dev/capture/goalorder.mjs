/* goalorder — #1006: rendered geometry, not stylesheet text, owns the claim
   that the goal tree is the page subject above its controls and editor.

   The static pytest deliberately catches only order/grid-row/reverse-flex in
   four first exact selector blocks. This guard asks Chromium for every rendered
   row-action rectangle, so it is indifferent to the CSS mechanism while staying
   explicitly bounded to the action boxes it measures.

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
  drives: 'the shared fixture server GET /goals; first-row Edit; change the ' +
          'goal selector and details; click Cancel edit; no POST',
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

  const treeExists = await present(
    page, '.goaltree-section', 'the rendered goal-tree section');
  const editorExists = await present(
    page, '.goalwrites', 'the rendered goal editor');
  const subjectsExist = treeExists && editorExists;
  if (subjectsExist) {
    const measured = await page.evaluate(() => {
      const rect = box => {
        box = box.getBoundingClientRect();
        return { top: Math.round(box.top), bottom: Math.round(box.bottom) };
      };
      const section = document.querySelector('.goaltree-section');
      const rows = [...section.querySelectorAll('.goaltree-row')];
      const treeActions = [...section.querySelectorAll('.goaltree-actions')];
      const actionsByRow = rows.map(row => treeActions.filter(action =>
        action.closest('.goaltree-row') === row));
      const actions = actionsByRow.flat();
      const attributed = new Set(actions);
      const unattributed = treeActions.filter(action => !attributed.has(action));
      const unattributedIndices = treeActions.flatMap((action, index) =>
        attributed.has(action) ? [] : [index]);
      const editor = document.querySelector('.goalwrites');
      return {
        dom: {
          actionDom: actions.every(action => section.contains(action)),
          editorDom: !!(section.compareDocumentPosition(editor) &
            Node.DOCUMENT_POSITION_FOLLOWING),
        },
        rowCount: rows.length,
        actionCountsByRow: actionsByRow.map(rowActions => rowActions.length),
        treeActionCount: treeActions.length,
        unattributed: unattributed.map(rect),
        unattributedIndices,
        tree: rect(section),
        actions: actions.map(rect),
        editor: rect(editor),
      };
    });
    const missingRow = measured.actionCountsByRow.findIndex(count => count === 0);
    const coverage = measured.rowCount > 0 && missingRow === -1;
    const attribution = measured.unattributed.length === 0 &&
      measured.actions.length === measured.treeActionCount;
    const outside = measured.actions.findIndex(action =>
      !(measured.tree.top < action.top && action.bottom <= measured.tree.bottom));
    const rendered = coverage && attribution && outside === -1 &&
      measured.tree.bottom < measured.editor.top;
    notes.push(`DOM actionDom=${measured.dom.actionDom} ` +
      `editorDom=${measured.dom.editorDom}`);
    notes.push(`coverage rows=${measured.rowCount} ` +
      `actionBoxesPerRow=[${measured.actionCountsByRow.join(',')}] ` +
      `attributed=${measured.actions.length}/${measured.treeActionCount}`);
    notes.push(`rectangles tree=${measured.tree.top}-${measured.tree.bottom} ` +
      `actions=${measured.actions.map(action =>
        action.top + '-' + action.bottom).join(',')} ` +
      `editor=${measured.editor.top}-${measured.editor.bottom}`);
    const coverageMessage = measured.rowCount === 0
      ? 'measured no rendered goal rows, so per-row action coverage is absent'
      : missingRow === -1
      ? `every rendered goal row has an action box; distribution ` +
        `[${measured.actionCountsByRow.join(',')}]`
      : `rendered goal row #${missingRow + 1} has no action box; distribution ` +
        `[${measured.actionCountsByRow.join(',')}]`;
    ok(coverageMessage, coverage);
    const attributionMessage = attribution
      ? `all ${measured.treeActionCount} tree action boxes are attributed to a row`
      : `tree action box #${measured.unattributedIndices[0] + 1} is attributed to no ` +
        `rendered goal row`;
    ok(attributionMessage, attribution);
    ok('DOM keeps row actions inside the tree and the editor after it',
      measured.dom.actionDom && measured.dom.editorDom);
    const containmentMessage = outside === -1
      ? `rendered containment keeps all ${measured.actions.length} action boxes ` +
        `inside tree [${measured.tree.top},${measured.tree.bottom}] and tree above ` +
        `editor [${measured.editor.top},${measured.editor.bottom}]`
      : `rendered action box #${outside + 1} ` +
        `[${measured.actions[outside].top},${measured.actions[outside].bottom}] ` +
        `left tree [${measured.tree.top},${measured.tree.bottom}]`;
    ok(containmentMessage, rendered);

    await page.getByRole('link', { name: 'Edit details for Healthy goal' }).click();
    await page.locator('#goal-details-text').waitFor();
    const originalDetails = await page.locator('#goal-details-text').inputValue();
    const originalGoal = await page.locator('#goal-details-goal').inputValue();
    await page.locator('#goal-details-goal').selectOption('2');
    await page.locator('#goal-details-text').fill('unsaved replacement from goalorder');
    const changedDetails = await page.locator('#goal-details-text').inputValue();
    const changedGoal = await page.locator('#goal-details-goal').inputValue();
    notes.push(`Edit perturbation read from DOM details=${JSON.stringify(changedDetails)} ` +
      `goal=${JSON.stringify(changedGoal)}`);
    ok('Edit perturbation changes both details and selected goal before Cancel',
      changedDetails !== originalDetails && changedGoal !== originalGoal);
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

    await page.getByRole('button', { name: 'Add goal' }).click();
    const parentDescribedBy = await page.locator('#goal-new-parent')
      .getAttribute('aria-describedby');
    const parentHintExists = parentDescribedBy
      ? await page.locator(`#${parentDescribedBy}`).count() === 1 : false;
    notes.push(`parent aria-describedby=${JSON.stringify(parentDescribedBy)} ` +
      `targetExists=${parentHintExists}`);
    ok('the Parent select aria-describedby resolves to its visible hint',
      parentDescribedBy === 'goal-new-parent-hint' && parentHintExists);
  }

  await browser.close();
  finish();
}
