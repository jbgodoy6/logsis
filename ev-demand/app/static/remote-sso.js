'use strict';
(async()=>{
 const status=document.getElementById('sso-status');
 const ticket=new URLSearchParams(location.hash.slice(1)).get('ticket');
 history.replaceState(null,'',location.pathname);
 try{
  if(!/^[0-9a-f]{64}$/.test(ticket||''))throw Error('Passe ausente. Abra este cliente pela central Windows.');
  const response=await fetch('/api/remote/sso',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({ticket})});
  if(!response.ok)throw Error('A entrada não foi validada. Volte à central e clique novamente em Acessar cliente.');
  location.replace('/ui/overview');
 }catch(error){status.textContent=error.message;}
})();
