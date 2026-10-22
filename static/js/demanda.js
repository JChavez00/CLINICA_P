(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const charts = {};
  const fmt = v => typeof v === 'number' ? v.toLocaleString('es-PE', {maximumFractionDigits: 3}) : v ?? '—';
  const hora = iso => iso ? new Date(iso).toLocaleString('es-PE', {timeZone:'America/Lima'}) + ' (Perú)' : 'Sin emisiones guardadas';
  const texto = (id, v) => { $(id).textContent = v; };
  function elemento(tag, textoValor) { const n = document.createElement(tag); if (textoValor != null) n.textContent = textoValor; return n; }
  function tabla(id, columnas, filas) {
    const t = elemento('table'), h = elemento('thead'), tr = elemento('tr'), b = elemento('tbody');
    columnas.forEach(c => tr.append(elemento('th', c))); h.append(tr);
    filas.forEach(f => { const r = elemento('tr'); f.forEach(c => r.append(elemento('td', fmt(c)))); b.append(r); });
    t.append(h, b); $(id).replaceChildren(t);
  }
  function grafico(id, tipo, etiquetas, datasets, opciones = {}) {
    if (charts[id]) charts[id].destroy();
    if (!window.Chart) return;
    charts[id] = new Chart($(id), {type: tipo, data: {labels: etiquetas, datasets}, options: {
      responsive: true, maintainAspectRatio: false, scales: {y: {beginAtZero: true}}, ...opciones
    }});
  }
  async function api(url, opciones = {}) {
    const r = await fetch(url, {...opciones, headers: {'Accept': 'application/json', ...opciones.headers}});
    const d = await r.json(); if (!r.ok) throw new Error(d.error || 'No se pudo consultar.'); return d;
  }
  function error(e) { $('demanda-error').hidden = false; texto('demanda-error', e.message); }
  function comparar(meta) {
    const c = meta.resultados.clasificacion, r = meta.resultados.regresion;
    texto('ml-clasificador', c.ganador); texto('ml-regresor', r.ganador);
    for (const [o, datos, keys] of [['clasificacion', c, ['accuracy','precision_macro','recall_macro','f1_macro']], ['regresion', r, ['mae','rmse','r2']]]) {
      tabla('ml-tabla-' + o, ['Modelo', ...keys, 'Seleccionado'], Object.entries(datos.validacion).map(([n,m]) => [n,...keys.map(k => m[k]), n === datos.ganador ? 'Sí' : '—']));
    }
    const barras = (id, d, metrica, color) => grafico(id, 'bar', Object.keys(d.validacion), [{label: metrica, data: Object.values(d.validacion).map(m => m[metrica]), backgroundColor: color}]);
    barras('ml-f1', c, 'f1_macro', '#286857'); barras('ml-mae', r, 'mae', '#b58b46');
    const etiquetas = meta.etiquetas;
    tabla('ml-confusion', ['Real / Predicho', ...etiquetas], c.matriz_confusion.map((fila,i) => [etiquetas[i], ...fila]));
    tabla('ml-clases', ['Clase','Precision','Recall','F1','Casos'], etiquetas.map(e => {const d=c.reporte_clases[e]; return [e,d.precision,d.recall,d['f1-score'],d.support];}));
    texto('ml-prueba-clasificacion', `F1 macro: ${fmt(c.prueba.f1_macro)} · Referencia: ${fmt(c.referencia_prueba.f1_macro)}. Accuracy: ${fmt(c.prueba.accuracy)} · Referencia: ${fmt(c.referencia_prueba.accuracy)}. ${c.mejora_demostrada ? 'Supera el criterio orientativo de mejora en F1; continúa experimental.' : 'No se demostró mejora suficiente frente a la referencia.'}`);
    texto('ml-prueba-regresion', `MAE: ${fmt(r.prueba.mae)} · Referencia: ${fmt(r.referencia_prueba.mae)}. ${r.mejora_demostrada ? 'Supera el criterio orientativo de mejora; continúa experimental.' : 'No se demostró mejora suficiente frente a la referencia.'}`);
    const puntos=r.real_vs_predicho;
    grafico('ml-real','line',puntos.map(p=>p.fecha),[{label:'Real',data:puntos.map(p=>p.real),borderColor:'#286857'},{label:'Predicho',data:puntos.map(p=>p.predicho),borderColor:'#b58b46'}]);
    tabla('ml-real-tabla', ['Fecha','Real','Predicho'], puntos.map(p=>[p.fecha,p.real,p.predicho]));
    texto('ml-entrenamiento-real', `Versión ${meta.version} · Entrenado: ${hora(meta.fecha_entrenamiento)} · ${meta.registros} días (${meta.periodo.desde} a ${meta.periodo.hasta}). Prueba: ${meta.corte.inicio_prueba} en adelante. ${meta.auditoria.regla_etiquetas} Días faltantes: ${meta.auditoria.dias_faltantes}. Discrepancias con atenciones: ${meta.auditoria.discrepancias_con_atenciones}. Características: ${meta.caracteristicas.join(', ')}.`);
    $('ml-limitaciones').replaceChildren(...meta.limitaciones.map(t=>elemento('li', t)));
    const importancia = $('ml-importancia'); importancia.replaceChildren();
    for (const [nombre,d] of [['Clasificación',c],['Regresión',r]]) {
      importancia.append(elemento('p', d.importancia ? `${nombre} · Importancia interna del árbol (no causal, puede sesgarse): ${Object.entries(d.importancia).map(([k,v])=>`${k}: ${fmt(v)}`).join(' · ')}` : `${nombre}: el ganador no ofrece importancia de árbol; no se presenta una atribución equivalente.`));
    }
  }
  function mostrarPronosticos(p) {
    const cal=$('demanda-calendario'); cal.replaceChildren();
    p.forEach(d=>{
      const b=elemento('button'); b.type='button'; b.className='demanda-dia '+({BAJA:'baja',MEDIA:'media',ALTA:'alta'}[d.nivel] || '');
      b.append(elemento('small',d.fecha),elemento('strong',d.nivel || '—'),elemento('span',d.tipo));
      b.addEventListener('click',()=>{
        cal.querySelectorAll('button').forEach(n=>n.classList.remove('seleccionado')); b.classList.add('seleccionado');
        texto('demanda-detalle', `${d.fecha} · ${d.tipo} · Real: ${fmt(d.total)} · Estimación guardada: ${fmt(d.cantidad)} · Probabilidad sin calibrar: ${d.probabilidad == null ? '—' : fmt(d.probabilidad*100)+' %'}`);
      }); cal.append(b);
    });
    if (cal.firstChild) cal.firstChild.click();
    grafico('ml-linea','line',p.map(d=>d.fecha),[{label:'Observado',data:p.map(d=>d.total),borderColor:'#286857',spanGaps:false},{label:'Estimado guardado',data:p.map(d=>d.cantidad),borderColor:'#b58b46',spanGaps:false}]);
    tabla('ml-historial-tabla',['Fecha','Tipo','Real','Estimado','Emisiones anteriores'],p.map(d=>[d.fecha,d.tipo,d.total,d.cantidad,d.pronosticos_anteriores.map(e=>`${e.objetivo}: ${e.resultado.nivel ?? e.resultado.cantidad} (${e.generado_en}, ${e.modelo}, ${e.version}, ${e.estado})`).join('; ') || 'Sin emisión']));
    const futuros=p.filter(d=>d.tipo==='predicción'), altos=futuros.filter(d=>d.nivel==='ALTA');
    const decisiones=$('ml-decisiones'); decisiones.replaceChildren();
    decisiones.append(elemento('p', altos.length ? `Posible demanda ALTA: ${altos.map(d=>d.fecha).join(', ')}. Revisar disponibilidad de personal y materiales para esas fechas.` : 'No hay emisiones con demanda ALTA en este período; esto no garantiza demanda baja.'));
    if (futuros.length) {
      const max=Math.max(...futuros.map(d=>d.cantidad));
      decisiones.append(elemento('p', `Mayor cantidad estimada: ${max}, en ${futuros.filter(d=>d.cantidad===max).map(d=>d.fecha).join(', ')}. Revisar capacidad de atención.`));
      if (futuros.length>1) decisiones.append(elemento('p', `Cambio estimado entre primera y última emisión del período: ${futuros.at(-1).cantidad-futuros[0].cantidad} atenciones. No es una tendencia estadísticamente validada.`));
    }
    const faltan=p.filter(d=>d.tipo==='sin pronóstico').length;
    if(faltan) decisiones.append(elemento('p', `${faltan} fechas sin emisión. Usa “Generar y guardar pronósticos” para un período futuro o ejecuta la tarea programada; no se imputan valores.`));
    decisiones.append(elemento('p','Todos los modelos siguen siendo experimentales. Verifica las métricas frente a la referencia antes de usar estas sugerencias.'));
  }
  async function cargar() {
    $('demanda-error').hidden=true; texto('ml-estado','Consultando emisiones…');
    const boton=$('ml-filtros').querySelector('button'); boton.disabled=true;
    try {
      const q=new URLSearchParams({fecha:$('demanda-fecha').value,dias:$('demanda-dias').value});
      const d=await api('/api/demanda?'+q);
      texto('ml-total',fmt(d.historial.atenciones)); texto('ml-dias',fmt(d.historial.dias));
      texto('ml-manana',d.manana.nivel || 'Sin emisión'); texto('ml-cantidad',fmt(d.manana.cantidad));
      texto('ml-actualizacion',hora(d.ultima_actualizacion));
      texto('ml-aviso',d.aviso); comparar(d.entrenamiento); mostrarPronosticos(d.pronosticos);
      texto('ml-estado',window.Chart ? 'Datos actualizados.' : 'Datos cargados. Gráficos no disponibles: revisa el acceso a Chart.js; las tablas conservan todos los resultados.');
    } catch(e) { error(e); texto('ml-estado','No se pudo actualizar. Los valores previos pueden estar desactualizados.'); }
    finally {boton.disabled=false;}
  }
  $('ml-filtros').addEventListener('submit',e=>{e.preventDefault();cargar();});
  $('ml-generar-guardados').addEventListener('click',async e=>{
    const boton=e.currentTarget,fecha=$('demanda-fecha').value,dias=Number($('demanda-dias').value);
    boton.disabled=true; $('demanda-error').hidden=true;
    texto('ml-generacion-estado',`Generando y guardando ${dias} días desde ${fecha}…`);
    try {
      const d=await api('/api/ml/pronosticos/generar',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':boton.dataset.csrf},body:JSON.stringify({fecha,dias,confirmar:true})});
      $('demanda-fecha').value=fecha; $('demanda-dias').value=String(dias);
      await cargar();
      const disponibles=d.pronosticos.filter(p=>p.tipo==='predicción').length;
      texto('ml-generacion-estado',`${d.mensaje} ${disponibles} fechas con pronóstico disponibles en el período seleccionado. Esta acción no activa el cron diario.`);
    } catch(e) {error(e);texto('ml-generacion-estado','No se pudo completar la generación. Revisa el mensaje de error.');}
    finally {boton.disabled=false;}
  });
  $('ml-manual').addEventListener('submit',async e=>{
    e.preventDefault(); const boton=e.target.querySelector('button'); boton.disabled=true; $('demanda-error').hidden=true;
    try {
      const q=new URLSearchParams({fecha:$('ml-fecha-manual').value}); if($('ml-feriado').value) q.set('feriado',$('ml-feriado').value);
      const d=await api('/api/ml/predecir?'+q); const caja=$('ml-manual-resultado'); caja.replaceChildren();
      caja.append(elemento('h4',`${d.fecha} · ${d.nivel} · ${d.cantidad} atenciones estimadas`),elemento('p',d.explicacion));
      for(const o of ['clasificacion','regresion']){
        caja.append(elemento('h4',o==='clasificacion'?'Cinco clasificadores':'Cinco regresores'));
        const zona=elemento('div'); zona.id='ml-manual-'+o; zona.className='ml-scroll'; caja.append(zona);
        tabla(zona.id,['Modelo','Resultado',o==='clasificacion'?'Probabilidades por clase':'Incertidumbre','Seleccionado'],Object.entries(d.resultados[o]).map(([n,r])=>[n,r.nivel ?? r.cantidad,r.probabilidades ? Object.entries(r.probabilidades).map(([k,v])=>`${k}: ${fmt(v*100)} %`).join(' · ') : 'Sin intervalo disponible',n===d.ganadores[o]?'Sí':'—']));
      }
    } catch(e) {error(e);} finally {boton.disabled=false;}
  });
  cargar();
})();
