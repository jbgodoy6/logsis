const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const logs=[];
const ctx=vm.createContext({
 console:{info:s=>logs.push(s),error:s=>logs.push(s)},
 LockService:{getScriptLock:()=>({tryLock:()=>true,releaseLock:()=>{}})},
 PropertiesService:{getScriptProperties:()=>({})},
 Utilities:{getUuid:()=> 'a'.repeat(32)},
 ContentService:{MimeType:{JSON:'json'},createTextOutput:text=>({text,setMimeType(){return this;}})}
});
vm.runInContext(fs.readFileSync('google-apps-script/Code.gs','utf8'),ctx);
assert.equal(JSON.parse(ctx.doGet().text).script_revision,'sheet-user-write-1');
ctx.portalSession_=()=>({actor:{role:'developer'},rows:[]});
ctx.sjcl.misc.pbkdf2=()=>{throw new TypeError('fixture-password-and-verifier-must-stay-private');};
const result=ctx.portalSaveUser('fixture-token',{actor_password:'fixture-actor-password',password:'fixture-password',confirmation:'fixture-password'});
assert.equal(result.code,503);
const failure=JSON.parse(logs.find(s=>s.startsWith('DMAX_SAVE_FAILURE ')).slice('DMAX_SAVE_FAILURE '.length));
assert.equal(failure.stage,'generate_verifier');assert.equal(failure.kind,'TypeError');
assert.ok(!logs.join('\n').includes('fixture-'));assert.ok(!JSON.stringify(result).includes('fixture-'));
logs.length=0;
assert.equal(ctx.portalReply_(()=>({value:1}),{stage:'lock'}).ok,true);
assert.ok(logs.some(s=>s.includes('"stage":"complete"')));
console.log('Save trace PASS: revision, failing stage, error type, completion, no secret or exception-message disclosure.');
