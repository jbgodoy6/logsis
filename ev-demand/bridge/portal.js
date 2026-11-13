(() => {
 'use strict';
 const key='dmax-access-position';
 if('scrollRestoration' in history)history.scrollRestoration='manual';
 function save(path){try{sessionStorage.setItem(key,JSON.stringify({path,y:scrollY,x:scrollX,at:Date.now()}));}catch(_){}}
 document.addEventListener('submit',e=>{const form=e.target;if(form.action.endsWith('/logout')){try{sessionStorage.removeItem(key);}catch(_){}return;}save(new URL(form.action).pathname==='/login'?'/':new URL(form.action).pathname);},true);
 document.addEventListener('click',e=>{const a=e.target.closest('a[href]');if(a&&a.target!=='_blank'){const u=new URL(a.href);if(u.origin===location.origin)save(u.pathname);}},true);
 addEventListener('pagehide',()=>{try{if(!sessionStorage.getItem(key))save(location.pathname);}catch(_){}});
 try{const p=JSON.parse(sessionStorage.getItem(key)||'null');sessionStorage.removeItem(key);if(p&&p.path===location.pathname&&Date.now()-p.at<60000){const restore=()=>scrollTo({top:p.y,left:p.x,behavior:'instant'});requestAnimationFrame(restore);addEventListener('load',restore,{once:true});}}catch(_){}
 let stopped=false,timer;
 addEventListener('pagehide',()=>{stopped=true;clearTimeout(timer);});
 if(!document.getElementById('sim-live'))return;
 async function tick(){
  try{
   const r=await fetch('/api/simulation',{cache:'no-store'});
   if(!r.ok)throw Error('Sessão encerrada. Entre novamente.');
   const data=await r.json();document.getElementById('sim-total').textContent=data.total.toFixed(1)+' kW';
   for(const p of data.ports){document.getElementById('sim-soc-'+p.id).textContent=p.soc.toFixed(1)+'%';document.getElementById('sim-power-'+p.id).textContent=p.kw.toFixed(1)+' kW';document.getElementById('sim-status-'+p.id).textContent=!p.connected?'Sem veículo':p.soc>=100?'Carga completa':p.paused?'Pausado':p.kw>0?'Carregando':'Aguardando potência';}
   document.getElementById('sim-live').textContent='Simulação atualizada · sem acesso a equipamentos reais';
  }catch(e){document.getElementById('sim-live').textContent=e.message;}
  if(!stopped)timer=setTimeout(tick,2000);
 }
 timer=setTimeout(tick,1000);
})();
