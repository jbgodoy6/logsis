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
   const data=await response.json();const published=document.getElementById('remote-publication');if(published){const p=data.publication||{};published.textContent=!p.directory_enabled?'Planilha: plataforma desativada; configure Técnicos globais':p.pending?'Planilha: envio pendente; confira a atualização do Apps Script':p.published_at?'Planilha: última confirmação em '+new Date(p.published_at*1000).toLocaleString('pt-BR'):'Planilha: aguardando primeira confirmação';}state.textContent=data.connected?'Conectado':'Sem conexão confirmada';message.textContent=data.message;
   if(typeof data.url==='string'&&/^https:\/\/[a-z0-9-]+\.(?:trycloudflare\.com|tunnl\.gg)\/?$/.test(data.url)){link.href=data.url;link.textContent=data.url;}else{link.removeAttribute('href');link.textContent='Aguardando endereço';}
  }catch(error){state.textContent=error.message;}
  finally{if(!stopped)timer=setTimeout(update,5000);}
 };
 window.addEventListener('pagehide',()=>{stopped=true;clearTimeout(timer);});timer=setTimeout(update,1000);
})();
