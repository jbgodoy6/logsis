// Read-only protocol and error classification, with no real Google services.
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[2]||'google-apps-script/Code.gs','utf8');
let writes=0;
const props={getProperty:()=>null,getProperties:()=>({}),setProperty:()=>writes++,deleteProperty:()=>writes++};
const ctx=vm.createContext({
 PropertiesService:{getScriptProperties:()=>props},
 LockService:{getScriptLock:()=>({tryLock:()=>true,releaseLock:()=>{}})},
 SpreadsheetApp:{openById:()=>({getSheetByName:()=>null})},
 ContentService:{MimeType:{JSON:'json'},createTextOutput:text=>({text,setMimeType(){return this;}})}
});
vm.runInContext(source,ctx);
const banner=JSON.parse(ctx.doGet().text);
assert.equal(ctx.headersMatch_(['\uFEFF ID ',' Nome ','LOGIN'],['id','nome','login']),true);
assert.equal(ctx.headersMatch_(['id','login','nome'],['id','nome','login']),false);
assert.equal(ctx.headersMatch_(['id','nome','nome'],['id','nome','login']),false);
assert.equal(ctx.headersMatch_(['id','nome'],['id','nome','login']),false);
assert.equal(banner.desktop_protocol,1);assert.equal(banner.desktop_actions.length,10);
assert.equal(writes,0);
const missing=ctx.portalReply_(p=>ctx.portalRoster_(p));
assert.equal(missing.code,422);assert.equal(missing.diagnostic,'directory_not_prepared');assert.equal(writes,0);
assert.equal(ctx.portalReply_(()=>ctx.userRows_({getLastRow:()=>0},{})).diagnostic,'users_headers');
assert.equal(ctx.portalReply_(()=>ctx.userRows_({getLastRow:()=>1,getRange:()=>({getValues:()=>[['wrong']]})},{})).diagnostic,'users_headers');
// Exercise the roster wrapper rather than only the error serializer.
vm.runInContext(`unifiedSheet_=()=>({}); userRows_=()=>error_(422,'fixture-secret');`,ctx);
assert.equal(ctx.portalReply_(p=>ctx.portalRoster_(p)).diagnostic,'users_record');
vm.runInContext(`portalSession_=()=>({}); remoteDirectory_=()=>error_(422,'fixture-secret');`,ctx);
assert.equal(ctx.portalClients('not-a-real-token').diagnostic,'remote_record');
assert.equal(writes,0);
for(const diagnostic of ['users_headers','users_record','remote_headers','remote_record']){
 const result=ctx.portalReply_(()=>ctx.error_(422,'fixture-secret',diagnostic));
 assert.equal(result.diagnostic,diagnostic);assert.ok(!JSON.stringify(result).includes('fixture-secret'));
}
const unknown=ctx.portalReply_(()=>ctx.error_(422,'fixture-secret','fixture-secret'));
assert.equal(unknown.diagnostic,'validation');assert.ok(!JSON.stringify(unknown).includes('fixture-secret'));
assert.equal(ctx.portalReply_(()=>ctx.error_(409,'fixture-secret')).code,409);
assert.equal(ctx.portalReply_(()=>ctx.error_(401,'fixture-secret')).diagnostic,undefined);
assert.equal(ctx.desktopRequest_({action:'desktop_unknown'}).code,404);
const alerts=[];
ctx.SpreadsheetApp.getUi=()=>({alert:message=>alerts.push(message)});
vm.runInContext(`unifiedSheet_=()=>null; rows_=()=>({rows:[]}); historicalUsers_=()=>({byId:{},byName:{}});`,ctx);
ctx.diagnosticarUsuarios();
assert.equal(alerts.length,1);assert.ok(alerts[0].includes('este resultado valida apenas o cadastro legado do Raspberry'));
assert.equal(writes,0);
console.log('Desktop diagnostics contract passed: capabilities, preparation, validation, legacy safety, no writes or secret disclosure.');
