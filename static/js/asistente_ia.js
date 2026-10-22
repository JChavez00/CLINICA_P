(() => {
  const mensajes=document.getElementById('ia-mensajes'),form=document.getElementById('ia-form'),input=document.getElementById('ia-pregunta'),enviar=document.getElementById('ia-enviar');
  let ocupado=false;
  function agregar(texto,tipo){const d=document.createElement('div');d.className='ia-mensaje '+tipo;d.textContent=texto;mensajes.appendChild(d);mensajes.scrollTop=mensajes.scrollHeight;return d;}
  async function preguntar(texto,seleccion){
    if(ocupado||(!seleccion&&!texto.trim()))return;ocupado=true;enviar.disabled=true;input.disabled=true;
    agregar(seleccion?'Consultar paciente seleccionado':texto,'usuario');input.value='';const espera=agregar('Consultando información…','bot');
    try{
      const r=await fetch('/api/asistente-ia',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(seleccion?{seleccion}:{pregunta:texto})});const data=await r.json();espera.remove();if(!r.ok)throw new Error(data.error||'Error al consultar.');
      const contenedor=agregar(data.respuesta||'No se recibió respuesta.','bot');
      const origen=document.createElement('small');origen.className='ia-origen';origen.textContent=`Atendió: ${data.agente||'coordinador'} · ${data.estado||'local'}`;contenedor.appendChild(origen);
      if(data.advertencia){const aviso=document.createElement('p');aviso.textContent=data.advertencia;contenedor.appendChild(aviso);}
      (data.opciones||[]).forEach(p=>{const b=document.createElement('button');b.type='button';b.className='btn';b.textContent=p.nombre;b.addEventListener('click',()=>preguntar('',p.id));contenedor.appendChild(b);});
      const d=data.datos||{},a=d.actual||d;
      if(a.total_atenciones!=null){const p=document.createElement('p');p.textContent=`${a.desde} a ${a.hasta}: ${a.total_atenciones} atenciones. `+(d.anterior?`Período anterior: ${d.anterior.total_atenciones}. Diferencia: ${d.diferencia}.`:'');contenedor.appendChild(p);}
      if(a.por_mes){const lista=document.createElement('ul');a.por_mes.forEach(m=>{const li=document.createElement('li');li.textContent=`${m.mes}: ${m.cantidad} atenciones`;lista.appendChild(li);});contenedor.appendChild(lista);}
      if(d.resultados){const lista=document.createElement('ul');d.resultados.forEach(p=>{const li=document.createElement('li');li.textContent=`${p.fecha} · ${p.tipo} · ${p.nivel??'Sin nivel'} · Estimado: ${p.cantidad??'sin emisión'}`;lista.appendChild(li);});contenedor.appendChild(lista);}
    }catch(e){espera.remove();agregar(e.message,'error');}finally{ocupado=false;enviar.disabled=false;input.disabled=false;input.focus();mensajes.scrollTop=mensajes.scrollHeight;}
  }
  form.addEventListener('submit',e=>{e.preventDefault();preguntar(input.value);});
  document.querySelectorAll('[data-pregunta]').forEach(b=>b.addEventListener('click',()=>preguntar(b.dataset.pregunta)));
})();
