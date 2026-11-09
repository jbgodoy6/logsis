// Exercise the exact TypeScript Edge handler under Node's standard type stripper.
const fs=require('node:fs');const vm=require('node:vm');const assert=require('node:assert/strict');const {stripTypeScriptTypes}=require('node:module');
const source=fs.readFileSync('cloud/supabase/functions/dmax-ingest/index.ts','utf8');let handler;let forwarded;
const scope={Request,Response,Uint8Array,TextDecoder,AbortSignal,JSON,Deno:{serve:f=>handler=f,env:{get:n=>n==='SUPABASE_URL'?'https://project.example':n==='SUPABASE_SERVICE_ROLE_KEY'?'test-server-key':undefined}},fetch:async(url,init)=>{forwarded={url,init};return new Response(JSON.stringify({acknowledged_ids:['a'.repeat(32)]}),{status:200})}};
vm.runInNewContext(stripTypeScriptTypes(source),scope);
(async()=>{
 assert.equal((await handler(new Request('https://ingest.example',{method:'GET'}))).status,405);
 assert.equal((await handler(new Request('https://ingest.example',{method:'POST',body:'{}'}))).status,401);
 const headers={Authorization:'Bearer '+'d'.repeat(43)};
 assert.equal((await handler(new Request('https://ingest.example',{method:'POST',headers,body:'bad'}))).status,400);
 assert.equal((await handler(new Request('https://ingest.example',{method:'POST',headers,body:'x'.repeat(1500001)}))).status,413);
 const response=await handler(new Request('https://ingest.example',{method:'POST',headers,body:JSON.stringify({controller_id:'test',records:[{id:'a'.repeat(32)}]})}));
 assert.equal(response.status,200);assert.equal(forwarded.url,'https://project.example/rest/v1/rpc/dmax_ingest');
 assert.equal(JSON.parse(forwarded.init.body).p_token,'d'.repeat(43));assert.equal(forwarded.init.headers.apikey,'test-server-key');
 assert.equal((await response.json()).acknowledged_ids.length,1);
 scope.fetch=async()=>new Response('private SQL details',{status:401});
 const denied=await handler(new Request('https://ingest.example',{method:'POST',headers,body:JSON.stringify({controller_id:'test',records:[]})}));
 assert.equal(denied.status,403);assert(!((await denied.text()).includes('private')));
 console.log('Edge handler contract: 8 scenarios passed (hosted Deno deployment still required).');
})().catch(e=>{console.error(e);process.exit(1)});
