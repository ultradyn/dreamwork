/* #231 human-to-dreamer answers channel. Usage: node answers.mjs <out> <port> */
import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
import { readFileSync } from 'node:fs';
const OUT=process.argv[2], PORT=+(process.argv[3]||39890);
const checks=[]; const ok=(n,c)=>checks.push(`${c?'PASS':'FAIL'} ${n}`);
const br=await chromium.launch({args:['--use-gl=swiftshader']});
const page=await br.newPage({viewport:{width:1100,height:800}}); const errs=[];
page.on('pageerror',e=>errs.push(String(e))); page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('Failed to load resource')) errs.push(m.text())});
await page.goto(`http://127.0.0.1:${PORT}/answers`);
const exposed=await page.locator('#askbox').waitFor({state:'visible',timeout:5000}).then(()=>true).catch(()=>false);
ok('answers route exposes #askbox',exposed);
if(!exposed){console.log(checks.join('\n'));await br.close();process.exit(1)}
ok('route title',await page.locator('#chrome .htitle').textContent()==='answers');
ok('missing channel is calm',await page.locator('.aq.open').count()===0 &&
   (await page.locator('#answersections').textContent()).includes('none awaiting the dreamer'));
const asked='Does the live ask persist?\n## not a section\n- **not another entry**';
await page.locator('#askbox').fill(asked); await page.locator('#askbox').focus();
const tickResponse=await page.evaluate(()=>fetch('/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:'do-next',text:'',from:'/answers'})}).then(r=>r.status));
ok('tick trigger accepted',tickResponse===200);
await page.waitForTimeout(2500);
ok('draft survives live tick',await page.locator('#askbox').inputValue()===asked);
ok('focus survives live tick',await page.evaluate(()=>document.activeElement?.id)==='askbox');
await page.locator('#askform button').click(); await page.waitForFunction(()=>document.querySelector('#askbox')?.value==='');
await page.waitForTimeout(400);
const pageText=await page.locator('#answersections').textContent();
ok('first ask creates exactly one entry',await page.locator('.aq.open').count()===1);
ok('successful ask appears',pageText.includes('Does the live ask persist?'));
ok('multiline markdown meaning survives',pageText.includes('not a section')&&pageText.includes('not another entry'));
await page.route('**/ask',r=>r.fulfill({status:409,body:'refused'})); await page.locator('#askbox').fill('Keep these exact words'); await page.locator('#askform button').click(); await page.waitForFunction(()=>document.querySelector('#askmsg')?.textContent.includes('kept'));
ok('failed ask keeps words',await page.locator('#askbox').inputValue()==='Keep these exact words');
ok('failed ask explains outcome',(await page.locator('#askmsg').textContent()).includes('kept'));
ok('page-owned errors',errs.length===0); if(errs.length) console.error(errs.join('\n'));
const reduced=await br.newPage({reducedMotion:'reduce'}); await reduced.goto(`http://127.0.0.1:${PORT}/answers`); await reduced.waitForSelector('#answersections');
ok('reduced motion preserves function',await reduced.locator('#askbox').isVisible());
await br.close(); console.log(checks.join('\n')); if(checks.some(x=>x.startsWith('FAIL'))) process.exit(1);
