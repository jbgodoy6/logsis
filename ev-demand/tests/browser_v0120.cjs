/** Real Chromium, ephemeral local fixture. No customer data or external requests. */
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const p=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true}),base='http://127.0.0.1:8111',errors=[];
  p.on('pageerror',e=>errors.push(e.message));
  const api=async(method,path,data)=>{const r=await p.request[method](base+path,data===undefined?{}:{data});assert(r.ok(),path+': '+r.status());return r.json()};
  const fixture=async(action,data)=>{const r=await p.request.post(base+'/fixture/'+action,{headers:{'X-Fixture-Key':process.env.DMAX_TEST_ROOT},data});assert(r.ok());return r.json()};
  await api('post','/api/setup',{admin_password:crypto.randomBytes(20).toString('hex')});
  await api('post','/api/login',{username:'root',password:process.env.DMAX_TEST_ROOT});await api('post','/api/demo',{});
  await p.goto(base+'/ui/overview');
  assert.equal(await p.locator('[data-live-key=site-meter]').count(),1);assert.equal(await p.locator('nav a[href="/ui/monitor"]').count(),0);
  const load=p.locator('input[name=other_kw]');await load.fill('730');await p.waitForTimeout(2500);assert.equal(await load.inputValue(),'730');
  await load.locator('xpath=ancestor::form').getByRole('button',{name:'Aplicar carga'}).click();
  await p.waitForFunction(()=>document.querySelector('.flash-notice'));await p.waitForTimeout(5200);assert.equal(await p.locator('.flash-notice').isVisible(),false);
  await p.reload();assert.equal(await p.locator('.flash-notice').count(),0);await p.screenshot({path:'/tmp/dmax-v0120-overview.png',fullPage:true});
  await fixture('curve',{});await p.reload();
  await p.waitForFunction(()=>document.querySelectorAll('[data-curve-value]').length>20);
  const meterBox=await p.locator('[data-live-key=site-meter]').boundingBox(),chartBox=await p.locator('[data-live-key=chart]').boundingBox(),chargersBox=await p.locator('.plant-section-title').first().boundingBox();
  assert(meterBox.y+meterBox.height<=chartBox.y+2);assert(chartBox.y+chartBox.height<=chargersBox.y+2);
  const filter=p.locator('[name=curve_start]');await filter.fill(new Date(Date.now()-600000).toISOString().slice(0,16));await p.waitForTimeout(2500);assert((await filter.inputValue()).length>0);
  const point=p.locator('[data-curve-value]').nth(15);await point.hover();assert((await p.locator('.curve-tooltip').textContent()).includes('Total:'));await point.focus();assert(await p.locator('.curve-tooltip').isVisible());await point.dispatchEvent('pointerdown',{clientX:200,clientY:400,pointerType:'touch'});assert(await p.locator('.curve-tooltip').isVisible());
  await p.locator('[name=curve_mode]').selectOption('simulation');await filter.fill('');await p.getByRole('button',{name:'Aplicar período'}).click();assert(p.url().includes('curve_mode=simulation'));
  for(const name of ['Relatório PDF da curva','CSV com todos os registros']){
   const [download]=await Promise.all([p.waitForEvent('download'),p.getByRole('link',{name,exact:true}).click()]);const bytes=fs.readFileSync(await download.path());
   if(name.startsWith('Relatório'))assert(bytes.subarray(0,8).toString().startsWith('%PDF-1.4'));else assert(bytes.toString().includes('total_kw'));
  }
  let state=await api('get','/api/state');state.settings.mode='physical';state.settings.site_name='Instalação de demonstração EnergyCube';state.settings.meter.transport='rtu';state.settings.meter.serial_port='/dev/ttyUSB0';
  for(const r of state.settings.meter.registers)r.enabled=true;
  await api('put','/api/settings',state.settings);
  for(const page of ['overview','monitor']){
   await p.goto(base+'/ui/'+page);await p.waitForFunction(()=>document.querySelector('[data-live-status]').textContent.startsWith('Atualizado'));
   await p.waitForFunction(()=>document.querySelector('.plant-readings').textContent.includes('230,00'));
   assert((await p.locator('.plant-meter-art').boundingBox()).width>=130);
   assert(Number.parseFloat(await p.locator('.plant-readings b').first().evaluate(n=>getComputedStyle(n).fontSize))<=18);
   assert.equal(await p.locator('[data-dmax-version]').textContent(),'v0.12.0');
  }
  const meter=await p.locator('[data-live-key=site-meter]').elementHandle();let navigations=0;p.on('framenavigated',f=>{if(f===p.mainFrame())navigations++});
  await fixture('notice',{state:'pending',revision:1});await p.waitForFunction(()=>document.querySelector('#subscription-banner').textContent.includes('10 dia(s)'));
  assert(await meter.evaluate(n=>n===document.querySelector('[data-live-key=site-meter]')));assert.equal(navigations,0);
  await p.screenshot({path:'/tmp/dmax-v0120-meter-preview.png',fullPage:true});
  await fixture('notice',{state:'expired',revision:2});await p.waitForFunction(()=>document.querySelector('#subscription-banner').textContent.includes('Controle de demanda desativado'));
  await fixture('notice',{state:'regular',revision:3});await p.waitForFunction(()=>document.querySelector('#subscription-banner').textContent.trim()==='');assert.equal(navigations,0);
  await p.setViewportSize({width:390,height:844});await p.waitForTimeout(200);
  assert(await p.locator('body').evaluate(n=>n.scrollWidth<=window.innerWidth+1));assert((await p.locator('.plant-meter-art').boundingBox()).width>=90);
  await p.setViewportSize({width:1440,height:1000});await fixture('sessions',{});await p.goto(base+'/ui/history');
  const form=p.locator('form[action="/api/reports/sessions.pdf"]');await form.locator('[name=vehicle_id]').selectOption('PDF-TEST');
  const [download]=await Promise.all([p.waitForEvent('download'),form.getByRole('button',{name:'Baixar relatório PDF'}).click()]);
  const bytes=fs.readFileSync(await download.path());assert(bytes.subarray(0,8).toString().startsWith('%PDF-1.4'));assert(bytes.includes(Buffer.from('/Count 3 ')));
  await p.goto(base+'/ui/vehicles');const deletion=p.locator('form').filter({has:p.locator('[name=_action][value=delete_vehicle][type=hidden]')}).filter({has:p.locator('[name=id][value=PDF-TEST]')});
  await deletion.locator('xpath=..').locator('summary').click();await deletion.locator('[name=confirm]').check();await Promise.all([p.waitForNavigation(),deletion.getByRole('button',{name:'Excluir veículo'}).click()]);
  state=await api('get','/api/state');assert(!state.vehicles.some(v=>v.id==='PDF-TEST'));
  await p.goto(base+'/ui/history');assert((await p.locator('select[name=vehicle_id]').innerText()).includes('Veículo teste PDF · excluído'));
  assert.deepEqual(errors,[]);console.log('PASS: desktop/mobile readable meter, stable live DOM, pending/expired/renewed banners without navigation, PDF browser download, historical fleet deletion and version.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
