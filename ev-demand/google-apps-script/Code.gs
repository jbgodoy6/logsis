/** D-Max global directory. Bound to Google Sheets; no external server required. */
const DMAX_SHEET_ID = '17HCp2CX3eUZXqQsTkTNDZvrLkGqzZQrJkCfeHo-toPQ';
const DMAX_TAB = 'Tecnicos';
const DMAX_SCRIPT_REVISION='alphabetical-directory-1';
const DMAX_HEADERS = ['id', 'nome', 'login', 'situacao', 'valido_ate'];
const DMAX_DEFAULT_HASH = 'pbkdf2_sha256$600000$0cc644386557630153579d018267d636$07eb3cfc2778a1ee08fa321b86c897f72237f6749cecda0eee2ea788cb678c53';

function onOpen() {
  SpreadsheetApp.getUi().createMenu('D-Max')
    .addItem('Ordenar usuários e clientes de A a Z', 'ordenarCadastros')
    .addItem('Organizar equipamentos (situação na coluna E)', 'organizarEquipamentos')
    .addItem('Definir senha da linha selecionada', 'definirSenhaDaLinha')
    .addItem('Verificar cadastro (sem alterar dados)', 'diagnosticarUsuarios')
    .addItem('Preparar/migrar usuários (aba única)', 'migrarUsuarios')
    .addItem('Unificar assinaturas e acesso remoto', 'unificarEquipamentos')
    .addItem('Preparar diretório de acesso remoto', 'prepararRemoto')
    .addItem('Autorizar um D-Max', 'autorizarDMax')
    .addItem('Revogar chave de um D-Max', 'revogarDMax').addToUi();
}

// Move complete rows, including extra columns, formulas and cell formatting.
// Call only after row-index based writes and read-back confirmations are finished.
function ordenarLinhas_(sheet){
  const count=sheet.getLastRow()-1;
  if(count<2)return;
  sheet.getRange(2,1,count,sheet.getLastColumn()).sort([{column:2,ascending:true},{column:1,ascending:true}]);
}
function ordenarCadastros(){
  const book=passwordEditorBook_(),lock=LockService.getScriptLock();
  if(!lock.tryLock(5000))throw new Error('Cadastro ocupado. Tente novamente.');
  try{for(const name of [DMAX_USERS_TAB,DMAX_REMOTE_TAB]){const sheet=book.getSheetByName(name);if(sheet)ordenarLinhas_(sheet);}}
  finally{lock.releaseLock();}
}
function onEdit(event){
  if(!event||!event.range||!event.source||event.source.getId()!==DMAX_SHEET_ID)return;
  const sheet=event.range.getSheet();
  if(![DMAX_USERS_TAB,DMAX_REMOTE_TAB].includes(sheet.getName())||event.range.getRow()<2)return;
  const lock=LockService.getScriptLock();
  if(!lock.tryLock(5000))return; // The menu can retry if another write is in progress.
  try{ordenarLinhas_(sheet);}finally{lock.releaseLock();}
}

function prepararTecnicos() {return migrarUsuarios();}

function autorizarDMax() {
  const ui = SpreadsheetApp.getUi();
  const answer = ui.prompt('Autorizar equipamento D-Max', 'Cole o identificador mostrado em Configurações do D-Max ou na configuração inicial da central Windows.', ui.ButtonSet.OK_CANCEL);
  if (answer.getSelectedButton() !== ui.Button.OK) return;
  const id = answer.getResponseText().trim();
  if (!/^[A-Za-z0-9_-]{1,100}$/.test(id)) throw new Error('Identificador inválido.');
  const properties = PropertiesService.getScriptProperties();
  if (properties.getProperty('device.'+id) && ui.alert('Já autorizado', 'Substituir a chave? Será necessário atualizar a chave no equipamento.', ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  const key = [Utilities.getUuid(),Utilities.getUuid(),Utilities.getUuid()].join('').replace(/-/g,'');
  properties.setProperty('device.'+id, sha_(key));
  const html = HtmlService.createHtmlOutput('<div style="font:14px Arial;padding:20px"><h2>Chave do D-Max</h2><p>Copie agora e cole no campo Chave das Configurações do D-Max ou da central Windows. Ela não será gravada nas células.</p><textarea readonly style="width:100%;height:90px">'+key+'</textarea><p>Depois configure a URL publicada deste Apps Script. Guarde a chave em local seguro.</p></div>').setWidth(480).setHeight(300);
  ui.showModalDialog(html,'Autorização do equipamento');
}

function revogarDMax() {
  const ui=SpreadsheetApp.getUi();
  const answer=ui.prompt('Revogar chave de equipamento','Informe o identificador do D-Max. Isso revoga a sincronização; não apaga o cadastro offline já existente.',ui.ButtonSet.OK_CANCEL);
  if(answer.getSelectedButton()!==ui.Button.OK)return;
  PropertiesService.getScriptProperties().deleteProperty('device.'+answer.getResponseText().trim());
  ui.alert('Chave revogada. Para bloquear um técnico, altere a situação na aba Usuarios.');
}

function sha_(value) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,String(value),Utilities.Charset.UTF_8)
    .map(b=>('0'+((b+256)%256).toString(16)).slice(-2)).join('');
}
function equal_(a,b) {
  if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length)return false;
  let mismatch=0;for(let i=0;i<a.length;i++)mismatch|=a.charCodeAt(i)^b.charCodeAt(i);return mismatch===0;
}
function validHash_(hash) {return typeof hash==='string'&&/^pbkdf2_sha256\$600000\$[0-9a-f]{32}\$[0-9a-f]{64}$/.test(hash);}
function error_(code,message,diagnostic) {const e=new Error(message);e.code=code;if(diagnostic)e.diagnostic=diagnostic;throw e;}
function json_(value) {return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON);}
// Formatting is not part of the protocol. Column names and order still are.
function headersMatch_(actual,expected){
  return Array.isArray(actual)&&actual.length===expected.length&&actual.every((v,i)=>String(v).trim().toLowerCase()===expected[i]);
}

function doGet() {return json_({ok:true,service:'D-Max Acesso Desktop',version:'1.0',desktop_protocol:1,desktop_actions:['desktop_login','desktop_state','desktop_logout','desktop_clients','desktop_members','desktop_save_user','desktop_devices','desktop_save_device','desktop_open_client','desktop_change_password'],diagnostics_version:2,script_revision:DMAX_SCRIPT_REVISION,message:'Abra o aplicativo instalado no Windows. Nenhum cadastro é público.'});}
/** Spreadsheet editors already control account cells; no desktop session required. */
function passwordEditorBook_(){
  SpreadsheetApp.getUi(); // Fails outside the bound spreadsheet editor.
  const book=SpreadsheetApp.getActiveSpreadsheet();
  if(!book||book.getId()!==DMAX_SHEET_ID)error_(403,'Abra a planilha configurada');
  return book;
}
function definirSenhaDaLinha(){
  const book=passwordEditorBook_(),sheet=book.getActiveSheet(),range=sheet.getActiveRange();
  if(sheet.getName()!==DMAX_USERS_TAB||!range||range.getRow()<2||range.getNumRows()!==1){SpreadsheetApp.getUi().alert('Selecione uma única linha de usuário na aba Usuarios.');return;}
  const row=range.getRow(),props=PropertiesService.getScriptProperties();
  const actor=portalRoster_(props).find(r=>r.row===row);
  if(!actor){SpreadsheetApp.getUi().alert('A linha selecionada não contém um usuário.');return;}
  const target={row:row,id:actor.id,name:actor.name,fingerprint:sha_(JSON.stringify(sheet.getRange(row,1,1,7).getValues()[0]))};
  SpreadsheetApp.getUi().showModalDialog(HtmlService.createHtmlOutput(passwordEditorHtml_(target)).setWidth(480).setHeight(460),'Definir senha de '+actor.name);
}
function passwordEditorHtml_(target){
  // Identity fields were validated by portalRoster_; escape '<' as defense in depth.
  const payload=JSON.stringify(target).replace(/</g,'\\u003c');
  return `<!doctype html><html lang="pt-BR"><meta charset="utf-8"><style>body{font:15px Arial;padding:18px;color:#16304c}label{display:block;margin-top:14px}input,button{box-sizing:border-box;width:100%;padding:10px;margin-top:6px}button{background:#123d67;color:white;border:0;cursor:pointer}#status{white-space:pre-wrap}</style>
<p>Informe a senha da conta. O verificador será gravado automaticamente na coluna G da linha selecionada.</p>
<form id="form"><label for="password">Nova senha (8 a 200 caracteres)</label><input id="password" type="password" minlength="8" maxlength="200" required autocomplete="new-password"><label for="confirmation">Confirme a senha</label><input id="confirmation" type="password" minlength="8" maxlength="200" required autocomplete="new-password"><button id="save">Salvar senha na planilha</button></form><p id="status" role="status" aria-live="polite"></p>
<script>
const target=${payload};
const form=document.getElementById('form'),password=document.getElementById('password'),confirmation=document.getElementById('confirmation'),button=document.getElementById('save'),status=document.getElementById('status');
const hex=b=>Array.from(new Uint8Array(b),v=>v.toString(16).padStart(2,'0')).join('');
function finish(message){button.disabled=false;password.disabled=false;confirmation.disabled=false;status.textContent=message;}
form.onsubmit=async event=>{
 event.preventDefault();
 if(password.value.length<8||password.value.length>200||password.value!==confirmation.value){status.textContent='As senhas devem ser iguais e ter de 8 a 200 caracteres.';return;}
 button.disabled=true;password.disabled=true;confirmation.disabled=true;status.textContent='Salvando…';
 try{
  const salt=crypto.getRandomValues(new Uint8Array(16)),key=await crypto.subtle.importKey('raw',new TextEncoder().encode(password.value),'PBKDF2',false,['deriveBits']);
  const bits=await crypto.subtle.deriveBits({name:'PBKDF2',salt,iterations:600000,hash:'SHA-256'},key,256);
  const verifier='pbkdf2_sha256$600000$'+hex(salt)+'$'+hex(bits);
  password.value='';confirmation.value='';
  google.script.run.withSuccessHandler(reply=>{finish(reply.message);if(reply.ok){button.disabled=true;button.textContent='Senha salva';}}).withFailureHandler(()=>finish('Não foi possível salvar. A célula não foi confirmada; mantenha esta janela e tente novamente.')).salvarSenhaDaPlanilha(target,verifier);
 }catch{finish('O navegador não conseguiu preparar a senha. Abra a planilha no Chrome ou Edge atualizado.');}
};
</script></html>`;
}
function salvarSenhaDaPlanilha(target,verifier){
  let lock,acquired=false;
  try{
    const book=passwordEditorBook_();
    if(!target||!Number.isInteger(target.row)||target.row<2||!validHash_(verifier))error_(422,'Dados inválidos');
    lock=LockService.getScriptLock();acquired=lock.tryLock(5000);if(!acquired)error_(503,'Ocupado');
    const props=PropertiesService.getScriptProperties(),sheet=unifiedSheet_(props);
    if(!sheet)error_(422,'Cadastro unificado não preparado');
    const current=portalRoster_(props).find(r=>r.row===target.row);
    if(!current||current.id!==target.id||current.name!==target.name||sha_(JSON.stringify(sheet.getRange(target.row,1,1,7).getValues()[0]))!==target.fingerprint)error_(409,'A linha mudou');
    const cell=sheet.getRange(target.row,7);cell.setValue(verifier);SpreadsheetApp.flush();
    if(String(cell.getValue()).trim()!==verifier)error_(503,'Gravação não confirmada');
    return {ok:true,message:'Senha salva na coluna G. Use a senha informada para entrar no D-Max.'+(current.deleted||current.expires_at!==null&&current.expires_at<=Date.now()/1000?' A conta continua excluída ou vencida.':String(sheet.getRange(target.row,5).getValue()).trim().toLowerCase()!=='ativo'?' Para permitir o acesso, ajuste a situação da conta para ativo.':'')};
  }catch(e){
    return {ok:false,message:e.code===409?'A linha mudou durante a edição. Feche esta janela, selecione o usuário novamente e repita.':e.code===422?'Não foi possível validar a linha ou o cadastro. Execute Verificar cadastro no menu D-Max.':'O Google não confirmou a gravação. Confira se sua conta pode editar a célula G desta planilha.'};
  }finally{if(acquired)lock.releaseLock();}
}
function saveStage_(trace,stage){
  if(!trace)return;
  trace.stage=stage;
  console.info('DMAX_SAVE '+JSON.stringify({revision:DMAX_SCRIPT_REVISION,stage:stage}));
}
function doPost(event) {
  let lock, acquired=false;
  try {
    if(!event||!event.postData||event.postData.contents.length>20000)error_(413,'Solicitação inválida');
    const data=JSON.parse(event.postData.contents),props=PropertiesService.getScriptProperties();
    if(typeof data.action==='string'&&data.action.startsWith('desktop_'))return json_(desktopRequest_(data));
    if(!/^[A-Za-z0-9_-]{1,100}$/.test(data.controller_id||'')||typeof data.key!=='string'||data.key.length>512||
       !equal_(props.getProperty('device.'+data.controller_id),sha_(data.key)))error_(401,'Equipamento não autorizado');
    lock=LockService.getScriptLock();
    acquired=lock.tryLock(5000);
    if(!acquired)error_(503,'Consulta ocupada; tente novamente');
    if(data.action==='redeem_login')return json_(redeemLogin_(props,data));
    if(data.action==='manage_user')return json_(bridgeManageUser_(props,data));
    if(data.action==='remote_directory'){
      return json_(remoteDirectory_());
    }
    if(data.action==='snapshot'){
      const result=snapshot_(props);
      if(!Object.prototype.hasOwnProperty.call(result,'accounts'))result.accounts=accounts_(props);
      const notice=subscription_(props,data.controller_id);
      if(notice)result.subscription=notice;
      if(data.remote){
        try{result.remote_ack=remote_(data.controller_id,data.remote);}
        catch(e){result.remote_error=true;}
      }
      return json_(result);
    }
    if(data.action==='update')return json_(update_(props,data.record));
    error_(422,'Ação desconhecida');
  } catch(e) {
    // Never echo request contents, device keys or password hashes.
    return json_({ok:false,code:e.code||503,message:e.code?'Solicitação recusada':'Confira a aba, permissões e cotas do Apps Script'});
  } finally {if(acquired)lock.releaseLock();}
}

const DMAX_REMOTE_TAB='DMax_Remoto';
const DMAX_REMOTE_HEADERS=['controller_id','instalacao','url','ultimo_estado_informado','ultima_comunicacao','ultimo_sinal_tunel','revisao'];
function remoteSheet_(){
  const book=SpreadsheetApp.openById(DMAX_SHEET_ID);
  let sheet=book.getSheetByName(DMAX_REMOTE_TAB);
  if(!sheet)sheet=book.insertSheet(DMAX_REMOTE_TAB);
  if(!sheet.getLastRow()){
    sheet.getRange(1,1,1,DMAX_REMOTE_HEADERS.length).setValues([DMAX_REMOTE_HEADERS]);
    sheet.setFrozenRows(1);sheet.autoResizeColumns(1,DMAX_REMOTE_HEADERS.length);
  }
  if(!deviceLayout_(sheet)&&!headersMatch_(sheet.getRange(1,1,1,DMAX_REMOTE_HEADERS.length).getValues()[0],DMAX_REMOTE_HEADERS))error_(422,'Cabeçalhos remotos incompatíveis','remote_headers');
  return sheet;
}
function prepararRemoto(){
  SpreadsheetApp.getUi(); // Requires the bound spreadsheet editor, not the public web app.
remoteSheet_();}
function sheetText_(value){return /^[=+\-@\t\r]/.test(value)?"'"+value:value;}
function sheetUserChoice_(sheet,row,column,value,isRole){
  const canonical=v=>isRole?DMAX_GLOBAL_ROLES[String(v).trim().toLowerCase()]:String(v).trim().toLowerCase().replace('excluído','excluido');
  const fallback=isRole?{developer:'desenvolvedor',commercial:'comercial',technician:'tecnico'}[value]:value;
  const cell=sheet.getRange(row,column),rule=typeof cell.getDataValidation==='function'?cell.getDataValidation():null;
  if(!rule)return fallback;
  const type=rule.getCriteriaType(),args=rule.getCriteriaValues();let choices;
  if(type===SpreadsheetApp.DataValidationCriteria.VALUE_IN_LIST)choices=args[0];
  else if(type===SpreadsheetApp.DataValidationCriteria.VALUE_IN_RANGE)choices=args[0].getDisplayValues().reduce((a,r)=>a.concat(r),[]);
  if(choices){
    const found=choices.find(v=>canonical(v)===value);
    if(found!==undefined)return String(found);
    if(!rule.getAllowInvalid())error_(422,'A lista de perfil/situação não contém a opção selecionada');
  }
  return fallback;
}
function remote_(id,data){
  if(!data||Object.keys(data).sort().join(',')!=='connected,heartbeat_at,provider,revision,site_name,url'||
     data.provider!=='cloudflare'||typeof data.connected!=='boolean'||!Number.isSafeInteger(data.revision)||data.revision<1||
     typeof data.site_name!=='string'||data.site_name.length>100||
     typeof data.url!=='string'||!/^https:\/\/[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.trycloudflare\.com$/.test(data.url)||
     typeof data.heartbeat_at!=='number'||!Number.isFinite(data.heartbeat_at)||data.heartbeat_at<1||data.heartbeat_at>Date.now()/1000+300)error_(422,'Registro remoto inválido');
  const sheet=remoteSheet_();
  const matches=remoteRows_(sheet).map((row,i)=>({row,index:i+2})).filter(item=>String(item.row[0])===id);
  if(matches.length>1)error_(409,'Identificador remoto duplicado');
  const old=matches[0];
  const revision=old?Number(old.row[6]):0;
  if(!Number.isSafeInteger(revision)||revision<0)error_(422,'Revisão remota inválida');
  if(data.revision<revision)return {revision:revision,accepted:false};
  if(data.revision===revision&&old&&(old.row[2]!==data.url||old.row[3]!== (data.connected?'CONECTADO':'DESCONECTADO')))return {revision:revision,accepted:false};
  const values=[id,sheetText_(deviceLayout_(sheet)&&old&&old.row[1]?String(old.row[1]):data.site_name),data.url,data.connected?'CONECTADO':'DESCONECTADO',new Date().toISOString(),new Date(data.heartbeat_at*1000).toISOString(),data.revision];
  if(deviceLayout_(sheet)&&old){
    // Never write the administrative columns during a heartbeat, even if a
    // spreadsheet editor changes E between reading and writing this report.
    sheet.getRange(old.index,3,1,2).setValues([[values[2],values[3]]]);
    sheet.getRange(old.index,6,1,3).setValues([values.slice(4)]);
  }
  else if(deviceLayout_(sheet)){
    const history=JSON.parse(PropertiesService.getScriptProperties().getProperty('subscription.'+id)||'null');
    sheet.getRange(sheet.getLastRow()+1,1,1,11).setValues([[...values.slice(0,4),history&&history.state==='pending'?'pendente':'ativo',...values.slice(4),'','',history?history.message:'']]);
  }
  else sheet.getRange(old?old.index:sheet.getLastRow()+1,1,1,7).setValues([values]);
  ordenarLinhas_(sheet);
  return {revision:data.revision,accepted:true};
}

function remoteDirectory_(){
  const sheet=remoteSheet_(),clients=[],seen={};
  if(sheet.getLastRow()>1001)error_(422,'Limite de 1000 clientes');
  const rows=remoteRows_(sheet);
  rows.forEach(row=>{
    if(row.every(v=>String(v).trim()==='') || !String(row[2]).trim())return;
    const id=String(row[0]).trim(),name=String(row[1]).trim(),url=String(row[2]).trim(),stamp=row[4] instanceof Date?row[4].getTime():String(row[4]).trim()===''&&row[3]==='DESCONECTADO'?0:Date.parse(String(row[4]));
    if(!/^[A-Za-z0-9_-]{1,100}$/.test(id)||seen[id]||!name||name.length>100||
       !/^https:\/\/[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.trycloudflare\.com$/.test(url)||
       ['https://api.trycloudflare.com','https://www.trycloudflare.com'].includes(url)||
       !['CONECTADO','DESCONECTADO'].includes(row[3])||!Number.isFinite(stamp))error_(422,'Registro remoto inválido');
    seen[id]=true;clients.push({controller_id:id,site_name:name,url:url,connected:row[3]==='CONECTADO',updated_at:stamp/1000});
  });
  return {ok:true,clients:clients};
}

function date_(value,timezone) {
  if(value===''||value===null||value===undefined)return null;
  let text=value instanceof Date?Utilities.formatDate(value,timezone,'yyyy-MM-dd'):String(value).trim();
  let parts;
  if((parts=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(text)))text=parts[3]+'-'+parts[2]+'-'+parts[1];
  if(/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    const date=Utilities.parseDate(text+' 23:59:59',timezone,'yyyy-MM-dd HH:mm:ss');
    if(Utilities.formatDate(date,timezone,'yyyy-MM-dd')!==text)error_(422,'Data inválida');
    return date.getTime()/1000+1;
  }
  if(!/(Z|[+-]\d{2}:\d{2})$/.test(text))error_(422,'Data/hora exige fuso');
  const parsed=Date.parse(text);if(!Number.isFinite(parsed))error_(422,'Data inválida');return parsed/1000;
}

function rows_() {
  const book=SpreadsheetApp.openById(DMAX_SHEET_ID),sheet=book.getSheetByName(DMAX_TAB);
  if(!sheet||sheet.getLastRow()<1)error_(503,'Prepare a aba Tecnicos');
  const values=sheet.getRange(1,1,sheet.getLastRow(),5).getValues();
  if(!headersMatch_(values[0],DMAX_HEADERS))error_(422,'Cabeçalhos inválidos');
  const ids={},names={},rows=[];
  values.slice(1).forEach((cells,index)=>{
    if(cells.every(v=>String(v).trim()===''))return;
    const id=String(cells[0]).trim(),name=String(cells[2]).trim().toLowerCase(),full=String(cells[1]).trim(),status=String(cells[3]).trim().toLowerCase();
    if(!/^[A-Za-z0-9_-]{1,100}$/.test(id)||!/^[a-z0-9._-]{3,40}$/.test(name)||['root','admin'].includes(name)||!full||full.length>100||ids[id]||names[name])error_(422,'Cadastro inválido ou duplicado');
    if(!['ativo','bloqueado','excluido','excluído'].includes(status))error_(422,'Situação inválida');
    rows.push({id:id,name:name,full_name:full,active:status==='ativo',deleted:status==='excluido'||status==='excluído',expires_at:date_(cells[4],book.getSpreadsheetTimeZone()),row:index+2});
    ids[id]=true;names[name]=true;
  });
  if(rows.length>1000)error_(422,'Limite desta implantação: 1000 técnicos');
  return {sheet:sheet,rows:rows};
}

function refresh_(props) {
  if(unifiedSheet_(props))return unifiedState_(props);
  const source=rows_(),all=props.getProperties(),seen={},records=[];
  // Validate every identity before committing any metadata change.
  source.rows.forEach(meta=>{
    const old=all['user.'+meta.id]?JSON.parse(all['user.'+meta.id]):null;
    if(old&&old.name!==meta.name)error_(409,'Login/id é permanente; altere somente o nome exibido');
    Object.keys(all).filter(k=>k.startsWith('user.')).forEach(k=>{
      const other=JSON.parse(all[k]);if(other.name===meta.name&&other.id!==meta.id)error_(409,'Login pertence a identidade histórica');
    });
  });
  source.rows.forEach(meta=>{
    const pending=all['pending.'+meta.id]?JSON.parse(all['pending.'+meta.id]):null;
    let old=all['user.'+meta.id]?JSON.parse(all['user.'+meta.id]):null;
    if(!old)old={id:meta.id,name:meta.name,password:pending&&pending.name===meta.name?pending.password:DMAX_DEFAULT_HASH,
      activation_hash:null,
      must_change:pending&&pending.name===meta.name?Boolean(pending.must_change):true,
      credential_version:pending&&pending.name===meta.name?pending.credential_version:1,meta_version:0};
    const digest=sha_(JSON.stringify([meta.full_name,meta.active,meta.deleted,meta.expires_at]));
    const changed=old.meta_digest!==digest;
    const record=Object.assign({},old,{full_name:meta.full_name,active:meta.active,deleted:meta.deleted,expires_at:meta.expires_at,
      meta_digest:digest,meta_version:old.meta_version+(changed?1:0),activation_hash:null});
    if(changed||old.activation_hash!==null)props.setProperty('user.'+meta.id,JSON.stringify(record));
    if(pending)props.deleteProperty('pending.'+meta.id);
    records.push(record);seen[meta.id]=true;
  });
  Object.keys(all).filter(k=>k.startsWith('user.')).forEach(key=>{
    const record=JSON.parse(all[key]);if(seen[record.id])return;
    if(record.active||!record.deleted){record.active=false;record.deleted=true;record.meta_version++;props.setProperty(key,JSON.stringify(record));}
    records.push(record);
  });
  if(records.length>5000)error_(503,'Histórico de identidades excedeu a capacidade desta implantação');
  return {source:source,records:records};
}
function snapshot_(props) {
  if(unifiedSheet_(props))return unifiedSnapshot_(props);
  const state=refresh_(props);
  return {ok:true,complete:true,generated_at:Date.now()/1000,technicians:state.records.map(r=>{
    const copy=Object.assign({},r);delete copy.meta_digest;return copy;
  })};
}

function update_(props,r) {
  if(!r||!Array.isArray(r.operations)||!r.operations.length||r.operations.some(x=>!['register','metadata','credential'].includes(x)))error_(422,'Operação inválida');
  if(!/^[A-Za-z0-9_-]{1,100}$/.test(r.id||'')||!/^[a-z0-9._-]{3,40}$/.test(r.name||'')||['root','admin'].includes(r.name)||typeof r.full_name!=='string'||!r.full_name||r.full_name.length>100)error_(422,'Identidade inválida');
  if(!validHash_(r.password)||(r.activation_hash!==null&&!validHash_(r.activation_hash))||!Number.isInteger(r.credential_version)||r.credential_version<1)error_(422,'Credencial inválida');
  if(![true,false,0,1].includes(r.active)||![true,false,0,1].includes(r.deleted)||![true,false,0,1].includes(r.must_change)||
    (r.expires_at!==null&&(!Number.isFinite(r.expires_at)||r.expires_at<0)))error_(422,'Situação inválida');
  if(unifiedSheet_(props))return updateUnified_(props,r);
  const state=refresh_(props),old=state.records.find(x=>x.id===r.id),register=r.operations.includes('register');
  if(state.records.some(x=>x.name===r.name&&x.id!==r.id))error_(409,'Login já existe');
  if(register&&old){if(old.name===r.name&&old.password===r.password)return {ok:true,acknowledged_id:r.id};error_(409,'Identidade já existe');}
  if(!register){
    if(!old||old.name!==r.name)error_(409,'Identidade não encontrada');
    if(r.operations.includes('credential')&&(!old.active||old.deleted||(old.expires_at!==null&&old.expires_at<=Date.now()/1000)||old.credential_version!==r.base_version)){
      if(old.password===r.password&&old.credential_version===r.credential_version)return {ok:true,acknowledged_id:r.id};error_(409,'Credencial mudou ou acesso foi revogado');
    }
    const matches=old.full_name===r.full_name&&Boolean(old.active)===Boolean(r.active)&&Boolean(old.deleted)===Boolean(r.deleted)&&old.expires_at===r.expires_at;
    if(r.operations.includes('metadata')&&old.meta_version!==r.base_meta_version&&!matches)error_(409,'Planilha mudou');
  }
  if(register)props.setProperty('pending.'+r.id,JSON.stringify(r));
  if(register||r.operations.includes('metadata')){
    const row=[r.id,r.full_name,r.name,r.deleted?'excluido':r.active?'ativo':'bloqueado',r.expires_at===null?'':new Date(r.expires_at*1000).toISOString()];
    const meta=state.source.rows.find(x=>x.id===r.id),index=meta?meta.row:state.source.sheet.getLastRow()+1;
    // Store as literal text, not spreadsheet formulas from names or logins.
    const safe=row.map(v=>typeof v==='string'&&/^[=+\-@\t\r]/.test(v)?"'"+v:v);
    state.source.sheet.getRange(index,1,1,5).setValues([safe]);
  }
  let record=old?Object.assign({},old):{id:r.id,name:r.name,full_name:r.full_name,active:Boolean(r.active),deleted:Boolean(r.deleted),expires_at:r.expires_at,meta_version:0};
  if(register||r.operations.includes('credential'))Object.assign(record,{password:r.password,activation_hash:null,must_change:Boolean(r.must_change),credential_version:r.credential_version});
  props.setProperty('user.'+r.id,JSON.stringify(record));props.deleteProperty('pending.'+r.id);
  return {ok:true,acknowledged_id:r.id};
}

/** Optional per-installation billing. Missing/deleted rows never cancel a notice. */
const DMAX_SUB_HEADERS=['controller_id','instalacao','situacao','aviso_em','prazo_final','mensagem'];
function prepararAssinaturas() {
  SpreadsheetApp.getUi(); // Requires the bound spreadsheet editor, not the public web app.

  const book=SpreadsheetApp.openById(DMAX_SHEET_ID);
  let sheet=book.getSheetByName('Assinaturas');
  if(!sheet)sheet=book.insertSheet('Assinaturas');
  if(sheet.getLastRow()===0){
    sheet.getRange(1,1,1,6).setValues([DMAX_SUB_HEADERS]);sheet.setFrozenRows(1);
    sheet.getRange(1,1,1,6).setBackground('#06264a').setFontColor('#ffffff').setFontWeight('bold');
    sheet.autoResizeColumns(1,6);
  }else if(!headersMatch_(sheet.getRange(1,1,1,6).getValues()[0],DMAX_SUB_HEADERS)){
    throw new Error('Cabeçalhos diferentes. Nenhum dado foi substituído.');
  }
  SpreadsheetApp.getUi().alert('Use uma linha por D-Max. Situação: regular ou pendente. O prazo é fixo de dez dias; aviso_em e prazo_final são preenchidos pelo serviço. Para liberar, altere para regular. Apagar a linha não libera o equipamento.');
}
function subscription_(props,id) {
  const book=SpreadsheetApp.openById(DMAX_SHEET_ID);
  const unified=book.getSheetByName(DMAX_REMOTE_TAB);
  if(unified && (deviceLayout_(unified)||headersMatch_(unified.getRange(1,8,1,4).getValues()[0],['situacao','aviso_em','prazo_final','mensagem'])))return unifiedSubscription_(props,id,unified);
  const sheet=book.getSheetByName('Assinaturas');
  if(!sheet||sheet.getLastRow()<2)return null;
  if(!headersMatch_(sheet.getRange(1,1,1,6).getValues()[0],DMAX_SUB_HEADERS))error_(422,'Cabeçalhos de assinaturas inválidos');
  const matches=sheet.getRange(2,1,sheet.getLastRow()-1,6).getValues().map((v,i)=>({v:v,row:i+2})).filter(r=>String(r.v[0]).trim()===id);
  if(!matches.length)return null;
  if(matches.length!==1)error_(422,'Assinatura duplicada');
  const row=matches[0];
  return subscriptionFromRow_(props,id,row.v,dates=>sheet.getRange(row.row,4,1,2).setValues([dates]));
}
function subscriptionFromRow_(props,id,values,writeDates){
  const status=String(values[2]).trim().toLowerCase();
  if(!['regular','pendente'].includes(status))error_(422,'Situação de assinatura inválida');
  const state=status==='pendente'?'pending':'regular',now=Math.floor(Date.now()/1000);
  const message=String(values[5]||'Regularize sua assinatura com o fornecedor.').trim();
  if(message.length>300)error_(422,'Mensagem muito longa');
  const property='subscription.'+id,old=JSON.parse(props.getProperty(property)||'null');
  let record=old;
  if(!old||old.state!==state||old.message!==message){
    // Editing a message cannot restart an existing pending grace period.
    const issued=old&&old.state==='pending'&&state==='pending'?old.issued_at:now;
    record={controller_id:id,revision:old?old.revision+1:1,state:state,issued_at:issued,
      deadline:state==='pending'?issued+864000:null,message:message};
    props.setProperty(property,JSON.stringify(record));
  }
  const dates=[new Date(record.issued_at*1000).toISOString(),record.deadline?new Date(record.deadline*1000).toISOString():''];
  writeDates(dates);
  const payload=JSON.stringify(Object.assign({},record,{server_time:now}));
  const signature=Utilities.computeHmacSha256Signature('DMAX-LICENSE-1\n'+payload,props.getProperty('device.'+id),Utilities.Charset.UTF_8)
    .map(b=>('0'+((b+256)%256).toString(16)).slice(-2)).join('');
  return {payload:payload,signature:signature};
}

/** Optional privileged accounts. Existing Tecnicos rows and credentials stay intact. */
const DMAX_ACCOUNT_HEADERS=['id','nome','login','perfil','situacao','valido_ate','verificador'];
function prepararContas(){return migrarUsuarios();}
function accounts_(props){
  const book=SpreadsheetApp.openById(DMAX_SHEET_ID),sheet=book.getSheetByName('Contas');
  if(!sheet)return [];
  const values=sheet.getRange(1,1,sheet.getLastRow(),7).getValues();
  if(!headersMatch_(values[0],DMAX_ACCOUNT_HEADERS))error_(422,'Cabeçalhos Contas incompatíveis');
  const ids=new Set(),names=new Set(),records=[];
  values.slice(1).forEach(c=>{
    if(c.every(v=>String(v).trim()===''))return;
    const id=String(c[0]).trim(),full=String(c[1]).trim(),name=String(c[2]).trim().toLowerCase();
    const role=({desenvolvedor:'developer',comercial:'commercial',developer:'developer',commercial:'commercial'})[String(c[3]).trim().toLowerCase()];
    const status=String(c[4]).trim().toLowerCase(),hash=String(c[6]).trim();
    if(!/^[A-Za-z0-9_-]{1,100}$/.test(id)||!/^[a-z0-9._-]{3,40}$/.test(name)||['root','admin'].includes(name)||!full||full.length>100||!role||!validHash_(hash)||ids.has(id)||names.has(name)||!['ativo','bloqueado','excluido','excluído'].includes(status))error_(422,'Conta global inválida');
    ids.add(id);names.add(name);
    const expires=date_(c[5],book.getSpreadsheetTimeZone());
    const record={id:id,name:name,full_name:full,role:role,active:status==='ativo',deleted:['excluido','excluído'].includes(status),expires_at:expires,password:hash,must_change:false,activation_hash:null,credential_version:1,meta_version:0};
    // Fingerprints provide monotonic versions without storing plain passwords.
    const previous=props.getProperty('account.'+id),old=previous?JSON.parse(previous):null;
    if(old&&old.name!==name)error_(409,'Login/id permanente');
    record.credential_version=old?old.credential_version+(old.password!==hash?1:0):1;
    record.meta_version=old?old.meta_version+1:1;
    records.push(record);
  });
  if(records.length>1000)error_(422,'Limite de contas excedido');
  // Validate collisions with legacy technicians before persisting anything.
  const legacy=refresh_(props).records;
  if(records.some(r=>legacy.some(t=>t.id===r.id||t.name===r.name)))error_(409,'Conta conflita com técnico existente');
  records.forEach(r=>props.setProperty('account.'+r.id,JSON.stringify(r)));
  return records;
}

/** One active roster for all global roles. Legacy tabs are retained as archives. */
const DMAX_USERS_TAB='Usuarios';
const DMAX_USERS_HEADERS=['id','nome','login','perfil','situacao','valido_ate','verificador'];
const DMAX_GLOBAL_ROLES={tecnico:'technician','técnico':'technician',technician:'technician',desenvolvedor:'developer',developer:'developer',comercial:'commercial',commercial:'commercial'};
function unifiedSheet_(props){
  if(props.getProperty('directory.unified')!=='1')return null;
  const sheet=SpreadsheetApp.openById(DMAX_SHEET_ID).getSheetByName(DMAX_USERS_TAB);
  if(!sheet)error_(503,'Aba Usuarios ausente; restaure a aba, não apague propriedades');
  return sheet;
}
function userRows_(sheet,book){
  if(!sheet.getLastRow())error_(422,'Cabeçalhos Usuarios ausentes','users_headers');
  const values=sheet.getRange(1,1,sheet.getLastRow(),7).getValues();
  if(!headersMatch_(values[0],DMAX_USERS_HEADERS))error_(422,'Cabeçalhos Usuarios incompatíveis','users_headers');
  const ids=new Set(),names=new Set();
  const rows=[];
  values.slice(1).forEach((c,index)=>{
    if(c.every(v=>String(v).trim()===''))return;
    const id=String(c[0]).trim(),name=String(c[2]).trim().toLowerCase(),full=String(c[1]).trim();
    const role=DMAX_GLOBAL_ROLES[String(c[3]).trim().toLowerCase()],status=String(c[4]).trim().toLowerCase();
    const hash=String(c[6]).trim();
    if(!/^[A-Za-z0-9_-]{1,100}$/.test(id)||!/^[a-z0-9._-]{3,40}$/.test(name)||['root','admin'].includes(name)||!full||full.length>100||!role||ids.has(id)||names.has(name))error_(422,'Identidade/perfil inválido ou duplicado na linha '+(index+2));
    if(!['ativo','bloqueado','excluido','excluído'].includes(status)||(hash&&!validHash_(hash)))error_(422,'Situação/verificador inválido na linha '+(index+2));
    ids.add(id);names.add(name);
    rows.push({id:id,name:name,full_name:full,role:role,active:status==='ativo'&&Boolean(hash),deleted:['excluido','excluído'].includes(status),expires_at:date_(c[5],book.getSpreadsheetTimeZone()),password:hash,row:index+2,credential_pending:!hash});
  });
  if(rows.length>2000)error_(422,'Limite desta implantação: 2000 usuários');
  return rows;
}
function historicalUsers_(all){
  const byId=Object.create(null),byName=Object.create(null);
  // Resolve precedence BEFORE checking login uniqueness. Canonical identities
  // (including revocations) supersede obsolete technician/account caches.
  // Keep the archived properties intact for recovery; never reactivate from them.
  ['identity.','account.','user.'].forEach(prefix=>{
    Object.keys(all).filter(k=>k.startsWith(prefix)).forEach(k=>{
      const r=JSON.parse(all[k]);
      if(Object.prototype.hasOwnProperty.call(byId,r.id)){
        if(!Object.prototype.hasOwnProperty.call(all,'identity.'+r.id)&&byId[r.id].name!==r.name)
          error_(409,'ID histórico tem logins divergentes: '+r.id);
        return;
      }
      byId[r.id]=Object.assign({role:prefix==='user.'?'technician':r.role},r);
    });
  });
  Object.values(byId).forEach(r=>{
    if(Object.prototype.hasOwnProperty.call(byName,r.name)&&byName[r.name]!==r.id)
      error_(409,'Login histórico tem IDs divergentes: '+r.name);
    byName[r.name]=r.id;
  });
  return {byId:byId,byName:byName};
}
function unifiedState_(props){
  const book=SpreadsheetApp.openById(DMAX_SHEET_ID),sheet=unifiedSheet_(props);
  const rows=userRows_(sheet,book),all=props.getProperties(),history=historicalUsers_(all),seen=new Set(),records=[];
  // Validate the entire roster against all historical identities before any write.
  rows.forEach(r=>{
    if(history.byId[r.id]&&history.byId[r.id].name!==r.name)error_(409,'Login/id permanente: '+r.id);
    if(history.byName[r.name]&&history.byName[r.name]!==r.id)error_(409,'Login pertence a outro ID: '+r.name);
  });
  rows.forEach(r=>{
    const old=history.byId[r.id],pending=all['pending.'+r.id]?JSON.parse(all['pending.'+r.id]):null;
    if(r.credential_pending){
      // Blank cells do not invalidate unrelated accounts or replace a saved hash.
      // Existing Pi caches still need an explicit inactive record for this ID.
      seen.add(r.id);
      if(old){
        const digest=sha_(JSON.stringify([r.full_name,r.role,false,r.deleted,r.expires_at]));
        records.push(Object.assign({},old,{full_name:r.full_name,role:r.role,active:false,deleted:r.deleted,expires_at:r.expires_at,credential_pending:true,meta_digest:digest,meta_version:(old.meta_version||0)+(old.meta_digest!==digest?1:0)}));
      }
      return;
    }
    const credentialChanged=old&&old.password!==r.password;
    const mustChange=r.password===DMAX_DEFAULT_HASH||(pending&&pending.name===r.name&&pending.password===r.password?Boolean(pending.must_change):old&&!credentialChanged?Boolean(old.must_change):false);
    const digest=sha_(JSON.stringify([r.full_name,r.role,r.active,r.deleted,r.expires_at]));
    const record=Object.assign({},r,{activation_hash:null,must_change:mustChange,credential_version:old?old.credential_version+(credentialChanged?1:0):pending?pending.credential_version:1,meta_version:old?(old.meta_version||0)+(old.meta_digest!==digest?1:0):1,meta_digest:digest});
    delete record.row;records.push(record);seen.add(r.id);
  });
  Object.values(history.byId).forEach(old=>{
    if(seen.has(old.id))return;
    records.push(Object.assign({},old,{active:false,deleted:true,meta_version:(old.meta_version||0)+((old.active||!old.deleted)?1:0)}));
  });
  if(records.length>5000)error_(503,'Histórico de identidades excedeu a capacidade');
  records.forEach(r=>props.setProperty('identity.'+r.id,JSON.stringify(r)));
  rows.forEach(r=>{if(!r.credential_pending&&all['pending.'+r.id])props.deleteProperty('pending.'+r.id);});
  return {source:{sheet:sheet,rows:rows},records:records};
}
function unifiedSnapshot_(props){
  const state=unifiedState_(props);
  const wire=r=>{const copy=Object.assign({},r);delete copy.meta_digest;return copy;};
  return {ok:true,complete:true,generated_at:Date.now()/1000,technicians:state.records.filter(r=>r.role==='technician').map(wire),accounts:state.records.filter(r=>['developer','commercial'].includes(r.role)).map(wire)};
}
function updateUnified_(props,r){
  const state=unifiedState_(props),old=state.records.find(x=>x.id===r.id),register=r.operations.includes('register');
  if(old&&old.role!=='technician')error_(403,'Perfis são gerenciados somente na aba Usuarios');
  if(state.records.some(x=>x.name===r.name&&x.id!==r.id))error_(409,'Login já existe');
  if(register&&old){if(old.name===r.name&&old.password===r.password)return {ok:true,acknowledged_id:r.id};error_(409,'Identidade já existe');}
  if(!register){
    if(!old||old.name!==r.name)error_(409,'Identidade não encontrada');
    if(r.operations.includes('credential')&&(!old.active||old.deleted||(old.expires_at!==null&&old.expires_at<=Date.now()/1000)||old.credential_version!==r.base_version)){
      if(old.password===r.password&&old.credential_version===r.credential_version)return {ok:true,acknowledged_id:r.id};error_(409,'Credencial mudou ou acesso foi revogado');
    }
    const matches=old.full_name===r.full_name&&Boolean(old.active)===Boolean(r.active)&&Boolean(old.deleted)===Boolean(r.deleted)&&old.expires_at===r.expires_at;
    if(r.operations.includes('metadata')&&old.meta_version!==r.base_meta_version&&!matches)error_(409,'Planilha mudou');
  }
  let record=old?Object.assign({},old):{id:r.id,name:r.name,role:'technician',meta_version:0};
  if(register||r.operations.includes('metadata'))Object.assign(record,{full_name:r.full_name,active:Boolean(r.active),deleted:Boolean(r.deleted),expires_at:r.expires_at});
  if(register||r.operations.includes('credential'))Object.assign(record,{password:r.password,activation_hash:null,must_change:Boolean(r.must_change),credential_version:r.credential_version});
  const meta=state.source.rows.find(x=>x.id===r.id),index=meta?meta.row:state.source.sheet.getLastRow()+1;
  const row=[record.id,record.full_name,record.name,'tecnico',record.deleted?'excluido':record.active?'ativo':'bloqueado',record.expires_at===null?'':new Date(record.expires_at*1000).toISOString(),record.password];
  props.setProperty('pending.'+r.id,JSON.stringify(record));
  state.source.sheet.getRange(index,1,1,7).setValues([row.map(v=>typeof v==='string'?sheetText_(v):v)]);
  // Recompute metadata versions through the same canonical path as snapshots.
  props.setProperty('identity.'+r.id,JSON.stringify(record));
  unifiedState_(props);
  ordenarLinhas_(state.source.sheet);
  return {ok:true,acknowledged_id:r.id};
}
function migrarUsuarios(){
  SpreadsheetApp.getUi(); // Requires the bound spreadsheet editor, not the public web app.

  const lock=LockService.getScriptLock();
  if(!lock.tryLock(5000))throw new Error('Sincronização ocupada; tente novamente');
  try {
    const props=PropertiesService.getScriptProperties(),book=SpreadsheetApp.openById(DMAX_SHEET_ID);
    if(unifiedSheet_(props)){unifiedState_(props);SpreadsheetApp.getUi().alert('Usuarios já é a única aba ativa de acessos.');return;}
    if(book.getSheetByName(DMAX_USERS_TAB))throw new Error('Aba Usuarios já existe sem ativação. Preserve-a e revise antes de migrar.');
    const all=props.getProperties(),history=historicalUsers_(all),byId={},byName={};
    function merge(record,fromAccount){
      const old=byId[record.id];
      if(old&&old.name!==record.name)throw new Error('ID com logins diferentes: '+record.id);
      if(byName[record.name]&&byName[record.name]!==record.id)throw new Error('Login com IDs diferentes: '+record.name+'. Preserve o ID histórico antes de migrar.');
      if(history.byId[record.id]&&history.byId[record.id].name!==record.name)throw new Error('Login histórico alterado no ID '+record.id);
      if(history.byName[record.name]&&history.byName[record.name]!==record.id)throw new Error('Login pertence a outro ID histórico: '+record.name);
      if(!old||fromAccount)byId[record.id]=record;
      byName[record.name]=record.id;
    }
    const tech=book.getSheetByName(DMAX_TAB),accounts=book.getSheetByName('Contas');
    if(tech){
      rows_().rows.forEach(r=>{
        const old=history.byId[r.id],pending=all['pending.'+r.id]?JSON.parse(all['pending.'+r.id]):null;
        const password=old?old.password:pending&&pending.name===r.name?pending.password:DMAX_DEFAULT_HASH;
        merge(Object.assign({},r,{role:'technician',password:password}),false);
      });
    }
    if(accounts){
      const header=accounts.getRange(1,1,1,7).getValues()[0];
      if(!headersMatch_(header,DMAX_USERS_HEADERS))throw new Error('Cabeçalhos Contas incompatíveis');
      userRows_(accounts,book).forEach(r=>{
        if(r.role==='technician')throw new Error('Perfil inesperado na antiga aba Contas');
        merge(r,true);
      });
    }
    const output=[DMAX_USERS_HEADERS];
    Object.values(byId).forEach(r=>{
      if(!validHash_(r.password))throw new Error('Verificador inválido no ID '+r.id);
      output.push([r.id,r.full_name,r.name,{technician:'tecnico',developer:'desenvolvedor',commercial:'comercial'}[r.role],r.deleted?'excluido':r.active?'ativo':'bloqueado',r.expires_at===null?'':new Date(r.expires_at*1000).toISOString(),r.password]);
    });
    const stamp=Date.now()+'_'+Utilities.getUuid().slice(0,8);
    // Back up original tabs before creating the canonical roster. No originals deleted.
    [tech,accounts].filter(Boolean).forEach((sheet,i)=>sheet.copyTo(book).setName('Backup_acessos_'+stamp+'_'+i).hideSheet());
    const staging=book.insertSheet('Usuarios_preparacao_'+stamp);
    staging.getRange(1,1,output.length,7).setValues(output.map(row=>row.map(v=>typeof v==='string'?sheetText_(v):v)));
    SpreadsheetApp.flush();userRows_(staging,book);
    staging.setFrozenRows(1);staging.autoResizeColumns(1,7);
    staging.setName(DMAX_USERS_TAB);SpreadsheetApp.flush();
    props.setProperty('directory.unified','1');
    // Old properties remain intact for recovery; only canonical records are new.
    unifiedState_(props);
    [tech,accounts].filter(Boolean).forEach(sheet=>sheet.hideSheet());
    SpreadsheetApp.getUi().alert('Usuarios pronta: '+(output.length-1)+' contas. Edite somente Usuarios. Tecnicos/Contas e backups foram preservados e ocultados.');
  } finally {lock.releaseLock();}
}

/** Explicit migration: validate first, back up both sheets, preserve old rows. */
function unificarEquipamentos(){
  SpreadsheetApp.getUi(); // Requires the bound spreadsheet editor, not the public web app.

  const lock=LockService.getScriptLock();if(!lock.tryLock(10000))throw new Error('Migração em andamento');
  try {
    const book=SpreadsheetApp.openById(DMAX_SHEET_ID),remote=remoteSheet_(),old=book.getSheetByName('Assinaturas');
    if(deviceLayout_(remote))return;
    const extra=['situacao','aviso_em','prazo_final','mensagem'];
    if(headersMatch_(remote.getRange(1,8,1,4).getValues()[0],extra))return;
    const data=remote.getRange(1,1,remote.getLastRow(),11).getValues();
    if(data.some(row=>row.slice(7).some(v=>String(v)!=='')))throw new Error('Colunas H:K ocupadas; nenhum dado alterado');
    const seen=new Set();data.slice(1).forEach(row=>{if(seen.has(String(row[0])))throw new Error('D-Max duplicado');seen.add(String(row[0]));});
    const billing=old&&old.getLastRow()?old.getRange(1,1,old.getLastRow(),6).getValues():[DMAX_SUB_HEADERS];
    if(!headersMatch_(billing[0],DMAX_SUB_HEADERS))throw new Error('Cabeçalhos de assinaturas inválidos');
    const billed=new Set();
    billing.slice(1).forEach(row=>{
      const id=String(row[0]).trim();if(!id)return;
      if(billed.has(id))throw new Error('Assinatura duplicada');billed.add(id);
      if(!['regular','pendente'].includes(String(row[2]).trim().toLowerCase()))throw new Error('Situação inválida');
      let target=data.slice(1).find(r=>String(r[0]).trim()===id);
      if(!target){target=[id,row[1],'','DESCONECTADO','','',0];data.push(target);}
      target.splice(7,4,...row.slice(2,6));
    });
    const stamp=Date.now();remote.copyTo(book).setName('Backup_remoto_'+stamp).hideSheet();
    if(old)old.copyTo(book).setName('Backup_assinaturas_'+stamp).hideSheet();
    data[0]=DMAX_REMOTE_HEADERS.concat(extra);
    remote.getRange(1,1,data.length,11).setValues(data.map(row=>Array.from({length:11},(_,i)=>row[i]??'')));
    SpreadsheetApp.flush();if(old)old.hideSheet();
    SpreadsheetApp.getUi().alert('DMax_Remoto reúne acesso remoto e assinaturas. Backups preservados; edite a situação nas colunas H:K.');
  } finally {lock.releaseLock();}
}
function unifiedSubscription_(props,id,sheet){
  const rows=remoteRows_(sheet);
  const matches=rows.map((r,i)=>({r,index:i+2})).filter(x=>String(x.r[0]).trim()===id);
  if(matches.length>1)error_(422,'Assinatura duplicada');
  if(!matches.length||!String(matches[0].r[7]).trim())return null;
  const match=matches[0];
  // Delegate signing and deadline semantics to the legacy implementation.
  const status=String(match.r[7]).trim().toLowerCase()==='ativo'?'regular':match.r[7];
  return subscriptionFromRow_(props,id,[match.r[0],match.r[1],status,...match.r.slice(8,11)],dates=>sheet.getRange(match.index,9,1,2).setValues([dates]));
}

/** Editor-only read-only diagnosis. Never logs credentials or full records. */
function diagnosticarUsuarios(){
  const ui=SpreadsheetApp.getUi(); // Requires the bound spreadsheet editor, not the public web app.

  try {
    const props=PropertiesService.getScriptProperties(),all=props.getProperties();
    const book=SpreadsheetApp.openById(DMAX_SHEET_ID),sheet=unifiedSheet_(props);
    const rows=sheet?userRows_(sheet,book):rows_().rows;
    const history=historicalUsers_(all);
    rows.forEach(r=>{
      if(history.byId[r.id]&&history.byId[r.id].name!==r.name)
        error_(409,'Login/id permanente no ID: '+r.id);
      if(history.byName[r.name]&&history.byName[r.name]!==r.id)
        error_(409,'Login associado a outro ID: '+r.name);
    });
    const message='Validação de usuários OK. Cadastro unificado: '+Boolean(sheet)+'. Linhas: '+rows.length+'. Contas sem verificador (sem acesso): '+rows.filter(r=>r.credential_pending).length+'. Nenhum dado alterado.'+(sheet?'':' A central Windows exige cadastro unificado; este resultado valida apenas o cadastro legado do Raspberry.');
    console.log(message);ui.alert(message);
  } catch(e){
    const message='Diagnóstico de usuários: código '+(e.code||503)+'; '+e.message;
    console.log(message);ui.alert(message);
  }
}

/** A company bridge can manage accounts only after developer reauthentication.
 * A device key or possession of a stored verifier is never accepted as proof.
 */
function verifyPlatformPassword_(password,encoded){
  if(typeof password!=='string'||password.length>200||!validHash_(encoded))return false;
  const parts=encoded.split('$');
  const actual=sjcl.codec.hex.fromBits(sjcl.misc.pbkdf2(password,sjcl.codec.hex.toBits(parts[2]),600000,256));
  return equal_(actual,parts[3]);
}
function bridgeManageUser_(props,data,trace){
  saveStage_(trace,'prepare_directory');
  if(!unifiedSheet_(props))error_(422,'Prepare primeiro a aba Usuarios');
  if(typeof data.actor_login!=='string'||data.actor_login.length>40||typeof data.actor_password!=='string'||!data.actor_password||data.actor_password.length>200)error_(401,'Autenticação necessária');
  const now=Math.floor(Date.now()/1000),attemptKey='bridge.attempt.'+sha_(data.controller_id);
  let attempt=JSON.parse(props.getProperty(attemptKey)||'null');
  if(!attempt||now-attempt.at>=300)attempt={at:now,count:0};
  if(attempt.count>=5)error_(429,'Muitas tentativas');
  attempt.count++;props.setProperty(attemptKey,JSON.stringify(attempt));
  saveStage_(trace,'read_roster');
  const state=unifiedState_(props),actor=state.records.find(r=>r.name===data.actor_login.trim().toLowerCase());
  if(!actor||actor.role!=='developer'||!actor.active||actor.deleted||actor.must_change||(actor.expires_at!==null&&actor.expires_at<=now))error_(403,'Desenvolvedor ativo necessário');
  saveStage_(trace,'verify_developer_password');
  if(!verifyPlatformPassword_(data.actor_password,actor.password))error_(401,'Credenciais inválidas');
  props.deleteProperty(attemptKey);
  saveStage_(trace,'validate_record');
  const r=data.record;
  const current=r&&state.source.rows.find(x=>x.id===r.id);
  const keepPending=current&&current.credential_pending&&r.password==='';
  if(!r||Object.keys(r).sort().join(',')!=='expires,full_name,id,name,password,role,status'||
     !/^[A-Za-z0-9_-]{1,100}$/.test(r.id||'')||!/^[a-z0-9._-]{3,40}$/.test(r.name||'')||['root','admin'].includes(r.name)||
     typeof r.full_name!=='string'||!r.full_name.trim()||r.full_name.length>100||!['developer','commercial','technician'].includes(r.role)||
     !['ativo','bloqueado','excluido'].includes(r.status)||(!validHash_(r.password)&&!keepPending)||typeof r.expires!=='string'||
     (r.expires!==''&&!/^\d{4}-\d{2}-\d{2}$/.test(r.expires)))error_(422,'Dados inválidos');
  const history=historicalUsers_(props.getProperties()),old=history.byId[r.id];
  if(old&&old.name!==r.name)error_(409,'Login/id permanente');
  if(history.byName[r.name]&&history.byName[r.name]!==r.id)error_(409,'Login já pertence a outro ID');
  const book=SpreadsheetApp.openById(DMAX_SHEET_ID);
  date_(r.expires,book.getSpreadsheetTimeZone());
  if(!current&&state.source.rows.length>=2000)error_(422,'Limite de usuários atingido');
  const index=current?current.row:state.source.sheet.getLastRow()+1;
  const row=[r.id,r.full_name.trim(),r.name,sheetUserChoice_(state.source.sheet,index,4,r.role,true),sheetUserChoice_(state.source.sheet,index,5,r.status,false),r.expires,r.password];
  saveStage_(trace,'write_sheet');
  state.source.sheet.getRange(index,1,1,7).setValues([row.map(v=>sheetText_(v))]);
  saveStage_(trace,'flush_sheet');
  SpreadsheetApp.flush();
  saveStage_(trace,'confirm_write');
  const saved=state.source.sheet.getRange(index,1,1,7).getValues()[0];
  if([0,1,2,3,4,6].some(i=>String(saved[i])!==String(row[i])&&String(saved[i])!==sheetText_(String(row[i]))))error_(503,'Não foi possível confirmar a gravação completa do usuário');
  // Explicit developer changes supersede a queued technical password reset.
  props.deleteProperty('pending.'+r.id);
  saveStage_(trace,'sync_identity');
  unifiedState_(props);
  ordenarLinhas_(state.source.sheet);
  return {ok:true,acknowledged_id:r.id};
}

// Vendored PBKDF2-HMAC-SHA256 implementation; keeps this Code.gs self-contained.
/* SJCL 1.0.8, BSD-2-Clause. Upstream npm sjcl@1.0.8.
SJCL is open. You can use, modify and redistribute it under a BSD
license or under the GNU GPL, version 2.0.

---------------------------------------------------------------------

http://opensource.org/licenses/BSD-2-Clause

Copyright (c) 2009-2015, Emily Stark, Mike Hamburg and Dan Boneh at
Stanford University. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

1. Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright
notice, this list of conditions and the following disclaimer in the
documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

---------------------------------------------------------------------

http://opensource.org/licenses/GPL-2.0

The Stanford Javascript Crypto Library (hosted here on GitHub) is a
project by the Stanford Computer Security Lab to build a secure,
powerful, fast, small, easy-to-use, cross-browser library for
cryptography in Javascript.

Copyright (c) 2009-2015, Emily Stark, Mike Hamburg and Dan Boneh at
Stanford University.

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2 of the License, or (at your
option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
Public License for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, write to the Free Software Foundation, Inc.,
59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
*/
"use strict";var sjcl={cipher:{},hash:{},keyexchange:{},mode:{},misc:{},codec:{},exception:{corrupt:function(a){this.toString=function(){return"CORRUPT: "+this.message};this.message=a},invalid:function(a){this.toString=function(){return"INVALID: "+this.message};this.message=a},bug:function(a){this.toString=function(){return"BUG: "+this.message};this.message=a},notReady:function(a){this.toString=function(){return"NOT READY: "+this.message};this.message=a}}};
/** @fileOverview Arrays of bits, encoded as arrays of Numbers.
 *
 * @author Emily Stark
 * @author Mike Hamburg
 * @author Dan Boneh
 */

/**
 * Arrays of bits, encoded as arrays of Numbers.
 * @namespace
 * @description
 * <p>
 * These objects are the currency accepted by SJCL's crypto functions.
 * </p>
 *
 * <p>
 * Most of our crypto primitives operate on arrays of 4-byte words internally,
 * but many of them can take arguments that are not a multiple of 4 bytes.
 * This library encodes arrays of bits (whose size need not be a multiple of 8
 * bits) as arrays of 32-bit words.  The bits are packed, big-endian, into an
 * array of words, 32 bits at a time.  Since the words are double-precision
 * floating point numbers, they fit some extra data.  We use this (in a private,
 * possibly-changing manner) to encode the number of bits actually  present
 * in the last word of the array.
 * </p>
 *
 * <p>
 * Because bitwise ops clear this out-of-band data, these arrays can be passed
 * to ciphers like AES which want arrays of words.
 * </p>
 */
sjcl.bitArray = {
  /**
   * Array slices in units of bits.
   * @param {bitArray} a The array to slice.
   * @param {Number} bstart The offset to the start of the slice, in bits.
   * @param {Number} bend The offset to the end of the slice, in bits.  If this is undefined,
   * slice until the end of the array.
   * @return {bitArray} The requested slice.
   */
  bitSlice: function (a, bstart, bend) {
    a = sjcl.bitArray._shiftRight(a.slice(bstart/32), 32 - (bstart & 31)).slice(1);
    return (bend === undefined) ? a : sjcl.bitArray.clamp(a, bend-bstart);
  },

  /**
   * Extract a number packed into a bit array.
   * @param {bitArray} a The array to slice.
   * @param {Number} bstart The offset to the start of the slice, in bits.
   * @param {Number} blength The length of the number to extract.
   * @return {Number} The requested slice.
   */
  extract: function(a, bstart, blength) {
    // FIXME: this Math.floor is not necessary at all, but for some reason
    // seems to suppress a bug in the Chromium JIT.
    var x, sh = Math.floor((-bstart-blength) & 31);
    if ((bstart + blength - 1 ^ bstart) & -32) {
      // it crosses a boundary
      x = (a[bstart/32|0] << (32 - sh)) ^ (a[bstart/32+1|0] >>> sh);
    } else {
      // within a single word
      x = a[bstart/32|0] >>> sh;
    }
    return x & ((1<<blength) - 1);
  },

  /**
   * Concatenate two bit arrays.
   * @param {bitArray} a1 The first array.
   * @param {bitArray} a2 The second array.
   * @return {bitArray} The concatenation of a1 and a2.
   */
  concat: function (a1, a2) {
    if (a1.length === 0 || a2.length === 0) {
      return a1.concat(a2);
    }

    var last = a1[a1.length-1], shift = sjcl.bitArray.getPartial(last);
    if (shift === 32) {
      return a1.concat(a2);
    } else {
      return sjcl.bitArray._shiftRight(a2, shift, last|0, a1.slice(0,a1.length-1));
    }
  },

  /**
   * Find the length of an array of bits.
   * @param {bitArray} a The array.
   * @return {Number} The length of a, in bits.
   */
  bitLength: function (a) {
    var l = a.length, x;
    if (l === 0) { return 0; }
    x = a[l - 1];
    return (l-1) * 32 + sjcl.bitArray.getPartial(x);
  },

  /**
   * Truncate an array.
   * @param {bitArray} a The array.
   * @param {Number} len The length to truncate to, in bits.
   * @return {bitArray} A new array, truncated to len bits.
   */
  clamp: function (a, len) {
    if (a.length * 32 < len) { return a; }
    a = a.slice(0, Math.ceil(len / 32));
    var l = a.length;
    len = len & 31;
    if (l > 0 && len) {
      a[l-1] = sjcl.bitArray.partial(len, a[l-1] & 0x80000000 >> (len-1), 1);
    }
    return a;
  },

  /**
   * Make a partial word for a bit array.
   * @param {Number} len The number of bits in the word.
   * @param {Number} x The bits.
   * @param {Number} [_end=0] Pass 1 if x has already been shifted to the high side.
   * @return {Number} The partial word.
   */
  partial: function (len, x, _end) {
    if (len === 32) { return x; }
    return (_end ? x|0 : x << (32-len)) + len * 0x10000000000;
  },

  /**
   * Get the number of bits used by a partial word.
   * @param {Number} x The partial word.
   * @return {Number} The number of bits used by the partial word.
   */
  getPartial: function (x) {
    return Math.round(x/0x10000000000) || 32;
  },

  /**
   * Compare two arrays for equality in a predictable amount of time.
   * @param {bitArray} a The first array.
   * @param {bitArray} b The second array.
   * @return {boolean} true if a == b; false otherwise.
   */
  equal: function (a, b) {
    if (sjcl.bitArray.bitLength(a) !== sjcl.bitArray.bitLength(b)) {
      return false;
    }
    var x = 0, i;
    for (i=0; i<a.length; i++) {
      x |= a[i]^b[i];
    }
    return (x === 0);
  },

  /** Shift an array right.
   * @param {bitArray} a The array to shift.
   * @param {Number} shift The number of bits to shift.
   * @param {Number} [carry=0] A byte to carry in
   * @param {bitArray} [out=[]] An array to prepend to the output.
   * @private
   */
  _shiftRight: function (a, shift, carry, out) {
    var i, last2=0, shift2;
    if (out === undefined) { out = []; }

    for (; shift >= 32; shift -= 32) {
      out.push(carry);
      carry = 0;
    }
    if (shift === 0) {
      return out.concat(a);
    }

    for (i=0; i<a.length; i++) {
      out.push(carry | a[i]>>>shift);
      carry = a[i] << (32-shift);
    }
    last2 = a.length ? a[a.length-1] : 0;
    shift2 = sjcl.bitArray.getPartial(last2);
    out.push(sjcl.bitArray.partial(shift+shift2 & 31, (shift + shift2 > 32) ? carry : out.pop(),1));
    return out;
  },

  /** xor a block of 4 words together.
   * @private
   */
  _xor4: function(x,y) {
    return [x[0]^y[0],x[1]^y[1],x[2]^y[2],x[3]^y[3]];
  },

  /** byteswap a word array inplace.
   * (does not handle partial words)
   * @param {sjcl.bitArray} a word array
   * @return {sjcl.bitArray} byteswapped array
   */
  byteswapM: function(a) {
    var i, v, m = 0xff00;
    for (i = 0; i < a.length; ++i) {
      v = a[i];
      a[i] = (v >>> 24) | ((v >>> 8) & m) | ((v & m) << 8) | (v << 24);
    }
    return a;
  }
};

/** @fileOverview Bit array codec implementations.
 *
 * @author Emily Stark
 * @author Mike Hamburg
 * @author Dan Boneh
 */

/**
 * UTF-8 strings
 * @namespace
 */
sjcl.codec.utf8String = {
  /** Convert from a bitArray to a UTF-8 string. */
  fromBits: function (arr) {
    var out = "", bl = sjcl.bitArray.bitLength(arr), i, tmp;
    for (i=0; i<bl/8; i++) {
      if ((i&3) === 0) {
        tmp = arr[i/4];
      }
      out += String.fromCharCode(tmp >>> 8 >>> 8 >>> 8);
      tmp <<= 8;
    }
    return decodeURIComponent(escape(out));
  },

  /** Convert from a UTF-8 string to a bitArray. */
  toBits: function (str) {
    str = unescape(encodeURIComponent(str));
    var out = [], i, tmp=0;
    for (i=0; i<str.length; i++) {
      tmp = tmp << 8 | str.charCodeAt(i);
      if ((i&3) === 3) {
        out.push(tmp);
        tmp = 0;
      }
    }
    if (i&3) {
      out.push(sjcl.bitArray.partial(8*(i&3), tmp));
    }
    return out;
  }
};

/** @fileOverview Bit array codec implementations.
 *
 * @author Emily Stark
 * @author Mike Hamburg
 * @author Dan Boneh
 */

/**
 * Hexadecimal
 * @namespace
 */
sjcl.codec.hex = {
  /** Convert from a bitArray to a hex string. */
  fromBits: function (arr) {
    var out = "", i;
    for (i=0; i<arr.length; i++) {
      out += ((arr[i]|0)+0xF00000000000).toString(16).substr(4);
    }
    return out.substr(0, sjcl.bitArray.bitLength(arr)/4);//.replace(/(.{8})/g, "$1 ");
  },
  /** Convert from a hex string to a bitArray. */
  toBits: function (str) {
    var i, out=[], len;
    str = str.replace(/\s|0x/g, "");
    len = str.length;
    str = str + "00000000";
    for (i=0; i<str.length; i+=8) {
      out.push(parseInt(str.substr(i,8),16)^0);
    }
    return sjcl.bitArray.clamp(out, len*4);
  }
};


/** @fileOverview Javascript SHA-256 implementation.
 *
 * An older version of this implementation is available in the public
 * domain, but this one is (c) Emily Stark, Mike Hamburg, Dan Boneh,
 * Stanford University 2008-2010 and BSD-licensed for liability
 * reasons.
 *
 * Special thanks to Aldo Cortesi for pointing out several bugs in
 * this code.
 *
 * @author Emily Stark
 * @author Mike Hamburg
 * @author Dan Boneh
 */

/**
 * Context for a SHA-256 operation in progress.
 * @constructor
 */
sjcl.hash.sha256 = function (hash) {
  if (!this._key[0]) { this._precompute(); }
  if (hash) {
    this._h = hash._h.slice(0);
    this._buffer = hash._buffer.slice(0);
    this._length = hash._length;
  } else {
    this.reset();
  }
};

/**
 * Hash a string or an array of words.
 * @static
 * @param {bitArray|String} data the data to hash.
 * @return {bitArray} The hash value, an array of 16 big-endian words.
 */
sjcl.hash.sha256.hash = function (data) {
  return (new sjcl.hash.sha256()).update(data).finalize();
};

sjcl.hash.sha256.prototype = {
  /**
   * The hash's block size, in bits.
   * @constant
   */
  blockSize: 512,

  /**
   * Reset the hash state.
   * @return this
   */
  reset:function () {
    this._h = this._init.slice(0);
    this._buffer = [];
    this._length = 0;
    return this;
  },

  /**
   * Input several words to the hash.
   * @param {bitArray|String} data the data to hash.
   * @return this
   */
  update: function (data) {
    if (typeof data === "string") {
      data = sjcl.codec.utf8String.toBits(data);
    }
    var i, b = this._buffer = sjcl.bitArray.concat(this._buffer, data),
        ol = this._length,
        nl = this._length = ol + sjcl.bitArray.bitLength(data);
    if (nl > 9007199254740991){
      throw new sjcl.exception.invalid("Cannot hash more than 2^53 - 1 bits");
    }

    if (typeof Uint32Array !== 'undefined') {
  var c = new Uint32Array(b);
      var j = 0;
      for (i = 512+ol - ((512+ol) & 511); i <= nl; i+= 512) {
            this._block(c.subarray(16 * j, 16 * (j+1)));
            j += 1;
      }
      b.splice(0, 16 * j);
    } else {
  for (i = 512+ol - ((512+ol) & 511); i <= nl; i+= 512) {
            this._block(b.splice(0,16));
        }
    }
    return this;
  },

  /**
   * Complete hashing and output the hash value.
   * @return {bitArray} The hash value, an array of 8 big-endian words.
   */
  finalize:function () {
    var i, b = this._buffer, h = this._h;

    // Round out and push the buffer
    b = sjcl.bitArray.concat(b, [sjcl.bitArray.partial(1,1)]);

    // Round out the buffer to a multiple of 16 words, less the 2 length words.
    for (i = b.length + 2; i & 15; i++) {
      b.push(0);
    }

    // append the length
    b.push(Math.floor(this._length / 0x100000000));
    b.push(this._length | 0);

    while (b.length) {
      this._block(b.splice(0,16));
    }

    this.reset();
    return h;
  },

  /**
   * The SHA-256 initialization vector, to be precomputed.
   * @private
   */
  _init:[],
  /*
  _init:[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19],
  */

  /**
   * The SHA-256 hash key, to be precomputed.
   * @private
   */
  _key:[],
  /*
  _key:
    [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
     0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
     0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
     0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
     0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
     0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
     0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
     0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2],
  */


  /**
   * Function to precompute _init and _key.
   * @private
   */
  _precompute: function () {
    var i = 0, prime = 2, factor, isPrime;

    function frac(x) { return (x-Math.floor(x)) * 0x100000000 | 0; }

    for (; i<64; prime++) {
      isPrime = true;
      for (factor=2; factor*factor <= prime; factor++) {
        if (prime % factor === 0) {
          isPrime = false;
          break;
        }
      }
      if (isPrime) {
        if (i<8) {
          this._init[i] = frac(Math.pow(prime, 1/2));
        }
        this._key[i] = frac(Math.pow(prime, 1/3));
        i++;
      }
    }
  },

  /**
   * Perform one cycle of SHA-256.
   * @param {Uint32Array|bitArray} w one block of words.
   * @private
   */
  _block:function (w) {
    var i, tmp, a, b,
      h = this._h,
      k = this._key,
      h0 = h[0], h1 = h[1], h2 = h[2], h3 = h[3],
      h4 = h[4], h5 = h[5], h6 = h[6], h7 = h[7];

    /* Rationale for placement of |0 :
     * If a value can overflow is original 32 bits by a factor of more than a few
     * million (2^23 ish), there is a possibility that it might overflow the
     * 53-bit mantissa and lose precision.
     *
     * To avoid this, we clamp back to 32 bits by |'ing with 0 on any value that
     * propagates around the loop, and on the hash state h[].  I don't believe
     * that the clamps on h4 and on h0 are strictly necessary, but it's close
     * (for h4 anyway), and better safe than sorry.
     *
     * The clamps on h[] are necessary for the output to be correct even in the
     * common case and for short inputs.
     */
    for (i=0; i<64; i++) {
      // load up the input word for this round
      if (i<16) {
        tmp = w[i];
      } else {
        a   = w[(i+1 ) & 15];
        b   = w[(i+14) & 15];
        tmp = w[i&15] = ((a>>>7  ^ a>>>18 ^ a>>>3  ^ a<<25 ^ a<<14) +
                         (b>>>17 ^ b>>>19 ^ b>>>10 ^ b<<15 ^ b<<13) +
                         w[i&15] + w[(i+9) & 15]) | 0;
      }

      tmp = (tmp + h7 + (h4>>>6 ^ h4>>>11 ^ h4>>>25 ^ h4<<26 ^ h4<<21 ^ h4<<7) +  (h6 ^ h4&(h5^h6)) + k[i]); // | 0;

      // shift register
      h7 = h6; h6 = h5; h5 = h4;
      h4 = h3 + tmp | 0;
      h3 = h2; h2 = h1; h1 = h0;

      h0 = (tmp +  ((h1&h2) ^ (h3&(h1^h2))) + (h1>>>2 ^ h1>>>13 ^ h1>>>22 ^ h1<<30 ^ h1<<19 ^ h1<<10)) | 0;
    }

    h[0] = h[0]+h0 | 0;
    h[1] = h[1]+h1 | 0;
    h[2] = h[2]+h2 | 0;
    h[3] = h[3]+h3 | 0;
    h[4] = h[4]+h4 | 0;
    h[5] = h[5]+h5 | 0;
    h[6] = h[6]+h6 | 0;
    h[7] = h[7]+h7 | 0;
  }
};



/** @fileOverview HMAC implementation.
 *
 * @author Emily Stark
 * @author Mike Hamburg
 * @author Dan Boneh
 */

/** HMAC with the specified hash function.
 * @constructor
 * @param {bitArray} key the key for HMAC.
 * @param {Object} [Hash=sjcl.hash.sha256] The hash function to use.
 */
sjcl.misc.hmac = function (key, Hash) {
  this._hash = Hash = Hash || sjcl.hash.sha256;
  var exKey = [[],[]], i,
      bs = Hash.prototype.blockSize / 32;
  this._baseHash = [new Hash(), new Hash()];

  if (key.length > bs) {
    key = Hash.hash(key);
  }

  for (i=0; i<bs; i++) {
    exKey[0][i] = key[i]^0x36363636;
    exKey[1][i] = key[i]^0x5C5C5C5C;
  }

  this._baseHash[0].update(exKey[0]);
  this._baseHash[1].update(exKey[1]);
  this._resultHash = new Hash(this._baseHash[0]);
};

/** HMAC with the specified hash function.  Also called encrypt since it's a prf.
 * @param {bitArray|String} data The data to mac.
 */
sjcl.misc.hmac.prototype.encrypt = sjcl.misc.hmac.prototype.mac = function (data) {
  if (!this._updated) {
    this.update(data);
    return this.digest(data);
  } else {
    throw new sjcl.exception.invalid("encrypt on already updated hmac called!");
  }
};

sjcl.misc.hmac.prototype.reset = function () {
  this._resultHash = new this._hash(this._baseHash[0]);
  this._updated = false;
};

sjcl.misc.hmac.prototype.update = function (data) {
  this._updated = true;
  this._resultHash.update(data);
};

sjcl.misc.hmac.prototype.digest = function () {
  var w = this._resultHash.finalize(), result = new (this._hash)(this._baseHash[1]).update(w).finalize();

  this.reset();

  return result;
};

/** @fileOverview Password-based key-derivation function, version 2.0.
 *
 * @author Emily Stark
 * @author Mike Hamburg
 * @author Dan Boneh
 */

/** Password-Based Key-Derivation Function, version 2.0.
 *
 * Generate keys from passwords using PBKDF2-HMAC-SHA256.
 *
 * This is the method specified by RSA's PKCS #5 standard.
 *
 * @param {bitArray|String} password  The password.
 * @param {bitArray|String} salt The salt.  Should have lots of entropy.
 * @param {Number} [count=1000] The number of iterations.  Higher numbers make the function slower but more secure.
 * @param {Number} [length] The length of the derived key.  Defaults to the
                            output size of the hash function.
 * @param {Object} [Prff=sjcl.misc.hmac] The pseudorandom function family.
 * @return {bitArray} the derived key.
 */
sjcl.misc.pbkdf2 = function (password, salt, count, length, Prff) {
  count = count || 10000;

  if (length < 0 || count < 0) {
    throw new sjcl.exception.invalid("invalid params to pbkdf2");
  }

  if (typeof password === "string") {
    password = sjcl.codec.utf8String.toBits(password);
  }

  if (typeof salt === "string") {
    salt = sjcl.codec.utf8String.toBits(salt);
  }

  Prff = Prff || sjcl.misc.hmac;

  var prf = new Prff(password),
      u, ui, i, j, k, out = [], b = sjcl.bitArray;

  for (k = 1; 32 * out.length < (length || 1); k++) {
    u = ui = prf.encrypt(b.concat(salt,[k]));

    for (i=1; i<count; i++) {
      ui = prf.encrypt(ui);
      for (j=0; j<ui.length; j++) {
        u[j] ^= ui[j];
      }
    }

    out = out.concat(u);
  }

  if (length) { out = b.clamp(out, length); }

  return out;
};

/** D-Max Acesso Web 1.0. No device credentials or verifiers enter the browser. */
function portalReply_(operation,trace){
  let lock,acquired=false;
  try {
    lock=LockService.getScriptLock();
    acquired=lock.tryLock(5000);
    if(!acquired)error_(503,'Ocupado');
    const result=Object.assign({ok:true},operation(PropertiesService.getScriptProperties()));
    saveStage_(trace,'complete');
    return result;
  } catch(e) {
    const code=e.code||503;
    if(trace){
      const kind=['Error','TypeError','ReferenceError','RangeError','SyntaxError','Exception'].includes(e.name)?e.name:'Error';
      console.error('DMAX_SAVE_FAILURE '+JSON.stringify({revision:DMAX_SCRIPT_REVISION,stage:trace.stage,code:code,kind:kind}));
    }
    const messages={401:'Login, senha ou sessão inválidos. Entre novamente.',403:'Seu perfil não permite esta operação.',409:'Conflito de ID/login. Preserve a identidade existente ou crie outra conta com novo login.',422:'Confira os campos e a aba Usuarios.',429:'Muitas tentativas. Aguarde cinco minutos.',503:'Não foi possível consultar a planilha. Tente novamente.'};
    const reply={ok:false,code:code,message:messages[code]||messages[503]};
    // Only fixed identifiers cross the API boundary, never exception details.
    if(code===422)reply.diagnostic=['directory_not_prepared','users_headers','users_record','remote_headers','remote_record'].includes(e.diagnostic)?e.diagnostic:'validation';
    return reply;
  } finally {if(acquired)lock.releaseLock();}
}
function portalRoster_(props){
  const book=SpreadsheetApp.openById(DMAX_SHEET_ID),sheet=unifiedSheet_(props);
  if(!sheet)error_(422,'Prepare a aba Usuarios','directory_not_prepared');
  let rows;
  try{rows=userRows_(sheet,book);}catch(e){if(e.code===422&&!e.diagnostic)e.diagnostic='users_record';throw e;}
  const history=historicalUsers_(props.getProperties()),seen=new Set();
  const records=rows.map(r=>{
    const old=history.byId[r.id];
    if(old&&old.name!==r.name)error_(409,'Identidade permanente');
    if(history.byName[r.name]&&history.byName[r.name]!==r.id)error_(409,'Login histórico');
    seen.add(r.id);
    return Object.assign({},r,{must_change:r.password===DMAX_DEFAULT_HASH||Boolean(old&&old.password===r.password&&old.must_change)});
  });
  Object.values(history.byId).forEach(r=>{if(!seen.has(r.id))records.push(Object.assign({},r,{active:false,deleted:true}));});
  return records;
}
function portalPublic_(r){
  return {id:r.id,name:r.name,full_name:r.full_name,role:r.role,active:r.active,deleted:r.deleted,expires_at:r.expires_at,credential_pending:Boolean(r.credential_pending),must_change:Boolean(r.must_change)};
}
function portalUsable_(r,allowChange=false){
  return Boolean(r&&['developer','commercial','technician'].includes(r.role)&&r.active&&!r.deleted&&(!r.must_change||allowChange)&&(r.expires_at===null||r.expires_at>Date.now()/1000));
}
function portalFingerprint_(r){
  return sha_(JSON.stringify([r.id,r.name,r.role,r.password,r.active,r.deleted,r.expires_at,Boolean(r.must_change)]));
}
function portalSession_(props,token,allowChange=false){
  if(typeof token!=='string'||!/^[0-9a-f]{64}$/.test(token))error_(401,'Sessão inválida');
  const key='portal.session.'+sha_(token),session=JSON.parse(props.getProperty(key)||'null');
  if(!session||session.until<=Date.now()/1000){props.deleteProperty(key);error_(401,'Sessão encerrada');}
  const rows=portalRoster_(props),actor=rows.find(r=>r.id===session.id);
  if(!portalUsable_(actor,true)||portalFingerprint_(actor)!==session.fingerprint){props.deleteProperty(key);error_(401,'Acesso alterado');}
  if(actor.must_change&&!allowChange)error_(403,'Troca de senha obrigatória');
  session.until=Date.now()/1000+(actor.role==='commercial'?900:3600);
  props.setProperty(key,JSON.stringify(session));
  return {actor:actor,rows:rows};
}
function portalLogin(name,password){
  return portalReply_(props=>{
    if(typeof name!=='string'||!(/^[a-z0-9._-]{3,40}$/).test(name.trim().toLowerCase())||typeof password!=='string'||!password||password.length>200)error_(401,'Credenciais inválidas');
    name=name.trim().toLowerCase();
    const now=Date.now()/1000,all=props.getProperties();
    Object.keys(all).filter(k=>k.startsWith('portal.attempt.')||k.startsWith('portal.session.')).forEach(k=>{
      const r=JSON.parse(all[k]);if((k.startsWith('portal.session.')?r.until:r.at+300)<=now)props.deleteProperty(k);
    });
    const attemptKey='portal.attempt.'+sha_(name),globalKey='portal.attempt.global';
    const counter=k=>{const old=JSON.parse(props.getProperty(k)||'null');return old&&now-old.at<300?old:{at:now,count:0};};
    const attempt=counter(attemptKey),global=counter(globalKey);
    if(attempt.count>=5||global.count>=60)error_(429,'Limite de tentativas');
    attempt.count++;global.count++;props.setProperty(attemptKey,JSON.stringify(attempt));props.setProperty(globalKey,JSON.stringify(global));
    const actor=portalRoster_(props).find(r=>r.name===name);
    const valid=verifyPlatformPassword_(password,actor?actor.password:DMAX_DEFAULT_HASH);
    if(!valid||!portalUsable_(actor,true))error_(401,'Credenciais inválidas');
    const active=Object.keys(props.getProperties()).filter(k=>k.startsWith('portal.session.'));
    if(active.length>=64)error_(503,'Limite de sessões');
    const token=(Utilities.getUuid()+Utilities.getUuid()).replace(/-/g,'');
    props.setProperty('portal.session.'+sha_(token),JSON.stringify({id:actor.id,fingerprint:portalFingerprint_(actor),until:now+(actor.role==='commercial'?900:3600)}));
    props.deleteProperty(attemptKey);
    return {token:token,user:portalPublic_(actor)};
  });
}
function portalState(token){
  return portalReply_(props=>({user:portalPublic_(portalSession_(props,token,true).actor)}));
}
function portalLogout(token){
  return portalReply_(props=>{
    if(typeof token==='string'&&/^[0-9a-f]{64}$/.test(token))props.deleteProperty('portal.session.'+sha_(token));
    return {};
  });
}
function portalClients(token){
  return portalReply_(props=>{
    portalSession_(props,token);
    let data;
    try{data=remoteDirectory_();}catch(e){if(e.code===422&&!e.diagnostic)e.diagnostic='remote_record';throw e;}
    return {clients:data.clients,fetched_at:Date.now()/1000};
  });
}
function portalMembers(token){
  return portalReply_(props=>{
    const session=portalSession_(props,token);
    if(session.actor.role!=='developer')error_(403,'Somente desenvolvedor');
    return {users:session.rows.map(portalPublic_)};
  });
}
function portalSaveUser(token,fields){
  const trace={stage:'lock'};
  return portalReply_(props=>{
    saveStage_(trace,'validate_session');
    const session=portalSession_(props,token),actor=session.actor;
    if(actor.role!=='developer')error_(403,'Somente desenvolvedor');
    if(!fields||typeof fields!=='object'||typeof fields.actor_password!=='string'||fields.actor_password.length>200)error_(422,'Campos inválidos');
    saveStage_(trace,'validate_fields');
    const old=session.rows.find(r=>r.id===fields.id);
    if(fields.password||fields.confirmation)error_(422,'O Windows só cria ou redefine a senha inicial');
    if(fields.reset_password!==undefined&&typeof fields.reset_password!=='boolean')error_(422,'Redefinição inválida');
    const reset=!old||fields.reset_password===true;
    const encoded=reset?DMAX_DEFAULT_HASH:old.password;
    const record={id:fields.id||'USR-'+Utilities.getUuid().replace(/-/g,'').slice(0,16),name:fields.name,full_name:fields.full_name,role:fields.role,status:fields.status,expires:fields.expires||'',password:encoded};
    const result=bridgeManageUser_(props,{controller_id:'WEB-'+actor.id,actor_login:actor.name,actor_password:fields.actor_password,record:record},trace);
    // A developer can reset the initial credential, never choose another user's password.
    return {acknowledged_id:result.acknowledged_id,password_reset:reset,message:reset?'Senha redefinida para 12345678. A troca é obrigatória no primeiro acesso.':'Usuário atualizado; senha preservada.'};
  },trace);
}

/** Desktop endpoints authenticate individual accounts; never accept a device key as identity. */
function portalChangePassword(token,fields){
  const trace={stage:'lock'};
  return portalReply_(props=>{
    saveStage_(trace,'validate_session');
    const session=portalSession_(props,token,true),actor=session.actor;
    if(!fields||typeof fields.password!=='string'||fields.password.length<8||fields.password.length>200||fields.password==='12345678'||fields.password!==fields.confirmation)error_(422,'Escolha outra senha com 8 a 200 caracteres');
    saveStage_(trace,'generate_verifier');
    const salt=Utilities.getUuid().replace(/-/g,'');
    const encoded='pbkdf2_sha256$600000$'+salt+'$'+sjcl.codec.hex.fromBits(sjcl.misc.pbkdf2(fields.password,sjcl.codec.hex.toBits(salt),600000,256));
    const sheet=unifiedSheet_(props),row=session.rows.find(r=>r.id===actor.id);
    if(!sheet||!row||!row.row)error_(409,'Conta não encontrada');
    saveStage_(trace,'write_sheet');sheet.getRange(row.row,7,1,1).setValues([[encoded]]);SpreadsheetApp.flush();
    if(String(sheet.getRange(row.row,7,1,1).getValues()[0][0])!==encoded)error_(503,'Senha não confirmada');
    props.deleteProperty('pending.'+actor.id);
    const updated=unifiedState_(props).records.find(r=>r.id===actor.id);
    if(updated.must_change)error_(503,'Troca não confirmada');
    props.deleteProperty('portal.session.'+sha_(token));
    const next=(Utilities.getUuid()+Utilities.getUuid()).replace(/-/g,'');
    props.setProperty('portal.session.'+sha_(next),JSON.stringify({id:actor.id,fingerprint:portalFingerprint_(updated),until:Date.now()/1000+(actor.role==='commercial'?900:3600)}));
    return {token:next,user:portalPublic_(updated)};
  },trace);
}
const DMAX_DEVICE_HEADERS=['controller_id','instalacao','url','ultimo_estado_informado','situacao','ultima_comunicacao','ultimo_sinal_tunel','revisao','aviso_em','prazo_final','mensagem'];
function deviceLayout_(sheet){return headersMatch_(sheet.getRange(1,1,1,11).getValues()[0],DMAX_DEVICE_HEADERS);}
function remoteRows_(sheet){
  const rows=sheet.getLastRow()>1?sheet.getRange(2,1,sheet.getLastRow()-1,11).getValues():[];
  return deviceLayout_(sheet)?rows.map(r=>[...r.slice(0,4),...r.slice(5,8),r[4],...r.slice(8,11)]):rows;
}
function deviceRows_(){
  const sheet=remoteSheet_(),original=remoteRows_(sheet).filter(r=>r.some(v=>String(v).trim()!==''));
  const props=PropertiesService.getScriptProperties();
  const rows=original.map(r=>{const old=JSON.parse(props.getProperty('subscription.'+String(r[0]).trim())||'null');return [...r.slice(0,4),r[7]||(old&&old.state==='pending'?'pendente':'ativo'),...r.slice(4,7),...r.slice(8,11)];});
  const book=SpreadsheetApp.openById(DMAX_SHEET_ID),legacy=book.getSheetByName('Assinaturas');
  const unified=deviceLayout_(sheet)||headersMatch_(sheet.getRange(1,8,1,4).getValues()[0],['situacao','aviso_em','prazo_final','mensagem']);
  if(!unified&&(sheet.getRange(1,8,1,4).getValues()[0].some(v=>String(v).trim()!=='')||original.some(r=>r.slice(7).some(v=>String(v).trim()!==''))))error_(422,'Colunas adicionais ocupadas; preserve os dados antes de organizar');
  if(!unified&&legacy&&legacy.getLastRow()>1){
    if(!headersMatch_(legacy.getRange(1,1,1,6).getValues()[0],DMAX_SUB_HEADERS))error_(422,'Assinaturas incompatíveis');
    const seen=new Set();legacy.getRange(2,1,legacy.getLastRow()-1,6).getValues().forEach(r=>{
      const id=String(r[0]).trim();if(!id)return;if(seen.has(id))error_(409,'D-Max duplicado');seen.add(id);
      let row=rows.find(v=>String(v[0]).trim()===id);if(!row){row=[id,r[1],'','DESCONECTADO','ativo','','',0,'','',''];rows.push(row);}
      row[4]=r[2];row.splice(8,3,...r.slice(3,6));
    });
  }
  const seen=new Set();
  rows.forEach(r=>{
    if(r.every(v=>String(v).trim()===''))return;
    const id=String(r[0]).trim();if(!/^[A-Za-z0-9_-]{1,100}$/.test(id)||seen.has(id))error_(409,'D-Max inválido ou duplicado');seen.add(id);
    r[4]=String(r[4]).trim().toLowerCase();if(r[4]==='regular')r[4]='ativo';
    if(!['ativo','pendente'].includes(r[4]))error_(422,'Situação inválida');
    if(!Number.isSafeInteger(Number(r[7]))||Number(r[7])<0)error_(422,'Revisão inválida');
  });
  return {sheet,rows};
}
function migrateDevices_(){
  const state=deviceRows_();if(deviceLayout_(state.sheet))return state;
  const book=SpreadsheetApp.openById(DMAX_SHEET_ID);
  state.sheet.copyTo(book).setName('Backup_equipamentos_'+Date.now()+'_'+Utilities.getUuid().slice(0,8)).hideSheet();
  const range=state.sheet.getRange(1,1,state.rows.length+1,11);
  if(typeof range.clearDataValidations==='function')range.clearDataValidations();
  range.setValues([DMAX_DEVICE_HEADERS,...state.rows]);SpreadsheetApp.flush();
  if(!deviceLayout_(state.sheet))error_(503,'Migração não confirmada');
  return state;
}
function organizarEquipamentos(){
  const ui=SpreadsheetApp.getUi(),lock=LockService.getScriptLock();if(!lock.tryLock(10000))throw Error('Ocupado');
  try{migrateDevices_();ui.alert('Equipamentos organizados. Coluna E: ativo ou pendente. Backup preservado; horários e prazos mantidos.');}finally{lock.releaseLock();}
}
function developerSession_(props,token){const s=portalSession_(props,token);if(s.actor.role!=='developer')error_(403,'Somente desenvolvedor');return s;}
function portalDevices(token){return portalReply_(props=>{
  developerSession_(props,token);
  return {devices:deviceRows_().rows.filter(r=>String(r[0]).trim()).map(r=>({controller_id:r[0],site_name:r[1],url:r[2],connected:r[3]==='CONECTADO',status:r[4],last_seen:r[5],heartbeat:r[6],revision:r[7],notice:r[8],deadline:r[9],message:r[10],authorized:Boolean(props.getProperty('device.'+r[0]))}))};
});}
function portalSaveDevice(token,f){return portalReply_(props=>{
  developerSession_(props,token);
  if(!f||typeof f.controller_id!=='string'||!/^[A-Za-z0-9_-]{1,100}$/.test(f.controller_id)||typeof f.site_name!=='string'||!f.site_name.trim()||f.site_name.length>100||!['ativo','pendente'].includes(f.status)||typeof f.url!=='string'||f.url&&!/^https:\/\/[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.trycloudflare\.com$/.test(f.url)||['https://api.trycloudflare.com','https://www.trycloudflare.com'].includes(f.url)||typeof f.message!=='string'||f.message.length>300)error_(422,'Equipamento inválido');
  const state=migrateDevices_();let index=state.rows.findIndex(r=>String(r[0])===f.controller_id),row=index<0?[f.controller_id,f.site_name,f.url,'DESCONECTADO',f.status,'','',0,'','',f.message]:[...state.rows[index]];
  if(index<0&&state.rows.length>=1000)error_(422,'Limite de equipamentos');
  row[1]=f.site_name.trim();row[2]=f.url;row[4]=f.status;row[10]=f.message;
  const destination=index<0?state.sheet.getLastRow()+1:index+2;
  state.sheet.getRange(destination,1,1,11).setValues([row.map(v=>typeof v==='string'?sheetText_(v):v)]);SpreadsheetApp.flush();
  const saved=state.sheet.getRange(destination,1,1,11).getValues()[0];
  if([0,1,2,4,10].some(i=>String(saved[i])!==String(row[i])&&String(saved[i])!==sheetText_(String(row[i]))))error_(503,'Cadastro de equipamento não confirmado');
  let key='';if(!props.getProperty('device.'+f.controller_id)){key=(Utilities.getUuid()+Utilities.getUuid()+Utilities.getUuid()).replace(/-/g,'');props.setProperty('device.'+f.controller_id,sha_(key));}
  ordenarLinhas_(state.sheet);
  return {controller_id:f.controller_id,key,message:key?'Equipamento cadastrado. Configure esta chave no D-Max instalado.':'Equipamento atualizado. A chave existente foi preservada.'};
});}
function portalOpenClient(token,id){return portalReply_(props=>{
  const session=portalSession_(props,token),client=remoteDirectory_().clients.find(c=>c.controller_id===id);if(!client)error_(404,'Cliente indisponível');
  const now=Date.now()/1000,all=props.getProperties();let count=0;
  Object.keys(all).filter(k=>k.startsWith('portal.handoff.')).forEach(k=>{const v=JSON.parse(all[k]);if(v.until<=now)props.deleteProperty(k);else count++;});
  if(count>=128)error_(429,'Muitos acessos');
  const ticket=(Utilities.getUuid()+Utilities.getUuid()).replace(/-/g,'');
  props.setProperty('portal.handoff.'+sha_(ticket),JSON.stringify({id:session.actor.id,controller_id:id,fingerprint:portalFingerprint_(session.actor),session_key:sha_(token),until:now+60}));
  return {url:client.url+'/remote/sso#ticket='+ticket};
});}
function redeemLogin_(props,data){
  if(typeof data.ticket!=='string'||!/^[0-9a-f]{64}$/.test(data.ticket))error_(401,'Passe inválido');
  const key='portal.handoff.'+sha_(data.ticket),record=JSON.parse(props.getProperty(key)||'null'),now=Date.now()/1000;
  if(!record||record.until<=now||record.controller_id!==data.controller_id)error_(401,'Passe expirado ou de outro equipamento');
  props.deleteProperty(key);
  const session=JSON.parse(props.getProperty('portal.session.'+record.session_key)||'null');
  const actor=portalRoster_(props).find(r=>r.id===record.id);
  if(!session||session.until<=now||session.id!==record.id||!portalUsable_(actor)||portalFingerprint_(actor)!==record.fingerprint)error_(401,'Acesso alterado');
  return {ok:true,user:portalPublic_(actor),snapshot:unifiedSnapshot_(props)};
}
function desktopRequest_(data){
  switch(data.action){
    case 'desktop_login':return portalLogin(data.name,data.password);
    case 'desktop_state':return portalState(data.token);
    case 'desktop_logout':return portalLogout(data.token);
    case 'desktop_clients':return portalClients(data.token);
    case 'desktop_members':return portalMembers(data.token);
    case 'desktop_change_password':return portalChangePassword(data.token,data.fields);
    case 'desktop_save_user':return portalSaveUser(data.token,data.fields);
    case 'desktop_devices':return portalDevices(data.token);
    case 'desktop_save_device':return portalSaveDevice(data.token,data.fields);
    case 'desktop_open_client':return portalOpenClient(data.token,data.controller_id);
    default:return {ok:false,code:404,message:'Operação desktop desconhecida'};
  }
}
