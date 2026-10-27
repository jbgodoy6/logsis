// Local development dashboards only. Run validate_deif_integration.py first.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..');
const models=['AGC150_GEN','AGC150_GEN_BUS','AGC150_MAINS','AGC150_ATS','AGC150_ENG','SGC420_MKII','CGC412','CGC413'];
async function clipping(page){return page.locator('div[role=button][style*="position: absolute"]').evaluateAll(es=>es.flatMap(e=>{
 const spans=[...e.querySelectorAll('span')].filter(s=>!s.childElementCount&&s.textContent.trim());if(!spans.length)return[];
 const r=e.getBoundingClientRect();if(!r.width||!r.height)return[];
 const ranges=spans.map(s=>{const t=document.createRange();t.selectNodeContents(s);return t.getBoundingClientRect()});
 return Math.min(...ranges.map(x=>x.left))<r.left-1||Math.max(...ranges.map(x=>x.right))>r.right+1||Math.max(...ranges.map(x=>x.bottom))-Math.min(...ranges.map(x=>x.top))>r.height+1?[e.textContent]:[];
}));}
(async()=>{let b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try{let page=await b.newPage({viewport:{width:1440,height:1100}}),report={result:'pending',models:[]},errors=[];
page.on('response',async r=>{if(r.url().includes('/api/ds/query'))try{let j=await r.json();for(let v of Object.values(j.results||{}))if(v.error)errors.push(v.error)}catch(e){}});
for(let model of models){
 let record={model,widths:[],clipping:[]};
 await page.setViewportSize({width:1440,height:1100});
 await page.goto('http://127.0.0.1:3300/d/studio9-'+model.toLowerCase().replaceAll('_','-')+'?from=1792756800000&to=1792760400000&kiosk');
 await page.getByText('23/10 09:30',{exact:true}).waitFor({timeout:45000});
 if(!['AGC150_MAINS','AGC150_ATS'].includes(model))await page.getByText(model==='SGC420_MKII'?'1.50 h':'1.00 h',{exact:true}).waitFor({timeout:45000});
 for(let width of [1440,390]){
  await page.setViewportSize({width,height:1100});await page.locator('.scrollbar-view').first().evaluate(e=>e.scrollTo(0,0));await page.waitForTimeout(650);
  let cut=await clipping(page);record.clipping.push(...cut.map(text=>({width,text})));if(cut.length)console.log('CLIPPING',model,width,JSON.stringify(cut));
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Page overflow '+model+' '+width);
  if(['AGC150_GEN','SGC420_MKII','CGC413'].includes(model))await page.screenshot({path:root+'/STUDIO_9_'+model+'_'+width+'.png'});
  // Visit below-the-fold source cards and input/maintenance variable labels.
  await page.locator('.scrollbar-view').first().evaluate(e=>e.scrollTo(0,e.scrollHeight));await page.waitForTimeout(650);
  cut=await clipping(page);record.clipping.push(...cut.map(text=>({width,text})));if(cut.length)console.log('LOWER CLIPPING',model,width,JSON.stringify(cut));
  record.widths.push(width);
 }
 report.models.push(record);console.log(model,'checked');
}
await page.waitForTimeout(200);report.queryErrors=errors;
report.result=report.models.every(m=>!m.clipping.length)&&!errors.length?'passed':'failed';
fs.writeFileSync(root+'/LOGSIS_STUDIO_9_VALIDACAO_UI.json',JSON.stringify(report,null,2)+'\n');
if(report.result!=='passed')throw Error('Review clipping/query errors in report');
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
