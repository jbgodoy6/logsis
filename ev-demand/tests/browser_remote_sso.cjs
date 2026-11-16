const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});try{
 const context=await browser.newContext(),page=await context.newPage(),requests=[],errors=[];
 page.on('request',r=>requests.push({url:r.url(),method:r.method(),body:r.postData()}));page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8115/remote/sso#ticket='+'a'.repeat(64));await page.waitForURL('**/ui/overview');
 assert.equal(await page.locator('input[name=password]').count(),0);assert.ok((await page.textContent('body')).includes('Desenvolvedor SSO'));
 const request=requests.find(r=>r.url.endsWith('/api/remote/sso'));assert.deepEqual(JSON.parse(request.body),{ticket:'a'.repeat(64)});
 assert.ok(requests.every(r=>!r.url.includes('ticket=')));assert.ok((await context.cookies()).some(c=>c.name==='ev_session'&&c.httpOnly));assert.equal(errors.length,0,errors.join('\n'));
 const other=await browser.newContext(),second=await other.newPage();await second.goto('http://127.0.0.1:8115/remote/sso#ticket='+'a'.repeat(64));await second.waitForFunction(()=>document.getElementById('sso-status').textContent.includes('não foi validada'));
 assert.ok(!(await other.cookies()).some(c=>c.name==='ev_session'));assert.ok(!second.url().includes('#'));await other.close();
 console.log('Remote SSO browser PASS: no second password form, fragment removed, only one-time pass posted, HttpOnly session, replay refused.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
