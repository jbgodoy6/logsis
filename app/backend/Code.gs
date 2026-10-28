/** Create a NEW standalone script; do not overwrite any existing D-Max script.
 * Execute as owner. Native app endpoint is fixed at build time, never user-editable.
 * No passwords or technician list are returned to the app.
 */
const REGISTRY = Object.freeze({
  spreadsheetId: '17HCp2CX3eUZXqQsTkTNDZvrLkGqzZQrJkCfeHo-toPQ',
  sheet: 'Tecnicos', sessionSeconds: 600
});

function configurarSenhaTecnica() {
  const properties=PropertiesService.getScriptProperties();
  const password=properties.getProperty('AUTH_PASSWORD_SETUP')||'';
  if(password.length<10)throw new Error('Use ao menos 10 caracteres.');
  const pepper=Utilities.getUuid()+Utilities.getUuid();
  properties.setProperties({
    AUTH_PEPPER:pepper,AUTH_PASSWORD_HASH:hmac_(password,pepper),
    AUTH_EPOCH:Utilities.getUuid()
  });
  properties.deleteProperty('AUTH_PASSWORD_SETUP');
  console.log('Senha configurada no servidor. Sessões anteriores foram revogadas.');
}
function hmac_(text,key) {
  return Utilities.computeHmacSha256Signature(text,key,Utilities.Charset.UTF_8)
    .map(n=>('0'+((n+256)%256).toString(16)).slice(-2)).join('');
}
function hash_(text){
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,text,Utilities.Charset.UTF_8)
    .map(n=>('0'+((n+256)%256).toString(16)).slice(-2)).join('');
}
function equal_(a,b){
  let diff=a.length^b.length;
  for(let i=0;i<Math.max(a.length,b.length);i++)diff|=(a.charCodeAt(i)||0)^(b.charCodeAt(i)||0);
  return diff===0;
}
function normalize_(s){return String(s||'').trim().toLowerCase();}
function active_(row,now) {
  const status=String(row.situacao||'').trim().normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase();
  if(status!=='ATIVO'||!String(row.id||'').trim()||!normalize_(row.login))return false;
  // Blank validity is unrestricted; a populated invalid or expired date denies.
  const value=String(row.valido_ate||'').trim();
  if(!value)return true;
  const match=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value)||/^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if(!match)return false;
  const iso=match[1].length===4?`${match[1]}-${match[2]}-${match[3]}`:`${match[3]}-${match[2]}-${match[1]}`;
  const date=new Date(iso+'T12:00:00Z');
  if(!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==iso)return false;
  return now<=new Date(iso+'T23:59:59.999-03:00').getTime();
}
function technician_(login) {
  const book=SpreadsheetApp.openById(REGISTRY.spreadsheetId);
  const sheet=book.getSheetByName(REGISTRY.sheet);
  if(!sheet)throw new Error('Cadastro indisponível.');
  const rows=sheet.getDataRange().getDisplayValues();
  const headers=(rows.shift()||[]).map(normalize_);
  for(const k of ['id','nome','login','situacao','valido_ate'])if(!headers.includes(k))throw new Error('Cabeçalhos inválidos.');
  if(new Set(headers.filter(Boolean)).size!==headers.filter(Boolean).length)throw new Error('Cabeçalhos duplicados.');
  const matches=rows.map(values=>Object.fromEntries(headers.map((k,i)=>[k,values[i]||''])))
    .filter(row=>normalize_(row.login)===normalize_(login));
  if(matches.length!==1)return null;
  const row=matches[0];
  // Also reject duplicate technician IDs, even on another login.
  if(rows.filter(values=>String(values[headers.indexOf('id')]).trim()===String(row.id).trim()).length!==1)return null;
  return active_(row,Date.now())?row:null;
}
function rate_(login) {
  const lock=LockService.getScriptLock();
  if(!lock.tryLock(3000))throw new Error('Tente novamente.');
  try {
    const cache=CacheService.getScriptCache(),key='attempt:'+hash_(login);
    const record=JSON.parse(cache.get(key)||'{"count":0,"start":0}');
    const now=Date.now();
    const count=now-record.start<600000?record.count:0;
    if(count>=10)throw new Error('Muitas tentativas. Aguarde 10 minutos.');
    cache.put(key,JSON.stringify({count:count+1,start:count?record.start:now}),600);
  }finally{lock.releaseLock();}
}
function authorized_(token) {
  if(typeof token!=='string'||!/^[a-f0-9]{64}$/.test(token))return null;
  const cache=CacheService.getScriptCache(),key='session:'+hash_(token),raw=cache.get(key);
  if(!raw)return null;
  const session=JSON.parse(raw);
  const properties=PropertiesService.getScriptProperties();
  if(Date.now()>=session.expires||session.epoch!==properties.getProperty('AUTH_EPOCH')){cache.remove(key);return null;}
  const row=technician_(session.login);
  if(!row||String(row.id)!==session.id){cache.remove(key);return null;}
  return {row,session};
}
function api_(input) {
  if(!input||typeof input.action!=='string')return {ok:false,message:'Solicitação inválida.'};
  if(input.action==='login'){
    const login=normalize_(input.login),password=input.password;
    if(!login||login.length>128||typeof password!=='string'||password.length>256)return {ok:false,message:'Acesso não autorizado.'};
    rate_(login);
    const properties=PropertiesService.getScriptProperties();
    const pepper=properties.getProperty('AUTH_PEPPER'),stored=properties.getProperty('AUTH_PASSWORD_HASH');
    if(!pepper||!stored)return {ok:false,message:'Serviço técnico ainda não configurado.'};
    if(!equal_(hmac_(password,pepper),stored))return {ok:false,message:'Acesso não autorizado.'};
    const row=technician_(login);
    if(!row)return {ok:false,message:'Acesso não autorizado.'};
    const token=(Utilities.getUuid()+Utilities.getUuid()).replace(/-/g,'');
    const expires=Date.now()+REGISTRY.sessionSeconds*1000;
    CacheService.getScriptCache().put('session:'+hash_(token),JSON.stringify({
      id:String(row.id),login,expires,epoch:properties.getProperty('AUTH_EPOCH')
    }),REGISTRY.sessionSeconds);
    return {ok:true,token,expires,name:row.nome};
  }
  const auth=authorized_(input.token);
  if(!auth)return {ok:false,message:'Autorização ausente, expirada ou revogada.'};
  if(input.action==='verify')return {ok:true,expires:auth.session.expires,name:auth.row.nome};
  if(input.action==='logout'){
    CacheService.getScriptCache().remove('session:'+hash_(input.token));return {ok:true};
  }
  // Drive library update is server-side and uses a folder configured by owner.
  const folderId=PropertiesService.getScriptProperties().getProperty('LIBRARY_FOLDER_ID');
  if(!folderId)return {ok:false,message:'Pasta da biblioteca ainda não configurada.'};
  const folder=DriveApp.getFolderById(folderId);
  if(input.action==='library'){
    const files=folder.getFiles(),entries=[];
    while(files.hasNext()){
      const file=files.next(),name=file.getName();
      if(!/^[A-Z0-9_-]+\.bin$/.test(name)||file.getSize()>2097152)continue;
      const bytes=file.getBlob().getBytes();
      const sha256=Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,bytes)
        .map(n=>('0'+((n+256)%256).toString(16)).slice(-2)).join('');
      entries.push({model:name.slice(0,-4),fileId:file.getId(),sha256,modified:file.getLastUpdated().getTime()});
      if(entries.length>64)throw new Error('Biblioteca excede 64 modelos.');
    }
    return {ok:true,entries};
  }
  if(input.action==='bin'){
    if(typeof input.fileId!=='string'||input.fileId.length>128)return {ok:false,message:'Arquivo inválido.'};
    const file=DriveApp.getFileById(input.fileId),parents=file.getParents();let belongs=false;
    while(parents.hasNext())if(parents.next().getId()===folder.getId())belongs=true;
    if(!belongs||!file.getName().endsWith('.bin')||file.getSize()>2097152)return {ok:false,message:'Arquivo inválido.'};
    return {ok:true,data:Utilities.base64Encode(file.getBlob().getBytes())};
  }
  return {ok:false,message:'Operação inválida.'};
}
function doPost(e) {
  let result;
  try {
    if(!e||!e.postData||e.postData.contents.length>8192)throw new Error('Solicitação inválida.');
    result=api_(JSON.parse(e.postData.contents));
  }catch(error){result={ok:false,message:'Não foi possível validar o acesso. Tente novamente.'};}
  result.registryId=REGISTRY.spreadsheetId;
  return ContentService.createTextOutput(JSON.stringify(result)).setMimeType(ContentService.MimeType.JSON);
}
function doGet(){return ContentService.createTextOutput('Logsis — serviço de autorização técnica. Use o aplicativo.');}
