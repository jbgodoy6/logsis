const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});try{
const ctx=await browser.newContext({viewport:{width:412,height:915}});
await ctx.addInitScript(()=>{
 let actor=null;window.calls=[];
 const users={primeiro:{id:'P',name:'primeiro',full_name:'Primeiro acesso',role:'developer',must_change:true},dev:{id:'D',name:'dev',full_name:'Desenvolvedor',role:'developer',must_change:false},comercial:{id:'C',name:'comercial',full_name:'Comercial',role:'commercial',must_change:false}};
 window.DMaxNative={request:(id,name,raw)=>{const args=JSON.parse(raw);window.calls.push({name,args});let r={ok:true};
 if(name==='bootstrap')r.user=actor;
 else if(name==='portalLogin'){actor={...users[args[0]]};r.user=actor;}
 else if(name==='portalLogout')actor=null;
 else if(name==='portalChangePassword'){actor.must_change=false;r.user=actor;}
 else if(name==='portalState')r.user=actor;
 else if(name==='portalClients')r.clients=[{controller_id:'CP1',site_name:'Cliente de teste',url:'https://fixture.trycloudflare.com',connected:true,updated_at:Date.now()/1000}];
 else if(name==='portalMembers')r.users=Object.values(users).map(u=>({...u,active:true}));
 else if(name==='portalDevices')r.devices=[{controller_id:'CP1',site_name:'Cliente de teste',status:'ativo',url:'https://fixture.trycloudflare.com',message:''}];
 else if(name==='portalSaveDevice')Object.assign(r,{key:'fixture-key-only',message:'Salvo'});
 else if(name==='portalSaveUser')Object.assign(r,{password_reset:true,acknowledged_id:'NEW',message:'Senha inicial 12345678. Troca obrigatória.'});
 else if(name==='loadSettings')r.platform_url='https://script.google.com/macros/s/fixture/exec';
 else if(name==='saveSettings'){actor=null;r.message='Plataforma salva. Entre novamente.';}
 setTimeout(()=>window.dmaxReply(id,r),5);
 }};
});
await ctx.route('**/assets/*',route=>route.fulfill({path:path.join(__dirname,'../build/assets',new URL(route.request().url()).pathname.split('/').pop())}));
const page=await ctx.newPage(),errors=[],network=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>network.push(r.url()));await page.goto('http://127.0.0.1:8795/');
async function login(name){await page.locator('#login-form input[name=name]').fill(name);await page.locator('#login-form input[name=password]').fill('Teste1234');await page.getByRole('button',{name:'Entrar na central',exact:true}).click();}
await page.screenshot({path:'/tmp/dmax-android-login-101.png',fullPage:true});
await login('primeiro');await page.getByRole('heading',{name:'Troque a senha inicial'}).waitFor();assert.equal(await page.locator('#sidebar').isVisible(),false);await page.locator('#password-form input[name=password]').fill('NovaSenha123');await page.locator('#password-form input[name=confirmation]').fill('NovaSenha123');await page.getByRole('button',{name:'Trocar senha e continuar'}).click();await page.getByRole('link',{name:'Acessar cliente',exact:true}).waitFor();
await page.screenshot({path:'/tmp/dmax-android-overview-101.png',fullPage:true});
await page.getByRole('link',{name:'Acessar cliente',exact:true}).click();await page.waitForTimeout(100);assert.equal(ctx.pages().length,1);assert.deepEqual(await page.evaluate(()=>calls.find(c=>c.name==='portalOpenClient').args),['CP1']);assert.equal(await page.getByText('https://fixture.trycloudflare.com',{exact:true}).count(),0);
await page.getByRole('button',{name:'Equipamentos',exact:true}).click();await page.getByRole('button',{name:'Editar equipamento',exact:true}).click();assert.equal(await page.locator('#device-form input[name=controller_id]').inputValue(),'CP1');await page.locator('#device-form select[name=status]').selectOption('pendente');await page.getByRole('button',{name:'Salvar equipamento',exact:true}).click();await page.waitForTimeout(100);assert.equal(await page.evaluate(()=>calls.find(c=>c.name==='portalSaveDevice').args[0].status),'pendente');
await page.locator('[data-view=members]').click();await page.getByRole('button',{name:'Criar novo membro'}).click();assert.equal(await page.locator('#member-form input[name=password]').count(),0);await page.locator('#member-form input[name=full_name]').fill('Novo Usuário');await page.locator('#member-form input[name=name]').fill('novo.usuario');await page.locator('#member-form input[name=actor_password]').fill('Teste1234');await page.getByRole('button',{name:'Salvar usuário',exact:true}).click();await page.waitForTimeout(100);assert.equal(await page.evaluate(()=>calls.find(c=>c.name==='portalSaveUser').args[1].reset_password),true);
await page.locator('[data-view=simulation]').click();await page.evaluate(()=>{for(const p of state.sim.ports){p.connected=true;p.soc=99.999;}state.simAt=performance.now()-60000;advanceSimulation();renderSimulation();});assert.equal(await page.locator('#sim-soc-0').textContent(),'100.0%');assert.equal(await page.locator('#sim-kw-0').textContent(),'0.0 kW');
await page.locator('[data-view=settings]').click();await page.getByRole('heading',{name:'Configurações deste Android'}).waitFor();assert.equal(await page.locator('#settings-form input[name=port]').count(),0);await page.locator('#settings-form input[name=password]').fill('Teste1234');await page.getByRole('button',{name:'Salvar plataforma',exact:true}).click();await page.locator('#login-view').waitFor({state:'visible'});
await login('comercial');await page.getByRole('link',{name:'Acessar cliente',exact:true}).waitFor();assert.equal(await page.locator('#members-nav').isVisible(),false);assert.equal(await page.locator('#devices-nav').isVisible(),false);assert.equal(await page.locator('#settings-nav').isVisible(),false);await page.locator('[data-view=simulation]').click();assert.notEqual(await page.locator('#sim-soc-0').textContent(),'100.0%');
assert.equal(await page.evaluate(()=>localStorage.length+sessionStorage.length),0);assert.ok(network.every(url=>url.startsWith('http://127.0.0.1:8795/')));assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.equal(errors.length,0,errors.join('\n'));await page.screenshot({path:'/tmp/dmax-android-simulation.png',fullPage:true});
console.log('Android browser PASS: first password, embedded handoff command, clients, developer devices/users, default reset, role UI, independent settings, isolated simulation and no platform tokens/storage/external fetch.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
