const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..');
const models=Object.keys(JSON.parse(fs.readFileSync(root+'/logsis_studio/resources/profiles.json','utf8'))).filter(m=>!process.env.MODELS||process.env.MODELS.split(',').includes(m));
async function clipping(page){return page.locator('div[role=button][style*="position: absolute"]').evaluateAll(es=>es.flatMap(e=>{
 const spans=[...e.querySelectorAll('span')].filter(s=>!s.childElementCount&&s.textContent.trim());if(!spans.length)return[];
 const r=e.getBoundingClientRect();if(!r.width||!r.height)return[];
 const ranges=spans.map(s=>{const t=document.createRange();t.selectNodeContents(s);return t.getBoundingClientRect()});
 return Math.min(...ranges.map(x=>x.left))<r.left-1||Math.max(...ranges.map(x=>x.right))>r.right+1||Math.max(...ranges.map(x=>x.bottom))-Math.min(...ranges.map(x=>x.top))>r.height+1?[e.textContent]:[];
}));}
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try{const page=await b.newPage({viewport:{width:1440,height:1100}}),report={result:'pending',grafana:'11.2.2',models:[],queryErrors:[]};
page.on('response',async r=>{if(r.url().includes('/api/ds/query'))try{const j=await r.json();for(const v of Object.values(j.results||{}))if(v.error)report.queryErrors.push(v.error)}catch(e){}});
for(const model of models){
 const record={model,widths:[],clipping:[]};
 await page.setViewportSize({width:1440,height:1100});
 await page.goto('http://127.0.0.1:3300/d/standard-'+model.toLowerCase().replaceAll('_','-')+'?from=1792756800000&to=1792760400000&kiosk');
 await page.getByText('23/10 09:30',{exact:true}).waitFor({timeout:45000});
 if(model==='DSE8660'){
  // The medium-voltage fixture intentionally has no phase-neutral reading.
  // Inspect the first Canvas rather than accepting values from detail cards.
  const texts=await page.locator('div[role=button][style*="position: absolute"]').allTextContents();
  for(const expected of ['13.59 kV','13.46 kV','13.44 kV','FECHADO','ABERTO'])if(!texts.includes(expected))throw Error('Missing local reading/contact '+expected);
  if(texts.some(t=>/LED ATIVO|LED INATIVO|IND\. ATIVA|IND\. INATIVA/.test(t)))throw Error('Old LED state labels');
  if(texts.some(t=>['L1–N','L2–N','L3–N'].includes(t)))throw Error('Phase-neutral in DSE8660 local cards');
  const outputs=await page.locator('div[role=button][style*="position: absolute"]').evaluateAll(es=>es.filter(e=>e.style.top==='583px'&&e.style.backgroundImage).map(e=>e.style.backgroundImage));
  if(outputs.length!==2||!outputs.every(s=>s.includes('f2495c')))throw Error('Both common output branches must be energized from the closed mains source');
 }
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:1100});await page.locator('.scrollbar-view').first().evaluate(e=>e.scrollTo(0,0));await page.waitForTimeout(650);
  let cut=await clipping(page);record.clipping.push(...cut.map(text=>({width,text})));if(cut.length)console.log('CLIP',model,width,JSON.stringify(cut));
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Page overflow '+model);
  if(['DSE7420','DSE8660','DSE8680','AGC150_GEN','SGC420_MKII','CGC413'].includes(model))await page.screenshot({path:root+'/STUDIO_9_1_'+model+'_'+width+'.png'});
  await page.locator('.scrollbar-view').first().evaluate(e=>e.scrollTo(0,e.scrollHeight));await page.waitForTimeout(650);
  cut=await clipping(page);record.clipping.push(...cut.map(text=>({width,text})));if(cut.length)console.log('LOWER CLIP',model,width,JSON.stringify(cut));
  record.widths.push(width);
 }
 report.models.push(record);console.log(model,'checked');
}
report.result=report.models.every(m=>!m.clipping.length)&&!report.queryErrors.length?'passed':'failed';
fs.writeFileSync(root+'/'+(process.env.UI_REPORT||'LOGSIS_STUDIO_9_1_VALIDACAO_UI.json'),JSON.stringify(report,null,2)+'\n');if(report.result!=='passed')throw Error('Review UI report');
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
