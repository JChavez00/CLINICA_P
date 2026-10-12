(() => {
  const $ = id => document.getElementById(id);
  const fechaInput = $('demanda-fecha');
  // Fecha local, no UTC, para evitar saltos de día por huso horario.
  const hoy = new Date();
  fechaInput.value = `${hoy.getFullYear()}-${String(hoy.getMonth()+1).padStart(2,'0')}-${String(hoy.getDate()).padStart(2,'0')}`;
  const nombres = ['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'];
  const texto = (id, valor) => { $(id).textContent = valor; };
  const fmt = iso => { const [y,m,d]=iso.split('-').map(Number); const f=new Date(y,m-1,d); return `${nombres[f.getDay()]} ${d}/${m}`; };
  const nivelClase = nivel => ({BAJA:'baja', MEDIA:'media', ALTA:'alta'}[nivel] || '');
  async function consultar() {
    $('demanda-error').hidden = true;
    $('demanda-consultar').disabled = true;
    try {
      const p = new URLSearchParams({fecha:fechaInput.value, dias:$('demanda-dias').value});
      const respuesta = await fetch(`/api/demanda?${p.toString()}`);
      if (!respuesta.ok) { const e=await respuesta.json(); throw new Error(e.error || 'Error al consultar'); }
      const data = await respuesta.json();
      texto('demanda-total', data.historial.atenciones.toLocaleString('es-PE'));
      texto('demanda-dias-hist', data.historial.dias);
      texto('demanda-altos', data.pronosticos.filter(d=>d.nivel==='ALTA').length);
      const calendario = $('demanda-calendario'); calendario.replaceChildren();
      const detalle = $('demanda-detalle');
      data.pronosticos.forEach((d, i) => {
        const b=document.createElement('button'); b.type='button';
        b.className=`demanda-dia ${nivelClase(d.nivel)}`;
        const dia=document.createElement('small'); dia.textContent=fmt(d.fecha);
        const nivel=document.createElement('strong'); nivel.textContent=d.nivel || '—';
        const tipo=document.createElement('span'); tipo.textContent=d.tipo==='histórico'?'Registrado':'Estimado';
        b.append(dia,nivel,tipo);
        b.addEventListener('click', () => {
          calendario.querySelectorAll('button').forEach(el=>el.classList.remove('seleccionado'));
          b.classList.add('seleccionado');
          detalle.textContent=d.tipo==='histórico'
            ? `${fmt(d.fecha)} · Demanda ${d.nivel} · ${d.total} atenciones registradas (histórico).`
            : `${fmt(d.fecha)} · Demanda ${d.nivel} · Confianza estimada del clasificador: ${(d.probabilidad*100).toFixed(1)} %. No se estima un número exacto de pacientes.`;
        });
        calendario.append(b); if (i===0) b.click();
      });
      const grafico=$('demanda-grafico'); grafico.replaceChildren();
      const max=Math.max(1,...data.serie.map(x=>x.total));
      data.serie.forEach(d=>{
        const barra=document.createElement('div'); barra.className='demanda-barra';
        barra.style.height=`${Math.max(2,d.total/max*100)}%`;
        barra.title=`${d.fecha}: ${d.total} atenciones (${d.nivel})`;
        grafico.append(barra);
      });
      const motivos=$('demanda-motivos'); motivos.replaceChildren();
      if (!data.motivos.length) motivos.textContent='No hay motivos registrados en este período.';
      data.motivos.forEach(d=>{
        const fila=document.createElement('div'); fila.className='demanda-motivo';
        const nombre=document.createElement('span'); nombre.textContent=d.motivo;
        const total=document.createElement('strong'); total.textContent=d.cantidad;
        fila.append(nombre,total); motivos.append(fila);
      });
    } catch(e) { $('demanda-error').hidden=false; texto('demanda-error', e.message); }
    finally { $('demanda-consultar').disabled=false; }
  }
  $('demanda-consultar').addEventListener('click', consultar);
  consultar();
})();
