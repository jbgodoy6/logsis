'use strict';
(() => {
 const status=document.getElementById('maintenance-status');
 if(!status)return;
 const refresh=async()=>{const r=await fetch('/api/maintenance',{cache:'no-store'});if(!r.ok())throw Error('Acesso encerrado');return r.json()};
 refresh().then(d=>status.textContent=d.message).catch(e=>status.textContent=e.message);
 document.querySelectorAll('[data-maintenance]').forEach(button=>button.addEventListener('click',async()=>{
  const action=button.dataset.maintenance,file=document.getElementById(action+'-file').files[0];
  if(!file){status.textContent='Selecione o arquivo.';return;}
  if(!confirm('Confirmar '+(action==='update'?'atualização':'restauração')+'? O D-Max reiniciará e fará backup antes de alterar dados.'))return;
  button.disabled=true;
  try{
   const info=await refresh();status.textContent='Enviando e validando…';
   const r=await fetch('/api/maintenance/'+action,{method:'POST',headers:{'Content-Type':'application/octet-stream','X-DMax-Maintenance':info.csrf},body:file});
   const data=await r.json();if(!r.ok())throw Error(data.detail||'Operação recusada');status.textContent=data.message;
  }catch(e){status.textContent=e.message;}finally{button.disabled=false;}
 }));
})();
