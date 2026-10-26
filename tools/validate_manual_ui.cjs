// Local synthetic lab only: seed with tools/seed_manual_lab.py.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..');
function assert(value,message){if(!value)throw Error(message)}
async function clipping(page){return page.locator('div[role=button][style*="position: absolute"]').evaluateAll(es=>es.flatMap(e=>{
 const spans=[...e.querySelectorAll('span')].filter(s=>!s.childElementCount&&s.textContent.trim());if(!spans.length)return[];
 const r=e.getBoundingClientRect();if(!r.width||!r.height)return[];
 const ranges=spans.map(s=>{const t=document.createRange();t.selectNodeContents(s);return t.getBoundingClientRect()});
 return Math.min(...ranges.map(x=>x.left))<r.left-1||Math.max(...ranges.map(x=>x.right))>r.right+1||Math.max(...ranges.map(x=>x.bottom))-Math.min(...ranges.map(x=>x.top))>r.height+1?[e.textContent]:[];
}));}
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try{
 const page=await b.newPage({viewport:{width:1440,height:1100}});const report={result:'pending',models:[]};
 for(const model of ['DSE4520','DSE6120','DSE6320','DSE7320','DSE8620','DSE8660','DSE8680']){
  const record={model,widths:[],clipping:[]};
  await page.goto(`http://127.0.0.1:3300/d/studio-manual-${model.toLowerCase()}?from=1792756800000&to=1792760400000&kiosk`);
  await page.getByText('23/10 09:30',{exact:true}).waitFor({timeout:30000});
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:1100});await page.locator('.scrollbar-view').first().evaluate(e=>e.scrollTo(0,0));await page.waitForTimeout(400);
   const body=await page.locator('body').innerText();
   if(['DSE8660','DSE8680'].includes(model))assert(!body.includes('GRUPO GERADOR')&&!body.includes('RPM motor'),'Engine content in non-engine model');
   else await page.getByText('Troca de óleo / VENCIDA',{exact:true}).waitFor();
   let cut=await clipping(page);assert(!cut.length,model+' '+width+' clipped '+cut.join('|'));
   assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)),'Page overflow');
   if(['DSE6120','DSE8660','DSE8680'].includes(model))await page.screenshot({path:`${root}/STUDIO_8_${model}_${width}.png`});
   await page.locator('.scrollbar-view').first().evaluate(e=>e.scrollTo(0,e.scrollHeight));await page.waitForTimeout(900);
   await page.getByText('Porta da sala',{exact:true}).waitFor();
   assert(!(await page.locator('body').innerText()).includes('${Nome_'),'Unresolved variable');
   cut=await clipping(page);assert(!cut.length,model+' '+width+' lower clipped '+cut.join('|'));
   record.widths.push(width);
  }
  report.models.push(record);
 }
 report.result='passed';fs.writeFileSync(root+'/LOGSIS_STUDIO_8_VALIDACAO_UI.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
