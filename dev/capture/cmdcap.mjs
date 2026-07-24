import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
const BASE = process.argv[2] || 'http://127.0.0.1:39890';
const OUT = process.argv[3] || '/tmp/shots-cmd';
const sleep = ms => new Promise(r => setTimeout(r, ms));
import { mkdirSync } from 'node:fs';
mkdirSync(OUT, { recursive: true });
const log = [];
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl'] });

// ---------- 1. open palette, check reveal + position ----------
const page = await browser.newPage({ viewport: { width: 1100, height: 820 } });
await page.goto(BASE + '/', { waitUntil: 'networkidle' });
await sleep(900);
await page.click('#cmdplus');
await sleep(650);                                    // dream reveal
await page.screenshot({ path: `${OUT}/01-palette-open.png` });
const openState = await page.evaluate(() => {
  const pal = document.getElementById('cmdpalette');
  const plus = document.getElementById('cmdplus');
  const pr = pal.getBoundingClientRect(), br = plus.getBoundingClientRect();
  const cs = getComputedStyle(pal);
  return { open: pal.classList.contains('open'), plusOn: plus.classList.contains('on'),
    opacity: +cs.opacity, visibility: cs.visibility,
    nearPlus: Math.abs(pr.left - br.left) < 30 && pr.top > br.bottom - 2,
    focused: document.activeElement && document.activeElement.id };
});
log.push('open: ' + JSON.stringify(openState));

// ---------- 2. layer-hotkey guard: typing 'l' in the box must NOT cycle ----------
await page.focus('#cmdtext');
await page.keyboard.type('idea: l is a letter here');
const afterTypeL = await page.evaluate(() => ({
  layerhint: !!document.getElementById('layerhint'),
  text: document.getElementById('cmdtext').value }));
log.push('after typing (incl l) in box: ' + JSON.stringify(afterTypeL));

// ---------- 3. submit -> ripple + ok message ----------
await page.selectOption('#cmdkind', 'add-idea');
const reqs = [];
page.on('request', r => { if (r.url().endsWith('/command')) reqs.push(r.method()); });
await page.click('#cmdsend');
await sleep(250);
const rippled = await page.evaluate(() => !!document.querySelector('.ripple'));
const msg = await page.evaluate(() => document.getElementById('cmdmsg').textContent);
await page.screenshot({ path: `${OUT}/02-submitted.png` });
log.push('submit: msg=' + JSON.stringify(msg) + ' rippleSeen=' + rippled +
  ' postToCommand=' + JSON.stringify(reqs));
await sleep(1100);
const afterClose = await page.evaluate(() =>
  document.getElementById('cmdpalette').classList.contains('open'));
log.push('palette auto-closed after submit: ' + (afterClose === false));

// ---------- 4. pop-out (PiP or window.open fallback) ----------
await page.click('#cmdplus');
await sleep(400);
const pipSupported = await page.evaluate(() => 'documentPictureInPicture' in window);
log.push('documentPictureInPicture supported here: ' + pipSupported);
let popupInfo = '(none)';
const popupP = page.waitForEvent('popup', { timeout: 2500 }).catch(() => null);
await page.click('#cmdpop');
const popup = await popupP;
if (popup) {
  await popup.waitForLoadState('domcontentloaded').catch(() => {});
  await sleep(300);
  popupInfo = await popup.evaluate(() => ({
    title: document.title,
    ident: document.querySelector('.ptitle')?.textContent,
    path: document.querySelector('.ppath')?.textContent,
    hasForm: !!document.getElementById('pform'),
    kinds: [...document.querySelectorAll('#pkind option')].map(o => o.value) }));
  // submit from the popup
  await popup.fill('#ptext', 'from the popout window');
  const popReqP = page.waitForRequest(r => r.url().endsWith('/command'), { timeout: 2500 }).catch(() => null);
  await popup.click('#pform button[type=submit]');
  const popReq = await popReqP;
  await sleep(200);
  const pmsg = await popup.evaluate(() => document.getElementById('pmsg').textContent);
  await popup.screenshot({ path: `${OUT}/03-popout.png` });
  log.push('popout: ' + JSON.stringify(popupInfo));
  log.push('popout submit: msg=' + JSON.stringify(pmsg) + ' posted=' + !!popReq);
} else {
  log.push('popout: no popup captured (PiP path or blocked in headless)');
}

// ---------- 5. reduced-motion: instant open, still functional ----------
const rmctx = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 1000, height: 800 } });
const p3 = await rmctx.newPage();
await p3.goto(BASE + '/', { waitUntil: 'networkidle' });
await sleep(400);
await p3.click('#cmdplus');
await sleep(60);
const rmOpen = await p3.evaluate(() => {
  const pal = document.getElementById('cmdpalette');
  return { open: pal.classList.contains('open'), opacity: +getComputedStyle(pal).opacity }; });
log.push('reduced-motion palette (instant): ' + JSON.stringify(rmOpen));

const checks = [];
const ok = (n, c) => checks.push(`${c ? 'PASS' : 'FAIL'} ${n}`);
ok('palette reveals (open, visible, near +)', openState.open && openState.opacity > 0.9 && openState.nearPlus);
ok('+ rotates to on-state', openState.plusOn);
ok('textarea focused on open', openState.focused === 'cmdtext');
ok('layer hotkey NOT triggered while typing in box', afterTypeL.layerhint === false);
ok('submit posted to /command', reqs.includes('POST'));
ok('submit shows dream confirmation', /sent to the dream/.test(msg));
ok('dream ripple on submit', rippled === true);
ok('palette auto-closes after submit', afterClose === false);
ok('reduced-motion opens instantly at full opacity', rmOpen.open && rmOpen.opacity > 0.9);
if (popup) {
  ok('popout identifies project (name + path)', /dreamwork|vtarget/.test(popupInfo.ident || '') && !!popupInfo.path);
  ok('popout has command form', popupInfo.hasForm === true);
}

console.log(log.join('\n'));
console.log('----');
console.log(checks.join('\n'));
await browser.close();
