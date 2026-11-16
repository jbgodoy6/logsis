const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict'),crypto=require('node:crypto');
let editor=true,writes=0,drop=false,protectedCell=false;
const cells=['USR-4','Usuário Quatro','user4','comercial','ativo','',''];
const sheet={getRange:(row,col,height,width)=>({
 getValues:()=>[[...cells]],getValue:()=>cells[col-1],
 setValue:value=>{if(protectedCell)throw Error('fixture-secret');writes++;if(!drop)cells[col-1]=value;}
})};
const book={getId:()=>vm.runInContext('DMAX_SHEET_ID',ctx)};
const ctx=vm.createContext({
 SpreadsheetApp:{getUi:()=>{if(!editor)throw Error('No editor');return {};},getActiveSpreadsheet:()=>book,flush:()=>{}},
 PropertiesService:{getScriptProperties:()=>({})},
 LockService:{getScriptLock:()=>({tryLock:()=>true,releaseLock:()=>{}})}
});
vm.runInContext(fs.readFileSync('google-apps-script/Code.gs','utf8'),ctx);
ctx.sha_=s=>crypto.createHash('sha256').update(s).digest('hex');ctx.unifiedSheet_=()=>sheet;
ctx.portalRoster_=()=>[{row:4,id:cells[0],name:cells[2],deleted:false,expires_at:null}];
function target(){return {row:4,id:cells[0],name:cells[2],fingerprint:ctx.sha_(JSON.stringify(cells))};}
const hash='pbkdf2_sha256$600000$'+'a'.repeat(32)+'$'+'b'.repeat(64),before=cells.slice(0,6);
assert.equal(ctx.salvarSenhaDaPlanilha(target(),hash).ok,true);assert.equal(cells[6],hash);assert.deepEqual(cells.slice(0,6),before);assert.equal(writes,1);
const stale=target();cells[1]='Nome mudou';assert.equal(ctx.salvarSenhaDaPlanilha(stale,hash).ok,false);assert.equal(writes,1);
editor=false;assert.equal(ctx.salvarSenhaDaPlanilha(target(),hash).ok,false);assert.equal(writes,1);editor=true;
assert.equal(ctx.salvarSenhaDaPlanilha(target(),'plain-password').ok,false);assert.equal(writes,1);
protectedCell=true;const denied=ctx.salvarSenhaDaPlanilha(target(),hash);assert.equal(denied.ok,false);assert.ok(!JSON.stringify(denied).includes('fixture-secret'));assert.equal(writes,1);protectedCell=false;
cells[6]='';drop=true;assert.equal(ctx.salvarSenhaDaPlanilha(target(),hash).ok,false);
console.log('Sheet password PASS: writes only G, preserves identity, editor required, stale row denied, verifier checked, write confirmed, errors sanitized.');
