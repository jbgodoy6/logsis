const fs=require('fs'),vm=require('vm'),crypto=require('crypto'),assert=require('assert');
let checks=0;
function check(condition,label){assert(condition,label);checks++;}
let clock=Date.parse('2026-10-28T15:00:00Z'),reads=0;
const properties=new Map(),cache=new Map();
const base=[['id','nome','login','situacao','valido_ate'],['1','Técnico de teste','tecnico.teste','ATIVO','']];
let rows=base.map(r=>r.slice());
const props={getProperty:k=>properties.get(k)||null,setProperties:o=>{for(const[k,v]of Object.entries(o))properties.set(k,v);},deleteProperty:k=>properties.delete(k)};
const cacheService={get:k=>{const v=cache.get(k);return v&&v.end>clock?v.value:null;},put:(k,v,s)=>cache.set(k,{value:v,end:clock+s*1000}),remove:k=>cache.delete(k)};
const signed=b=>[...b].map(n=>n>127?n-256:n);
const context=vm.createContext({
  console:{log:()=>{}},
  Date:class extends Date{static now(){return clock;}},
  Utilities:{getUuid:()=>crypto.randomUUID(),Charset:{UTF_8:'UTF-8'},DigestAlgorithm:{SHA_256:'sha256'},
    computeHmacSha256Signature:(text,key)=>signed(crypto.createHmac('sha256',key).update(text).digest()),
    computeDigest:(algorithm,text)=>signed(crypto.createHash('sha256').update(text).digest())},
  PropertiesService:{getScriptProperties:()=>props},CacheService:{getScriptCache:()=>cacheService},
  LockService:{getScriptLock:()=>({tryLock:()=>true,releaseLock:()=>{}})},
  SpreadsheetApp:{openById:id=>{check(id==='17HCp2CX3eUZXqQsTkTNDZvrLkGqzZQrJkCfeHo-toPQ','fixed sheet');return {getSheetByName:name=>{check(name==='Tecnicos','fixed tab');return {getDataRange:()=>({getDisplayValues:()=>{reads++;return rows.map(r=>r.slice());}})}}};}},
  ContentService:{MimeType:{JSON:'json'},createTextOutput:text=>({text,setMimeType(){return this;}})}
});
vm.runInContext(fs.readFileSync(__dirname+'/Code.gs','utf8'),context);
function api(input){return context.api_(input);}
function seed(){cache.clear();rows=base.map(r=>r.slice());properties.set('AUTH_PEPPER','test-only-pepper');properties.set('AUTH_EPOCH','one');properties.set('AUTH_PASSWORD_HASH',context.hmac_('test-password-only','test-only-pepper'));}
function login(){return api({action:'login',login:'tecnico.teste',password:'test-password-only'});}
seed();let result=login();check(result.ok&&result.token.length===64,'active technician receives token');
check(api({action:'verify',token:result.token}).ok,'live session');
for(const status of ['INATIVO','EXCLUIDO','EXCLUÍDO','excluído','', 'PENDENTE']){
 seed();rows[1][3]=status;check(!login().ok,'deny status '+status);
}
seed();result=login();rows[1][3]='INATIVO';check(!api({action:'verify',token:result.token}).ok,'no cached active status after revocation');
seed();result=login();rows.splice(1);check(!api({action:'verify',token:result.token}).ok,'deleted row revokes');
seed();result=login();rows[1][0]='2';check(!api({action:'verify',token:result.token}).ok,'recreated account id revokes');
seed();rows.push(rows[1].slice());check(!login().ok,'duplicate login denied');
seed();rows.push(['1','Outro','outro','ATIVO','']);check(!login().ok,'duplicate id denied');
seed();rows[1][4]='27/10/2026';check(!login().ok,'expired validity');
seed();rows[1][4]='31/02/2027';check(!login().ok,'invalid calendar date');
seed();rows[1][4]='28/10/2026';check(login().ok,'valid through local end of date');
check(context.active_({id:'1',login:'a',situacao:'ATIVO',valido_ate:'28/10/2026'},Date.parse('2026-10-29T02:59:59Z')),'BRT last second accepted');
check(!context.active_({id:'1',login:'a',situacao:'ATIVO',valido_ate:'28/10/2026'},Date.parse('2026-10-29T03:00:00Z')),'BRT next day denied');
seed();let before=reads;check(!api({action:'login',login:'tecnico.teste',password:'wrong'}).ok,'wrong password');check(reads===before,'no sheet lookup on wrong password');
check(!api({action:'verify',token:'0'.repeat(64)}).ok,'forged bearer');
seed();result=login();clock+=601000;check(!api({action:'verify',token:result.token}).ok,'expired session');
seed();result=login();properties.set('AUTH_EPOCH','two');check(!api({action:'verify',token:result.token}).ok,'password epoch revokes');
seed();for(let i=0;i<10;i++)api({action:'login',login:'tecnico.teste',password:'wrong'});
assert.throws(()=>login(),/Muitas tentativas/);checks++;
seed();result=login();check(api({action:'logout',token:result.token}).ok,'logout');check(!api({action:'verify',token:result.token}).ok,'logout removes bearer');
const body=JSON.parse(context.doPost({postData:{contents:JSON.stringify({action:'login',login:'tecnico.teste',password:'wrong'})}}).text);
check(body.registryId==='17HCp2CX3eUZXqQsTkTNDZvrLkGqzZQrJkCfeHo-toPQ','response tied to fixed registry');
check(!JSON.stringify(body).includes('test-password-only'),'no credential returned');
properties.set('AUTH_PASSWORD_SETUP','new-password-for-test-only');context.configurarSenhaTecnica();
check(!properties.has('AUTH_PASSWORD_SETUP'),'temporary setup plaintext removed');
check(properties.get('AUTH_PASSWORD_HASH')!=='new-password-for-test-only','server stores HMAC, not raw password');
console.log(checks+' authorization checks passed (mock Google services, no real sheet/network).');
