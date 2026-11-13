const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async () => {
 const browser = await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try {
  const page = await browser.newPage({baseURL:'http://127.0.0.1:8098',viewport:{width:1280,height:650}});
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8098');
  await page.request.post('/api/setup',{data:{admin_password:'fixture-browser-admin'}});
  await page.request.post('/api/login',{data:{username:'root',password:'fixture-browser-root'}});
  await page.request.post('/api/demo');
  await page.goto('http://127.0.0.1:8098/ui/settings');
  for (const tab of ['users','remoteclients','remote','directory','simulation']) assert.equal(await page.locator(`nav a[href="/ui/${tab}"]`).count(),0);
  assert.ok(await page.getByText('Google Planilhas e Apps Script',{exact:true}).isVisible() || await page.getByText('Google Planilhas e Apps Script',{exact:true}).count());
  const saveButton=page.locator('form').filter({has:page.locator('input[name="_action"][value="settings"]')}).locator('button[type="submit"]');
  await saveButton.scrollIntoViewIfNeeded();
  const before=await page.evaluate(()=>scrollY);assert.ok(before>200);
  await saveButton.click();
  await page.waitForLoadState('load');
  await page.waitForTimeout(200);
  assert.ok(Math.abs(await page.evaluate(()=>scrollY)-before)<8,'form preserves scroll: '+before+' -> '+await page.evaluate(()=>scrollY));
  await page.reload();
  await page.waitForLoadState('load');await page.waitForTimeout(200);
  assert.ok(Math.abs(await page.evaluate(()=>scrollY)-before)<8,'refresh preserves scroll');
  await page.goto('http://127.0.0.1:8098/ui/overview');
  assert.ok(await page.getByText('SOC da bateria:',{exact:false}).count()>0);
  assert.equal(errors.length,0,errors.join('\n'));
  console.log('Browser passed: root navigation, embedded settings, form and refresh scroll, SOC, no JS errors.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
