(() => {
  'use strict';
  const nombres={consultor_clinico:'Consultor clínico',analista_inteligente:'Analista inteligente',generador_reportes:'Generador de reportes',automatizador_tareas:'Automatizador de tareas',control_calidad:'Control de calidad',coordinador:'Control local'};
  const estados={ok:'Completada',degradado:'Respaldo local',error:'Con error'};
  const nodo=(tag,texto,clase)=>{const n=document.createElement(tag);if(texto!=null)n.textContent=texto;if(clase)n.className=clase;return n;};
  window.recorridosUI={nombres,estados,nodo,
    resumen(contenedor,d){
      if(!d.ejecucion_id)return;
      const caja=nodo('aside',null,'tr-resumen');
      const texto=nodo('div');texto.append(nodo('small','RECORRIDO REGISTRADO','tr-kicker'),nodo('strong',nombres[d.agente]||'Control local'));
      texto.append(nodo('span',[estados[d.estado]||'Operación registrada',d.duracion_ms!=null?`${d.duracion_ms.toLocaleString('es-PE')} ms`:null].filter(Boolean).join(' · '),'tr-muted'));
      const enlace=nodo('a','Ver recorrido →');enlace.href='/actividad-agentes?ejecucion='+encodeURIComponent(d.ejecucion_id);
      caja.append(texto,enlace);contenedor.replaceChildren(caja);
    }
  };
})();
