// Local-only Apps Script service double for testing the actual HTML and server code.
const fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto'),http=require('node:http'),path=require('node:path');
const root=path.join(__dirname,'../google-apps-script');
const password='fixture-web-developer',salesPassword='fixture-web-commercial';
const hash=p=>{const salt='1234567890abcdef'.repeat(2);return 'pbkdf2_sha256$600000$'+salt+'$'+crypto.pbkdf2Sync(p,Buffer.from(salt,'hex'),600000,32,'sha256').toString('hex');};
const users=[['id','nome','login','perfil','situacao','valido_ate','verificador'],['DEV','Desenvolvedor fixture','developer','developer','ativo','',hash(password)],['SALES','Comercial fixture','commercial','commercial','ativo','',hash(salesPassword)]];
const remotes=[['controller_id','instalacao','url','ultimo_estado_informado','ultima_comunicacao','ultimo_sinal_tunel','revisao'],['CLIENT-1','Caratinga','https://fixture-client.trycloudflare.com','CONECTADO',new Date().toISOString(),new Date().toISOString(),1]];
const properties={'directory.unified':'1'};
const tab=data=>({getLastRow:()=>data.length,getRange:(r,c,h,w)=>({getValues:()=>Array.from({length:h},(_,i)=>Array.from({length:w},(_,j)=>data[r-1+i]?.[c-1+j]??'')),setValues:values=>values.forEach((row,i)=>{data[r-1+i]??=[];row.forEach((v,j)=>data[r-1+i][c-1+j]=v);})})});
const tabs={Usuarios:tab(users),DMax_Remoto:tab(remotes)};
const props={getProperty:k=>properties[k]??null,getProperties:()=>({...properties}),setProperty:(k,v)=>{properties[k]=String(v);},deleteProperty:k=>{delete properties[k];}};
const context={HtmlService:{createHtmlOutput:html=>({html,setTitle(){return this;},addMetaTag(){return this;}})},Date,JSON,Math,Number,String,Object,Array,Boolean,Error,RegExp,Set,
 PropertiesService:{getScriptProperties:()=>props},LockService:{getScriptLock:()=>({tryLock:()=>true,releaseLock:()=>{}})},
 SpreadsheetApp:{openById:()=>({getSheetByName:n=>tabs[n]||null,getSpreadsheetTimeZone:()=> 'America/Sao_Paulo'}),getUi:()=>{throw Error('No bound UI');}},
 Utilities:{getUuid:()=>crypto.randomUUID(),Charset:{UTF_8:'utf8'},DigestAlgorithm:{SHA_256:'sha256'},computeDigest:(_,value)=>[...crypto.createHash('sha256').update(value).digest()],computeHmacSha256Signature:(value,key)=>[...crypto.createHmac('sha256',key).update(value).digest()],formatDate:d=>new Date(d).toISOString().slice(0,10),parseDate:value=>new Date(value.replace(' ','T')+'-03:00')}
};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(root,'Code.gs'),'utf8'),context);
const rpc=`window.google={script:{run:new Proxy({},{get(_t,name){if(name==='withSuccessHandler')return success=>make(success,()=>{});}})}};function make(success,failure){return new Proxy({},{get(_t,name){if(name==='withFailureHandler')return f=>make(success,f);if(name==='withSuccessHandler')return f=>make(f,failure);return (...args)=>fetch('/rpc',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,args})}).then(r=>r.json()).then(success).catch(failure);}});}`;
const allowed=new Set(['portalLogin','portalLogout','portalState','portalClients','portalMembers','portalSaveUser']);
http.createServer((req,res)=>{
 if(req.method==='GET'&&req.url==='/'){res.setHeader('Content-Type','text/html;charset=utf-8');return res.end(context.doGet().html.replace('<head>','<head><script src="/rpc.js"></script>'));}
 if(req.url==='/rpc.js'){res.setHeader('Content-Type','application/javascript');return res.end(rpc);}
 if(req.method==='POST'&&req.url==='/rpc'){let body='';req.on('data',c=>body+=c);req.on('end',()=>{try{const data=JSON.parse(body);if(!allowed.has(data.name))throw Error('Denied');res.setHeader('Content-Type','application/json');res.end(JSON.stringify(context[data.name](...data.args)));}catch(_){res.statusCode=400;res.end('{"ok":false,"code":503}');}});return;}
 res.statusCode=404;res.end();
}).listen(8771,'127.0.0.1',()=>console.log('Local portal fixture on 8771'));
