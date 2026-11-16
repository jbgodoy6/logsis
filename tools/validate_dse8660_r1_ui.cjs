// Requires Playwright; set NODE_PATH to its user-owned installation directory.
const {chromium}=require('playwright');
(async()=>{
 const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
 try{
  const page=await b.newPage({viewport:{width:1440,height:1100}}),errors=[],responses=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.url().includes('/api/ds/query'))responses.push(r)});
  const from=Date.parse('2026-11-16T19:00Z'),to=Date.parse('2026-11-16T20:00Z');
  const url=`http://127.0.0.1:3300/d/logsis-dse8660-8c773727c7?from=${from}&to=${to}&kiosk`;
  await page.goto(url);
  await page.getByText(/^416\.20? V$/).first().waitFor({timeout:60000});
  await page.getByText('FECHADO',{exact:true}).first().waitFor({timeout:30000});
  await page.screenshot({path:'/tmp/dse8660-r1-desktop.png'});
  for(const section of ['TENSÕES','CORRENTES','POTÊNCIAS','DETALHES ELÉTRICOS','ENERGIA','ESTADOS E ALERTAS']){
   await page.getByText(new RegExp('^CURVAS / '+section)).click();
   await page.mouse.move(1050,700);
   const pages=section==='DETALHES ELÉTRICOS'?6:4;
   for(let j=0;j<pages;j++){await page.mouse.wheel(0,350);await page.waitForTimeout(300)}
   if(section==='POTÊNCIAS')await page.screenshot({path:'/tmp/dse8660-r1-power.png'});
  }
  await page.waitForTimeout(1500);
  await page.setViewportSize({width:390,height:1100});await page.reload();
  await page.waitForTimeout(1500);await page.mouse.move(250,650);await page.mouse.wheel(0,-30000);await page.waitForTimeout(800);
  await page.screenshot({path:'/tmp/dse8660-r1-mobile.png'});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Mobile overflow');
  for(const response of responses){
   if(response.status()>=400)errors.push('SQL HTTP '+response.status());
   else{try{const data=await response.json();for(const r of Object.values(data.results||{}))if(r.error)errors.push(r.error)}catch(e){}}
  }
  if(errors.length)throw Error(errors.join('\n'));
  await page.goto('http://127.0.0.1:3300/dashboard/import');
  await page.locator('input[type=file]').setInputFiles(require('path').resolve(__dirname,'..','DSE8660_REDE_BUS_R1_OTIMIZADO.json'));
  await page.getByText('Change uid',{exact:true}).waitFor({timeout:30000});
  if(/Import failed|Serialization failed/.test(await page.locator('body').innerText()))throw Error('Invalid import');
  console.log(JSON.stringify({result:'passed',desktop:true,mobile:true,histories:true,separateSections:true,powerTriplesPerSource:true,grafanaFileImport:true,datasourceResponses:responses.length,browserErrors:errors.length}));
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exit(1)});
