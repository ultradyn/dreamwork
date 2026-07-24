import { chromium } from '/home/xertrov/.llm-general/skills/headless-browser-screenshots/node_modules/playwright/index.mjs';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const b=await chromium.launch({args:['--use-gl=swiftshader','--enable-webgl']});
const p=await b.newPage({viewport:{width:1000,height:820}});
await p.goto('http://127.0.0.1:39890/',{waitUntil:'networkidle'}); await sleep(1400);
const samples=await p.evaluate(async () => {
  const out=[];
  navigate('questions', null, { push: true });
  const v=document.getElementById('view');
  const start=performance.now();
  return await new Promise(res=>{
    (function loop(){
      const t=performance.now()-start;
      const cs=getComputedStyle(v);
      out.push([Math.round(t), +(+cs.opacity).toFixed(3), cs.transform.includes('matrix3d')||cs.transform.includes('matrix')?'T':'-']);
      if(t<500) requestAnimationFrame(loop); else res(out);
    })();
  });
});
const ops=samples.map(s=>s[1]);
const minOp=Math.min(...ops);
console.log('first 12 frames:', JSON.stringify(samples.slice(0,12)));
console.log('minOpacity over 500ms:', minOp, ' finalOpacity:', ops[ops.length-1]);
console.log(minOp<=0.03 ? 'PASS incoming reaches true opacity ~0' : 'FAIL min opacity '+minOp);
await b.close();
