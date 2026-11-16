const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const cells=['TARGET','Nome','target','commercial','ativo','',''];let drop=false;
const props={getProperty:()=>null,setProperty:()=>{},deleteProperty:()=>{},getProperties:()=>({})};
const sheet={getLastRow:()=>2,getRange:()=>({setValues:rows=>{if(!drop)cells.splice(0,cells.length,...rows[0]);},getValues:()=>[[...cells]]})};
const actor={id:'DEV',name:'dev',role:'developer',active:true,deleted:false,must_change:false,expires_at:null,password:'unused'};
const context=vm.createContext({PropertiesService:{getScriptProperties:()=>props},SpreadsheetApp:{flush:()=>{},openById:()=>({getSpreadsheetTimeZone:()=> 'UTC'})}});
vm.runInContext(fs.readFileSync('google-apps-script/Code.gs','utf8'),context);
context.unifiedSheet_=()=>sheet;
context.unifiedState_=()=>({records:[actor],source:{sheet,rows:[{id:'TARGET',row:2,credential_pending:cells[6]===''}]}});
context.historicalUsers_=()=>({byId:{},byName:{}});
context.sha_=()=> 'safe-hash';context.verifyPlatformPassword_=()=>true;
const verifier='pbkdf2_sha256$600000$'+'a'.repeat(32)+'$'+'b'.repeat(64);
const record={id:'TARGET',full_name:'Nome alterado',name:'target',role:'commercial',status:'ativo',expires:'',password:verifier};
function save(password){return context.bridgeManageUser_(props,{controller_id:'WEB-DEV',actor_login:'dev',actor_password:'fixture',record:{...record,password}});}
// Leaving the new password empty must still allow editing a pending account.
assert.equal(save('').ok,true);assert.equal(cells[1],'Nome alterado');assert.equal(cells[6],'');
assert.equal(save(verifier).ok,true);assert.equal(cells[6],verifier);
// A storage write that silently did not persist cannot be reported as success.
cells[6]='';drop=true;
assert.throws(()=>save(verifier),e=>e.code===503);
console.log('Save confirmation PASS: pending metadata saved, verifier persisted, unconfirmed write rejected.');
