/** D-Max local console. Native DOM components, explicit same-origin API calls. */
import {
  $, $$, el, svg, replace, button, field, selectField, option, check, empty, table,
  number as fmt, percentage,
} from './dom.js';
import {request, liveSocket} from './transport.js';

const titles = {
  overview: 'Visão geral', chargers: 'Carregadores', vehicles: 'Veículos',
  schedule: 'Programação', meter: 'Multimedidor', history: 'Histórico',
  settings: 'Configurações', users: 'Usuários', directory: 'Técnicos globais',
};
const roles = {
  root: 'Raiz', technician: 'Técnico / instalador', admin: 'Administrador', operator: 'Operador',
};
const days = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
let state = null;
let account = null;
let setupRequired = false;
let view = 'overview';
let socket = null;
let reconnectTimer;
let toastTimer;
let editorSave = null;
let generation = 0;
let managedUsers = [];
let meterDefinitions = [];
let meterTestResult = null;

const text = (selector, value) => { $(selector).textContent = value ?? ''; };
const hint = (message) => el('p', {class: 'hint'}, message);
const grid = (...children) => el('div', {class: 'form-grid'}, children);
const portPath = (key) => '/ports/' + encodeURIComponent(key);
const userPath = (id) => '/users/' + encodeURIComponent(id);

function stamp(value) {
  if (!value) return '—';
  return new Date(value * 1000).toLocaleString('pt-BR', {
    timeZone: state?.settings.timezone || 'America/Sao_Paulo',
    dateStyle: 'short', timeStyle: 'short',
  });
}

function notify(message, error = false) {
  text('#toast', message);
  $('#toast').classList.toggle('error', error);
  $('#toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 6000);
}

async function perform(action) {
  try {
    return await action();
  } catch (error) {
    notify(error.message, true);
  }
}

async function api(path, body, method) {
  try {
    return await request(path, body, method);
  } catch (error) {
    if (error.status === 401 && path !== '/login' && account) await showAuth();
    throw error;
  }
}

function closeEditor() {
  $('#editor').close();
  replace('#editor-form');
  editorSave = null;
}

function stopLive() {
  clearTimeout(reconnectTimer);
  if (socket) {
    socket.onclose = null;
    socket.onmessage = null;
    socket.close();
    socket = null;
  }
}

async function showAuth() {
  const current = ++generation;
  stopLive();
  account = null;
  state = null;
  managedUsers = [];
  meterTestResult = null;
  closeEditor();
  $('#activation-dialog').close();
  $('#activation-code').value = '';
  $$('input[type=password]').forEach((input) => { input.value = ''; });
  $('#auth-form').hidden = false;
  $('#first-change-form').hidden = true;
  $('#shell').hidden = true;
  $('#auth').hidden = false;
  const status = await request('/setup');
  if (current !== generation) return;
  setupRequired = status.required;
  $('#activation-field').hidden = setupRequired;
  $('#setup-fields').hidden = !setupRequired;
  $('#login-fields').hidden = setupRequired;
  for (const input of $$('#login-fields input')) input.disabled = setupRequired;
  for (const input of $$('#setup-fields input')) input.disabled = !setupRequired;
  $('#auth-form [name=activation_code]').disabled = setupRequired;
  text('#auth-title', setupRequired ? 'Prepare seu controlador' : 'Bem-vindo de volta');
  text('#auth-description', setupRequired
    ? 'Defina as credenciais da primeira instalação.'
    : 'Entre para acompanhar sua instalação.');
  text('#auth-submit', setupRequired ? 'Configurar acesso' : 'Entrar no controlador');
}

async function load() {
  const current = generation;
  const snapshot = await api('/state');
  if (current !== generation || !account) return;
  state = snapshot;
  render();
}

function connectLive() {
  stopLive();
  const current = generation;
  const connection = liveSocket();
  socket = connection;
  connection.onmessage = (event) => {
    if (current !== generation || !account) return;
    try {
      state = JSON.parse(event.data);
      text('#connection-status', 'Conexão em tempo real');
      render();
    } catch {
      connection.close();
      notify('Dados de atualização inválidos; reconectando.', true);
    }
  };
  connection.onclose = () => {
    if (current !== generation || !account) return;
    text('#connection-status', 'Reconectando…');
    reconnectTimer = setTimeout(() => perform(async () => {
      await load();
      if (current === generation && account) connectLive();
    }), 3000);
  };
  connection.onerror = () => connection.close();
}

async function enter() {
  const current = generation;
  const user = await api('/me');
  if (current !== generation) return;
  account = user;
  if (user.must_change) {
    $('#shell').hidden = true;
    $('#auth').hidden = false;
    $('#auth-form').hidden = true;
    $('#first-change-form').hidden = false;
    text('#auth-title', 'Troque a senha inicial');
    text('#auth-description', 'Defina uma senha pessoal para liberar seu acesso.');
    return;
  }
  text('#username', user.full_name || user.name);
  $('#auth').hidden = true;
  $('#shell').hidden = false;
  view = 'overview';
  selectView();
  await load();
  if (current === generation && account) connectLive();
}

function selectView() {
  $$('.view').forEach((node) => { node.hidden = node.id !== 'view-' + view; });
  $$('.nav').forEach((node) => node.classList.toggle('active', node.dataset.view === view));
  text('#page-title', titles[view]);
}

function go(next) {
  if (!account || !state || !Object.hasOwn(titles, next)) return;
  const technical = ['root', 'technician'].includes(account.role);
  const manager = account.role !== 'operator';
  if (next === 'meter' && !technical) return;
  if (['settings', 'users'].includes(next) && !manager) return;
  if (next === 'directory' && account.role !== 'root') return;
  view = next;
  selectView();
  if (view === 'settings') populateSettings();
  if (view === 'meter') perform(populateMeter);
  if (view === 'history') perform(loadHistory);
  if (view === 'users') perform(loadUsers);
  if (view === 'directory') perform(loadDirectory);
  render();
}

function render() {
  if (!state || !account) return;
  const settings = state.settings;
  const summary = state.summary || {};
  const ports = state.ports;
  text('#site-name', settings.site_name);
  text('#nav-count', state.chargers.length);
  text('#clock', new Date(state.time * 1000).toLocaleTimeString('pt-BR', {timeZone: settings.timezone}));
  text('#mode-badge', settings.mode === 'simulation' ? 'SIMULAÇÃO' : 'PILOTO FÍSICO');
  text('#metric-total', fmt(summary.total_kw));
  text('#metric-ev', fmt(summary.ev_kw));
  text('#metric-other', fmt(summary.other_kw));
  text('#metric-budget', fmt(summary.budget_kw));
  text('#metric-limit', 'Limite ' + fmt(settings.limit_kw) + ' kW · margem ' + fmt(settings.margin_kw) + ' kW');
  $('#consumption-bar').style.width = percentage(summary.total_kw / settings.limit_kw * 100);
  const connected = ports.filter((port) => port.connected).length;
  const charging = ports.filter((port) => port.connected && port.power_kw > 0.1).length;
  text('#metric-active', charging + ' conectores em recarga');
  text('#connected-count', connected);
  text('#charging-count', charging);
  text('#waiting-count', connected - charging);
  text('#available-count', ports.length - connected);
  text('#schedule-status', summary.blocked
    ? 'Horário bloqueado · novas sessões em espera' : 'Horário permitido para recarga');
  text('#sync-description', state.cloud.status);
  text('#sync-pending', fmt(state.cloud.pending, 0) + ' registros pendentes');
  text('#schedule-zone', settings.timezone);
  const warning = state.fault || (!summary.meter_fresh
    ? 'Sem medição atual: novas liberações bloqueadas.'
    : settings.mode === 'physical'
      ? 'Piloto físico: exige homologação de zero/retomada e proteções elétricas independentes.'
      : '');
  $('#live-alert').hidden = !warning;
  text('#live-alert', warning);
  replace('#overview-cards', chargerCards(ports.slice(0, 6)));
  if (view === 'chargers') replace('#charger-list', chargerCards(ports));
  if (view === 'vehicles') renderVehicles();
  if (view === 'schedule') renderSchedule();
  if (view === 'meter') renderMeterDiagnostics();
  drawChart();
  applyPermissions();
}

function chargerCards(ports) {
  if (!ports.length) return empty('Sua instalação começa aqui', 'Carregue a demonstração ou cadastre um carregador.');
  return ports.map((port) => {
    const charger = state.chargers.find((item) => item.id === port.charger);
    const vehicle = state.vehicles.find((item) => item.id === port.vehicle_id);
    const active = port.power_kw > 0.1;
    const emergency = port.emergency_until > state.time;
    const action = (label, name, attrs = {}) => button(label, {
      'data-port': port.key, 'data-action': name, ...attrs,
    });
    const actions = [];
    if (port.connected) actions.push(
      action(port.manual_pause ? 'Retomar' : 'Pausar', port.manual_pause ? 'resume' : 'pause'),
      action(emergency ? 'Encerrar exceção' : 'Emergência', emergency ? 'cancel_emergency' : 'emergency'),
      action('Veículo', 'assign_vehicle'),
    );
    if (charger.transport === 'simulator') actions.push(action(
      port.connected ? 'Desconectar' : 'Conectar veículo', port.connected ? 'disconnect' : 'connect',
      {class: port.connected ? 'secondary' : 'primary'},
    ));
    if (port.running) actions.push(action('Testar limite', 'test_limit'));
    actions.push(button('Configurar', {class: 'text-button', 'data-edit-charger': charger.id}));
    const progress = el('i');
    progress.style.width = percentage(port.power_kw / charger.connector_max_kw * 100);
    return el('article', {class: 'charger-card'},
      el('div', {class: 'charger-head'},
        el('div', {class: 'charger-title'},
          el('div', {class: 'charger-icon'}, 'ϟ'),
          el('div', {class: 'charger-identity'},
            el('h3', {}, charger.name),
            el('small', {}, charger.id + ' · conector ' + port.connector + ' · ' + fmt(charger.max_kw) + ' kW total'))),
        el('span', {class: 'badge ' + (active ? '' : port.connected ? 'amber' : 'gray')},
          active ? 'EM CARGA' : port.connected ? 'OCUPADO' : 'DISPONÍVEL')),
      el('div', {class: 'charger-vehicle'},
        '◇ ' + (vehicle?.name || (port.connected ? 'Veículo não identificado' : 'Nenhum veículo conectado')),
        vehicle?.priority ? el('span', {class: 'priority-label'}, '★ PRIORITÁRIO') : null),
      el('div', {class: 'charger-power'},
        el('strong', {}, fmt(port.power_kw), ' ', el('small', {}, 'kW')),
        el('small', {}, 'Limite enviado ' + fmt(port.limit_kw) + ' kW')),
      el('div', {class: 'charger-progress'}, progress),
      el('div', {class: 'charger-state'}, port.status,
        emergency ? ' · Exceção: ' + Math.ceil((port.emergency_until - state.time) / 60) + ' min' : '',
        port.test ? ' · Teste em andamento' : ''),
      el('div', {class: 'card-actions'}, actions));
  });
}

function drawChart() {
  const data = state.trace || [];
  if (data.length < 2) {
    replace('#power-chart', empty('Aguardando leituras', 'O gráfico será atualizado automaticamente.'));
    return;
  }
  const width = Math.max(240, $('#power-chart').clientWidth);
  const height = Math.max(100, $('#power-chart').clientHeight);
  const left = 48, top = 12, bottom = 27, limit = state.settings.limit_kw;
  const max = Math.max(limit, ...data.map((item) => item.total)) * 1.12;
  const x = (index) => left + (width - left - 8) * index / Math.max(1, data.length - 1);
  const y = (value) => height - bottom - (height - top - bottom) * value / max;
  const points = (key) => data.map((item, index) => x(index).toFixed(1) + ',' + y(item[key]).toFixed(1)).join(' ');
  const nodes = [];
  for (let index = 0; index <= 3; index += 1) {
    const value = max * index / 3;
    nodes.push(
      svg('line', {x1: left, x2: width, y1: y(value), y2: y(value), stroke: '#edf2f3'}),
      svg('text', {x: left - 10, y: y(value) + 3, 'text-anchor': 'end'}, fmt(value, 0)),
    );
  }
  nodes.push(
    svg('polygon', {points: left + ',' + (height - bottom) + ' ' + points('total') + ' ' + (width - 8) + ',' + (height - bottom), fill: '#e4f1fc'}),
    svg('line', {x1: left, x2: width, y1: y(limit), y2: y(limit), stroke: '#c58e3d', 'stroke-dasharray': '5 5'}),
    svg('polyline', {points: points('ev'), fill: 'none', stroke: '#69b7ee', 'stroke-width': 2}),
    svg('polyline', {points: points('total'), fill: 'none', stroke: '#0879cf', 'stroke-width': 2.5, 'stroke-linejoin': 'round'}),
    svg('text', {x: left, y: height - 4}, new Date(data[0].ts * 1000).toLocaleTimeString('pt-BR', {timeZone: state.settings.timezone})),
    svg('text', {x: width, y: height - 4, 'text-anchor': 'end'}, 'agora'),
  );
  replace('#power-chart', svg('svg', {
    viewBox: '0 0 ' + width + ' ' + height, role: 'img',
    'aria-label': 'Gráfico de potência total e recarga em quilowatts',
  }, nodes));
}

function renderVehicles() {
  replace('#vehicle-list', state.vehicles.length
    ? table(['Veículo', 'Placa', 'Prioridade', 'Identificadores', ''], state.vehicles.map((vehicle) => [
      el('b', {}, vehicle.name), vehicle.plate || '—',
      vehicle.priority ? el('span', {class: 'badge amber'}, '★ Prioritário') : 'Normal',
      vehicle.identifiers.join(', ') || 'Associação manual',
      button('Editar', {'data-edit-vehicle': vehicle.id}),
    ]))
    : empty('Nenhum veículo cadastrado', 'Cadastre um veículo ou associe um identificador observado.'));
  replace('#identifier-list', state.identifiers.length
    ? table(['Identificador', 'Veículo', 'Origem', 'Última conexão', ''], state.identifiers.map((item) => {
      const vehicle = state.vehicles.find((candidate) => candidate.identifiers.includes(item.id));
      return [
        item.id, vehicle?.name || 'Não associado', item.source, stamp(item.last_seen),
        button(vehicle ? 'Editar nome' : 'Associar / nomear', {'data-name-identifier': item.id}),
      ];
    }))
    : empty('Aguardando identificadores', 'Identificadores técnicos EVSYS não são tratados como veículos.'));
}

function renderSchedule() {
  replace('#schedule-list', state.settings.schedules.length
    ? state.settings.schedules.map((item, index) => el('div', {class: 'schedule-item'},
      el('div', {}, el('b', {}, item.start + ' — ' + item.end), el('small', {}, item.days.map((day) => days[day]).join(' · '))),
      button('Remover', {'data-remove-schedule': index})))
    : empty('Sem bloqueios de horário', 'Adicione os períodos em que a recarga deverá aguardar.'));
}

function openEditor(title, content, save) {
  closeEditor();
  text('#editor-title', title);
  replace('#editor-form', content, el('div', {class: 'dialog-actions'},
    button('Confirmar', {class: 'primary', type: 'submit'})));
  editorSave = save;
  $('#editor').showModal();
}

function editCharger(id) {
  const charger = state.chargers.find((item) => item.id === id) || {
    id: '', name: '', model: '', ip: '', max_kw: 320, connector_max_kw: 320, min_kw: 6,
    connectors: 1, transport: 'simulator', circuit: state.settings.circuits[0].id,
    enabled: true, commissioned: false, zero_supported: false, rate_unit: 'W',
    voltage: 230, phases: 3, input_factor: 1,
  };
  openEditor(id ? 'Configurar carregador' : 'Novo carregador', [
    grid(field('Identificador OCPP', 'id', charger.id, 'text', {required: true, maxlength: 40, readonly: !!id}),
      field('Nome', 'name', charger.name, 'text', {required: true, maxlength: 100})),
    grid(selectField('Conexão', 'transport', [['simulator', 'Simulador'], ['ocpp', 'OCPP 1.6J']], charger.transport),
      field('IP para referência', 'ip', charger.ip)),
    field('Fabricante / modelo', 'model', charger.model),
    field('Reserva de entrada / saída · fator de perdas', 'input_factor', charger.input_factor, 'number',
      {required: true, min: 1, max: 2, step: 0.01}),
    grid(field('Máximo total · kW', 'max_kw', charger.max_kw, 'number', {required: true, min: 0.1, step: 'any'}),
      field('Máximo por conector · kW', 'connector_max_kw', charger.connector_max_kw, 'number', {required: true, min: 0.1, step: 'any'})),
    grid(field('Mínimo validado · kW', 'min_kw', charger.min_kw, 'number', {required: true, min: 0, step: 'any'}),
      field('Conectores compartilhando o total', 'connectors', charger.connectors, 'number', {required: true, min: 1, max: 8, readonly: !!id})),
    selectField('Quadro / circuito', 'circuit', state.settings.circuits.map((item) => [item.id, item.name]), charger.circuit),
    grid(selectField('Unidade aceita no perfil OCPP', 'rate_unit', [['W', 'Watts'], ['A', 'Ampères · AC']], charger.rate_unit),
      field('Tensão fase-neutro · V', 'voltage', charger.voltage, 'number', {min: 1, step: 'any'})),
    field('Número de fases · AC', 'phases', charger.phases, 'number', {min: 1, max: 3}),
    field(id ? 'Nova senha OCPP · deixe vazio para manter' : 'Senha OCPP · obrigatória para equipamento físico',
      'password', '', 'password', {minlength: 8, maxlength: 200, autocomplete: 'new-password'}),
    check('Equipamento habilitado', 'enabled', charger.enabled),
    check('Limite zero e retomada testados no equipamento', 'zero_supported', charger.zero_supported),
    check('Comissionamento concluído para piloto físico', 'commissioned', charger.commissioned),
    hint('Conexão: wss://ENDEREÇO-DO-CONTROLADOR/ocpp/IDENTIFICADOR. O modo físico exige TLS, medidor e homologação. IP não identifica o veículo.'),
  ], async (form) => {
    const data = Object.fromEntries(form);
    for (const name of ['max_kw', 'connector_max_kw', 'min_kw', 'connectors', 'voltage', 'phases', 'input_factor']) data[name] = Number(data[name]);
    for (const name of ['enabled', 'zero_supported', 'commissioned']) data[name] = form.has(name);
    if (!data.password) delete data.password;
    await api('/chargers', data);
  });
}

function editVehicle(id, identifier) {
  const vehicle = state.vehicles.find((item) => item.id === id) || {
    name: '', plate: '', priority: false, identifiers: identifier ? [identifier] : [],
  };
  openEditor(id ? 'Editar veículo' : 'Cadastrar veículo', [
    field('Nome do veículo', 'name', vehicle.name, 'text', {required: true, maxlength: 100}),
    field('Placa · opcional', 'plate', vehicle.plate, 'text', {maxlength: 20}),
    field('Identificadores · separados por vírgula', 'identifiers', vehicle.identifiers.join(', ')),
    check('★ Veículo prioritário', 'priority', vehicle.priority),
    hint('A prioridade acompanha o veículo reconhecido e não libera o horário bloqueado. Confirme se o identificador distingue veículos.'),
  ], async (form) => {
    const data = {
      name: form.get('name'), plate: form.get('plate'),
      identifiers: form.get('identifiers').split(',').map((item) => item.trim()).filter(Boolean),
      priority: form.has('priority'),
    };
    if (id) data.id = id;
    await api('/vehicles', data);
  });
}

function portAction(key, action) {
  const port = state.ports.find((item) => item.key === key);
  if (!port) return;
  if (['connect', 'assign_vehicle'].includes(action)) {
    const options = [['', 'Não identificado / associação manual'], ...state.vehicles.map((vehicle) => [vehicle.id, vehicle.name + (vehicle.priority ? ' ★' : '')])];
    const content = [selectField('Veículo', 'vehicle_id', options, port.vehicle_id || '')];
    if (action === 'connect') content.push(field('Potência aceita pelo veículo · kW', 'acceptance_kw',
      state.chargers.find((charger) => charger.id === port.charger).connector_max_kw,
      'number', {min: 0.1, step: 'any', required: true}));
    content.push(hint('Uma associação manual será registrada na auditoria.'));
    openEditor(action === 'connect' ? 'Conectar veículo simulado' : 'Associar veículo à sessão', content, async (form) => {
      const data = {action, vehicle_id: form.get('vehicle_id') || null};
      if (action === 'connect') data.acceptance_kw = Number(form.get('acceptance_kw'));
      await api(portPath(key) + '/action', data);
    });
  } else if (action === 'test_limit') {
    openEditor('Aprendizado assistido · testar limite', [
      field('Limite temporário · kW', 'cap_kw', port.limit_kw / 2, 'number', {min: 0, step: 'any', required: true}),
      field('Duração · segundos', 'seconds', 30, 'number', {min: 10, max: 300, required: true}),
      hint('O teste só reduz o orçamento atual. O resultado é observacional e uma sessão não comprova o mínimo do equipamento.'),
    ], async (form) => api(portPath(key) + '/learn', {cap_kw: Number(form.get('cap_kw')), seconds: Number(form.get('seconds'))}));
  } else if (action === 'emergency') {
    openEditor('Liberar recarga de emergência', [
      field('Duração · minutos', 'minutes', 30, 'number', {min: 1, max: 1440, required: true}),
      field('Motivo', 'reason', '', 'text', {required: true, maxlength: 200}),
      hint('Libera o bloqueio de horário, preservando demanda e circuitos. Termina ao desconectar o veículo.'),
    ], async (form) => api(portPath(key) + '/action', {action, minutes: Number(form.get('minutes')), reason: form.get('reason')}));
  } else {
    perform(async () => { await api(portPath(key) + '/action', {action}); await load(); });
  }
}

function circuitRow(circuit = {id: 'circuito-' + Date.now().toString(36), name: 'Novo circuito', limit_kw: 100}) {
  return el('div', {class: 'circuit-row'},
    field('Identificador', 'circuit_id', circuit.id, 'text', {required: true, maxlength: 40}),
    field('Nome', 'circuit_name', circuit.name, 'text', {required: true}),
    field('Limite · kW', 'circuit_limit', circuit.limit_kw, 'number', {min: 0.1, step: 'any', required: true}),
    button('×', {class: 'icon-button', 'data-remove-circuit': '1', 'aria-label': 'Remover circuito'}));
}

function populateSettings() {
  const form = $('#settings-form');
  for (const [name, value] of Object.entries(state.settings)) {
    const input = form.elements.namedItem(name);
    if (input && !['circuits', 'schedules', 'meter'].includes(name)) input.value = value;
  }
  replace('#circuit-fields', state.settings.circuits.map(circuitRow));
  applyPermissions();
}

const eventNames = {
  connected: 'Veículo conectado', disconnected: 'Veículo desconectado', session_start: 'Recarga iniciada',
  session_end: 'Recarga encerrada', limit_changed: 'Limite alterado', operator_action: 'Ação do operador',
  settings_changed: 'Configuração alterada', charger_configured: 'Carregador configurado',
  vehicle_configured: 'Veículo configurado', test_started: 'Teste de limite iniciado',
  test_finished: 'Teste de limite concluído', command_failed: 'Comando rejeitado / sem resposta',
  ocpp_connected: 'Conexão OCPP', ocpp_disconnected: 'Conexão OCPP encerrada',
  ocpp_status: 'Estado OCPP', controller_fault: 'Falha no controle',
};

async function loadHistory() {
  const current = generation;
  const history = await api('/history');
  if (current !== generation || !account) return;
  replace('#session-list', history.sessions.length
    ? table(['Início', 'Conector', 'Veículo', 'Energia', 'Pico', 'Estado', 'Origem'],
      history.sessions.sort((a, b) => b.started_at - a.started_at).map((session) => [
        stamp(session.started_at), session.port,
        state.vehicles.find((vehicle) => vehicle.id === session.vehicle_id)?.name || 'Não identificado',
        fmt(session.energy_kwh, 3) + ' kWh', fmt(session.peak_kw) + ' kW',
        session.ended_at ? session.reason || 'Encerrada' : 'Em andamento',
        session.mode === 'simulator' ? 'Simulação' : 'OCPP',
      ]))
    : empty('Nenhuma sessão ainda', 'As recargas aparecerão aqui quando iniciarem.'));
  replace('#event-list', history.events.length
    ? table(['Horário', 'Evento', 'Detalhes'], history.events.map((event) => [
      stamp(event.ts), eventNames[event.kind] || event.kind, JSON.stringify(event.payload),
    ]))
    : empty('Sem eventos', 'Aguardando atividade.'));
}

async function populateMeter() {
  meterTestResult = null;
  const current = generation;
  const data = await api('/meter/measurements');
  if (current !== generation || !account) return;
  meterDefinitions = data.measurements;
  const meter = state.settings.meter;
  for (const [name, value] of Object.entries(meter)) {
    const input = $('#meter-form').elements.namedItem(name);
    if (input && name !== 'registers') input.value = value;
  }
  replace('#register-fields', meter.registers.map(registerRow));
  updateMeterTransport();
  renderMeterDiagnostics();
}

function registerRow(register) {
  const definition = meterDefinitions.find((item) => item.key === register.measurement);
  const input = (name, type, attrs = {}) => {
    const node = el('input', {type, 'data-field': name, 'aria-label': definition.label + ' · ' + name, ...attrs});
    if (type !== 'checkbox') node.value = register[name];
    return node;
  };
  const select = (name, options) => {
    const node = el('select', {'data-field': name, 'aria-label': definition.label + ' · ' + name},
      options.map(([value, title]) => option(value, title)));
    node.value = register[name];
    return node;
  };
  return el('tr', {'data-measurement': register.measurement, class: register.enabled ? '' : 'disabled'},
    el('td', {}, input('enabled', 'checkbox', {checked: register.enabled})),
    el('td', {class: 'measurement-name'}, el('b', {}, definition.label), el('small', {}, 'Unidade final: ' + (definition.unit || 'adimensional'))),
    el('td', {}, input('address', 'number', {min: 0, max: 65536, required: true})),
    el('td', {}, select('function', [[3, '03 · Holding'], [4, '04 · Input']])),
    el('td', {}, select('type', ['float32', 'float64', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64'].map((type) => [type, type]))),
    el('td', {}, input('scale', 'number', {step: 'any', required: true})),
    el('td', {}, select('word_order', [['big', 'Normal'], ['little', 'Invertidas']])),
    el('td', {}, select('byte_order', [['big', 'Normais'], ['little', 'Invertidos']])));
}

function updateMeterTransport() {
  const rtu = $('#meter-form [name=transport]').value === 'rtu';
  $('#meter-tcp-fields').hidden = rtu;
  $('#meter-rtu-fields').hidden = !rtu;
  $('#meter-form [name=unit]').min = rtu ? '1' : '0';
  $('#meter-form [name=unit]').max = rtu ? '247' : '255';
  if (rtu) perform(async () => {
    const current = generation;
    const data = await api('/meter/ports');
    if (current === generation && account) replace('#serial-ports', data.ports.map((port) => option(port.device, port.description)));
  });
}

function meterDraft() {
  const form = new FormData($('#meter-form'));
  const meter = structuredClone(state.settings.meter);
  for (const name of ['transport', 'host', 'serial_port', 'parity']) meter[name] = form.get(name);
  for (const name of ['port', 'unit', 'address_base', 'poll_s', 'timeout_s', 'baudrate', 'stopbits']) meter[name] = Number(form.get(name));
  meter.bytesize = 8;
  meter.registers = $$('#register-fields tr').map((row) => {
    const record = {measurement: row.dataset.measurement};
    for (const input of row.querySelectorAll('[data-field]')) {
      const name = input.dataset.field;
      record[name] = name === 'enabled' ? input.checked
        : ['address', 'function', 'scale'].includes(name) ? Number(input.value) : input.value;
    }
    return record;
  });
  return meter;
}

function renderMeterDiagnostics() {
  const readings = meterTestResult?.readings || state.meter.readings || [];
  const error = meterTestResult?.error || (!meterTestResult ? state.meter.error : '');
  text('#meter-health', state.summary.meter_fresh ? state.settings.mode === 'simulation' ? 'Simulação' : 'Leitura atual' : 'Sem leitura atual');
  text('#meter-diagnostic-label', meterTestResult ? 'Resultado do teste do formulário · não salvo automaticamente' : 'Leituras recebidas em operação');
  text('#meter-test-message', error || (meterTestResult
    ? meterTestResult.ok ? 'Teste concluído. Confira unidades e valores antes de salvar.' : 'Teste parcial: confira as leituras com erro.'
    : 'O teste é somente leitura e não salva o formulário.'));
  $('#meter-test-message').classList.toggle('meter-read-error', !!error);
  replace('#meter-readings', readings.length
    ? table(['Grandeza', 'Leitura', 'Horário'], readings.map((reading) => [
      [reading.label, el('small', {class: 'meter-reading-time'}, ' · ' + String(reading.function).padStart(2, '0') + '/' + reading.address)],
      reading.error ? el('span', {class: 'meter-read-error'}, reading.error)
        : [el('b', {class: 'meter-reading-number'}, fmt(reading.value, 3)), ' ' + reading.unit],
      stamp(reading.at),
    ]))
    : empty('Aguardando teste ou medição', 'Insira os offsets do manual e teste a conexão.'));
}

function applyPermissions() {
  if (!account || !state) return;
  const technical = ['root', 'technician'].includes(account.role);
  const manager = account.role !== 'operator';
  for (const [name, allowed] of [['meter', technical], ['settings', manager], ['users', manager], ['directory', account.role === 'root']]) {
    $('[data-view=' + name + ']').hidden = !allowed;
  }
  for (const node of $$('[data-edit-charger],#add-charger')) node.hidden = !technical;
  for (const node of $$('[data-edit-vehicle],#add-vehicle')) node.hidden = !manager;
  $('#demo').hidden = !manager || state.chargers.length > 0;
  $('#simulator').hidden = !manager || state.settings.mode !== 'simulation';
  for (const node of $$('#schedule-form input,#schedule-form button')) node.disabled = !manager;
  for (const node of $$('[data-remove-schedule]')) node.hidden = !manager;
  for (const node of $$('[data-port]')) {
    const action = node.dataset.action;
    if (action === 'test_limit') node.hidden = !technical;
    if (['connect', 'disconnect'].includes(action)) node.hidden = !manager;
    if (['emergency', 'cancel_emergency'].includes(action)) node.hidden = !manager && !account.can_emergency;
  }
  for (const node of $$('#settings-form input,#settings-form select,#settings-form button')) {
    node.disabled = !technical && !['site_name', 'limit_kw', 'blocked_policy'].includes(node.name) && node.type !== 'submit';
  }
  $('#recovery-panel').hidden = account.role !== 'root';
}

function showActivation(code) {
  $('#activation-code').value = code;
  $('#activation-dialog').showModal();
}

function untilInput(value) {
  if (!value) return '';
  const date = new Date(value * 1000);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

async function loadUsers() {
  const current = generation;
  const data = await api('/users');
  if (current !== generation || !account) return;
  managedUsers = data.users;
  const sources = {local: 'Local', local_pending: 'Local · a sincronizar', directory: 'Plataforma'};
  replace('#user-list', managedUsers.length
    ? table(['Nome / login', 'Perfil', 'Situação', 'Validade', 'Origem', ''], managedUsers.map((user) => [
      [el('b', {}, user.full_name), el('small', {class: 'meter-reading-time'}, ' · ' + user.name)],
      roles[user.role],
      [el('span', {class: 'badge ' + (user.active && !user.deleted ? '' : 'amber')},
        user.deleted ? 'Excluído' : user.active ? 'Ativo' : 'Bloqueado'),
      user.must_change ? el('small', {}, ' · Primeiro acesso') : null],
      user.expires_at ? stamp(user.expires_at) : 'Sem vencimento',
      sources[user.source] || user.source,
      user.role === 'root' ? 'Recuperação' : [
        button('Editar', {'data-edit-user': user.id}), ' ',
        button('Renovar ativação', {'data-reset-user': user.id}),
      ],
    ]))
    : empty('Nenhuma conta gerenciável', 'Cadastre o primeiro usuário do seu perfil de gestão.'));
}

function editUser(id) {
  const old = managedUsers.find((user) => user.id === id);
  const user = old || {name: '', full_name: '', role: 'operator', active: true, deleted: false, expires_at: null, can_emergency: false};
  const allowed = old?.role === 'technician' ? ['technician'] : account.role === 'root'
    ? ['operator', 'admin', 'technician'] : account.role === 'technician' ? ['operator', 'admin'] : ['operator'];
  openEditor(old ? 'Editar conta' : 'Adicionar usuário', [
    field('Nome completo', 'full_name', user.full_name, 'text', {required: true, maxlength: 100}),
    field('Login permanente', 'name', user.name, 'text', {required: true, minlength: 3, maxlength: 40, readonly: !!old}),
    selectField('Perfil', 'role', allowed.map((role) => [role, roles[role]]), user.role),
    field('Validade · deixe vazio para não expirar', 'expires_at', untilInput(user.expires_at), 'datetime-local'),
    check('Operador autorizado a liberar emergência', 'can_emergency', user.can_emergency),
    old ? [check('Conta ativa', 'active', user.active), check('Excluir acesso e preservar auditoria', 'deleted', user.deleted)] : null,
    hint('Técnicos são globais e entram na fila de sincronização. A senha inicial é 12345678, com ativação individual e troca obrigatória.'),
  ], async (form) => {
    const data = {
      full_name: form.get('full_name'), role: form.get('role'), can_emergency: form.has('can_emergency'),
      expires_at: form.get('expires_at') ? new Date(form.get('expires_at')).toISOString() : null,
    };
    const result = old
      ? await api(userPath(old.id), {...data, active: form.has('active'), deleted: form.has('deleted')}, 'PUT')
      : await api('/users', {...data, name: form.get('name')});
    await loadUsers();
    return result;
  });
}

async function loadDirectory() {
  const current = generation;
  const data = await api('/directory');
  if (current !== generation || !account) return;
  const form = $('#directory-form');
  form.elements.url.value = data.config.url;
  form.elements.interval_minutes.value = data.config.interval_s / 60;
  form.elements.enabled.checked = data.config.enabled;
  replace('#directory-status', table(['Informação', 'Valor'], [
    ['Identificador do D-Max', data.controller_id],
    ['Resultado', data.status.message],
    ['Última consulta', stamp(data.status.last_attempt)],
    ['Último sucesso', stamp(data.status.last_success)],
    ['Próxima consulta prevista', stamp(data.status.next_attempt)],
    ['Alterações locais pendentes', data.pending],
    ['Chave do equipamento', data.token_present ? 'Configurada' : 'Pendente'],
  ]));
}

function bindEvents() {
  $('#auth-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const submit = event.submitter;
    submit.disabled = true;
    text('#auth-error', '');
    try {
      const form = new FormData(event.target);
      if (setupRequired) {
        await api('/setup', {root_password: form.get('root_password'), admin_password: form.get('admin_password')});
        await api('/login', {username: 'admin', password: form.get('admin_password')});
      } else {
        await api('/login', {username: form.get('username'), password: form.get('password'), activation_code: form.get('activation_code') || ''});
      }
      event.target.reset();
      await enter();
    } catch (error) {
      text('#auth-error', error.message);
    } finally {
      submit.disabled = false;
    }
  });
  $('#logout').addEventListener('click', () => perform(async () => { await api('/logout', {}); await showAuth(); }));
  $('#refresh').addEventListener('click', () => perform(load));
  $$('[data-view]').forEach((node) => node.addEventListener('click', () => go(node.dataset.view)));
  $$('[data-go]').forEach((node) => node.addEventListener('click', () => go(node.dataset.go)));
  $('#close-editor').addEventListener('click', closeEditor);
  $('#editor').addEventListener('cancel', (event) => { event.preventDefault(); closeEditor(); });
  $('#editor-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const save = editorSave;
    if (!save) return;
    const current = generation;
    const submit = event.submitter;
    submit.disabled = true;
    perform(async () => {
      try {
        const result = await save(new FormData(event.target));
        if (current !== generation || !account) return;
        closeEditor();
        await load();
        if (current !== generation || !account) return;
        if (result?.activation_code) showActivation(result.activation_code);
        else notify('Alteração aplicada no controlador.');
      } finally {
        submit.disabled = false;
      }
    });
  });
  $('#add-charger').addEventListener('click', () => editCharger());
  $('#add-vehicle').addEventListener('click', () => editVehicle());
  $('#add-circuit').addEventListener('click', () => $('#circuit-fields').append(circuitRow()));
  $('#add-user').addEventListener('click', () => editUser());
  $('#refresh-users').addEventListener('click', () => perform(loadUsers));
  $('#refresh-history').addEventListener('click', () => perform(loadHistory));
  $('#close-activation').addEventListener('click', () => {
    $('#activation-code').value = '';
    $('#activation-dialog').close();
  });
  $('#activation-dialog').addEventListener('close', () => { $('#activation-code').value = ''; });
  document.addEventListener('click', (event) => {
    const node = event.target.closest('button');
    if (!node || !account || !state) return;
    if (node.dataset.port) portAction(node.dataset.port, node.dataset.action);
    if (node.dataset.editCharger) editCharger(node.dataset.editCharger);
    if (node.dataset.editVehicle) editVehicle(node.dataset.editVehicle);
    if (node.dataset.nameIdentifier) {
      const id = node.dataset.nameIdentifier;
      editVehicle(state.vehicles.find((vehicle) => vehicle.identifiers.includes(id))?.id, id);
    }
    if (node.dataset.removeSchedule !== undefined) perform(async () => {
      const settings = structuredClone(state.settings);
      settings.schedules.splice(Number(node.dataset.removeSchedule), 1);
      await api('/settings', settings, 'PUT');
      await load();
    });
    if (node.dataset.removeCircuit !== undefined) node.closest('.circuit-row').remove();
    if (node.dataset.editUser) editUser(node.dataset.editUser);
    if (node.dataset.resetUser) perform(async () => {
      const current = generation;
      const data = await api(userPath(node.dataset.resetUser) + '/reset', {});
      if (current !== generation || !account) return;
      showActivation(data.activation_code);
      await loadUsers();
    });
  });
  $('#load-form').addEventListener('submit', (event) => {
    event.preventDefault();
    perform(async () => {
      await api('/simulation', {other_kw: Number($('#other-load').value)});
      notify('Carga do cliente atualizada no simulador.');
    });
  });
  $('#demo').addEventListener('click', () => perform(async () => {
    await api('/demo', {});
    await load();
    notify('Demonstração iniciada.');
  }));
  $('#schedule-form').addEventListener('submit', (event) => {
    event.preventDefault();
    perform(async () => {
      const form = new FormData(event.target);
      const settings = structuredClone(state.settings);
      settings.schedules.push({days: form.getAll('days').map(Number), start: form.get('start'), end: form.get('end'), enabled: true});
      await api('/settings', settings, 'PUT');
      await load();
      notify('Bloqueio de horário adicionado.');
    });
  });
  $('#settings-form').addEventListener('submit', (event) => {
    event.preventDefault();
    perform(async () => {
      const form = new FormData(event.target);
      const settings = structuredClone(state.settings);
      for (const name of ['site_name', 'mode', 'timezone', 'blocked_policy', 'cloud_url']) if (form.has(name)) settings[name] = form.get(name);
      for (const name of ['limit_kw', 'technical_limit_kw', 'margin_kw', 'freshness_s', 'ramp_kw_s', 'retain_days']) if (form.has(name)) settings[name] = Number(form.get(name));
      settings.circuits = $$('#circuit-fields .circuit-row').map((row) => ({
        id: row.querySelector('[name=circuit_id]').value, name: row.querySelector('[name=circuit_name]').value,
        limit_kw: Number(row.querySelector('[name=circuit_limit]').value),
      }));
      await api('/settings', settings, 'PUT');
      await load();
      if (account) populateSettings();
      notify('Configurações salvas e auditadas.');
    });
  });
  $('#recovery-form').addEventListener('submit', (event) => {
    event.preventDefault();
    perform(async () => {
      await api('/recover-admin', {username: 'admin', password: new FormData(event.target).get('password')});
      event.target.reset();
      notify('Senha do administrador redefinida; sessões anteriores encerradas.');
    });
  });
  $('#meter-form [name=transport]').addEventListener('change', updateMeterTransport);
  $('#meter-form').addEventListener('change', (event) => {
    if (event.target.dataset.field === 'enabled') event.target.closest('tr').classList.toggle('disabled', !event.target.checked);
    meterTestResult = null;
    text('#meter-test-message', 'Configuração alterada. Teste antes de aplicar.');
  });
  $('#meter-test').addEventListener('click', () => perform(async () => {
    const submit = $('#meter-test');
    const current = generation;
    submit.disabled = true;
    submit.textContent = 'Lendo…';
    try {
      const result = await api('/meter/test', meterDraft());
      if (current === generation && account) { meterTestResult = result; renderMeterDiagnostics(); }
    } finally {
      submit.disabled = false;
      submit.textContent = 'Testar leitura';
    }
  }));
  $('#meter-form').addEventListener('submit', (event) => {
    event.preventDefault();
    perform(async () => {
      await api('/settings', {...structuredClone(state.settings), meter: meterDraft()}, 'PUT');
      await load();
      notify('Multimedidor e mapa de registradores salvos.');
    });
  });
  $('#first-change-form').addEventListener('submit', (event) => {
    event.preventDefault();
    perform(async () => {
      const form = new FormData(event.target);
      if (form.get('new_password') !== form.get('confirmation')) throw new Error('As novas senhas não coincidem');
      await api('/change-password', {current_password: form.get('current_password'), new_password: form.get('new_password')});
      event.target.reset();
      await showAuth();
      text('#auth-description', 'Senha alterada. Entre com sua nova senha.');
    });
  });
  $('#change-own-password').addEventListener('click', () => openEditor('Alterar minha senha', [
    field('Senha atual', 'current_password', '', 'password', {required: true, autocomplete: 'current-password'}),
    field('Nova senha', 'new_password', '', 'password', {required: true, minlength: 8, maxlength: 200, autocomplete: 'new-password'}),
  ], async (form) => { await api('/change-password', Object.fromEntries(form)); await showAuth(); }));
  $('#directory-form').addEventListener('submit', (event) => {
    event.preventDefault();
    perform(async () => {
      const form = new FormData(event.target);
      const data = {
        url: form.get('url'), interval_s: Math.round(Number(form.get('interval_minutes')) * 60),
        enabled: form.has('enabled'),
      };
      if (form.get('device_token')) data.device_token = form.get('device_token');
      try {
        await api('/directory', data, 'PUT');
      } finally {
        $('#directory-form [name=device_token]').value = '';
      }
      await loadDirectory();
      notify('Período de consulta salvo.');
    });
  });
  $('#sync-directory').addEventListener('click', () => perform(async () => {
    const submit = $('#sync-directory');
    submit.disabled = true;
    try {
      const result = await api('/directory/sync', {});
      await loadDirectory();
      notify(result.status.message, !result.ok);
    } finally {
      submit.disabled = false;
    }
  }));
}

bindEvents();
enter().catch(() => showAuth()).catch((error) => notify(error.message, true));
