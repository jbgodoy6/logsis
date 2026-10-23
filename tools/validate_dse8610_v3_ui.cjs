// Isolated Docker lab only. Run with NODE_PATH pointing to an installed Playwright package.
const {chromium}=require('playwright'),fs=require('fs'),cp=require('child_process'),path=require('path');
const root=path.resolve(__dirname,'..'),URL=process.env.GRAFANA_TEST_URL||'http://127.0.0.1:3300';
function assert(x,message){if(!x)throw Error(message)}
function sql(text){return cp.execFileSync('docker',['exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-X','-qAt','-v','ON_ERROR_STOP=1'],{input:text,encoding:'utf8'});}
async function contact(p){return p.locator('div[style*="data:image/svg"]').evaluateAll(es=>es.flatMap(e=>{let raw;try{raw=decodeURIComponent(getComputedStyle(e).backgroundImage)}catch{return []}const m=raw.match(/data-state="([^"]+)"/);return m?[m[1]]:[]}));}
async function colours(p){return p.locator('div[style*="data:image/svg"]').evaluateAll(async es=>{
 const wires=await Promise.all(es.filter(e=>['447px','534px'].includes(e.style.top)).map(async e=>{
  const img=new Image(),src=getComputedStyle(e).backgroundImage.slice(5,-2);const loaded=await new Promise(r=>{img.onload=()=>r(true);img.onerror=()=>r(false);img.src=src});
  let stroke;if(loaded){const c=document.createElement('canvas');c.width=Math.max(1,Math.ceil(e.clientWidth));c.height=Math.ceil(e.clientHeight);const ctx=c.getContext('2d');ctx.drawImage(img,0,0,c.width,c.height);const data=ctx.getImageData(0,0,c.width,c.height).data;let at=0;for(let i=0;i<data.length;i+=4)if(data[i+3]>data[at+3])at=i;if(data[at+3])stroke=[data[at],data[at+1],data[at+2]];}
  return {top:e.style.top,left:e.getBoundingClientRect().left,stroke};
 }));const pre=wires.filter(x=>x.top==='447px').sort((a,b)=>a.left-b.left);return {gmg:pre[0]?.stroke,bus:pre[1]?.stroke,post:wires.find(x=>x.top==='534px')?.stroke};
});}
async function clipping(p){return p.locator('div[role=button][style*="position: absolute"]').evaluateAll(es=>es.flatMap(e=>{
 const spans=[...e.querySelectorAll('span')].filter(s=>!s.childElementCount&&s.textContent.trim());if(!spans.length)return [];
 const r=e.getBoundingClientRect();if(!r.width||!r.height)return [];const ranges=spans.map(s=>{const t=document.createRange();t.selectNodeContents(s);return t.getBoundingClientRect()});
 return Math.min(...ranges.map(x=>x.left))<r.left-1||Math.max(...ranges.map(x=>x.right))>r.right+1||Math.max(...ranges.map(x=>x.bottom))-Math.min(...ranges.map(x=>x.top))>r.height+1?[e.textContent]:[];
}));}
const rgb=h=>h.slice(1).match(/../g).map(x=>parseInt(x,16));
(async()=>{let b,backup=false;const report={result:'pending',widths:[],states:[],filteredStates:[]};try{
 sql('CREATE TABLE logsis_8610_v3_ui_backup AS TABLE id_dse8610;');backup=true;
 const vals={1:65535,2:82,3:32767,4:76,5:278,6:274,7:1800,8:600,18:0,22:186420,23:192186,24:46780,28:32765,29:600,38:29,39:2147483647,40:1,41:0,42:0,43:0,52:1};
 [2201,2206,2198,3810,3820,3802,2840,2820,2850].forEach((v,i)=>vals[9+i]=v);for(let i=19;i<=21;i++)vals[i]=62140;for(let i=25;i<=27;i++)vals[i]=97;for(let i=30;i<=35;i++)vals[i]=i<33?2200:3810;
 const columns=['time','gsm_rssi','"WiFi_rssi"',...Array.from({length:52},(_,i)=>'mdb'+(i+1))];
 const statements=['BEGIN;TRUNCATE id_dse8610;'];
 for(const [time,h,kwh] of [['7 hours',360000,2000],['1 minute',372600,2180]]){
  vals[36]=h;vals[37]=kwh;
  statements.push('INSERT INTO id_dse8610 ('+columns.join(',')+') VALUES ('+["now()-interval '"+time+"'",-53,-67,...Array.from({length:52},(_,i)=>vals[i+1]??0)].join(',')+');');
 }statements.push('COMMIT;');sql(statements.join('\n'));
 b=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE||'/usr/bin/chromium',args:['--no-sandbox']});const p=await b.newPage({viewport:{width:1366,height:1200}}),errors=[];
 p.on('pageerror',e=>errors.push(String(e)));p.on('response',async r=>{if(r.url().includes('/api/ds/query'))try{for(const v of Object.values((await r.json()).results||{}))if(v.error)errors.push(v.error)}catch{}});
 await p.goto(URL+'/dashboard/import');await p.getByText('Upload dashboard JSON file').waitFor({timeout:45000});await p.locator('input[type=file]').setInputFiles(root+'/dist/DSE8610_V3_IMPORTAR.json');await p.getByRole('button',{name:'Import (Overwrite)',exact:true}).click();await p.waitForURL(/\/d\/logsis-dse8610-v1-bus\//,{timeout:45000});
 const url=URL+'/d/logsis-dse8610-v1-bus?orgId=1&kiosk&from=now-6h&to=now';await p.goto(url);await p.getByText('DISJUNTOR FECHADO',{exact:true}).waitFor({timeout:45000});
 for(const width of [320,390,768,1366,1920]){
  await p.setViewportSize({width,height:1200});const seen=new Set(),bad=[];
  for(const y of [0,700,1400,2100,2800,3500,4200,4900]){
   await p.locator('.scrollbar-view').first().evaluate((e,y)=>e.scrollTo(0,y),y);await p.waitForTimeout(300);
   for(const v of await p.getByText(/^MDB\d{2}$/).allTextContents())seen.add(v);
   bad.push(...await clipping(p));assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Horizontal overflow '+width);
  }
  assert(seen.size===45,'45 grouped readings + 7 BUS readings: '+width+' got '+seen.size);assert(!bad.length,'Text clipped '+width+': '+JSON.stringify(bad.slice(0,10)));report.widths.push({width,channels:52,textClipping:0});console.log('Responsive width passed:',width);
  if([390,1366].includes(width)){await p.locator('.scrollbar-view').first().evaluate(e=>e.scrollTo(0,0));await p.waitForTimeout(200);await p.screenshot({path:root+'/DSE8610_V3_'+(width===390?'CELULAR':'DESKTOP')+'.png'});}
 }
 await p.setViewportSize({width:1366,height:1200});
 for(const y of [0,500,1000,1400]){await p.locator('.scrollbar-view').first().evaluate((e,y)=>e.scrollTo(0,y),y);await p.waitForTimeout(200);if(await p.getByText('HORAS / PERÍODO',{exact:true}).count())break;}
 await p.getByText('ENERGIA / PERÍODO',{exact:true}).evaluate(e=>e.scrollIntoView({block:'center'}));await p.getByText('3.50 h',{exact:true}).waitFor();await p.getByText('18.00 kWh',{exact:true}).waitFor();await p.screenshot({path:root+'/DSE8610_V3_PERIODO.png'});report.period={hours:3.5,kwh:18,baselineOutsideFilter:true};
 await p.locator('.scrollbar-view').first().evaluate(e=>e.scrollTo(0,0));
 for(const [name,g,bus,k,mode,w,t,s,label] of [
  ['OUTROS_GRUPOS',0,1,0,0,0,0,0,'STOP'],['WARNING',1,1,0,2,1,0,0,'MANUAL'],['TRIP',1,0,0,3,1,1,0,'TESTE C/ CARGA'],['SHUTDOWN',0,1,0,6,1,1,1,'TESTE S/ CARGA'],['OFF',0,0,1,7,0,0,0,'OFF'],['INVALIDO',1,1,2,1,0,0,0,'AUTO']]){
  const updates=['mdb52='+k,'mdb40='+mode,'mdb41='+w,'mdb42='+t,'mdb43='+s];for(let n=9;n<=14;n++)updates.push('mdb'+n+'='+(g?2200:0));for(let n=30;n<=35;n++)updates.push('mdb'+n+'='+(bus?2200:0));
  sql('UPDATE id_dse8610 SET '+updates.join(',')+' WHERE time=(SELECT MAX(time) FROM id_dse8610);');
  const expected=k===1?'fechado':k===0?'aberto':'indisponivel';let actual,cs,ok=false;
  const expectedColours={gmg:rgb(g?'#f2495c':'#e9bd79'),bus:rgb(bus?'#f2495c':'#e5eef7'),post:rgb(bus?'#f2495c':'#e5eef7')};
  for(let i=0;i<100;i++){
   actual=await contact(p);cs=await colours(p);
   if(actual[0]===expected&&Object.keys(expectedColours).every(key=>JSON.stringify(cs[key])===JSON.stringify(expectedColours[key]))&&(await p.getByText(label,{exact:true}).first().isVisible().catch(()=>false))){ok=true;break}await p.waitForTimeout(150);
  }
  assert(ok,'Auto-refresh state '+name+' '+JSON.stringify({actual,cs,expectedColours}));
  const short=k===1?'FECHADO':k===0?'ABERTO':'INVÁLIDO';await p.getByText(short,{exact:true}).first().waitFor();
  if(w||t||s)await p.getByText('GERADOR / '+(s?'SHUTDOWN':t?'TRIP':'WARNING'),{exact:true}).waitFor();
  report.states.push({name,breaker:expected,mode:label,lineColours:cs,autoRefresh:true});console.log('Auto-refresh state passed:',name);
  if(['OUTROS_GRUPOS','WARNING','TRIP','SHUTDOWN'].includes(name))await p.screenshot({path:root+'/DSE8610_V3_'+name+'.png'});
 }
 // Add an older valid state inside the selection. Latest voltage-only row must retain the later closure.
 sql("INSERT INTO id_dse8610 SELECT (jsonb_populate_record(NULL::id_dse8610,to_jsonb(t)||jsonb_build_object('time',now()-interval '2 hours','mdb52',0))).* FROM id_dse8610 t ORDER BY time DESC LIMIT 1; INSERT INTO id_dse8610 SELECT (jsonb_populate_record(NULL::id_dse8610,to_jsonb(t)||jsonb_build_object('time',now()-interval '1 hour','mdb52',1))).* FROM id_dse8610 t ORDER BY time DESC LIMIT 1; UPDATE id_dse8610 SET mdb52=NULL WHERE time=(SELECT MAX(time) FROM id_dse8610);");
 for(const [end,expected] of [['now-90m','aberto'],['now','fechado']]){
  await p.goto(url.replace('to=now','to='+end));let ok=false;for(let i=0;i<100;i++){if((await contact(p))[0]===expected){ok=true;break}await p.waitForTimeout(150)}assert(ok,'Filtered breaker '+end);report.filteredStates.push({end,breaker:expected});
 }
 await p.locator('.scrollbar-view').first().evaluate(e=>e.scrollTo(0,e.scrollHeight));await p.waitForTimeout(500);await p.getByText(/HISTÓRICOS E ALERTAS \/ DSE8610/).first().click();await p.waitForTimeout(400);
 for(const y of [2000,3000,4000,5000,6000,7000,8000,9000]){await p.locator('.scrollbar-view').first().evaluate((e,y)=>e.scrollTo(0,y),y);await p.waitForTimeout(350)}
 assert(!errors.length,'Grafana errors '+errors.join(';'));report.result='passed';report.import='UI upload/Overwrite passed';report.histories=11;report.errors=errors;report.scope='Grafana 11.2.2 with synthetic data in isolated Docker; lab table restored; no production or physical switching';
 fs.writeFileSync(root+'/DSE8610_V3_UI_VALIDACAO.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
 }finally{if(b)await b.close();if(backup)sql('BEGIN;TRUNCATE id_dse8610;INSERT INTO id_dse8610 SELECT * FROM logsis_8610_v3_ui_backup;DROP TABLE logsis_8610_v3_ui_backup;COMMIT;');}
})().catch(e=>{console.error(e);process.exit(1)});
