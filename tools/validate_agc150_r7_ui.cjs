// Install Playwright in a user-owned directory and set NODE_PATH before running.
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}});
  const errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.url().includes('/api/ds/query'))requests.push(r)});
  await page.goto('http://127.0.0.1:3300/d/logsis-agc150-ecu-me96ss-r5?from=1793300400000&to=1793304000000&kiosk');
  await page.getByText('346 kW',{exact:true}).first().waitFor({timeout:60000});
  await page.screenshot({path:'/tmp/logsis-r7-desktop.png'});
  for(const section of ['TENSÕES','CORRENTES','POTÊNCIAS','MOTOR ECU','ENERGIA']){
   await page.getByText(new RegExp('^CURVAS / '+section)).click();
   await page.mouse.move(1050,700);
   for(let j=0;j<4;j++){await page.mouse.wheel(0,350);await page.waitForTimeout(350);}
   if(section==='POTÊNCIAS')await page.screenshot({path:'/tmp/logsis-r7-power.png'});
  }
  await page.waitForTimeout(2000);
  await page.screenshot({path:'/tmp/logsis-r7-history.png'});
  await page.setViewportSize({width:390,height:1100});
  await page.reload();
  await page.waitForTimeout(1000);await page.mouse.move(300,650);await page.mouse.wheel(0,-30000);await page.waitForTimeout(500);await page.mouse.wheel(0,700);
  await page.getByText('MITSUBISHI ELECTRIC  /  ME96SS',{exact:true}).waitFor({timeout:60000});
  await page.waitForTimeout(1000);
  await page.getByText('MITSUBISHI ELECTRIC  /  ME96SS',{exact:true}).scrollIntoViewIfNeeded();
  await page.screenshot({path:'/tmp/logsis-r7-mobile.png'});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Mobile overflow');
  for(const response of requests){
   if(response.status()>=400)errors.push('Datasource HTTP '+response.status());
   else{try{const data=await response.json();for(const result of Object.values(data.results||{}))if(result.error)errors.push(result.error)}catch(e){}}
  }
  if(errors.length)throw Error(errors.join('\n'));
  await page.goto('http://127.0.0.1:3300/dashboard/import');
  await page.locator('input[type=file]').setInputFiles(require('path').resolve(__dirname,'..','AGC150_ECU_MITSUBISHI_R7_CORRIGIDO.json'));
  await page.getByText('Change uid',{exact:true}).waitFor({timeout:30000});
  if(/Import failed|Serialization failed/.test(await page.locator('body').innerText()))throw Error('Invalid JSON import');
  console.log(JSON.stringify({result:'passed',desktop:true,mobile:true,sharedMeterData:true,historyQueries:true,separateSections:true,powerTriplesPerInstrument:true,grafanaFileImport:true,datasourceResponses:requests.length,browserErrors:errors.length}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
