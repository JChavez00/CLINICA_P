(() => {
 const mensajes=document.getElementById('ia-mensajes');
 const form=document.getElementById('ia-form');
 const input=document.getElementById('ia-pregunta');
 const enviar=document.getElementById('ia-enviar');
 let ocupado=false;
 function agregar(texto,tipo){const d=document.createElement('div');d.className='ia-mensaje '+tipo;d.textContent=texto;mensajes.appendChild(d);mensajes.scrollTop=mensajes.scrollHeight;return d;}
 async function preguntar(texto){if(ocupado||!texto.trim())return;ocupado=true;enviar.disabled=true;input.disabled=true;agregar(texto,'usuario');input.value='';const espera=agregar('Consultando información...','bot');try{const r=await fetch('/api/asistente-ia',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pregunta:texto})});const data=await r.json();espera.remove();if(!r.ok)throw new Error(data.error||'Error al consultar.');agregar(data.respuesta||'No se recibió respuesta.','bot');}catch(e){espera.remove();agregar(e.message,'error');}finally{ocupado=false;enviar.disabled=false;input.disabled=false;input.focus();}}
 form.addEventListener('submit',e=>{e.preventDefault();preguntar(input.value)});
 document.querySelectorAll('[data-pregunta]').forEach(b=>b.addEventListener('click',()=>preguntar(b.dataset.pregunta)));
})();
