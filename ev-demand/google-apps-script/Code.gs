/** D-Max global directory. Bound to Google Sheets; no external server required. */
const DMAX_SHEET_ID = '17HCp2CX3eUZXqQsTkTNDZvrLkGqzZQrJkCfeHo-toPQ';
const DMAX_TAB = 'Tecnicos';
const DMAX_HEADERS = ['id', 'nome', 'login', 'situacao', 'valido_ate'];
const DMAX_DEFAULT_HASH = 'pbkdf2_sha256$600000$0cc644386557630153579d018267d636$07eb3cfc2778a1ee08fa321b86c897f72237f6749cecda0eee2ea788cb678c53';

function onOpen() {
  SpreadsheetApp.getUi().createMenu('D-Max')
    .addItem('Preparar aba Tecnicos', 'prepararTecnicos')
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
    if(data.action==='snapshot')return json_(snapshot_(props));
    if(data.action==='update')return json_(update_(props,data.record));
    error_(422,'Ação desconhecida');
  } catch(e) {
    // Never echo request contents, device keys or password hashes.
    return json_({ok:false,code:e.code||503,message:e.code?'Solicitação recusada':'Confira a aba, permissões e cotas do Apps Script'});
  } finally {if(acquired)lock.releaseLock();}
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
