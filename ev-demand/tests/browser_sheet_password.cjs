const {chromium}=require('playwright'),assert=require('node:assert/strict'),crypto=require('node:crypto'),vm=require('node:vm'),fs=require('node:fs'),http=require('node:http');
(async()=>{
 const ctx=vm.createContext({});vm.runInContext(fs.readFileSync('google-apps-script/Code.gs','utf8'),ctx);
 const target={row:4,id:'USR-4',name:'user4',fingerprint:'fixture'};
 const html=ctx.passwordEditorHtml_(target);
 const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html);});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const context=await browser.newContext(),page=await context.newPage();
  await page.addInitScript(()=>{globalThis.google={script:{run:{withSuccessHandler(fn){this.success=fn;return this;},withFailureHandler(fn){this.failure=fn;return this;},salvarSenhaDaPlanilha(target,verifier){globalThis.sent={target,verifier};this.success({ok:true,message:'Senha salva na coluna G.'});}}}};});
  await page.goto('http://127.0.0.1:'+server.address().port);await page.waitForLoadState('networkidle');await context.setOffline(true);
  await page.locator('#password').fill('Fictícia123');await page.locator('#confirmation').fill('Diferente123');await page.locator('#save').click();
  assert.ok((await page.locator('#status').textContent()).includes('iguais'));assert.equal(await page.evaluate(()=>globalThis.sent),undefined);
  await page.locator('#confirmation').fill('Fictícia123');await page.locator('#save').click();await page.waitForFunction(()=>document.getElementById('status').textContent.includes('Senha salva'));
  const sent=await page.evaluate(()=>globalThis.sent);assert.deepEqual(sent.target,target);assert.match(sent.verifier,/^pbkdf2_sha256\$600000\$[0-9a-f]{32}\$[0-9a-f]{64}$/);
  const parts=sent.verifier.split('$');assert.equal(parts[3],crypto.pbkdf2Sync('Fictícia123',Buffer.from(parts[2],'hex'),600000,32,'sha256').toString('hex'));
  assert.equal(await page.locator('#password').inputValue(),'');assert.equal(await page.locator('#confirmation').inputValue(),'');assert.equal(JSON.stringify(sent).includes('Fictícia123'),false);
  console.log('Sheet dialog browser PASS: password confirmation, Unicode PBKDF2 independently verified, only verifier sent, fields cleared.');
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1;});
