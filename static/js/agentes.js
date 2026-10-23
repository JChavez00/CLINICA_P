(() => {
  'use strict';
  const $=id=>document.getElementById(id), app=$('agentes-app'), modulo=app.dataset.modulo;
  let grafico, token=null;
  const el=(tag,t)=>{const n=document.createElement(tag);if(t!=null)n.textContent=String(t);return n;};
  const hora=v=>new Date(v).toLocaleString('es-PE',{timeZone:'America/Lima'});
  const tipos={reporte:'Reporte administrativo',estadisticas:'Resumen de estadísticas',alerta_alta:'Alerta de demanda alta',consulta_ml:'Consulta de pronósticos ML'};
  const dias=['lunes','martes','miércoles','jueves','viernes','sábado','domingo'];
  const estados={ok:'Completada',degradado:'Completada sin IA',error:'Error',ejecutando:'En curso'};
  function resumenEjecucion(e){const r=e.resultado||{};if(e.error_codigo)return 'No se pudo completar. Consulta el historial técnico.';if(r.informe_id)return 'Informe generado. Disponible en Reportes inteligentes.';if(r.alertas&&(!r.disponible||!r.emisiones_evaluadas))return 'No hay emisiones guardadas suficientes para evaluar alertas ALTA.';if(r.alertas)return r.alertas.length?`Posible demanda ALTA: ${r.alertas.map(x=>x.fecha).join(', ')}. Aviso del panel.`:'No hay alertas ALTA en las emisiones consultadas.';if(r.total_atenciones!=null)return `${r.desde} a ${r.hasta}: ${r.total_atenciones} atenciones registradas.`;if(r.resultados)return `${r.resultados.length} fechas de ML consultadas. Predicciones experimentales.`;return 'Consulta completada; no hay datos suficientes para un resumen.';}
  const frecuencia=c=>c.frecuencia==='semanal'?`Cada ${dias[c.dia_semana]}`:c.frecuencia==='mensual'?`Día ${c.dia_mes} de cada mes`:'Todos los días';
  function error(e){$('ag-error').hidden=false;$('ag-error').textContent=e.message;}
  async function api(url,datos){const r=await fetch(url,{method:datos?'POST':'GET',headers:{'Content-Type':'application/json','X-CSRF-Token':app.dataset.csrf},...(datos?{body:JSON.stringify(datos)}:{})});const d=await r.json();if(!r.ok)throw new Error(d.error||'No se pudo completar la operación.');return d;}
  function tabla(id,columnas,filas){const t=el('table'),h=el('thead'),b=el('tbody'),r=el('tr');columnas.forEach(c=>r.append(el('th',c)));h.append(r);filas.forEach(f=>{const r=el('tr');f.forEach(c=>r.append(el('td',c??'—')));b.append(r);});t.append(h,b);$(id).replaceChildren(t);}
  function tarjetas(pares){$('ag-indicadores').replaceChildren(...pares.map(([t,v])=>{const d=el('div');d.className='stat-card';d.append(el('strong',v),el('span',t));return d;}));}
  function chart(etiquetas,datos,titulo){if(grafico){grafico.destroy();grafico=null;}const zona=$('ag-grafico').parentElement;document.getElementById('ag-sin-datos')?.remove();zona.hidden=!datos.length;if(!datos.length){const aviso=el('p',modulo==='calidad'?'No se detectaron incidencias con las reglas aplicadas.':'Sin observaciones para graficar; revisa el periodo y las secciones seleccionadas.');aviso.id='ag-sin-datos';zona.after(aviso);return;}if(!window.Chart){$('ag-estado').textContent='Gráfico no disponible. Las tablas contienen los datos completos.';return;}grafico=new Chart($('ag-grafico'),{type:'bar',data:{labels:etiquetas,datasets:[{label:titulo,data:datos,backgroundColor:'#286857'}]},options:{responsive:true,maintainAspectRatio:false,scales:{y:{beginAtZero:true,ticks:{precision:0}}}}});}
  function conclusiones(datos,agente,estado,advertencia){$('ag-agente').textContent=`Agente: ${agente} · Estado: ${estado}`;$('ag-conclusiones').replaceChildren(...(datos.conclusiones||[]).map(c=>el('li',c)));$('ag-advertencia').textContent=advertencia||'Conclusiones seleccionadas por IA entre hechos verificables; cifras calculadas por Python.';}
  async function informes(){const d=await api('/api/agentes/reportes');$('ag-informes').replaceChildren(...d.informes.map(i=>{const a=el('article');a.append(el('strong',`${i.desde} a ${i.hasta}`),el('p','Generado: '+hora(i.generado_en)),el('p',(i.archivos||[]).map(a=>a.formato.toUpperCase()+': '+a.estado.replaceAll('_',' ')).join(' · ')||'Contenido conservado; archivos se archivarán al descargar'));for(const formato of ['pdf','xlsx']){const l=el('a','Descargar '+formato.toUpperCase());l.href=`/api/agentes/reportes/${i.id}/${formato}`;a.append(l);}return a;}));}
  async function tareas(){
    const d=await api('/api/agentes/tareas');
    $('ag-programador').textContent=d.programador.mensaje+' '+d.programador.revisiones.map(r=>r.origen+': '+hora(r.fecha)+(r.ultima_tarea?' · Última tarea: '+hora(r.ultima_tarea):'')).join(' | ');
    const tabla=el('table'),head=el('thead'),fila=el('tr'),body=el('tbody');
    ['Nombre','Tipo','Frecuencia y horario','Próxima ejecución (Perú)','Última ejecución (Perú)','Estado','Acciones'].forEach(t=>fila.append(el('th',t)));head.append(fila);
    for(const t of d.tareas){const c=t.configuracion,r=el('tr'),acciones=el('td');
      [t.nombre,tipos[c.tipo],`${frecuencia(c)} · ${String(c.hora).padStart(2,'0')}:00 · ${t.zona}`,t.proxima?hora(t.proxima):'Sin programación activa',t.ultima?hora(t.ultima):'Sin ejecuciones',t.activa?'Activa':'Inactiva'].forEach(v=>r.append(el('td',v)));
      const activar=el('button',t.activa?'Desactivar':'Activar');activar.className='btn';activar.onclick=async()=>{try{await api('/api/agentes/tareas/'+t.id,{activa:!t.activa});await tareas();}catch(e){error(e);}};
      const ejecutar=el('button','Ejecutar ahora');ejecutar.className='btn';ejecutar.disabled=!t.activa;ejecutar.onclick=async()=>{ejecutar.disabled=true;try{await api(`/api/agentes/tareas/${t.id}/ejecutar`,{ejecutar:true});await tareas();}catch(e){error(e);ejecutar.disabled=false;}};
      const historial=el('button','Ver historial');historial.className='btn';historial.onclick=()=>mostrarHistorial(d,t.id);
      const editar=el('button','Editar programación');editar.className='btn';editar.onclick=()=>editarTarea(t,acciones);
      acciones.append(activar,ejecutar,historial,editar);r.append(acciones);body.append(r);
    }
    tabla.append(head,body);$('ag-tareas').replaceChildren(tabla);
    if(!d.tareas.length)$('ag-tareas').append(el('p','Todavía no hay tareas confirmadas.'));
    mostrarHistorial(d);
  }
  function mostrarHistorial(d,id){
    const lista=d.ejecuciones.filter(e=>!id||e.tarea_id===id);
    tabla('ag-ejecuciones',['Tarea','Fecha Perú','Período','Duración ms','Estado','Intentos','Resultado / error'],lista.map(e=>[d.tareas.find(t=>t.id===e.tarea_id)?.nombre||'Tarea anterior',hora(e.fecha),e.periodo,e.resultado?.duracion_ms,estados[e.estado]||e.estado,e.intentos,resumenEjecucion(e)+(e.error_codigo?' · '+e.error_codigo:'')]));
    const cont=$('ag-ejecuciones');for(const e of lista){if(e.resultado?.informe_id){const p=el('p','Reporte del '+e.periodo+': ');for(const f of ['pdf','xlsx']){const a=el('a','Descargar '+f.toUpperCase());a.href=`/api/agentes/reportes/${e.resultado.informe_id}/${f}`;p.append(a,el('span',' '));}cont.append(p);}}
  }
  function editarTarea(t,zona){
    zona.querySelector('form')?.remove();const f=el('form'),campos={};
    for(const [k,titulo,v,tipo] of [['nombre','Nombre',t.nombre,'text'],['hora','Hora (0–23)',t.configuracion.hora,'number'],['dia_semana','Día semanal (lunes 0, domingo 6)',t.configuracion.dia_semana,'number'],['dia_mes','Día mensual (1–28)',t.configuracion.dia_mes,'number'],['zona','Zona horaria IANA',t.zona,'text']]){const label=el('label',titulo),input=el('input');input.type=tipo;input.value=v;input.required=true;campos[k]=input;label.append(input);f.append(label);}
    const select=el('select');for(const v of ['diaria','semanal','mensual']){const op=el('option',v);op.value=v;op.selected=v===t.configuracion.frecuencia;select.append(op);}f.append(select);
    const b=el('button','Confirmar nueva programación');b.type='submit';b.className='btn';f.append(b);f.onsubmit=async e=>{e.preventDefault();try{await api('/api/agentes/tareas/'+t.id,{confirmar:true,nombre:campos.nombre.value,zona:campos.zona.value,configuracion:{...t.configuracion,hora:Number(campos.hora.value),dia_semana:Number(campos.dia_semana.value),dia_mes:Number(campos.dia_mes.value),frecuencia:select.value}});await tareas();}catch(e){error(e);}};zona.append(f);
  }
  if($('ag-form'))$('ag-form').addEventListener('submit',async e=>{e.preventDefault();$('ag-error').hidden=true;$('ag-estado').textContent='Procesando solicitud…';const b=e.target.querySelector('button[type=submit]');b.disabled=true;try{
    if(modulo==='reportes'){
      const config={desde:$('ag-desde').value,hasta:$('ag-hasta').value,tipo:$('ag-tipo').value,secciones:[...document.querySelectorAll('[name=seccion]:checked')].map(n=>n.value)};
      const d=await api('/api/agentes/reportes',{configuracion:config,revision_groq:$('ag-revision').checked});const a=d.datos.estadisticas;
      window.recorridosUI.resumen($('ag-recorrido'),d);
      $('ag-resultado').hidden=false;tarjetas([['Atenciones',a.total_atenciones??'No incluida'],['Pacientes distintos',a.pacientes_unicos??'No incluida'],['Período',`${d.desde} a ${d.hasta}`]]);
      chart(a.por_mes.map(x=>x.mes),a.por_mes.map(x=>x.cantidad),'Atenciones observadas');tabla('ag-tabla',['Fecha observada','Cantidad'],a.por_dia.map(x=>[x.fecha,x.cantidad]));
      conclusiones(d.datos,d.agente,d.estado,d.advertencia);$('ag-pdf').href=`/api/agentes/reportes/${d.id}/pdf`;$('ag-excel').href=`/api/agentes/reportes/${d.id}/xlsx`;
      if(d.datos.ml)tabla('ag-ml',['Fecha','Tipo','Nivel','Estimado','Real'],(d.datos.ml.resultados||[]).map(x=>[x.fecha,x.tipo,x.nivel,x.cantidad,x.real]));else $('ag-ml').replaceChildren();
      await informes();
    } else if(modulo==='calidad'){
      const d=await api('/api/agentes/calidad',{desde:$('ag-desde').value,hasta:$('ag-hasta').value}),a=d.datos.agregado;
      window.recorridosUI.resumen($('ag-recorrido'),d);
      $('ag-resultado').hidden=false;tarjetas([['Registros evaluados',a.total],['Sin incidencias',a.completos],['Con incidencias',a.incompletos],['Posibles duplicados',a.posibles_duplicados]]);
      chart(Object.keys(a.categorias),Object.values(a.categorias),'Incidencias');tabla('ag-tabla',['Categoría','Incidencias'],Object.entries(a.categorias));conclusiones(d.datos,d.agente,d.estado,d.advertencia);
      $('ag-alcance').textContent=a.alcance+` Atenciones sin fecha: ${a.atenciones_fecha_nula}. ${a.costos}`;
      tabla('ag-incidencias',['Entidad','ID local','Categoría','Revisión'],d.datos.incidencias_locales.map(i=>[i.entidad,i.id,i.categoria,'Requiere revisión humana']));
      if(d.datos.incidencias_truncadas)$('ag-alcance').textContent+=' Se muestran las primeras 200 incidencias.';
    } else {
      const d=await api('/api/agentes/tareas/preview',{solicitud:$('ag-solicitud').value});token=d.confirmacion_token;$('ag-preview').hidden=false;$('ag-confirmar').disabled=false;
      window.recorridosUI.resumen($('ag-recorrido'),d);
      const c=d.datos.configuracion;$('ag-config').className='ag-config';$('ag-config').textContent=`Tarea: ${tipos[c.tipo]}\nProgramación: ${frecuencia(c)}\nHora: ${String(c.hora).padStart(2,'0')}:00\nZona: ${d.zona}\nPróxima ejecución: ${hora(d.proxima)}\nAcción: ${tipos[c.tipo]}\nAvisos: ${d.avisos}\n${d.advertencia||''}`;
    }
    $('ag-estado').textContent='Operación completada. Revisa los resultados y advertencias.';
  }catch(e){error(e);$('ag-estado').textContent='La operación no pudo completarse.';}finally{b.disabled=false;}});
  if(modulo==='tareas'){
    $('ag-solicitud').addEventListener('input',()=>{token=null;$('ag-preview').hidden=true;});
    $('ag-confirmar').addEventListener('click',async()=>{if(!token)return;$('ag-confirmar').disabled=true;try{const d=await api('/api/agentes/tareas/confirmar',{token,confirmar:true});window.recorridosUI.resumen($('ag-recorrido'),d);token=null;$('ag-preview').hidden=true;$('ag-estado').textContent='Tarea confirmada. Se ejecutará automáticamente cuando el cron externo esté configurado. También puedes ejecutarla ahora.';await tareas();}catch(e){error(e);$('ag-confirmar').disabled=false;}});
    tareas().catch(error);
  }
  if(modulo==='reportes')informes().catch(error);
  if(modulo==='reportes')$('ag-tipo').addEventListener('change',()=>{
    const inicio=$('ag-desde').value;if(!inicio)return;
    const [y,m,d]=inicio.split('-').map(Number);let fin=new Date(y,m-1,d);
    if($('ag-tipo').value==='semanal')fin.setDate(fin.getDate()+6);
    if($('ag-tipo').value==='mensual'){$('ag-desde').value=`${y}-${String(m).padStart(2,'0')}-01`;fin=new Date(y,m,0);}
    if($('ag-tipo').value!=='rango')$('ag-hasta').value=`${fin.getFullYear()}-${String(fin.getMonth()+1).padStart(2,'0')}-${String(fin.getDate()).padStart(2,'0')}`;
  });
})();
