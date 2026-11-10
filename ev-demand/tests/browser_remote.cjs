'use strict';
const assert=require('node:assert/strict'),crypto=require('node:crypto');
const {chromium}=require('playwright');
(async()=>{
 // Pin only the ephemeral loopback fixture certificate; no public tunnel is used.
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--ignore-certificate-errors-spki-list='+process.env.DMAX_TEST_REMOTE_PIN]});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),base='https://127.0.0.1:8447',errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const remote=async(path,method='GET',data)=>page.evaluate(async({path,method,data})=>{const r=await fetch(path,{method,headers:data===undefined?{}:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});return {status:r.status,ok:r.ok};},{path,method,data});
  let r=await page.request.post('http://127.0.0.1:8123/api/setup',{data:{admin_password:crypto.randomBytes(20).toString('hex')}});assert(r.ok());
  await page.goto(base+'/');await page.locator('[name=username]').fill('root');await page.locator('[name=password]').fill(process.env.DMAX_TEST_REMOTE_ROOT);
  await page.getByRole('button',{name:'Entrar no controlador'}).click();await page.waitForURL(base+'/ui/overview');
  const cookie=(await page.context().cookies()).find(c=>c.name==='ev_session');assert(cookie.secure&&cookie.httpOnly&&cookie.sameSite==='Strict');
  r=await remote('/api/demo','POST',{});assert(r.ok);await page.reload();
  await page.waitForFunction(()=>document.querySelector('[data-live-status]').textContent.startsWith('Atualizado'));
  const response=await page.waitForResponse(r=>r.url().includes('/ui-data/overview'));assert.equal(response.headers()['content-encoding'],'gzip');
  const meter=await page.locator('[data-live-key=site-meter]').elementHandle();
  const field=page.locator('[name=other_kw]');await field.fill('650');await page.waitForTimeout(2500);assert.equal(await field.inputValue(),'650');
  assert(await meter.evaluate(n=>n===document.querySelector('[data-live-key=site-meter]')));
  await field.locator('xpath=ancestor::form').getByRole('button',{name:'Aplicar carga'}).click();assert((await page.locator('body').textContent()).includes('Alteração aplicada.'));
  r=await remote('/ocpp/REAL');assert.equal(r.status,404);
  r=await remote('/api/setup','POST',{admin_password:'blocked-fixture-password'});assert.equal(r.status,404);
  await page.goto(base+'/ui/remote');await page.waitForTimeout(1200);assert((await page.locator('main').textContent()).includes('Grafana'));
  assert.equal(await page.locator('[data-dmax-version]').textContent(),'v0.13.0');
  await page.screenshot({path:'/tmp/dmax-remote-v0110.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.goto(base+'/ui/overview');
  await page.waitForFunction(()=>document.querySelector('[data-live-status]').textContent.startsWith('Atualizado'));
  assert(await page.locator('body').evaluate(n=>n.scrollWidth<=window.innerWidth+1));assert.deepEqual(errors,[]);
  console.log('PASS: local HTTPS relay, secure session, signed forms, live gzip, stable DOM, OCPP/setup blocked, remote status and mobile layout. Public provider not exercised.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
