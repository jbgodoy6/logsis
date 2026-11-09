// Executes the exact shipped Apps Script with local Google-service doubles.
const vm=require('node:vm'),fs=require('node:fs'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[2],'utf8');
let rows=[['id','nome','login','situacao','valido_ate'],['TEC-1','Técnico Um','tecnico.um','ativo','']];
const properties={'device.controller':crypto.createHash('sha256').update('fixture-device-key').digest('hex')};
let uncertain=false;
let subscriptions=null;
const sheet={
 getLastRow:()=>rows.length,
 getRange:(start,column,height,width)=>({
  getValues:()=>Array.from({length:height},(_,i)=>Array.from({length:width},(_,j)=>rows[start-1+i]?.[column-1+j]??'')),
  setValues:values=>{values.forEach((row,i)=>{rows[start-1+i]??=[];row.forEach((v,j)=>rows[start-1+i][column-1+j]=v);});if(uncertain){uncertain=false;throw Error('lost response after commit');}}
 })};
const props={getProperty:k=>properties[k]??null,setProperty:(k,v)=>properties[k]=String(v),deleteProperty:k=>delete properties[k],getProperties:()=>({...properties})};
const context={
 Date,JSON,Math,Number,String,Object,Array,Boolean,Error,RegExp,
 PropertiesService:{getScriptProperties:()=>props},
 SpreadsheetApp:{openById:()=>({getSheetByName:name=>name==='Assinaturas'?subscriptions:sheet,getSpreadsheetTimeZone:()=> 'America/Sao_Paulo'})},
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
