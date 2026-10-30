/**
 * Browser regression for the DOM console.
 * Legacy DOM interface only: start a fresh simulation server with DMAX_WEB_UI=legacy, then:
 * DMAX_TEST_URL=http://127.0.0.1:8094 node tests/browser_ui.cjs
 * Requires Playwright and Chromium only in the validation environment.
 * No charger hardware, internet service, production data or fixed admin secret.
 */
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

const url = process.env.DMAX_TEST_URL || 'http://127.0.0.1:8094';
const origin = new URL(url).origin;
const password = () => crypto.randomBytes(18).toString('hex');
const secrets = {root: password(), admin: password(), operator: password()};
const literalName = '<strong data-probe="untrusted">Texto externo</strong>';

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.DMAX_CHROMIUM || '/usr/bin/chromium',
    args: ['--no-sandbox'],
  });
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1100}});
    const page = await context.newPage();
    const errors = [], external = [], payloads = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('request', (request) => {
      if (new URL(request.url()).origin !== origin) external.push(request.url());
      if (request.method() === 'POST') payloads.push({path: new URL(request.url()).pathname, body: request.postData()});
    });
    const waitShell = () => page.waitForSelector('#shell:not([hidden])');
    const navigate = async (name) => {
      await page.locator('[data-view=' + name + ']').click();
      await page.waitForSelector('#view-' + name + ':not([hidden])');
    };
    const login = async (name, secret, activation = '') => {
      await page.locator('#auth-form [name=username]').fill(name);
      await page.locator('#auth-form [name=password]').fill(secret);
      await page.locator('#auth-form [name=activation_code]').fill(activation);
      await page.locator('#auth-submit').click();
    };
    const saveEditor = async () => {
      await page.locator('#editor-form button[type=submit]').click();
      await page.waitForSelector('#editor:not([open])', {state: 'attached'});
    };
    const field = (name) => page.locator('#editor-form [name=' + name + ']');

    const capture = async (name) => {
      if (!process.env.DMAX_CAPTURE_DIR) return;
      fs.mkdirSync(process.env.DMAX_CAPTURE_DIR, {recursive: true});
      await page.screenshot({path: path.join(process.env.DMAX_CAPTURE_DIR, name), fullPage: true});
    };
    await page.goto(url);
    await page.waitForFunction(() => document.querySelector('#auth-title').textContent.includes('Prepare'));
    assert.equal(await page.locator('#auth-form [name=username]').isDisabled(), true);
    await capture('login-dom-v040.png');
    await page.locator('[name=root_password]').fill(secrets.root);
    await page.locator('[name=admin_password]').fill(secrets.admin);
    await page.locator('#auth-submit').click();
    await waitShell();
    await page.locator('#demo').click();
    await page.waitForFunction(() => document.querySelectorAll('#overview-cards article').length === 3);
    await page.waitForSelector('#power-chart svg');
    await capture('painel-dom-v040.png');
    await page.setViewportSize({width: 390, height: 844});
    await capture('painel-mobile-dom-v040.png');
    await page.setViewportSize({width: 1440, height: 1100});
    assert.equal(await page.locator('[data-view=meter]').isVisible(), false);
    await navigate('settings');
    assert.equal(await page.locator('#settings-form [name=technical_limit_kw]').isDisabled(), true);
    await page.locator('#settings-form [name=limit_kw]').fill('900');
    await page.locator('#settings-form button[type=submit],#settings-form .form-footer button').click();
    await page.waitForFunction(() => document.querySelector('#metric-limit').textContent.includes('900'));

    await page.locator('#logout').click();
    await page.waitForSelector('#auth:not([hidden])');
    await login('root', secrets.root);
    await waitShell();
    await navigate('meter');
    await page.waitForSelector('#register-fields tr');
    await page.locator('#meter-form [name=transport]').selectOption('rtu');
    assert.equal(await page.locator('#meter-rtu-fields').isVisible(), true);
    await page.locator('#meter-form [name=transport]').selectOption('tcp');
    await navigate('settings');
    assert.equal(await page.locator('#settings-form [name=technical_limit_kw]').isDisabled(), false);

    await navigate('chargers');
    await page.locator('#add-charger').click();
    await field('id').fill('DOM-TEST');
    await field('name').fill(literalName);
    await saveEditor();
    await page.waitForFunction((value) => document.querySelector('#charger-list').textContent.includes(value), literalName);
    assert.equal(await page.locator('#charger-list [data-probe]').count(), 0);
    await page.locator('#charger-list [data-edit-charger=DOM-TEST]').click();
    assert.equal(await field('name').inputValue(), literalName);
    await page.locator('#close-editor').click();
    assert.equal(await page.locator('#editor-form input[type=password]').count(), 0);

    await navigate('vehicles');
    await page.locator('#add-vehicle').click();
    await field('name').fill(literalName);
    await field('identifiers').fill('DOM-VEHICLE');
    await field('priority').check();
    await saveEditor();
    await page.waitForFunction((value) => document.querySelector('#vehicle-list').textContent.includes(value), literalName);
    assert.equal(await page.locator('#vehicle-list [data-probe]').count(), 0);

    await navigate('schedule');
    await page.locator('#schedule-form [name=start]').fill('23:01');
    await page.locator('#schedule-form [name=end]').fill('23:02');
    await page.locator('#schedule-form button').click();
    await page.waitForSelector('[data-remove-schedule]');
    await page.locator('[data-remove-schedule]').first().click();
    await page.waitForFunction(() => document.querySelectorAll('[data-remove-schedule]').length === 0);

    await navigate('users');
    await page.locator('#add-user').click();
    await field('name').fill('dom.operator');
    await field('full_name').fill(literalName);
    await saveEditor();
    await page.waitForSelector('#activation-dialog[open]');
    const code = await page.locator('#activation-code').inputValue();
    assert.ok(code.length >= 12);
    assert.equal(await page.locator('#user-list [data-probe]').count(), 0);
    await page.locator('#close-activation').click();
    assert.equal(await page.locator('#activation-code').inputValue(), '');

    await navigate('directory');
    await page.waitForSelector('#directory-status table');
    const deviceKey = crypto.randomBytes(32).toString('hex');
    await page.locator('#directory-form [name=url]').fill('https://script.google.com/macros/s/CONFIGURAR_IMPLANTACAO/exec');
    await page.locator('#directory-form [name=device_token]').fill(deviceKey);
    await page.locator('#directory-form button[type=submit]').click();
    await page.waitForFunction(() => document.querySelector('#directory-status').textContent.includes('Configurada'));
    assert.equal(await page.locator('#directory-form [name=device_token]').inputValue(), '');
    const directory = await (await context.request.get(url + '/api/directory')).text();
    assert.equal(directory.includes(deviceKey), false);

    await navigate('history');
    await page.waitForSelector('#event-list table');
    const snapshot = await (await context.request.get(url + '/api/state')).json();
    const demoPort = snapshot.ports.find((port) => port.connected);
    await navigate('chargers');
    await page.locator('#charger-list [data-port="' + demoPort.key + '"][data-action=pause]').click();
    await page.waitForSelector('#charger-list [data-port="' + demoPort.key + '"][data-action=resume]');
    await page.locator('#charger-list [data-port="' + demoPort.key + '"][data-action=resume]').click();
    await page.waitForSelector('#charger-list [data-port="' + demoPort.key + '"][data-action=pause]');
    await page.locator('#charger-list [data-port="' + demoPort.key + '"][data-action=emergency]').click();
    await field('reason').fill('Teste de interface em simulação');
    await saveEditor();
    await page.waitForSelector('#charger-list [data-port="' + demoPort.key + '"][data-action=cancel_emergency]');
    await page.locator('#charger-list [data-port="' + demoPort.key + '"][data-action=cancel_emergency]').click();

    const controls = await page.evaluate(async () => {
      const {el} = await import('/static/dom.js');
      const {request} = await import('/static/transport.js');
      const literal = '<b data-check="text">texto</b>';
      const node = el('div', {}, literal);
      const result = {textOnly: node.textContent === literal && node.childElementCount === 0, blocked: 0};
      for (const candidate of ['https://untrusted.invalid', '//untrusted.invalid', '/../login']) {
        try { await request(candidate); } catch { result.blocked += 1; }
      }
      try { el('script'); } catch { result.blocked += 1; }
      try { el('div', {onclick: 'not-allowed'}); } catch { result.blocked += 1; }
      return result;
    });
    assert.deepEqual(controls, {textOnly: true, blocked: 5});
    const csp = (await context.request.get(url)).headers()['content-security-policy'];
    assert.ok(csp.includes("require-trusted-types-for 'script'"));

    await page.locator('#logout').click();
    await page.waitForSelector('#auth:not([hidden])');
    await login('dom.operator', '12345678', code);
    await page.waitForSelector('#first-change-form:not([hidden])');
    await page.locator('#first-change-form [name=current_password]').fill('12345678');
    await page.locator('#first-change-form [name=new_password]').fill(secrets.operator);
    await page.locator('#first-change-form [name=confirmation]').fill(secrets.operator);
    await page.locator('#first-change-form button').click();
    await page.waitForSelector('#auth-form:not([hidden])');
    await login('dom.operator', secrets.operator);
    await waitShell();
    assert.equal(await page.locator('#username').textContent(), literalName);
    for (const name of ['settings', 'meter', 'users', 'directory']) {
      assert.equal(await page.locator('[data-view=' + name + ']').isVisible(), false);
    }
    await navigate('chargers');
    assert.equal(await page.locator('[data-edit-charger]:visible').count(), 0);
    assert.equal(await page.locator('[data-action=emergency]:visible').count(), 0);
    await navigate('overview');
    assert.equal(await page.locator('#simulator').isVisible(), false);
    await page.setViewportSize({width: 390, height: 844});
    await page.waitForTimeout(500);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
    assert.deepEqual(external, []);
    assert.deepEqual(errors, []);
    assert.ok(payloads.filter((item) => item.body?.includes(secrets.root)).every((item) => item.path === '/api/setup' || item.path === '/api/login'));
    console.log('PASS: DOM literal, same-origin, lifecycle, roles, forms, meter, history, simulation, mobile; no browser errors.');
    await browser.close();
  } finally {
    await browser.close();
  }
}

main().catch((error) => { console.error(error.message); process.exitCode = 1; });
