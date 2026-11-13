/** D-Max Acesso Web 1.0. No device credentials or verifiers enter the browser. */
function portalReply_(operation){
  let lock,acquired=false;
  try {
    lock=LockService.getScriptLock();
    acquired=lock.tryLock(5000);
    if(!acquired)error_(503,'Ocupado');
    return Object.assign({ok:true},operation(PropertiesService.getScriptProperties()));
  } catch(e) {
    const code=e.code||503;
    const messages={401:'Login, senha ou sessão inválidos. Entre novamente.',403:'Seu perfil não permite esta operação.',409:'Conflito de ID/login. Preserve a identidade existente ou crie outra conta com novo login.',422:'Confira os campos e a aba Usuarios.',429:'Muitas tentativas. Aguarde cinco minutos.',503:'Não foi possível consultar a planilha. Tente novamente.'};
    return {ok:false,code:code,message:messages[code]||messages[503]};
  } finally {if(acquired)lock.releaseLock();}
}
function portalRoster_(props){
  const book=SpreadsheetApp.openById(DMAX_SHEET_ID),sheet=unifiedSheet_(props);
  if(!sheet)error_(422,'Prepare a aba Usuarios');
  const rows=userRows_(sheet,book),history=historicalUsers_(props.getProperties()),seen=new Set();
  const records=rows.map(r=>{
    const old=history.byId[r.id];
    if(old&&old.name!==r.name)error_(409,'Identidade permanente');
    if(history.byName[r.name]&&history.byName[r.name]!==r.id)error_(409,'Login histórico');
    seen.add(r.id);
    return Object.assign({},r,{must_change:old&&old.password===r.password?Boolean(old.must_change):r.role==='technician'&&r.password===DMAX_DEFAULT_HASH});
  });
  Object.values(history.byId).forEach(r=>{if(!seen.has(r.id))records.push(Object.assign({},r,{active:false,deleted:true}));});
  return records;
}
function portalPublic_(r){
  return {id:r.id,name:r.name,full_name:r.full_name,role:r.role,active:r.active,deleted:r.deleted,expires_at:r.expires_at};
}
function portalUsable_(r){
  return Boolean(r&&['developer','commercial','technician'].includes(r.role)&&r.active&&!r.deleted&&!r.must_change&&(r.expires_at===null||r.expires_at>Date.now()/1000));
}
function portalFingerprint_(r){
  return sha_(JSON.stringify([r.id,r.name,r.role,r.password,r.active,r.deleted,r.expires_at,Boolean(r.must_change)]));
}
function portalSession_(props,token){
  if(typeof token!=='string'||!/^[0-9a-f]{64}$/.test(token))error_(401,'Sessão inválida');
  const key='portal.session.'+sha_(token),session=JSON.parse(props.getProperty(key)||'null');
  if(!session||session.until<=Date.now()/1000){props.deleteProperty(key);error_(401,'Sessão encerrada');}
  const rows=portalRoster_(props),actor=rows.find(r=>r.id===session.id);
  if(!portalUsable_(actor)||portalFingerprint_(actor)!==session.fingerprint){props.deleteProperty(key);error_(401,'Acesso alterado');}
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
    if(!valid||!portalUsable_(actor))error_(401,'Credenciais inválidas');
    const active=Object.keys(props.getProperties()).filter(k=>k.startsWith('portal.session.'));
    if(active.length>=64)error_(503,'Limite de sessões');
    const token=(Utilities.getUuid()+Utilities.getUuid()).replace(/-/g,'');
    props.setProperty('portal.session.'+sha_(token),JSON.stringify({id:actor.id,fingerprint:portalFingerprint_(actor),until:now+(actor.role==='commercial'?900:3600)}));
    props.deleteProperty(attemptKey);
    return {token:token,user:portalPublic_(actor)};
  });
}
function portalState(token){
  return portalReply_(props=>({user:portalPublic_(portalSession_(props,token).actor)}));
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
    const data=remoteDirectory_();
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
  return portalReply_(props=>{
    const session=portalSession_(props,token),actor=session.actor;
    if(actor.role!=='developer')error_(403,'Somente desenvolvedor');
    if(!fields||typeof fields!=='object'||typeof fields.actor_password!=='string'||fields.actor_password.length>200)error_(422,'Campos inválidos');
    let encoded;
    const old=session.rows.find(r=>r.id===fields.id);
    if(fields.password){
      if(typeof fields.password!=='string'||fields.password.length<8||fields.password.length>200||fields.password!==fields.confirmation)error_(422,'Senha inválida');
      const salt=Utilities.getUuid().replace(/-/g,'');
      encoded='pbkdf2_sha256$600000$'+salt+'$'+sjcl.codec.hex.fromBits(sjcl.misc.pbkdf2(fields.password,sjcl.codec.hex.toBits(salt),600000,256));
    } else if(old)encoded=old.password;
    else error_(422,'Informe uma senha');
    const record={id:fields.id||'USR-'+Utilities.getUuid().replace(/-/g,'').slice(0,16),name:fields.name,full_name:fields.full_name,role:fields.role,status:fields.status,expires:fields.expires||'',password:encoded};
    const result=bridgeManageUser_(props,{controller_id:'WEB-'+actor.id,actor_login:actor.name,actor_password:fields.actor_password,record:record});
    // Only a developer who just proved their password receives the new verifier.
    return {acknowledged_id:result.acknowledged_id,verifier:encoded};
  });
}
