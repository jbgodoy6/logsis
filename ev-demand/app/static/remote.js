'use strict';
(() => {
 const state=document.getElementById('remote-state'),message=document.getElementById('remote-message'),link=document.getElementById('remote-url');
 if(!state)return;
 let stopped=false,timer;
 const update=async()=>{
  try{
   const response=await fetch('/api/remote',{cache:'no-store',redirect:'error'});
   if([401,403].includes(response.status)){stopped=true;throw Error('Sessão encerrada. Entre novamente.');}
   if(!response.ok)throw Error('Sem confirmação de atualização');
   const data=await response.json();state.textContent=data.connected?'Conectado':'Sem conexão confirmada';message.textContent=data.message;
   if(typeof data.url==='string'&&/^https:\/\/[a-z0-9-]+\.tunnl\.gg\/?$/.test(data.url)){link.href=data.url;link.textContent=data.url;}
  }catch(error){state.textContent=error.message;}
  finally{if(!stopped)timer=setTimeout(update,5000);}
 };
 window.addEventListener('pagehide',()=>{stopped=true;clearTimeout(timer);});timer=setTimeout(update,1000);
})();
