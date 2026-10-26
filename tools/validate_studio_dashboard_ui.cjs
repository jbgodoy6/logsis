// Dedicated synthetic Docker lab only. Seed with tools/seed_studio_dashboard_lab.py.
const {chromium}=require('playwright'),cp=require('child_process'),fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..');
const sql=s=>cp.execFileSync('docker',['exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-q','-v','ON_ERROR_STOP=1'],{input:s,encoding:'utf8'});
function assert(value,message){if(!value)throw Error(message)}
(async()=>{
 const b=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE||'/usr/bin/chromium',args:['--no-sandbox']});
 try{
 const page=await b.newPage({viewport:{width:1440,height:1100}});
 const report={result:'pending',models:[]};
 for(const [model,maintenance,prefix] of [['dse7420',54,'DSE7420_V43'],['dse8610',53,'DSE8610_V5']]){
  const record={model,viewports:[],maintenanceCases:[],controllerAlarms:[]};
  const url=`http://127.0.0.1:3300/d/studio-72-${model}?from=1792756800000&to=1792760400000&kiosk`;
  let neutral;
  async function picture(){return page.locator('div[style*="data:image/svg"]').evaluateAll(es=>{const e=es.find(e=>['147px','146px'].includes(e.style.top)&&['90px','80px'].includes(e.style.height));return e?getComputedStyle(e).backgroundImage:null})}
  for(const [state,value,text] of [['VENCIDA',0,'Revisão geral / VENCIDA'],['PROXIMA',720000,'Troca de filtros / PRÓXIMA']]){
   sql(`UPDATE studio_72_${model} SET mdb41=0,mdb42=0,mdb43=0,mdb${maintenance+2}=${value}`);
   await page.goto(url);await page.getByText(text,{exact:true}).waitFor({timeout:30000});
   const uri=await picture();assert(uri,'Generator SVG was not rendered');if(neutral)assert(uri===neutral,'Maintenance changed generator color');else neutral=uri;
   await page.screenshot({path:`${root}/${prefix}_${state}.png`});record.maintenanceCases.push(state);
  }
  for(const [field,label] of [[41,'WARNING'],[42,'TRIP'],[43,'SHUTDOWN']]){
   sql(`UPDATE studio_72_${model} SET ${[41,42,43].map(n=>`mdb${n}=${n===field?1:0}`).join(',')}`);
   await page.goto(url);await page.getByText('GERADOR / '+label,{exact:true}).waitFor({timeout:30000});
   assert((await picture())!==neutral,'Controller alarm did not tint generator');
   await page.getByText('Troca de filtros / PRÓXIMA',{exact:true}).waitFor();record.controllerAlarms.push(label);
  }
  sql(`UPDATE studio_72_${model} SET mdb41=0,mdb42=0,mdb43=0`);
  await page.goto(url);await page.getByText('Troca de filtros / PRÓXIMA',{exact:true}).waitFor({timeout:30000});
  for(const width of [390,1440]){
   await page.setViewportSize({width,height:1100});await page.locator('.scrollbar-view').first().evaluate(e=>e.scrollTo(0,0));await page.waitForTimeout(400);
   await page.getByText('Troca de filtros / PRÓXIMA',{exact:true}).waitFor();
   if(width===390)await page.screenshot({path:`${root}/${prefix}_CELULAR.png`});
   assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)),'Horizontal overflow');
   await page.locator('.scrollbar-view').first().evaluate(e=>e.scrollTo(0,e.scrollHeight));await page.waitForTimeout(1200);
   await page.getByText('Porta de acesso',{exact:true}).waitFor({timeout:30000});
   await page.getByText('Nível do tanque',{exact:true}).waitFor();
   await page.getByText('ATIVA',{exact:true}).waitFor();
   await page.getByText('INATIVA',{exact:true}).waitFor();
   if(width===390)await page.screenshot({path:`${root}/${prefix}_INPUTS_CELULAR.png`});
   else await page.screenshot({path:`${root}/${prefix}_INPUTS.png`});
   assert(!(await page.locator('body').innerText()).includes('${Nome_Entrada_'),'Unresolved input name variable');record.viewports.push(width);
  }
  record.flexibleInputs=['Q active','R inactive','S unavailable'];record.customNames=true;report.models.push(record);
 }
 report.result='passed';fs.writeFileSync(root+'/LOGSIS_MANUTENCAO_UI_VALIDACAO.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exit(1)});
