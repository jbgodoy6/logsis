const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
let released=0,locked=true;
const ctx=vm.createContext({LockService:{getScriptLock:()=>({tryLock:()=>locked,releaseLock:()=>released++})}});
vm.runInContext(fs.readFileSync('google-apps-script/Code.gs','utf8'),ctx);
function tab(name,rows){return {getName:()=>name,getLastRow:()=>rows.length,getLastColumn:()=>rows[0].length,getRange:(r,c,h,w)=>({sort:spec=>{assert.equal(r,2);assert.equal(c,1);assert.equal(w,rows[0].length);const sorted=rows.slice(1).sort((a,b)=>String(a[1]).localeCompare(String(b[1]),'pt-BR')||String(a[0]).localeCompare(String(b[0]),'pt-BR'));rows.splice(1,h,...sorted);assert.equal(spec[0].column,2);assert.equal(spec[1].column,1);}})}}
const users=[['id','nome','login','perfil','situacao','validade','verificador','extra'],['Z','Zuleica','z','tecnico','ativo','','hash-z','=A2'],['B','Álvaro','b','comercial','bloqueado','','hash-b','nota-b'],['A','Álvaro','a','developer','ativo','','hash-a','nota-a']];
const clients=[['id','instalacao','url','estado','situacao','ultimo','sinal','rev','aviso','prazo','msg'],['Z','Zebra','https://z','CONECTADO','pendente','t','h',5,'aviso','prazo','msg'],['A','Árvore','https://a','DESCONECTADO','ativo','','',2,'','','']];
const original=new Map([...users.slice(1),...clients.slice(1)].map(r=>[r[0]+':'+r.length,JSON.stringify(r)]));
const u=tab('Usuarios',users),c=tab('DMax_Remoto',clients),book={getId:()=> '17HCp2CX3eUZXqQsTkTNDZvrLkGqzZQrJkCfeHo-toPQ',getSheetByName:n=>n==='Usuarios'?u:c};
ctx.passwordEditorBook_=()=>book;ctx.ordenarCadastros();assert.deepEqual(users.slice(1).map(r=>r[0]),['A','B','Z']);assert.equal(clients[1][0],'A');
for(const r of [...users.slice(1),...clients.slice(1)])assert.equal(JSON.stringify(r),original.get(r[0]+':'+r.length));
users.push(['C','Beatriz','c','tecnico','ativo','','hash-c','extra-c']);ctx.onEdit({source:book,range:{getSheet:()=>u,getRow:()=>5}});assert.deepEqual(users.slice(1).map(r=>r[0]),['A','B','C','Z']);
const before=JSON.stringify(users);locked=false;ctx.onEdit({source:book,range:{getSheet:()=>u,getRow:()=>2}});assert.equal(JSON.stringify(users),before);locked=true;
ctx.onEdit({source:book,range:{getSheet:()=>tab('Outra',users),getRow:()=>2}});ctx.onEdit({source:book,range:{getSheet:()=>u,getRow:()=>1}});assert.equal(released,2);
ctx.ordenarLinhas_(tab('Usuarios',[['id','nome']]));
console.log('Alphabetical sheet PASS: full rows, names, ID tie-break, headers, extra columns, credentials, pending deadlines, manual edits and lock contention.');
