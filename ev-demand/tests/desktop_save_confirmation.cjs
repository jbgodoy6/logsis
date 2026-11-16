const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const cells=['TARGET','Nome','target','commercial','ativo','',''];let drop=false,omitColumn=0;const choices={};
const props={getProperty:()=>null,setProperty:()=>{},deleteProperty:()=>{},getProperties:()=>({})};
const sheet={getLastRow:()=>2,getRange:(row,col)=>({
 setValues:rows=>{if(!drop){cells.splice(0,cells.length,...rows[0]);if(omitColumn)cells[omitColumn-1]='';}},getValues:()=>[[...cells]],
 getDataValidation:()=>choices[col]?{getCriteriaType:()=> 'list',getCriteriaValues:()=>[choices[col]],getAllowInvalid:()=>false}:null
})};
const actor={id:'DEV',name:'dev',role:'developer',active:true,deleted:false,must_change:false,expires_at:null,password:'unused'};
const context=vm.createContext({PropertiesService:{getScriptProperties:()=>props},SpreadsheetApp:{DataValidationCriteria:{VALUE_IN_LIST:'list',VALUE_IN_RANGE:'range'},flush:()=>{},openById:()=>({getSpreadsheetTimeZone:()=> 'UTC'})}});
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
assert.equal(cells[3],'comercial');assert.equal(cells[4],'ativo');
choices[4]=['Desenvolvedor','Comercial','Técnico'];choices[5]=['Ativo','Bloqueado','Excluído'];
assert.equal(save(verifier).ok,true);assert.equal(cells[3],'Comercial');assert.equal(cells[4],'Ativo');
assert.equal(context.sheetUserChoice_(sheet,2,4,'technician',true),'Técnico');
assert.equal(context.sheetUserChoice_(sheet,2,5,'excluido',false),'Excluído');
const rangeRuleSheet={getRange:()=>({getDataValidation:()=>({getCriteriaType:()=> 'range',getCriteriaValues:()=>[{getDisplayValues:()=>[['Comercial'],['Técnico']]}],getAllowInvalid:()=>false})})};
assert.equal(context.sheetUserChoice_(rangeRuleSheet,2,4,'commercial',true),'Comercial');
choices[4]=['Desenvolvedor'];assert.throws(()=>save(verifier),e=>e.code===422);choices[4]=['Comercial'];
for(const col of [4,5]){omitColumn=col;assert.throws(()=>save(verifier),e=>e.code===503);}omitColumn=0;
// A storage write that silently did not persist cannot be reported as success.
cells[6]='';drop=true;
assert.throws(()=>save(verifier),e=>e.code===503);
console.log('Save confirmation PASS: pending metadata saved, verifier persisted, unconfirmed write rejected.');
