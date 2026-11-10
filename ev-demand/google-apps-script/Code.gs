/** D-Max global directory. Bound to Google Sheets; no external server required. */
const DMAX_SHEET_ID = '17HCp2CX3eUZXqQsTkTNDZvrLkGqzZQrJkCfeHo-toPQ';
const DMAX_TAB = 'Tecnicos';
const DMAX_HEADERS = ['id', 'nome', 'login', 'situacao', 'valido_ate'];
const DMAX_DEFAULT_HASH = 'pbkdf2_sha256$600000$0cc644386557630153579d018267d636$07eb3cfc2778a1ee08fa321b86c897f72237f6749cecda0eee2ea788cb678c53';

function onOpen() {
  SpreadsheetApp.getUi().createMenu('D-Max')
    .addItem('Preparar aba Tecnicos', 'prepararTecnicos')
    .addItem('Preparar aba Assinaturas', 'prepararAssinaturas')
    .addItem('Preparar diretório de acesso remoto', 'prepararRemoto')
    .addItem('Permitir busca de clientes remotos', 'permitirBuscaRemota')
    .addItem('Revogar busca de clientes remotos', 'revogarBuscaRemota')
    .addItem('Autorizar um D-Max', 'autorizarDMax')
    .addItem('Revogar chave de um D-Max', 'revogarDMax').addToUi();
}

function prepararTecnicos() {
  const book = SpreadsheetApp.openById(DMAX_SHEET_ID);
  let sheet = book.getSheetByName(DMAX_TAB);
  if (!sheet) sheet = book.insertSheet(DMAX_TAB);
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, 5).setValues([DMAX_HEADERS]);
    sheet.setFrozenRows(1);
    sheet.getRange(1,1,1,5).setBackground('#06264a').setFontColor('#ffffff').setFontWeight('bold');
    sheet.autoResizeColumns(1,5);
  } else {
    const header = sheet.getRange(1,1,1,5).getValues()[0].map(v => String(v).trim().toLowerCase());
    if (JSON.stringify(header) !== JSON.stringify(DMAX_HEADERS)) {
      throw new Error('A aba já contém dados com outros cabeçalhos. Nada foi substituído.');
    }
  }
  SpreadsheetApp.getUi().alert('Aba Tecnicos pronta. Use id permanente, nome, login, situacao e valido_ate. Não coloque senhas na planilha.');
}

function autorizarDMax() {
  const ui = SpreadsheetApp.getUi();
  const answer = ui.prompt('Autorizar equipamento D-Max', 'Cole o identificador mostrado na página Técnicos globais do equipamento.', ui.ButtonSet.OK_CANCEL);
  if (answer.getSelectedButton() !== ui.Button.OK) return;
  const id = answer.getResponseText().trim();
  if (!/^[A-Za-z0-9_-]{1,100}$/.test(id)) throw new Error('Identificador inválido.');
  const properties = PropertiesService.getScriptProperties();
  if (properties.getProperty('device.'+id) && ui.alert('Já autorizado', 'Substituir a chave? Será necessário atualizar a chave no equipamento.', ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  const key = [Utilities.getUuid(),Utilities.getUuid(),Utilities.getUuid()].join('').replace(/-/g,'');
  properties.setProperty('device.'+id, sha_(key));
  const html = HtmlService.createHtmlOutput('<div style="font:14px Arial;padding:20px"><h2>Chave do D-Max</h2><p>Copie agora e cole em Técnicos globais → Chave deste D-Max. Ela não será gravada nas células.</p><textarea readonly style="width:100%;height:90px">'+key+'</textarea><p>Depois configure a URL publicada deste Apps Script. Guarde a chave em local seguro.</p></div>').setWidth(480).setHeight(300);
  ui.showModalDialog(html,'Autorização do equipamento');
}

function revogarDMax() {
  const ui=SpreadsheetApp.getUi();
  const answer=ui.prompt('Revogar chave de equipamento','Informe o identificador do D-Max. Isso revoga a sincronização; não apaga o cadastro offline já existente.',ui.ButtonSet.OK_CANCEL);
  if(answer.getSelectedButton()!==ui.Button.OK)return;
  PropertiesService.getScriptProperties().deleteProperty('device.'+answer.getResponseText().trim());
  ui.alert('Chave revogada. Para bloquear um técnico, altere a situação na aba Tecnicos.');
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
function error_(code,message) {const e=new Error(message);e.code=code;throw e;}
function json_(value) {return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON);}

function doGet() {return json_({ok:false,code:405,message:'Use POST autenticado. Nenhum cadastro é público.'});}
function doPost(event) {
  let lock, acquired=false;
  try {
    if(!event||!event.postData||event.postData.contents.length>20000)error_(413,'Solicitação inválida');
    const data=JSON.parse(event.postData.contents),props=PropertiesService.getScriptProperties();
    if(!/^[A-Za-z0-9_-]{1,100}$/.test(data.controller_id||'')||typeof data.key!=='string'||data.key.length>512||
       !equal_(props.getProperty('device.'+data.controller_id),sha_(data.key)))error_(401,'Equipamento não autorizado');
    lock=LockService.getScriptLock();
    acquired=lock.tryLock(5000);
    if(!acquired)error_(503,'Consulta ocupada; tente novamente');
    if(data.action==='remote_directory'){
      if(props.getProperty('remote_directory.'+data.controller_id)!=='enabled')error_(403,'Consulta remota não autorizada');
      return json_(remoteDirectory_());
    }
    if(data.action==='snapshot'){
      const result=snapshot_(props);
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
  if(JSON.stringify(sheet.getRange(1,1,1,DMAX_REMOTE_HEADERS.length).getValues()[0])!==JSON.stringify(DMAX_REMOTE_HEADERS))error_(422,'Cabeçalhos remotos incompatíveis');
  return sheet;
}
function prepararRemoto(){remoteSheet_();}
function sheetText_(value){return /^[=+\-@\t\r]/.test(value)?"'"+value:value;}
function remote_(id,data){
  if(!data||Object.keys(data).sort().join(',')!=='connected,heartbeat_at,provider,revision,site_name,url'||
     data.provider!=='cloudflare'||typeof data.connected!=='boolean'||!Number.isSafeInteger(data.revision)||data.revision<1||
     typeof data.site_name!=='string'||data.site_name.length>100||
     typeof data.url!=='string'||!/^https:\/\/[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.trycloudflare\.com$/.test(data.url)||
     typeof data.heartbeat_at!=='number'||!Number.isFinite(data.heartbeat_at)||data.heartbeat_at<1||data.heartbeat_at>Date.now()/1000+300)error_(422,'Registro remoto inválido');
  const sheet=remoteSheet_();
  const matches=sheet.getLastRow()>1?sheet.getRange(2,1,sheet.getLastRow()-1,7).getValues().map((row,i)=>({row,index:i+2})).filter(item=>String(item.row[0])===id):[];
  if(matches.length>1)error_(409,'Identificador remoto duplicado');
  const old=matches[0];
  const revision=old?Number(old.row[6]):0;
  if(!Number.isSafeInteger(revision)||revision<0)error_(422,'Revisão remota inválida');
  if(data.revision<revision)return {revision:revision,accepted:false};
  if(data.revision===revision&&old&&(old.row[2]!==data.url||old.row[3]!== (data.connected?'CONECTADO':'DESCONECTADO')))return {revision:revision,accepted:false};
  sheet.getRange(old?old.index:sheet.getLastRow()+1,1,1,7).setValues([[id,sheetText_(data.site_name),data.url,data.connected?'CONECTADO':'DESCONECTADO',new Date().toISOString(),new Date(data.heartbeat_at*1000).toISOString(),data.revision]]);
  return {revision:data.revision,accepted:true};
}

function permitirBuscaRemota(){
  const ui=SpreadsheetApp.getUi(),answer=ui.prompt('Permitir busca de clientes remotos','Identificador do equipamento usado pelo proprietário. Permite consultar todos os clientes; não autorize equipamentos de clientes comuns.',ui.ButtonSet.OK_CANCEL);
  if(answer.getSelectedButton()!==ui.Button.OK)return;
  const id=answer.getResponseText().trim(),props=PropertiesService.getScriptProperties();
  if(!props.getProperty('device.'+id))throw new Error('Autorize esse D-Max primeiro.');
  props.setProperty('remote_directory.'+id,'enabled');
  ui.alert('Busca de clientes permitida para este equipamento. A interface exige login root.');
}
function revogarBuscaRemota(){
  const ui=SpreadsheetApp.getUi(),answer=ui.prompt('Revogar busca de clientes remotos','Identificador do equipamento.',ui.ButtonSet.OK_CANCEL);
  if(answer.getSelectedButton()!==ui.Button.OK)return;
  PropertiesService.getScriptProperties().deleteProperty('remote_directory.'+answer.getResponseText().trim());
}
function remoteDirectory_(){
  const sheet=remoteSheet_(),clients=[],seen={};
  if(sheet.getLastRow()>1001)error_(422,'Limite de 1000 clientes');
  const rows=sheet.getLastRow()>1?sheet.getRange(2,1,sheet.getLastRow()-1,7).getValues():[];
  rows.forEach(row=>{
    if(row.every(v=>String(v).trim()===''))return;
    const id=String(row[0]).trim(),name=String(row[1]).trim(),url=String(row[2]).trim(),stamp=row[4] instanceof Date?row[4].getTime():Date.parse(String(row[4]));
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
  if(JSON.stringify(values[0].map(v=>String(v).trim().toLowerCase()))!==JSON.stringify(DMAX_HEADERS))error_(422,'Cabeçalhos inválidos');
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
  const book=SpreadsheetApp.openById(DMAX_SHEET_ID);
  let sheet=book.getSheetByName('Assinaturas');
  if(!sheet)sheet=book.insertSheet('Assinaturas');
  if(sheet.getLastRow()===0){
    sheet.getRange(1,1,1,6).setValues([DMAX_SUB_HEADERS]);sheet.setFrozenRows(1);
    sheet.getRange(1,1,1,6).setBackground('#06264a').setFontColor('#ffffff').setFontWeight('bold');
    sheet.autoResizeColumns(1,6);
  }else if(JSON.stringify(sheet.getRange(1,1,1,6).getValues()[0])!==JSON.stringify(DMAX_SUB_HEADERS)){
    throw new Error('Cabeçalhos diferentes. Nenhum dado foi substituído.');
  }
  SpreadsheetApp.getUi().alert('Use uma linha por D-Max. Situação: regular ou pendente. O prazo é fixo de dez dias; aviso_em e prazo_final são preenchidos pelo serviço. Para liberar, altere para regular. Apagar a linha não libera o equipamento.');
}
function subscription_(props,id) {
  const book=SpreadsheetApp.openById(DMAX_SHEET_ID),sheet=book.getSheetByName('Assinaturas');
  if(!sheet||sheet.getLastRow()<2)return null;
  if(JSON.stringify(sheet.getRange(1,1,1,6).getValues()[0])!==JSON.stringify(DMAX_SUB_HEADERS))error_(422,'Cabeçalhos de assinaturas inválidos');
  const matches=sheet.getRange(2,1,sheet.getLastRow()-1,6).getValues().map((v,i)=>({v:v,row:i+2})).filter(r=>String(r.v[0]).trim()===id);
  if(!matches.length)return null;
  if(matches.length!==1)error_(422,'Assinatura duplicada');
  const row=matches[0],status=String(row.v[2]).trim().toLowerCase();
  if(!['regular','pendente'].includes(status))error_(422,'Situação de assinatura inválida');
  const state=status==='pendente'?'pending':'regular',now=Math.floor(Date.now()/1000);
  const message=String(row.v[5]||'Regularize sua assinatura com o fornecedor.').trim();
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
  sheet.getRange(row.row,4,1,2).setValues([dates]);
  const payload=JSON.stringify(Object.assign({},record,{server_time:now}));
  const signature=Utilities.computeHmacSha256Signature('DMAX-LICENSE-1\n'+payload,props.getProperty('device.'+id),Utilities.Charset.UTF_8)
    .map(b=>('0'+((b+256)%256).toString(16)).slice(-2)).join('');
  return {payload:payload,signature:signature};
}
