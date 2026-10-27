'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (v, digits=1) => Number(v || 0).toLocaleString('pt-BR', {maximumFractionDigits:digits});
let state, account, setupRequired=false, view='overview', socket, reconnectTimer, toastTimer, editorSave;
const titles={overview:'Visão geral',chargers:'Carregadores',vehicles:'Veículos',schedule:'Programação',meter:'Multimedidor',history:'Histórico',settings:'Configurações',users:'Usuários',directory:'Técnicos globais'};
const days=['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'];
function notify(message,error=false){$('#toast').textContent=message;$('#toast').classList.toggle('error',error);$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,6000);}
async function api(path,body,method='POST'){
  const response=await fetch('/api'+path,{method:body===undefined?'GET':method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  let data;try{data=await response.json();}catch{throw new Error('Resposta inesperada do controlador');}
  if(!response.ok){if(response.status===401&&path!='/login')showAuth();const message=Array.isArray(data.detail)?data.detail.map(x=>`${x.loc.slice(1).join('.')}: ${x.msg}`).join('; '):data.detail;throw new Error(message||'Não foi possível concluir');}
  return data;
}
async function perform(fn){try{await fn();}catch(e){notify(e.message,true);}}
async function showAuth(){account=null;$('#editor').close();$('#activation-dialog').close();$('#activation-code').value='';$$('input[type=password]').forEach(el=>el.value='');$('#auth-form').hidden=false;$('#first-change-form').hidden=true;clearTimeout(reconnectTimer);if(socket){socket.onclose=null;socket.close();socket=null;}$('#shell').hidden=true;$('#auth').hidden=false;setupRequired=(await api('/setup')).required;$('#activation-field').hidden=setupRequired;$('#setup-fields').hidden=!setupRequired;$('#login-fields').hidden=setupRequired;$('#auth-title').textContent=setupRequired?'Prepare seu controlador':'Bem-vindo de volta';$('#auth-description').textContent=setupRequired?'Defina as credenciais da primeira instalação.':'Entre para acompanhar sua instalação.';$('#auth-form button').firstChild.textContent=setupRequired?'Configurar acesso ':'Entrar no controlador ';}
async function load(){state=await api('/state');render();}
function connectLive(){clearTimeout(reconnectTimer);socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/live`);socket.onmessage=e=>{state=JSON.parse(e.data);$('#connection-status').textContent='Conexão em tempo real';render();};socket.onclose=()=>{if(!$('#shell').hidden){$('#connection-status').textContent='Reconectando…';reconnectTimer=setTimeout(async()=>{try{await load();connectLive();}catch{}},3000);}};socket.onerror=()=>socket.close();}
async function enter(){account=await api('/me');if(account.must_change){$('#shell').hidden=true;$('#auth').hidden=false;$('#auth-form').hidden=true;$('#first-change-form').hidden=false;$('#auth-title').textContent='Troque a senha inicial';$('#auth-description').textContent='Seu acesso será liberado após definir uma senha pessoal.';return;}$('#auth').hidden=true;$('#shell').hidden=false;$('#username').textContent=account.full_name||account.name;$('#recovery-panel').hidden=account.role!=='root';go('overview');await load();connectLive();}
$('#auth-form').addEventListener('submit',async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;$('#auth-error').textContent='';try{const data=Object.fromEntries(new FormData(e.target));if(setupRequired){await api('/setup',{root_password:data.root_password,admin_password:data.admin_password});await api('/login',{username:'admin',password:data.admin_password});}else{await api('/login',{username:data.username,password:data.password,activation_code:data.activation_code||''});}e.target.reset();await enter();}catch(error){$('#auth-error').textContent=error.message;}finally{button.disabled=false;}});
$('#logout').addEventListener('click',()=>perform(async()=>{await api('/logout',{});await showAuth();}));
$('#refresh').addEventListener('click',()=>perform(load));
function go(next){view=next;$$('.view').forEach(el=>el.hidden=el.id!=='view-'+next);$$('.nav').forEach(el=>el.classList.toggle('active',el.dataset.view===next));$('#page-title').textContent=titles[next];if(next==='settings')populateSettings();if(next==='meter')perform(populateMeter);if(next==='history')perform(loadHistory);if(next==='users')perform(loadUsers);if(next==='directory')perform(loadDirectory);render();}
$$('[data-view]').forEach(el=>el.addEventListener('click',()=>go(el.dataset.view)));
$$('[data-go]').forEach(el=>el.addEventListener('click',()=>go(el.dataset.go)));
function stamp(ts){if(!ts)return '—';return new Date(ts*1000).toLocaleString('pt-BR',{timeZone:state?.settings.timezone||'America/Sao_Paulo',dateStyle:'short',timeStyle:'short'});}
function empty(title,text){return `<div class="empty-state"><strong>${esc(title)}</strong>${esc(text)}</div>`;}
function table(head,rows){return `<div class="table-wrap"><table><thead><tr>${head.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;}
function render(){if(!state)return;const s=state.settings,m=state.summary||{},ports=state.ports;$('#site-name').textContent=s.site_name;$('#nav-count').textContent=state.chargers.length;$('#clock').textContent=new Date(state.time*1000).toLocaleTimeString('pt-BR',{timeZone:s.timezone});$('#mode-badge').textContent=s.mode==='simulation'?'SIMULAÇÃO':'PILOTO FÍSICO';$('#mode-badge').classList.toggle('amber',true);$('#metric-total').textContent=fmt(m.total_kw);$('#metric-ev').textContent=fmt(m.ev_kw);$('#metric-other').textContent=fmt(m.other_kw);$('#metric-budget').textContent=fmt(m.budget_kw);$('#metric-limit').textContent=`Limite ${fmt(s.limit_kw)} kW · margem ${fmt(s.margin_kw)} kW`;$('#consumption-bar').style.width=Math.min(100,(m.total_kw||0)/s.limit_kw*100)+'%';const connected=ports.filter(p=>p.connected).length,charging=ports.filter(p=>p.connected&&p.power_kw>.1).length;$('#metric-active').textContent=`${charging} conectores em recarga`;$('#connected-count').textContent=connected;$('#charging-count').textContent=charging;$('#waiting-count').textContent=connected-charging;$('#available-count').textContent=ports.length-connected;$('#schedule-status').textContent=m.blocked?'Horário bloqueado · novas sessões em espera':'Horário permitido para recarga';$('#simulator').hidden=s.mode!=='simulation';$('#demo').hidden=state.chargers.length>0;$('#sync-description').textContent=state.cloud.status;$('#sync-pending').textContent=`${fmt(state.cloud.pending,0)} registros pendentes`;$('#schedule-zone').textContent=s.timezone;const alert=state.fault||(!m.meter_fresh?'Sem medição atual: novas liberações bloqueadas.':s.mode==='physical'?'Piloto físico: OCPP 1.6J e limites em kW. Exige homologação de zero/retomada e proteções elétricas independentes.':'');$('#live-alert').hidden=!alert;$('#live-alert').textContent=alert;$('#overview-cards').innerHTML=cards(ports.slice(0,6));if(view==='chargers')$('#charger-list').innerHTML=cards(ports);if(view==='vehicles')renderVehicles();if(view==='schedule')renderSchedule();if(view==='meter')renderMeterDiagnostics();$$('[data-progress]').forEach(el=>el.style.width=el.dataset.progress+'%');drawChart();applyPermissions();}
function cards(ports){if(!ports.length)return empty('Sua instalação começa aqui','Carregue a demonstração ou cadastre o primeiro carregador.');return ports.map(p=>{const c=state.chargers.find(c=>c.id===p.charger),v=state.vehicles.find(v=>v.id===p.vehicle_id);const active=p.power_kw>.1,emergency=p.emergency_until>state.time;let actions=p.connected?`<button class="secondary" data-port="${esc(p.key)}" data-action="${p.manual_pause?'resume':'pause'}">${p.manual_pause?'Retomar':'Pausar'}</button><button class="secondary" data-port="${esc(p.key)}" data-action="${emergency?'cancel_emergency':'emergency'}">${emergency?'Encerrar exceção':'Emergência'}</button><button class="secondary" data-port="${esc(p.key)}" data-action="assign_vehicle">Veículo</button>`:'';if(c.transport==='simulator')actions+=`<button class="${p.connected?'secondary':'primary'}" data-port="${esc(p.key)}" data-action="${p.connected?'disconnect':'connect'}">${p.connected?'Desconectar':'Conectar veículo'}</button>`;if(p.running)actions+=`<button class="secondary" data-port="${esc(p.key)}" data-action="test_limit">Testar limite</button>`;actions+=`<button class="text-button" data-edit-charger="${esc(c.id)}">Configurar</button>`;const progress=Math.min(100,p.power_kw/c.connector_max_kw*100);return `<article class="charger-card"><div class="charger-head"><div class="charger-title"><div class="charger-icon">ϟ</div><div class="charger-identity"><h3>${esc(c.name)}</h3><small>${esc(c.id)} · conector ${p.connector} · ${fmt(c.max_kw)} kW total</small></div></div><span class="badge ${active?'':p.connected?'amber':'gray'}">${active?'EM CARGA':p.connected?'OCUPADO':'DISPONÍVEL'}</span></div><div class="charger-vehicle">◇ ${esc(v?.name||(p.connected?'Veículo não identificado':'Nenhum veículo conectado'))}${v?.priority?'<span class="priority-label">★ PRIORITÁRIO</span>':''}</div><div class="charger-power"><strong>${fmt(p.power_kw)} <small>kW</small></strong><small>Limite enviado ${fmt(p.limit_kw)} kW</small></div><div class="charger-progress"><i data-progress="${progress}"></i></div><div class="charger-state">${esc(p.status)}${emergency?' · Exceção: '+Math.ceil((p.emergency_until-state.time)/60)+' min':''}${p.test?' · Teste em andamento':''}</div><div class="card-actions">${actions}</div></article>`;}).join('');}
function drawChart(){const data=state.trace||[];if(data.length<2){$('#power-chart').innerHTML=empty('Aguardando leituras','O gráfico será atualizado automaticamente.');return;}const w=Math.max(240,$('#power-chart').clientWidth),h=$('#power-chart').clientHeight,left=48,top=12,bottom=27,limit=state.settings.limit_kw,max=Math.max(limit,...data.map(x=>x.total))*1.12;const x=i=>left+(w-left-8)*i/Math.max(1,data.length-1),y=v=>h-bottom-(h-top-bottom)*v/max;const points=field=>data.map((d,i)=>`${x(i).toFixed(1)},${y(d[field]).toFixed(1)}`).join(' ');let grid='';for(let i=0;i<=3;i++){const v=max*i/3;grid+=`<line x1="${left}" x2="${w}" y1="${y(v)}" y2="${y(v)}" stroke="#edf2f3"/><text x="${left-10}" y="${y(v)+3}" text-anchor="end">${fmt(v,0)}</text>`;}const line=points('total');$('#power-chart').innerHTML=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Gráfico de potência total e recarga em quilowatts"><defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#0879cf" stop-opacity=".15"/><stop offset="100%" stop-color="#0879cf" stop-opacity="0"/></linearGradient></defs>${grid}<polygon points="${left},${h-bottom} ${line} ${w-8},${h-bottom}" fill="url(#area)"/><line x1="${left}" x2="${w}" y1="${y(limit)}" y2="${y(limit)}" stroke="#c58e3d" stroke-dasharray="5 5"/><polyline points="${points('ev')}" fill="none" stroke="#69b7ee" stroke-width="2"/><polyline points="${line}" fill="none" stroke="#0879cf" stroke-width="2.5" stroke-linejoin="round"/><text x="${left}" y="${h-4}">${esc(new Date(data[0].ts*1000).toLocaleTimeString('pt-BR',{timeZone:state.settings.timezone}))}</text><text x="${w}" y="${h-4}" text-anchor="end">agora</text></svg>`;}
function renderVehicles(){const rows=state.vehicles.map(v=>`<tr><td><b>${esc(v.name)}</b></td><td>${esc(v.plate||'—')}</td><td>${v.priority?'<span class="badge amber">★ Prioritário</span>':'Normal'}</td><td>${v.identifiers.map(esc).join(', ')||'Associação manual'}</td><td><button class="secondary" data-edit-vehicle="${esc(v.id)}">Editar</button></td></tr>`);$('#vehicle-list').innerHTML=rows.length?table(['Veículo','Placa','Prioridade','Identificadores',''],rows):empty('Nenhum veículo cadastrado','Cadastre um veículo ou associe um identificador observado.');const identifiers=state.identifiers.map(i=>{const v=state.vehicles.find(v=>v.identifiers.includes(i.id));return `<tr><td>${esc(i.id)}</td><td>${esc(v?.name||'Não associado')}</td><td>${esc(i.source)}</td><td>${stamp(i.last_seen)}</td><td><button class="secondary" data-name-identifier="${esc(i.id)}">${v?'Editar nome':'Associar / nomear'}</button></td></tr>`;});$('#identifier-list').innerHTML=identifiers.length?table(['Identificador','Veículo','Origem','Última conexão',''],identifiers):empty('Aguardando identificadores','Identificadores técnicos EVSYS não são tratados como veículos.');}
function renderSchedule(){$('#schedule-list').innerHTML=state.settings.schedules.map((s,i)=>`<div class="schedule-item"><div><b>${s.start} — ${s.end}</b><small>${s.days.map(d=>days[d]).join(' · ')}</small></div><button class="secondary" data-remove-schedule="${i}">Remover</button></div>`).join('')||empty('Sem bloqueios de horário','Adicione os períodos em que a recarga deverá aguardar.');}
function field(label,name,value='',type='text',extra=''){return `<label>${label}<input name="${name}" type="${type}" value="${esc(value)}" ${extra}></label>`;}
function select(label,name,options,value){return `<label>${label}<select name="${name}">${options.map(([v,t])=>`<option value="${esc(v)}" ${v===value?'selected':''}>${esc(t)}</option>`).join('')}</select></label>`;}
function check(label,name,value){return `<label class="checkbox-label"><input name="${name}" type="checkbox" ${value?'checked':''}>${label}</label>`;}
function openEditor(title,html,save){$('#editor-title').textContent=title;$('#editor-form').innerHTML=html+'<div class="dialog-actions"><button class="primary" type="submit">Confirmar</button></div>';editorSave=save;$('#editor').showModal();}
$('#close-editor').addEventListener('click',()=>$('#editor').close());
$('#editor-form').addEventListener('submit',e=>{e.preventDefault();perform(async()=>{const button=e.submitter;button.disabled=true;try{const result=await editorSave(new FormData(e.target));$('#editor').close();if(account)await load();if(result?.activation_code)showActivation(result.activation_code);else notify('Alteração aplicada no controlador.');}finally{button.disabled=false;}});});
function editCharger(id){const c=state.chargers.find(c=>c.id===id)||{id:'',name:'',model:'',ip:'',max_kw:320,connector_max_kw:320,min_kw:6,connectors:1,transport:'simulator',circuit:state.settings.circuits[0].id,enabled:true,commissioned:false,zero_supported:false,rate_unit:'W',voltage:230,phases:3,input_factor:1};openEditor(id?'Configurar carregador':'Novo carregador',`<div class="form-grid">${field('Identificador OCPP','id',c.id,'text',`required maxlength="40" ${id?'readonly':''}`)}${field('Nome','name',c.name,'text','required maxlength="100"')}</div><div class="form-grid">${select('Conexão','transport',[['simulator','Simulador'],['ocpp','OCPP 1.6J']],c.transport)}${field('IP para referência','ip',c.ip)}</div>${field('Fabricante / modelo','model',c.model)}${field('Reserva de entrada / saída · fator de perdas','input_factor',c.input_factor||1,'number','required min="1" max="2" step="0.01"')}<div class="form-grid">${field('Máximo total · kW','max_kw',c.max_kw,'number','required min="0.1" step="any"')}${field('Máximo por conector · kW','connector_max_kw',c.connector_max_kw,'number','required min="0.1" step="any"')}</div><div class="form-grid">${field('Mínimo validado · kW','min_kw',c.min_kw,'number','required min="0" step="any"')}${field('Conectores compartilhando o total','connectors',c.connectors,'number',`required min="1" max="8" ${id?'readonly':''}`)}</div>${select('Quadro / circuito','circuit',state.settings.circuits.map(c=>[c.id,c.name]),c.circuit)}<div class="form-grid">${select('Unidade aceita no perfil OCPP','rate_unit',[['W','Watts'],['A','Ampères · AC']],c.rate_unit)}${field('Tensão fase-neutro · V','voltage',c.voltage,'number','min="1" step="any"')}</div>${field('Número de fases · AC','phases',c.phases,'number','min="1" max="3"')}${field(id?'Nova senha OCPP · deixe vazio para manter':'Senha OCPP · obrigatória para equipamento físico','password','','password','minlength="8" autocomplete="new-password"')}${check('Equipamento habilitado','enabled',c.enabled)}${check('Limite zero e retomada testados no equipamento','zero_supported',c.zero_supported)}${check('Comissionamento concluído para piloto físico','commissioned',c.commissioned)}<p class="hint">Conexão: wss://ENDEREÇO-DO-CONTROLADOR/ocpp/IDENTIFICADOR. O carregador abre a conexão; IP não identifica o veículo. O modo físico exige configuração de TLS, medidor e homologação. Potência DC de saída pode diferir da entrada AC.</p>`,async f=>{const d=Object.fromEntries(f);for(const n of ['max_kw','connector_max_kw','min_kw','connectors','voltage','phases','input_factor'])d[n]=Number(d[n]);for(const n of ['enabled','zero_supported','commissioned'])d[n]=f.has(n);if(!d.password)delete d.password;await api('/chargers',d);});}
$('#add-charger').addEventListener('click',()=>editCharger());
function editVehicle(id,identifier){const v=state.vehicles.find(v=>v.id===id)||{name:'',plate:'',priority:false,identifiers:identifier?[identifier]:[]};openEditor(id?'Editar veículo':'Cadastrar veículo',`${field('Nome do veículo','name',v.name,'text','required maxlength="100"')}${field('Placa · opcional','plate',v.plate)}${field('Identificadores · separados por vírgula','identifiers',v.identifiers.join(', '))}${check('★ Veículo prioritário','priority',v.priority)}<p class="hint">A prioridade acompanha o veículo reconhecido e não libera o horário bloqueado. Confirme se o identificador recebido é estável e realmente distingue veículos.</p>`,async f=>{const d={name:f.get('name'),plate:f.get('plate'),identifiers:f.get('identifiers').split(',').map(x=>x.trim()).filter(Boolean),priority:f.has('priority')};if(id)d.id=id;await api('/vehicles',d);});}
$('#add-vehicle').addEventListener('click',()=>editVehicle());
function vehicleOptions(){return [['','Não identificado / associação manual'],...state.vehicles.map(v=>[v.id,v.name+(v.priority?' ★':'')])];}
function portAction(key,action){const p=state.ports.find(p=>p.key===key);if(action==='connect'||action==='assign_vehicle'){openEditor(action==='connect'?'Conectar veículo simulado':'Associar veículo à sessão',select('Veículo','vehicle_id',vehicleOptions(),p.vehicle_id||'')+(action==='connect'?field('Potência aceita pelo veículo · kW','acceptance_kw',state.chargers.find(c=>c.id===p.charger).connector_max_kw,'number','min="0.1" step="any" required'):'')+'<p class="hint">Uma associação manual será registrada na auditoria.</p>',async f=>{const d={action,vehicle_id:f.get('vehicle_id')||null};if(action==='connect')d.acceptance_kw=Number(f.get('acceptance_kw'));await api('/ports/'+encodeURIComponent(key)+'/action',d);});}else if(action==='test_limit'){openEditor('Aprendizado assistido · testar limite',field('Limite temporário · kW','cap_kw',p.limit_kw/2,'number','min="0" step="any" required')+field('Duração · segundos','seconds',30,'number','min="10" max="300" required')+'<p class="hint">O teste pode suspender a recarga. Só reduz o orçamento atual e respeita a demanda. O resultado é observacional: uma sessão não comprova o mínimo do equipamento. Ao terminar, a retomada respeita a fila e a rampa.</p>',async f=>api('/ports/'+encodeURIComponent(key)+'/learn',{cap_kw:Number(f.get('cap_kw')),seconds:Number(f.get('seconds'))}));}else if(action==='emergency'){openEditor('Liberar recarga de emergência',field('Duração · minutos','minutes',30,'number','min="1" max="1440" required')+field('Motivo','reason','','text','required maxlength="200"')+'<p class="hint">Libera o bloqueio de horário. Não ultrapassa demanda ou circuitos. Termina ao desconectar o veículo.</p>',async f=>api('/ports/'+encodeURIComponent(key)+'/action',{action,minutes:Number(f.get('minutes')),reason:f.get('reason')}));}else{perform(async()=>{await api('/ports/'+encodeURIComponent(key)+'/action',{action});await load();});}}
document.addEventListener('click',e=>{const button=e.target.closest('button');if(!button)return;if(button.dataset.port)portAction(button.dataset.port,button.dataset.action);if(button.dataset.editCharger)editCharger(button.dataset.editCharger);if(button.dataset.editVehicle)editVehicle(button.dataset.editVehicle);if(button.dataset.nameIdentifier){const id=button.dataset.nameIdentifier;const v=state.vehicles.find(v=>v.identifiers.includes(id));editVehicle(v?.id,id);}if(button.dataset.removeSchedule!==undefined)perform(async()=>{const s=structuredClone(state.settings);s.schedules.splice(Number(button.dataset.removeSchedule),1);await api('/settings',s,'PUT');await load();});if(button.dataset.removeCircuit!==undefined)button.closest('.circuit-row').remove();});
$('#load-form').addEventListener('submit',e=>{e.preventDefault();perform(async()=>{await api('/simulation',{other_kw:Number($('#other-load').value)});notify('Carga do cliente atualizada no simulador.');});});
$('#demo').addEventListener('click',()=>perform(async()=>{await api('/demo',{});await load();notify('Demonstração iniciada: 1.000 kW e dois carregadores de 320 kW.');}));
$('#schedule-form').addEventListener('submit',e=>{e.preventDefault();perform(async()=>{const f=new FormData(e.target),s=structuredClone(state.settings);s.schedules.push({days:f.getAll('days').map(Number),start:f.get('start'),end:f.get('end'),enabled:true});await api('/settings',s,'PUT');await load();notify('Bloqueio de horário adicionado.');});});
function circuitRow(c={id:'circuito-'+Date.now().toString(36),name:'Novo circuito',limit_kw:100}){return `<div class="circuit-row">${field('Identificador','circuit_id',c.id,'text','required maxlength="40"')}${field('Nome','circuit_name',c.name,'text','required')}${field('Limite · kW','circuit_limit',c.limit_kw,'number','min="0.1" step="any" required')}<button type="button" class="icon-button" data-remove-circuit="1" aria-label="Remover circuito">×</button></div>`;}
$('#add-circuit').addEventListener('click',()=>$('#circuit-fields').insertAdjacentHTML('beforeend',circuitRow()));
function populateSettings(){if(!state)return;const form=$('#settings-form');for(const [k,v] of Object.entries(state.settings)){const input=form.elements.namedItem(k);if(input&&!['circuits','schedules','meter'].includes(k))input.value=v;}for(const[k,v]of Object.entries(state.settings.meter)){const input=form.elements.namedItem('meter_'+k);if(input)input.value=v;}$('#circuit-fields').innerHTML=state.settings.circuits.map(circuitRow).join('');}
$('#settings-form').addEventListener('submit',e=>{e.preventDefault();perform(async()=>{const f=new FormData(e.target),d=structuredClone(state.settings);for(const k of ['site_name','mode','timezone','blocked_policy','cloud_url'])if(f.has(k))d[k]=f.get(k);for(const k of ['limit_kw','technical_limit_kw','margin_kw','freshness_s','ramp_kw_s','retain_days'])if(f.has(k))d[k]=Number(f.get(k));d.circuits=$$('#circuit-fields .circuit-row').map(row=>({id:row.querySelector('[name=circuit_id]').value,name:row.querySelector('[name=circuit_name]').value,limit_kw:Number(row.querySelector('[name=circuit_limit]').value)}));await api('/settings',d,'PUT');await load();populateSettings();notify('Configurações salvas e auditadas.');});});
$('#recovery-form').addEventListener('submit',e=>{e.preventDefault();perform(async()=>{await api('/recover-admin',{username:'admin',password:new FormData(e.target).get('password')});e.target.reset();notify('Senha do administrador redefinida; sessões anteriores encerradas.');});});
const eventNames={connected:'Veículo conectado',disconnected:'Veículo desconectado',session_start:'Recarga iniciada',session_end:'Recarga encerrada',limit_changed:'Limite alterado',operator_action:'Ação do operador',settings_changed:'Configuração alterada',charger_configured:'Carregador configurado',vehicle_configured:'Veículo configurado',test_started:'Teste de limite iniciado',test_finished:'Teste de limite concluído',command_failed:'Comando rejeitado / sem resposta',ocpp_connected:'Conexão OCPP',ocpp_disconnected:'Conexão OCPP encerrada',ocpp_status:'Estado OCPP',controller_fault:'Falha no controle'};
async function loadHistory(){const h=await api('/history');const sessions=h.sessions.sort((a,b)=>b.started_at-a.started_at).map(s=>`<tr><td>${stamp(s.started_at)}</td><td>${esc(s.port)}</td><td>${esc(state.vehicles.find(v=>v.id===s.vehicle_id)?.name||'Não identificado')}</td><td>${fmt(s.energy_kwh,3)} kWh</td><td>${fmt(s.peak_kw)} kW</td><td>${s.ended_at?esc(s.reason||'Encerrada'):'Em andamento'}</td><td>${s.mode==='simulator'?'Simulação':'OCPP'}</td></tr>`);$('#session-list').innerHTML=sessions.length?table(['Início','Conector','Veículo','Energia','Pico','Estado','Origem'],sessions):empty('Nenhuma sessão ainda','As recargas aparecerão aqui quando iniciarem.');const events=h.events.map(e=>`<tr><td>${stamp(e.ts)}</td><td>${esc(eventNames[e.kind]||e.kind)}</td><td>${esc(JSON.stringify(e.payload))}</td></tr>`);$('#event-list').innerHTML=events.length?table(['Horário','Evento','Detalhes'],events):empty('Sem eventos','Aguardando atividade.');}
$('#refresh-history').addEventListener('click',()=>perform(loadHistory));
(async()=>{try{await enter();}catch{await showAuth();}})();

let meterDefinitions = [], meterTestResult = null;
async function populateMeter() {
  meterTestResult = null;
  const metadata = await api('/meter/measurements');
  meterDefinitions = metadata.measurements;
  const meter = state.settings.meter, form = $('#meter-form');
  for (const [key, value] of Object.entries(meter)) {
    const input = form.elements.namedItem(key);
    if (input && key !== 'registers') input.value = value;
  }
  $('#register-fields').innerHTML = meter.registers.map(registerRow).join('');
  updateMeterTransport();
  renderMeterDiagnostics();
}
function registerRow(r) {
  const definition = meterDefinitions.find(m => m.key === r.measurement);
  const options = (values, current) => values.map(([v,label]) => `<option value="${esc(v)}" ${String(v)===String(current)?'selected':''}>${esc(label)}</option>`).join('');
  return `<tr data-measurement="${esc(r.measurement)}" class="${r.enabled?'':'disabled'}">
    <td><input type="checkbox" data-field="enabled" aria-label="Habilitar ${esc(definition.label)}" ${r.enabled?'checked':''}></td>
    <td class="measurement-name"><b>${esc(definition.label)}</b><small>Unidade final: ${esc(definition.unit||'adimensional')}</small></td>
    <td><input data-field="address" type="number" min="0" max="65536" value="${r.address}" required aria-label="Offset de ${esc(definition.label)}"></td>
    <td><select data-field="function" aria-label="Função de ${esc(definition.label)}">${options([['3','03 · Holding'],['4','04 · Input']],r.function)}</select></td>
    <td><select data-field="type" aria-label="Tipo de ${esc(definition.label)}">${options(['float32','float64','int16','uint16','int32','uint32','int64','uint64'].map(t=>[t,t]),r.type)}</select></td>
    <td><input data-field="scale" type="number" step="any" value="${r.scale}" required aria-label="Escala de ${esc(definition.label)}"></td>
    <td><select data-field="word_order" aria-label="Palavras de ${esc(definition.label)}">${options([['big','Normal'],['little','Invertidas']],r.word_order)}</select></td>
    <td><select data-field="byte_order" aria-label="Bytes de ${esc(definition.label)}">${options([['big','Normais'],['little','Invertidos']],r.byte_order)}</select></td></tr>`;
}
function updateMeterTransport() {
  const rtu = $('#meter-form [name=transport]').value === 'rtu';
  $('#meter-tcp-fields').hidden = rtu;
  $('#meter-rtu-fields').hidden = !rtu;
  $('#meter-form [name=unit]').min = rtu ? '1' : '0';
  $('#meter-form [name=unit]').max = rtu ? '247' : '255';
  if (rtu) perform(async () => {
    const data = await api('/meter/ports');
    $('#serial-ports').innerHTML = data.ports.map(p=>`<option value="${esc(p.device)}">${esc(p.description)}</option>`).join('');
  });
}
function meterDraft() {
  const f = new FormData($('#meter-form')), meter = structuredClone(state.settings.meter);
  for (const key of ['transport','host','serial_port','parity']) meter[key] = f.get(key);
  for (const key of ['port','unit','address_base','poll_s','timeout_s','baudrate','stopbits']) meter[key] = Number(f.get(key));
  meter.bytesize = 8;
  meter.registers = $$('#register-fields tr').map(row => {
    const reg = {measurement: row.dataset.measurement};
    for (const input of row.querySelectorAll('[data-field]')) {
      const key = input.dataset.field;
      reg[key] = key === 'enabled' ? input.checked : ['address','function','scale'].includes(key) ? Number(input.value) : input.value;
    }
    return reg;
  });
  return meter;
}
function renderMeterDiagnostics() {
  const readings = meterTestResult?.readings || state.meter.readings || [];
  const error = meterTestResult?.error || (!meterTestResult ? state.meter.error : '');
  $('#meter-health').textContent = state.summary.meter_fresh ? state.settings.mode==='simulation'?'Simulação':'Leitura atual' : 'Sem leitura atual';
  $('#meter-diagnostic-label').textContent = meterTestResult ? 'Resultado do teste do formulário · não salvo automaticamente' : 'Leituras recebidas em operação';
  $('#meter-test-message').textContent = error || (meterTestResult ? meterTestResult.ok?'Teste concluído. Confira unidades e valores antes de salvar.':'Teste parcial: confira as leituras com erro.' : 'O teste é somente leitura e não salva o formulário.');
  $('#meter-test-message').classList.toggle('meter-read-error',!!error);
  $('#meter-readings').innerHTML = readings.length ? table(['Grandeza','Leitura','Horário'],readings.map(r=>`<tr><td>${esc(r.label)}<small class="meter-reading-time"> · ${r.function.toString().padStart(2,'0')}/${r.address}</small></td><td>${r.error?`<span class="meter-read-error">${esc(r.error)}</span>`:`<b class="meter-reading-number">${fmt(r.value,3)}</b> ${esc(r.unit)}`}</td><td>${stamp(r.at)}</td></tr>`)) : empty('Aguardando teste ou medição','Insira os offsets do manual e teste a conexão.');
}
$('#meter-form [name=transport]').addEventListener('change', updateMeterTransport);
$('#meter-form').addEventListener('change', e => {
  if (e.target.dataset.field === 'enabled') e.target.closest('tr').classList.toggle('disabled', !e.target.checked);
  meterTestResult = null;
  $('#meter-test-message').textContent = 'Configuração alterada. Teste antes de aplicar.';
});
$('#meter-test').addEventListener('click', () => perform(async () => {
  const button = $('#meter-test');
  button.disabled = true; button.textContent = 'Lendo…';
  try { meterTestResult = await api('/meter/test', meterDraft()); renderMeterDiagnostics(); }
  finally { button.disabled = false; button.textContent = 'Testar leitura'; }
}));
$('#meter-form').addEventListener('submit', e => {
  e.preventDefault();
  perform(async () => {
    const settings = structuredClone(state.settings);
    settings.meter = meterDraft();
    await api('/settings', settings, 'PUT');
    await load();
    notify('Multimedidor e mapa de registradores salvos.');
  });
});

const roleLabels = {root:'Raiz',technician:'Técnico / instalador',admin:'Administrador',operator:'Operador'};
let managedUsers = [];
function applyPermissions() {
  if (!account) return;
  const technical = ['root','technician'].includes(account.role), manager = account.role !== 'operator';
  for (const [name, allowed] of [['meter',technical],['settings',manager],['users',manager],['directory',account.role==='root']]) {
    $(`[data-view=${name}]`).hidden = !allowed;
  }
  for (const el of $$('[data-edit-charger],#add-charger')) el.hidden = !technical;
  for (const el of $$('[data-edit-vehicle],#add-vehicle')) el.hidden = !manager;
  $('#demo').hidden = !manager || state.chargers.length>0;
  $('#simulator').hidden = !manager || state.settings.mode !== 'simulation';
  for (const el of $$('#schedule-form input,#schedule-form button')) el.disabled = !manager;
  for (const el of $$('[data-remove-schedule]')) el.hidden = !manager;
  for (const el of $$('[data-port]')) {
    const action = el.dataset.action;
    if (action==='test_limit') el.hidden = !technical;
    if (['connect','disconnect'].includes(action)) el.hidden = !manager;
    if (['emergency','cancel_emergency'].includes(action)) el.hidden = !manager && !account.can_emergency;
  }
  for (const el of $$('#settings-form input,#settings-form select,#settings-form button')) {
    el.disabled = !technical && !['site_name','limit_kw','blocked_policy'].includes(el.name) && el.type!=='submit';
  }
  $('#recovery-panel').hidden = account.role !== 'root';
}
function showActivation(code) {
  $('#activation-code').value = code;
  $('#activation-dialog').showModal();
}
$('#close-activation').addEventListener('click',()=>{$('#activation-code').value='';$('#activation-dialog').close();});
$('#first-change-form').addEventListener('submit',e=>{
  e.preventDefault();perform(async()=>{
    const f=new FormData(e.target);
    if(f.get('new_password')!==f.get('confirmation')) throw new Error('As novas senhas não coincidem');
    await api('/change-password',{current_password:f.get('current_password'),new_password:f.get('new_password')});
    e.target.reset();await showAuth();$('#auth-description').textContent='Senha alterada. Entre com sua nova senha.';
  });
});
$('#change-own-password').addEventListener('click',()=>openEditor('Alterar minha senha',
  field('Senha atual','current_password','','password','required autocomplete="current-password"')+
  field('Nova senha','new_password','','password','required minlength="8" autocomplete="new-password"'),async f=>{
    await api('/change-password',Object.fromEntries(f));await showAuth();
  }));
function untilInput(value) {
  if(!value) return '';
  const date=new Date(value*1000);return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);
}
async function loadUsers() {
  const data=await api('/users');managedUsers=data.users;
  $('#user-list').innerHTML=managedUsers.length?table(['Nome / login','Perfil','Situação','Validade','Origem',''],managedUsers.map(u=>
    `<tr><td><b>${esc(u.full_name)}</b><small class="meter-reading-time"> · ${esc(u.name)}</small></td><td>${esc(roleLabels[u.role])}</td><td><span class="badge ${u.active&&!u.deleted?'':'amber'}">${u.deleted?'Excluído':u.active?'Ativo':'Bloqueado'}</span>${u.must_change?'<small> · Primeiro acesso</small>':''}</td><td>${u.expires_at?stamp(u.expires_at):'Sem vencimento'}</td><td>${esc({local:'Local',local_pending:'Local · a sincronizar',directory:'Plataforma'}[u.source]||u.source)}</td><td>${u.role==='root'?'Recuperação':`<button class="secondary" data-edit-user="${esc(u.id)}">Editar</button> <button class="secondary" data-reset-user="${esc(u.id)}">Renovar ativação</button>`}</td></tr>`)):empty('Nenhuma conta gerenciável','Cadastre o primeiro usuário do seu perfil de gestão.');
}
function editUser(identifier) {
  const old=managedUsers.find(u=>u.id===identifier);
  const u=old||{name:'',full_name:'',role:'operator',active:true,deleted:false,expires_at:null,can_emergency:false};
  const roles=old?.role==='technician'?['technician']:account.role==='root'?['operator','admin','technician']:account.role==='technician'?['operator','admin']:['operator'];
  openEditor(old?'Editar conta':'Adicionar usuário',
    field('Nome completo','full_name',u.full_name,'text','required maxlength="100"')+
    field('Login permanente','name',u.name,'text',`required minlength="3" maxlength="40" ${old?'readonly':''}`)+
    select('Perfil','role',roles.map(r=>[r,roleLabels[r]]),u.role)+
    field('Validade · deixe vazio para não expirar','expires_at',untilInput(u.expires_at),'datetime-local')+
    check('Operador autorizado a liberar emergência','can_emergency',u.can_emergency)+
    (old?check('Conta ativa','active',u.active)+check('Excluir acesso e preservar auditoria','deleted',u.deleted):'')+
    '<p class="hint">Contas de técnico são globais e entram na fila de sincronização. Bloquear ou excluir encerra as sessões locais. A senha inicial é 12345678, com ativação individual e troca obrigatória.</p>',async f=>{
      const data={full_name:f.get('full_name'),role:f.get('role'),can_emergency:f.has('can_emergency'),expires_at:f.get('expires_at')?new Date(f.get('expires_at')).toISOString():null};
      let result;
      if(old) result=await api('/users/'+old.id,{...data,active:f.has('active'),deleted:f.has('deleted')},'PUT');
      else result=await api('/users',{...data,name:f.get('name')});
      await loadUsers();return result;
    });
}
$('#add-user').addEventListener('click',()=>editUser());
$('#refresh-users').addEventListener('click',()=>perform(loadUsers));
document.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.editUser)editUser(b.dataset.editUser);
  if(b.dataset.resetUser)perform(async()=>{const data=await api('/users/'+b.dataset.resetUser+'/reset',{});showActivation(data.activation_code);await loadUsers();});
});
async function loadDirectory() {
  const data=await api('/directory'),form=$('#directory-form');
  form.elements.url.value=data.config.url;form.elements.interval_minutes.value=data.config.interval_s/60;form.elements.enabled.checked=data.config.enabled;
  $('#directory-status').innerHTML=table(['Informação','Valor'],[
    `<tr><td>Identificador do D-Max</td><td>${esc(data.controller_id)}</td></tr>`,
    `<tr><td>Resultado</td><td>${esc(data.status.message)}</td></tr>`,
    `<tr><td>Última consulta</td><td>${stamp(data.status.last_attempt)}</td></tr>`,
    `<tr><td>Último sucesso</td><td>${stamp(data.status.last_success)}</td></tr>`,
    `<tr><td>Próxima consulta prevista</td><td>${stamp(data.status.next_attempt)}</td></tr>`,
    `<tr><td>Alterações locais pendentes</td><td>${data.pending}</td></tr>`,
    `<tr><td>Chave do equipamento</td><td>${data.token_present?'Configurada':'Pendente no ambiente'}</td></tr>`]);
}
$('#directory-form').addEventListener('submit',e=>{
  e.preventDefault();perform(async()=>{const f=new FormData(e.target);const data={url:f.get('url'),interval_s:Math.round(Number(f.get('interval_minutes'))*60),enabled:f.has('enabled')};if(f.get('device_token'))data.device_token=f.get('device_token');await api('/directory',data,'PUT');$('#directory-form [name=device_token]').value='';await loadDirectory();notify('Período de consulta salvo.');});
});
$('#sync-directory').addEventListener('click',()=>perform(async()=>{const b=$('#sync-directory');b.disabled=true;try{const result=await api('/directory/sync',{});await loadDirectory();notify(result.status.message,!result.ok);}finally{b.disabled=false;}}));
