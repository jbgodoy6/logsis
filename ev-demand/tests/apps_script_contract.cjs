// Executes the exact shipped Apps Script with local Google-service doubles.
const vm=require('node:vm'),fs=require('node:fs'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[2],'utf8');
let rows=[['id','nome','login','situacao','valido_ate'],['TEC-1','Técnico Um','tecnico.um','ativo','']];
const properties={'device.controller':crypto.createHash('sha256').update('fixture-device-key').digest('hex')};
let uncertain=false;
let subscriptions=null,remoteRows=[],remote=null,accountSheet=null;
const sheet={
 getLastRow:()=>rows.length,
 getRange:(start,column,height,width)=>({
  getValues:()=>Array.from({length:height},(_,i)=>Array.from({length:width},(_,j)=>rows[start-1+i]?.[column-1+j]??'')),
  setValues:values=>{values.forEach((row,i)=>{rows[start-1+i]??=[];row.forEach((v,j)=>rows[start-1+i][column-1+j]=v);});if(uncertain){uncertain=false;throw Error('lost response after commit');}}
 })};
const props={getProperty:k=>properties[k]??null,setProperty:(k,v)=>properties[k]=String(v),deleteProperty:k=>delete properties[k],getProperties:()=>({...properties})};
const extraSheets={};
function makeTab(data,name) {
 const tab={name,hidden:false,getLastRow:()=>data.length,setFrozenRows:()=>{},autoResizeColumns:()=>{},
  getRange:(start,column,height,width)=>({getValues:()=>Array.from({length:height},(_,i)=>Array.from({length:width},(_,j)=>data[start-1+i]?.[column-1+j]??'')),setValues:values=>{values.forEach((row,i)=>{data[start-1+i]??=[];row.forEach((v,j)=>data[start-1+i][column-1+j]=v)});if(uncertain){uncertain=false;throw Error('lost response after commit')}}}),
  setName:n=>{delete extraSheets[tab.name];tab.name=n;extraSheets[n]=tab;return tab},hideSheet:()=>{tab.hidden=true;return tab},copyTo:()=>{const n='copy-'+Object.keys(extraSheets).length,t=makeTab(JSON.parse(JSON.stringify(data)),n);extraSheets[n]=t;return t},data};
 return tab;
}
const book={getSheetByName:name=>name==='Tecnicos'?sheet:name==='Contas'?accountSheet:name==='Assinaturas'?subscriptions:name==='DMax_Remoto'?remote:extraSheets[name]??null,
 insertSheet:name=>{const t=makeTab(name==='DMax_Remoto'?remoteRows:[],name);if(name==='DMax_Remoto')remote=t;else extraSheets[name]=t;return t},getSpreadsheetTimeZone:()=> 'America/Sao_Paulo'};
sheet.copyTo=()=>{const n='copy-tech',t=makeTab(JSON.parse(JSON.stringify(rows)),n);extraSheets[n]=t;return t};sheet.hideSheet=()=>{sheet.hidden=true;return sheet};
const context={
 Date,JSON,Math,Number,String,Object,Array,Boolean,Error,RegExp,
 PropertiesService:{getScriptProperties:()=>props},
 SpreadsheetApp:{openById:()=>book,flush:()=>{},getUi:()=>({alert:()=>{}})},
 LockService:{getScriptLock:()=>({tryLock:()=>true,releaseLock:()=>{}})},
 ContentService:{MimeType:{JSON:'application/json'},createTextOutput:text=>({text,setMimeType(){return this;}})},
 Utilities:{DigestAlgorithm:{SHA_256:'sha256'},Charset:{UTF_8:'utf8'},getUuid:()=>crypto.randomUUID(),
  computeDigest:(_,value)=>[...crypto.createHash('sha256').update(value).digest()],
  computeHmacSha256Signature:(value,key)=>[...crypto.createHmac('sha256',key).update(value).digest()],
  formatDate:(d,tz)=>new Intl.DateTimeFormat('en-CA',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit'}).format(d),
  parseDate:value=>new Date(value.replace(' ','T')+'-03:00')}
};
vm.createContext(context);vm.runInContext(source,context);
const call=(action,record,key='fixture-device-key')=>JSON.parse(context.doPost({postData:{contents:JSON.stringify({action,record,controller_id:'controller',key})}}).text);
assert.equal(call('snapshot',null,'wrong').code,401);
let snapshot=call('snapshot');assert.equal(snapshot.complete,true);assert.equal(snapshot.technicians[0].must_change,true);
let original=snapshot.technicians[0];assert.equal(original.activation_hash,null);
const changed={...original,operations:['credential'],base_version:original.credential_version,credential_version:2,
 password:'pbkdf2_sha256$600000$'+'a'.repeat(32)+'$'+'b'.repeat(64),activation_hash:null,must_change:false};
assert.equal(call('update',changed).acknowledged_id,'TEC-1');
snapshot=call('snapshot');assert.equal(snapshot.technicians[0].password,changed.password);assert.equal(snapshot.technicians[0].must_change,false);
rows[1][1]='Nome atualizado';snapshot=call('snapshot');assert.equal(snapshot.technicians[0].password,changed.password);assert.equal(snapshot.technicians[0].full_name,'Nome atualizado');
rows[1][3]='bloqueado';snapshot=call('snapshot');assert.equal(snapshot.technicians[0].active,false);
rows=rows.slice(0,1);snapshot=call('snapshot');assert.equal(snapshot.technicians[0].deleted,true);
const newRecord={...changed,id:'TEC-2',name:'tecnico.dois',full_name:'Técnico Dois',active:true,deleted:false,expires_at:null,operations:['register']};
assert.equal(call('update',newRecord).acknowledged_id,'TEC-2');assert.equal(rows.length,2);
assert.equal(call('update',newRecord).acknowledged_id,'TEC-2');assert.equal(rows.length,2);
assert.equal(JSON.stringify(rows).includes('pbkdf2'),false);
rows.push(['TEC-3','Outro','tecnico.dois','ativo','']);assert.equal(call('snapshot').ok,false);rows.pop();
const retry={...newRecord,id:'TEC-4',name:'tecnico.quatro',full_name:'Técnico Quatro'};
uncertain=true;assert.equal(call('update',retry).ok,false);assert.equal(call('snapshot').technicians.find(r=>r.id==='TEC-4').password,retry.password);
assert.equal(call('update',retry).acknowledged_id,'TEC-4');assert.equal(rows.filter(r=>r[0]==='TEC-4').length,1);
assert.equal(context.date_('2026-12-31','America/Sao_Paulo'),Date.parse('2027-01-01T00:00:00-03:00')/1000);
console.log('Apps Script contract passed: device authentication, credentials outside cells, first login, metadata, revocation, deletion, idempotency, dates.');
// Billing is per controller, signed, optional, and does not store secrets in cells.
let subRows=[['controller_id','instalacao','situacao','aviso_em','prazo_final','mensagem'],['controller','Garagem','pendente','','','Regularize com o fornecedor.']];
subscriptions={getLastRow:()=>subRows.length,getRange:(start,column,height,width)=>({
 getValues:()=>Array.from({length:height},(_,i)=>Array.from({length:width},(_,j)=>subRows[start-1+i]?.[column-1+j]??'')),
 setValues:values=>values.forEach((row,i)=>row.forEach((v,j)=>subRows[start-1+i][column-1+j]=v))
})};
const verifyNotice=notice=>{
 assert.equal(notice.signature,crypto.createHmac('sha256',properties['device.controller']).update('DMAX-LICENSE-1\n'+notice.payload).digest('hex'));
 return JSON.parse(notice.payload);
};
let notice=verifyNotice(call('snapshot').subscription);assert.equal(notice.state,'pending');assert.equal(notice.deadline-notice.issued_at,864000);
const deadline=notice.deadline,revision=notice.revision;
assert.equal(verifyNotice(call('snapshot').subscription).revision,revision);
subRows[1][5]='Outra mensagem';notice=verifyNotice(call('snapshot').subscription);assert.equal(notice.deadline,deadline);assert.equal(notice.revision,revision+1);
subRows[1][2]='regular';notice=verifyNotice(call('snapshot').subscription);assert.equal(notice.state,'regular');assert.equal(notice.deadline,null);
subRows.push([...subRows[1]]);assert.equal(call('snapshot').ok,false);subRows.pop();
subRows[1][0]='another-controller';assert.equal(call('snapshot').subscription,undefined);
console.log('Subscription contract passed: signed per-controller ten-day notices, stable deadline, renewal and duplicate rejection.');

// Remote directory uses the existing authenticated identity, with no secrets in cells.
const registration={site_name:'=unsafe formula',url:'https://first-site.trycloudflare.com',connected:true,heartbeat_at:Date.now()/1000,provider:'cloudflare',revision:1};
const register=(data,key='fixture-device-key',id='controller')=>JSON.parse(context.doPost({postData:{contents:JSON.stringify({action:'snapshot',controller_id:id,key,remote:data})}}).text);
assert.equal(register(registration,'wrong').code,401);assert.equal(remoteRows.length,0);
assert.equal(register(registration).remote_ack.accepted,true);assert.equal(remoteRows.length,2);assert.equal(remoteRows[1][1],"'=unsafe formula");
assert.equal(register(registration).remote_ack.revision,1);assert.equal(remoteRows.length,2);
const newer={...registration,url:'https://second-site.trycloudflare.com',revision:2};
assert.equal(register(newer).remote_ack.accepted,true);assert.equal(remoteRows[1][2],newer.url);
assert.equal(register(registration).remote_ack.accepted,false);assert.equal(remoteRows[1][2],newer.url);
assert.equal(register({...newer,url:'https://evil.test'}).remote_error,true);
assert.equal(register({...newer,key:'must-never-be-stored'}).remote_error,true);
properties['device.other']=properties['device.controller'];assert.equal(register(registration,'fixture-device-key','other').remote_ack.accepted,true);assert.equal(remoteRows.length,3);
assert.equal(JSON.stringify(remoteRows).includes('fixture-device-key'),false);assert.equal(JSON.stringify(remoteRows).includes('pbkdf2'),false);
remoteRows.push([...remoteRows[1]]);assert.equal(register(newer).remote_error,true);
console.log('Remote directory contract passed: authenticated IDs, literal names, separate installations, revision ordering, duplicate rejection and no credentials in cells.');
// Every authenticated device can query all remote rows; root is enforced by the D-Max API/UI.
remoteRows.pop();
assert.equal(call('remote_directory',null,'wrong').code,401);
assert.equal(properties['remote_directory.controller'],undefined);
let catalog=call('remote_directory');assert.equal(catalog.ok,true);assert.equal(catalog.clients.length,2);
assert.equal(catalog.clients.find(r=>r.controller_id==='controller').url,newer.url);
assert.equal(JSON.stringify(catalog).includes('fixture-device-key'),false);assert.equal(JSON.stringify(catalog).includes('pbkdf2'),false);
properties['remote_directory.controller']='disabled';assert.equal(call('remote_directory').clients.length,2);delete properties['remote_directory.controller'];
assert.equal(register({...newer,revision:3}).remote_ack.accepted,true);
remoteRows[1][2]='https://api.trycloudflare.com';assert.equal(call('remote_directory').ok,false);remoteRows[1][2]=newer.url;
console.log('Remote catalog contract passed: authenticated full listing without extra grants, current URLs and credential-free response.');

// Registration is still authenticated; catalog permission never requires manual device grants.
assert.equal(register({...newer,revision:4,url:'https://latest-client.trycloudflare.com'}).remote_ack.accepted,true);
assert.equal(call('remote_directory').clients.find(row=>row.controller_id==='controller').url,'https://latest-client.trycloudflare.com');
assert.equal(call('remote_directory',null,'fixture-device-key').clients.length,2);

// Privileged accounts remain separate from existing technician cells.
const accountRows=[['id','nome','login','perfil','situacao','valido_ate','verificador'],['DEV-1','Desenvolvedor','dev.one','desenvolvedor','ativo','',changed.password],['SALES-1','Comercial','sales.one','comercial','ativo','',changed.password]];
accountSheet={getLastRow:()=>accountRows.length,getRange:(start,col,height,width)=>({getValues:()=>Array.from({length:height},(_,i)=>Array.from({length:width},(_,j)=>accountRows[start-1+i]?.[col-1+j]??''))})};
let accounts=call('snapshot').accounts;assert.equal(accounts.length,2);assert.equal(accounts[0].role,'developer');assert.equal(accounts[1].role,'commercial');
accountRows[1][4]='bloqueado';assert.equal(call('snapshot').accounts[0].active,false);
accountRows[1][6]='plaintext-is-forbidden';assert.equal(call('snapshot').code,422);accountRows[1][6]=changed.password;
accountRows[1][2]=rows[1][2];assert.equal(call('snapshot').code,409);
console.log('privileged accounts contract passed');

// One active sheet: full validation, backups, repeated migration and compatibility.
accountSheet.copyTo=()=>{const n='copy-accounts',t=makeTab(JSON.parse(JSON.stringify(accountRows)),n);extraSheets[n]=t;return t};accountSheet.hideSheet=()=>{accountSheet.hidden=true;return accountSheet};
assert.throws(()=>context.migrarUsuarios(),/IDs diferentes|outro ID histórico/);
assert.equal(properties['directory.unified'],undefined);assert.equal(extraSheets.Usuarios,undefined);
accountRows[1][2]='dev.one';
accountRows.push(['TEC-2','Técnico promovido','tecnico.dois','desenvolvedor','ativo','',changed.password]);
rows.push(['UNSYNC','Técnico ainda não sincronizado','unsynced.tech','ativo','']);
context.migrarUsuarios();assert.equal(properties['directory.unified'],'1');
assert.equal(sheet.hidden,true);assert.equal(accountSheet.hidden,true);
const unified=extraSheets.Usuarios;assert(unified);assert.equal(unified.data[0].join(','),'id,nome,login,perfil,situacao,valido_ate,verificador');
assert.equal(Object.keys(extraSheets).filter(n=>n.startsWith('Backup_acessos_')).length,2);
let unifiedResult=call('snapshot');assert.equal(unifiedResult.complete,true);assert.equal(unifiedResult.technicians.find(r=>r.id==='UNSYNC').must_change,true);
assert.equal(unifiedResult.accounts.find(r=>r.id==='TEC-2').role,'developer');
assert(!unifiedResult.technicians.some(r=>r.id==='TEC-2'));
assert.equal(unifiedResult.technicians.find(r=>r.id==='TEC-4').password,retry.password);
assert.equal(unifiedResult.technicians.find(r=>r.id==='TEC-1').deleted,true);
const canonicalBefore=JSON.stringify(unified.data);context.migrarUsuarios();assert.equal(JSON.stringify(unified.data),canonicalBefore);
// Archived tabs no longer affect authentication/synchronization.
rows[1][2]='bad legacy edit';accountRows[1][2]='bad legacy edit';assert.equal(call('snapshot').complete,true);
const canonicalTech=unifiedResult.technicians.find(r=>r.id==='TEC-4');
const edited={...canonicalTech,password:'pbkdf2_sha256$600000$'+'d'.repeat(32)+'$'+'e'.repeat(64),operations:['credential'],base_version:canonicalTech.credential_version,credential_version:canonicalTech.credential_version+1,must_change:false};
assert.equal(call('update',edited).acknowledged_id,'TEC-4');assert.equal(call('snapshot').technicians.find(r=>r.id==='TEC-4').password,edited.password);
assert.equal(unified.data.find(r=>r[0]==='TEC-4')[6],edited.password);
// Devices cannot demote/update privileged users or assign their role through uploads.
const privileged=call('snapshot').accounts.find(r=>r.id==='TEC-2');assert.equal(call('update',{...privileged,operations:['metadata'],base_meta_version:privileged.meta_version}).code,403);
const newUnified={...newRecord,id:'NEW-USER',name:'new.user',role:'developer',must_change:true,operations:['register']};
uncertain=true;assert.equal(call('update',newUnified).ok,false);
let created=call('snapshot').technicians.find(r=>r.id==='NEW-USER');assert.equal(created.must_change,true);assert.equal(created.role,'technician');
assert.equal(call('update',newUnified).acknowledged_id,'NEW-USER');
// Sheet-driven role changes, revocation, verifier reset and malformed snapshots.
unified.data.find(r=>r[0]==='TEC-4')[3]='comercial';assert.equal(call('snapshot').accounts.find(r=>r.id==='TEC-4').role,'commercial');
unified.data.find(r=>r[0]==='TEC-4')[4]='bloqueado';assert.equal(call('snapshot').accounts.find(r=>r.id==='TEC-4').active,false);
const oldCredential=call('snapshot').accounts.find(r=>r.id==='TEC-4').credential_version;
unified.data.find(r=>r[0]==='TEC-4')[6]=changed.password;assert.equal(call('snapshot').accounts.find(r=>r.id==='TEC-4').credential_version,oldCredential+1);
const snapshotProperties=JSON.stringify(properties);unified.data.push([...unified.data[1]]);assert.equal(call('snapshot').code,422);assert.equal(JSON.stringify(properties),snapshotProperties);unified.data.pop();
const deletedIndex=unified.data.findIndex(r=>r[0]==='NEW-USER');unified.data.splice(deletedIndex,1);assert.equal(call('snapshot').technicians.find(r=>r.id==='NEW-USER').deleted,true);
console.log('Unified users contract passed: backups, identity merge, idempotent migration, archived tabs ignored, role separation, credential edits, revocation, retry and no partial snapshot writes.');

// Unified device tab keeps remote updates separate from signed billing columns.
remoteRows.splice(0,remoteRows.length,
 ['controller_id','instalacao','url','ultimo_estado_informado','ultima_comunicacao','ultimo_sinal_tunel','revisao'],
 ['controller','Garagem','https://site.trycloudflare.com','CONECTADO',new Date().toISOString(),new Date().toISOString(),1]);
remote=makeTab(remoteRows,'DMax_Remoto');
subRows=[['controller_id','instalacao','situacao','aviso_em','prazo_final','mensagem'],
 ['controller','Garagem','pendente','','','Regularize'],['offline-device','Sem túnel','regular','','','']];
subscriptions=makeTab(subRows,'Assinaturas');
const beforeMerge=verifyNotice(call('snapshot').subscription);
context.unificarEquipamentos();
assert.equal(subscriptions.hidden,true);
assert.equal(remoteRows[0][7],'situacao');
assert.equal(remoteRows[1][7],'pendente');
const merged=verifyNotice(call('snapshot').subscription);
assert.equal(merged.deadline,beforeMerge.deadline);
assert.equal(merged.revision,beforeMerge.revision);
const copyCount=Object.keys(extraSheets).length;
context.unificarEquipamentos();assert.equal(Object.keys(extraSheets).length,copyCount);
register({...registration,revision:5});assert.equal(remoteRows[1][7],'pendente');
assert.equal(verifyNotice(call('snapshot').subscription).deadline,beforeMerge.deadline);
assert.equal(call('remote_directory').clients.some(x=>x.controller_id==='offline-device'),false);
remoteRows[1][7]='regular';assert.equal(verifyNotice(call('snapshot').subscription).state,'regular');
console.log('Unified device contract passed: backups, idempotence, preserved deadlines, billing-only rows and independent remote updates.');

// Deleted canonical identities must override stale pre-migration role caches.
const canonicalDeleted=JSON.parse(properties['identity.NEW-USER']);
assert.equal(canonicalDeleted.deleted,true);
properties['user.NEW-USER']=JSON.stringify({...canonicalDeleted,name:'obsolete.login',deleted:false,active:true,password:changed.password});
assert.equal(call('snapshot').complete,true);
assert.equal(call('snapshot').technicians.find(r=>r.id==='NEW-USER').name,canonicalDeleted.name);
assert.equal(call('snapshot').technicians.find(r=>r.id==='NEW-USER').deleted,true);
const canonicalActive=JSON.parse(properties['identity.TEC-4']);
properties['account.TEC-4']=JSON.stringify({...canonicalActive,name:'obsolete.account'});
assert.equal(call('snapshot').complete,true);
// Removing each global role publishes a revocation; repeated sync stays stable.
for(const role of ['technician','developer','commercial']){
 const id='DELETE-'+role,name='delete.'+role;
 unified.data.push([id,'Delete fixture',name,role,'ativo','',changed.password]);
 assert.equal(call('snapshot').complete,true);
 unified.data.splice(unified.data.findIndex(r=>r[0]===id),1);
 const result=call('snapshot');assert.equal(result.complete,true);
 const deleted=[...result.technicians,...result.accounts].find(r=>r.id===id);
 assert.equal(deleted.active,false);assert.equal(deleted.deleted,true);
 const meta=deleted.meta_version;
 assert.equal([...call('snapshot').technicians,...call('snapshot').accounts].find(r=>r.id===id).meta_version,meta);
}
// Canonical identities still reserve their login; conflicting new IDs are rejected.
unified.data.push(['TAKEOVER','Unsafe','delete.developer','developer','ativo','',changed.password]);
const beforeConflict=JSON.stringify(properties);
assert.equal(call('snapshot').code,409);assert.equal(JSON.stringify(properties),beforeConflict);
unified.data.pop();
console.log('Deleted users contract passed: canonical precedence, three-role revocations, idempotence and takeover protection.');
// Ambiguous legacy identities without a canonical record still fail safely.
properties['user.LEGACY-CONFLICT']=JSON.stringify({...canonicalDeleted,id:'LEGACY-CONFLICT',name:'legacy.one'});
properties['account.LEGACY-CONFLICT']=JSON.stringify({...canonicalDeleted,id:'LEGACY-CONFLICT',name:'legacy.two'});
assert.equal(call('snapshot').code,409);
delete properties['user.LEGACY-CONFLICT'];delete properties['account.LEGACY-CONFLICT'];
const beforeDiagnosis=JSON.stringify(properties),beforeDiagnosisSheet=JSON.stringify(unified.data);
context.diagnosticarUsuarios();
assert.equal(JSON.stringify(properties),beforeDiagnosis);assert.equal(JSON.stringify(unified.data),beforeDiagnosisSheet);

// Developer-only company bridge management verifies the actual password.
const devPassword='fixture-bridge-developer-pass';
const realHash=password=>{const salt='13579bdf'.repeat(4);return 'pbkdf2_sha256$600000$'+salt+'$'+crypto.pbkdf2Sync(password,Buffer.from(salt,'hex'),600000,32,'sha256').toString('hex');};
unified.data.push(['BRIDGE-DEV','Bridge developer','bridge.dev','developer','ativo','',realHash(devPassword)]);
assert.equal(call('snapshot').complete,true);
const manage=(record,login='bridge.dev',password=devPassword)=>JSON.parse(context.doPost({postData:{contents:JSON.stringify({action:'manage_user',controller_id:'controller',key:'fixture-device-key',actor_login:login,actor_password:password,record})}}).text);
const member={id:'MEMBER-NEW',name:'member.new',full_name:'Novo membro',role:'commercial',status:'ativo',expires:'',password:realHash('fixture-new-member-pass')};
assert.equal(manage(member,'', '').code,401);
assert.equal(manage(member,'delete.commercial',devPassword).code,403);
assert.equal(manage(member,'bridge.dev','wrong-password').code,401);
assert.equal(manage(member).acknowledged_id,member.id);
assert.equal(call('snapshot').accounts.find(r=>r.id===member.id).role,'commercial');
assert.equal(manage({...member,role:'technician'}).acknowledged_id,member.id);
assert.equal(call('snapshot').technicians.find(r=>r.id===member.id).role,'technician');
assert.equal(manage({...member,role:'developer',status:'bloqueado'}).acknowledged_id,member.id);
assert.equal(call('snapshot').accounts.find(r=>r.id===member.id).active,false);
assert.equal(manage({...member,status:'excluido'}).acknowledged_id,member.id);
assert.equal(call('snapshot').accounts.find(r=>r.id===member.id).deleted,true);
assert.equal(manage({...member,role:'root'}).code,422);
assert.equal(manage({...member,name:'renamed.user'}).code,409);
assert.equal(manage({...member,id:'TAKEOVER-ID'}).code,409);
// Verifier cannot be used as a password proof even though snapshots include it.
assert.equal(manage(member,'bridge.dev',realHash(devPassword)).code,401);
assert.equal(JSON.stringify(properties).includes(devPassword),false);
assert.equal(JSON.stringify(unified.data).includes(devPassword),false);
assert.equal(context.verifyPlatformPassword_('Senha áç 🔋',realHash('Senha áç 🔋')),true);
console.log('Bridge management contract passed: password proof, creation, role changes, revocation, immutable identity and no password storage.');
// An active commercial with the correct password still cannot manage members.
assert.equal(manage(member).acknowledged_id,member.id);
assert.equal(manage({...member,id:'FORBIDDEN-MEMBER',name:'forbidden.member'},member.name,'fixture-new-member-pass').code,403);
// Bounded authentication attempts also apply to direct calls, not only the UI.
const attemptProperty='bridge.attempt.'+crypto.createHash('sha256').update('controller').digest('hex');
delete properties[attemptProperty];
for(let i=0;i<5;i++)assert.equal(manage(member,'missing.user','invalid').code,403);
assert.equal(manage(member).code,429);delete properties[attemptProperty];
