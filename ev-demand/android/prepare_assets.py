"""Reuse reviewed LAN UI; Android owns transport/session and in-app navigation."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
out=root/'android/build/assets';out.mkdir(parents=True,exist_ok=True)
source=root/'lan/assets'
html=(source/'index.html').read_text()
html=html.replace('CENTRAL NA REDE · v1.2','ANDROID · v1.0.1').replace('D-Max Central de Acesso · v1.2','Sua operação, sempre por perto · Android 1.0.1').replace('Uma central.<br>Todos os seus clientes.','Seu D-Max.<br>Sempre por perto.')
html=html.replace('Clientes e demonstrações na rede da empresa.','Clientes e demonstrações no seu Android.').replace('WINDOWS · REDE LOCAL','ANDROID · CENTRAL INDEPENDENTE')
html=html.replace('Acessar cliente abre o D-Max em outra aba; entre nele com seu login.','Acessar cliente abre o D-Max dentro do aplicativo, usando seu acesso atual. Use Voltar à central para retornar.')
start=html.index('<div id="settings-view"');end=html.index('</main>',start)
html=html[:start]+'''<div id="settings-view" hidden><section><h2>Configurações deste Android</h2><p>A central conecta diretamente à plataforma Google. O computador Windows pode permanecer desligado.</p><form id="settings-form"><label>URL da plataforma Google Apps Script<input name="platform_url" type="url" required maxlength="1000"></label><label>Sua senha de desenvolvedor<input name="password" type="password" required maxlength="200" autocomplete="current-password"></label><button>Salvar plataforma</button></form><p id="discovery-status"></p></section></div>'''+html[end:]
js=(source/'app.js').read_text()
start=js.index('async function bootstrap()');end=js.index('function remember()',start)
js=js[:start]+'''let requestSequence=0;
const pendingRequests=new Map();
window.dmaxReply=(id,result)=>{const pending=pendingRequests.get(id);if(!pending)return;pendingRequests.delete(id);clearTimeout(pending.timer);if(!result.ok){if(result.code===401)clearSession();pending.reject(Error(result.message||'Não foi possível concluir.'));}else pending.resolve(result);};
function nativeCall(name,args=[]){return new Promise((resolve,reject)=>{if(pendingRequests.size>=8){reject(Error('Aguarde a operação atual.'));return;}const id=String(++requestSequence);const timer=setTimeout(()=>{pendingRequests.delete(id);reject(Error('A consulta demorou demais. Confira a conexão antes de tentar novamente.'));},150000);pendingRequests.set(id,{resolve,reject,timer});try{DMaxNative.request(id,name,JSON.stringify(args));}catch(e){clearTimeout(timer);pendingRequests.delete(id);reject(Error('Não foi possível acessar o serviço do aplicativo.'));}});}
async function bootstrap(){return nativeCall('bootstrap');}
async function rpc(name,...args){return nativeCall(name,args);}
'''+js[end:]
start=js.index('async function loadSettings()');end=js.index('(async()=>{try{const result=await bootstrap()',start)
js=js[:start]+'''async function loadSettings(){const data=await nativeCall('loadSettings');$('settings-form').elements.platform_url.value=data.platform_url;$('discovery-status').textContent='Android 1.0.1 · Conexão direta à plataforma Google.';}
$('settings-form').onsubmit=event=>{event.preventDefault();const form=event.currentTarget;action(form,async()=>{try{const result=await nativeCall('saveSettings',[Object.fromEntries(new FormData(form))]);clearSession();notice(result.message);}finally{form.elements.password.value='';}});};
'''+js[end:]
start=js.index('async function openClient(id)');end=js.index('function editDevice(',start)
js=js[:start]+'''async function openClient(id){await action($('overview-view'),async()=>{await rpc('portalOpenClient',id);notice('');});}
'''+js[end:]
# Real destinations stay native; the browser cannot accidentally leave the app.
js=js.replace("link.href=url.href;link.target='_blank';", "link.href='#';")
(out/'index.html').write_text(html)
(out/'app.js').write_text(js)
shutil.copy2(source/'d-max-logo.png',out/'d-max-logo.png')
(out/'style.css').write_text((source/'style.css').read_text()+'\n'+(root/'android/mobile.css').read_text())
print('Android assets prepared from lan/assets')
