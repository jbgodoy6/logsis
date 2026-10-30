/** Real-browser regression with JavaScript disabled. Use a fresh simulation DB. */
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const base = process.env.DMAX_TEST_URL || 'http://127.0.0.1:8098';
const origin = new URL(base).origin;
const password = () => crypto.randomBytes(18).toString('hex');

async function main() {
  const browser = await chromium.launch({executablePath: process.env.DMAX_CHROMIUM || '/usr/bin/chromium',
    headless:true, args:['--no-sandbox']});
  try {
    const context = await browser.newContext({javaScriptEnabled:false, viewport:{width:1440,height:1100}});
    const page = await context.newPage();
    const errors = [], external = [], scripts = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => {
      if (new URL(r.url()).origin !== origin) external.push(r.url());
      if (r.resourceType() === 'script') scripts.push(r.url());
    });
    const root = password(), admin = password(), personal = password();
    const form = action => page.locator('form').filter({has:page.locator('input[name=_action][value="' + action + '"]')});
    const fill = (action,name,value) => form(action).locator('[name="' + name + '"]').fill(value);
    const submit = async action => {
      await Promise.all([page.waitForNavigation(), form(action).locator('button[type=submit]').last().click()]);
    };
    const go = async name => { await page.goto(base + '/ui/' + name); };
    const capture = async name => {
      if (process.env.DMAX_CAPTURE_DIR) {
        fs.mkdirSync(process.env.DMAX_CAPTURE_DIR,{recursive:true});
        await page.screenshot({path:path.join(process.env.DMAX_CAPTURE_DIR,name),fullPage:true});
      }
    };
    await page.goto(base);
    assert.equal(await page.locator('script').count(),0);
    await capture('login-server-v050.png');
    await fill('setup','root_password',root);
    await fill('setup','admin_password',admin);
    await submit('setup');
    await fill('login','username','admin');
    await fill('login','password',admin);
    await submit('login');
    await go('simulation');
    await submit('demo');
    await go('overview');
    await page.waitForSelector('.server-chart');
    await page.waitForTimeout(2200);
    await capture('painel-server-v050.png');
    await go('settings');
    assert.equal(await form('settings').locator('[name=technical_limit_kw]').count(),0);
    await fill('settings','limit_kw','900');
    await submit('settings');
    assert.equal(Number(await form('settings').locator('[name=limit_kw]').inputValue()),900);
    await submit('logout');
    await fill('login','username','root');
    await fill('login','password',root);
    await submit('login');

    await go('vehicles');
    const literal = '<strong data-probe="literal">Veículo de teste</strong>';
    await fill('vehicle','name',literal);
    await fill('vehicle','identifiers','SERVER-TEST');
    await form('vehicle').locator('[name=priority]').check();
    await submit('vehicle');
    assert.ok((await page.locator('main').innerText()).includes(literal));
    assert.equal(await page.locator('[data-probe]').count(),0);

    await go('chargers');
    await fill('charger','id','SSR-TEST');
    await fill('charger','name','Estação de validação');
    await submit('charger');
    assert.ok((await page.locator('.charger-grid').innerText()).includes('Estação de validação'));
    const state = await (await context.request.get(base + '/api/state')).json();
    await go('monitor');
    assert.equal(await page.locator('.charger-card').count(),state.ports.length);
    await go('chargers');
    const port = state.ports.find(p => p.connected);
    const card = page.locator('.charger-card').filter({has:page.locator('small').filter({hasText:port.key})}).first();
    const actionForm = command => card.locator('form').filter({has:page.locator('input[name=command][value="' + command + '"]')});
    await Promise.all([page.waitForNavigation(),actionForm('pause').locator('button').click()]);
    await Promise.all([page.waitForNavigation(),actionForm('resume').locator('button').click()]);
    await card.locator('summary').filter({hasText:'Liberar emergência'}).click();
    await actionForm('emergency').locator('[name=reason]').fill('Teste de interface em simulação');
    await Promise.all([page.waitForNavigation(),actionForm('emergency').locator('button').click()]);
    await Promise.all([page.waitForNavigation(),actionForm('cancel_emergency').locator('button').click()]);

    await go('schedule');
    await fill('schedule_add','start','23:01');
    await fill('schedule_add','end','23:02');
    await submit('schedule_add');
    assert.equal(await form('schedule_delete').count(),1);
    await submit('schedule_delete');
    assert.equal(await form('schedule_delete').count(),0);

    await go('meter');
    await form('meter').locator('[name=transport]').selectOption('rtu');
    await fill('meter','serial_port','COM7');
    await fill('meter','reg_0_address','5100');
    await submit('meter');
    assert.equal(await form('meter').locator('[name=reg_0_address]').inputValue(),'5100');
    await capture('multimedidor-server-v050.png');

    await go('users');
    await fill('user','name','server.operator');
    await fill('user','full_name','Operador de validação');
    await submit('user');
    const code = await page.locator('[name=activation_result]').inputValue();
    assert.ok(code.length >= 12);
    await page.getByRole('link',{name:'Fechar código',exact:true}).click();
    assert.equal(await page.locator('[name=activation_result]').count(),0);

    await go('directory');
    const key = crypto.randomBytes(32).toString('hex');
    await fill('directory','url','https://script.google.com/macros/s/CONFIGURAR_IMPLANTACAO/exec');
    await fill('directory','device_token',key);
    await submit('directory');
    assert.equal(await form('directory').locator('[name=device_token]').inputValue(),'');
    assert.equal((await page.content()).includes(key),false);

    await go('history');
    assert.ok((await page.locator('main').innerText()).includes('Sessões'));
    await submit('logout');
    await fill('login','username','server.operator');
    await fill('login','password','12345678');
    await fill('login','activation_code',code);
    await submit('login');
    assert.equal(await page.locator('nav').count(),0);
    await fill('password','current_password','12345678');
    await fill('password','new_password',personal);
    await fill('password','confirmation',personal);
    await submit('password');
    await fill('login','username','server.operator');
    await fill('login','password',personal);
    await submit('login');
    for (const name of ['settings','users','meter','directory','simulation']) {
      assert.equal(await page.locator('nav a[href="/ui/' + name + '"]').count(),0);
    }
    await go('chargers');
    assert.equal(await form('charger').count(),0);
    await go('profile');
    await fill('password','current_password',personal);
    await fill('password','new_password',personal + 'new');
    await fill('password','confirmation',personal + 'new');
    await submit('password');
    await fill('login','username','server.operator');
    await fill('login','password',personal + 'new');
    await submit('login');
    await page.setViewportSize({width:390,height:844});
    await capture('painel-mobile-server-v050.png');
    const dimensions = await page.evaluate(() => ({width:document.documentElement.scrollWidth, viewport:window.innerWidth}));
    assert.equal(dimensions.width <= dimensions.viewport,true);
    assert.deepEqual(errors,[]);
    assert.deepEqual(external,[]);
    assert.deepEqual(scripts,[]);
    assert.equal(await page.locator('script').count(),0);
    if (process.env.DMAX_RUNTIME_PACKAGE === '1') {
      assert.equal((await context.request.get(base + '/static/app.js')).status(),404);
      assert.equal((await context.request.get(base + '/static/index.html')).status(),404);
    }
    console.log('PASS: JavaScript disabled; setup, roles, passwords, chargers, vehicles, meter, schedules, emergency, history, Google and mobile.');
  } finally { await browser.close(); }
}
main().catch(e => { console.error(e.message);process.exitCode=1; });
