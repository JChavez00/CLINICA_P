(() => {
  'use strict';
  const {nodo:n,nombres,estados}=window.recorridosUI;
  const $=id=>document.getElementById(id),fecha=v=>new Date(v).toLocaleString('es-PE',{timeZone:'America/Lima',dateStyle:'short',timeStyle:'medium'});
  const modulos={chat:'Asistente IA',reportes:'Reportes',tareas:'Tareas',calidad:'Calidad',cron:'Programador automático',manual:'Ejecución manual',programador:'Revisión del programador'};
  let registros=[],seleccion=null,turno=0;
  const badge=estado=>n('span',estados[estado]||estado,'tr-badge '+(estado==='error'?'error':estado==='degradado'?'degradado':''));
  async function api(url){const r=await fetch(url,{headers:{Accept:'application/json'}});const d=await r.json();if(!r.ok)throw new Error(d.error||'No se pudo cargar la actividad.');return d;}
  function error(e){$('ag-error').hidden=false;$('ag-error').textContent=e.message;}
  function lista(){
    const filtro=$('tr-filtro').value,filas=registros.filter(e=>!filtro||e.modulo===filtro);
    $('tr-lista').replaceChildren(...filas.map(e=>{
      const b=n('button',null,'tr-opcion');b.type='button';b.setAttribute('aria-pressed',String(e.id===seleccion));
      b.append(n('strong',nombres[e.agente]||e.agente),n('small',`${modulos[e.modulo]||e.modulo} · ${fecha(e.fecha)}`),badge(e.estado),n('small',`${e.duracion_ms.toLocaleString('es-PE')} ms · ${e.detalle_disponible?'Etapas registradas':'Registro parcial'}`));
      b.onclick=()=>abrir(e.id).catch(error);return b;
    }));
    if(!filas.length)$('tr-lista').append(n('p','No hay ejecuciones para este módulo.','tr-muted'));
  }
  function metrica(titulo,valor,nota){const d=n('article',null,'tr-metrica');d.append(n('span',titulo,'tr-muted'),n('strong',valor.toLocaleString('es-PE')),n('small',nota));return d;}
  function metricas(){
    const agentes=new Set(registros.filter(e=>e.agente!=='coordinador').map(e=>e.agente));
    const duraciones=registros.map(e=>e.duracion_ms).sort((a,b)=>a-b),mitad=Math.floor(duraciones.length/2);
    const mediana=duraciones.length?(duraciones.length%2?duraciones[mitad]:(duraciones[mitad-1]+duraciones[mitad])/2):0;
    $('tr-metricas').replaceChildren(metrica('Actividad reciente',registros.length,'Hasta 50 ejecuciones, no total histórico'),metrica('Agentes participantes',agentes.size,'Agentes distintos en estos registros'),metrica('Con etapas registradas',registros.filter(e=>e.detalle_disponible).length,'Los registros parciales se conservan'),metrica('Duración mediana',Math.round(mediana),'Milisegundos · incluye respaldos y errores'));
  }
  async function abrir(id){
    const actual=++turno;seleccion=id;lista();$('tr-detalle').setAttribute('aria-busy','true');
    try{
      const d=await api('/api/agentes/ejecuciones/'+encodeURIComponent(id));if(actual!==turno)return;
      const url=new URL(location.href);url.searchParams.set('ejecucion',id);history.replaceState(null,'',url);
      const panel=$('tr-detalle'),cab=n('header'),titulo=n('div');titulo.append(n('small','RECORRIDO DE LA EJECUCIÓN','tr-kicker'),n('h3',nombres[d.agente]||d.agente),n('p',fecha(d.fecha),'tr-muted'));cab.append(titulo,badge(d.estado));
      const datos=n('dl',null,'tr-datos');for(const [k,v] of [['Módulo',modulos[d.modulo]||d.modulo],['Proveedor',d.proveedor||'No registrado'],['Modelo',d.modelo||'No registrado'],['Duración total',`${d.duracion_ms.toLocaleString('es-PE')} ms`]]){const par=n('div');par.append(n('dt',k),n('dd',v));datos.append(par);}
      panel.replaceChildren(cab,datos,n('p',d.alcance,'tr-muted'));
      if(d.pasos.length){
        const camino=n('ol',null,'tr-camino');camino.setAttribute('aria-label','Diagrama del recorrido registrado');
        for(const paso of d.pasos){const li=n('li');li.append(n('span',paso.titulo));camino.append(li);}panel.append(camino,n('h4','Etapas y validaciones'));
        const pasos=n('ol',null,'tr-pasos');for(const paso of d.pasos){const li=n('li',null,paso.estado),encabezado=n('div',null,'tr-paso-cabecera');encabezado.append(n('strong',paso.titulo),n('small',`${paso.inicio_ms}–${paso.fin_ms} ms · ${paso.duracion_ms} ms`));li.append(encabezado,n('p',paso.detalle));if(paso.estado!=='ok')li.append(badge(paso.estado));pasos.append(li);}panel.append(pasos);
      }else panel.append(n('p','Este registro conserva el resultado global. No hay evidencia de pasos intermedios.','tr-aviso'));
      panel.append(n('h4','Participantes de este flujo'));
      panel.append(n('p',d.participantes.length>1?'Operaciones relacionadas mediante un identificador de flujo compartido.':'Esta ejecución tiene un único participante registrado. No se presupone colaboración adicional.','tr-muted'));
      for(const hijo of d.participantes.filter(p=>p.padre_id)){
        const padre=d.participantes.find(p=>p.id===hijo.padre_id);if(!padre)continue;
        const vinculo=n('div',null,'tr-vinculo'),origen=n('div'),destino=n('div'),conexion=n('span',hijo.herramienta==='confirmar_tarea'?'Confirmación humana →':'Revisión de estadísticas →','tr-conexion');
        origen.append(n('strong',nombres[padre.agente]||padre.agente),n('small',padre.proveedor||'Local'));destino.append(n('strong',nombres[hijo.agente]||hijo.agente),n('small',hijo.proveedor||'Local'));vinculo.append(origen,conexion,destino);panel.append(vinculo);
      }
      for(const p of d.participantes){const a=n('a',null,'tr-relacion');a.href='/actividad-agentes?ejecucion='+encodeURIComponent(p.id);a.setAttribute('aria-current',String(p.id===d.id));a.append(n('strong',nombres[p.agente]||p.agente),n('span',` · ${p.herramienta.replaceAll('_',' ')} · ${estados[p.estado]||p.estado}`));if(p.padre_id)a.append(n('small',p.herramienta==='confirmar_tarea'?' · Confirmación del borrador':' · Revisión adicional de estadísticas'));a.onclick=e=>{if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();abrir(p.id).catch(error);};panel.append(a);}
      if(d.error_codigo)panel.append(n('p','Código controlado: '+d.error_codigo,'tr-aviso'));
      const acciones=n('div',null,'tr-acciones'),exportar=n('a','Descargar evidencia JSON'),imprimir=n('button','Imprimir / guardar PDF');exportar.href='/api/agentes/ejecuciones/'+encodeURIComponent(d.id)+'?descargar=1';imprimir.type='button';imprimir.onclick=()=>window.print();acciones.append(exportar,imprimir);panel.append(acciones,n('p',d.privacidad,'tr-muted'),n('p','Ejecución: '+d.id+' · Flujo: '+d.flujo_id,'tr-id'));
    }finally{if(actual===turno)$('tr-detalle').removeAttribute('aria-busy');}
  }
  async function cargar(){
    $('ag-error').hidden=true;$('tr-recargar').disabled=true;
    try{const d=await api('/api/agentes/ejecuciones');registros=d.ejecuciones;metricas();lista();const id=seleccion||new URLSearchParams(location.search).get('ejecucion')||registros[0]?.id;if(id)await abrir(id);else $('tr-detalle').replaceChildren(n('h3','La actividad aparecerá aquí'),n('p','Realiza una consulta en Asistente IA, genera un reporte o prepara una tarea. Su recorrido se guardará con la ejecución.','tr-muted'));}
    finally{$('tr-recargar').disabled=false;}
  }
  $('tr-filtro').onchange=lista;$('tr-recargar').onclick=()=>cargar().catch(error);cargar().catch(error);
})();
