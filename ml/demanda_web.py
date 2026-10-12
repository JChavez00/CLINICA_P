from datetime import date, timedelta
from collections import Counter
from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for
from sqlalchemy import func
from models import db, Atencion, MLDemandaDiaria
from ml.predecir_demanda import predecir_demanda

bp_demanda = Blueprint('demanda', __name__)

@bp_demanda.before_request
def proteger():
    if not session.get('autenticado'):
        return redirect(url_for('login'))

@bp_demanda.route('/demanda')
def pagina():
    return render_template('demanda.html')

@bp_demanda.route('/api/demanda')
def datos():
    inicio_str = request.args.get('fecha', date.today().isoformat())
    try:
        inicio = date.fromisoformat(inicio_str)
        if inicio.year < 2000 or inicio.year > 2100:
            raise ValueError()
        dias = int(request.args.get('dias', '7'))
        if dias not in (7, 15, 30):
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({'error': 'Fecha o período inválido'}), 400

    historico = (
        db.session.query(MLDemandaDiaria)
        .order_by(MLDemandaDiaria.fecha)
        .all()
    )
    if not historico:
        return jsonify({'error': 'No hay datos históricos de demanda'}), 404

    primer_dia = historico[0].fecha
    ultimo_dia = historico[-1].fecha
    mapa = {r.fecha: r for r in historico}
    # Evitar presentar como predicción un día que ya tiene observación histórica.
    pronosticos = []
    for i in range(dias):
        fecha = inicio + timedelta(days=i)
        existente = mapa.get(fecha)
        if existente:
            pronosticos.append({
                'fecha': fecha.isoformat(), 'nivel': existente.nivel_demanda,
                'tipo': 'histórico', 'total': existente.total_atenciones,
                'probabilidad': None
            })
        else:
            try:
                resultado = predecir_demanda(fecha)
            except (FileNotFoundError, ValueError) as exc:
                return jsonify({'error': str(exc)}), 503
            pronosticos.append({
                'fecha': fecha.isoformat(), 'nivel': resultado['nivel'],
                'tipo': 'predicción', 'total': None,
                'probabilidad': resultado['probabilidad']
            })

    # Últimos 45 días históricos para una serie visual compacta.
    serie = [
        {'fecha': r.fecha.isoformat(), 'total': r.total_atenciones,
         'nivel': r.nivel_demanda}
        for r in historico[-45:]
    ]
    resumen = dict(Counter(r.nivel_demanda for r in historico))
    motivos = (
        db.session.query(Atencion.motivo, func.count(Atencion.id).label('cantidad'))
        .filter(Atencion.fecha >= ultimo_dia - timedelta(days=29))
        .filter(Atencion.fecha <= ultimo_dia)
        .filter(Atencion.motivo.isnot(None), Atencion.motivo != '')
        .group_by(Atencion.motivo)
        .order_by(func.count(Atencion.id).desc())
        .limit(5)
        .all()
    )
    return jsonify({
        'pronosticos': pronosticos, 'serie': serie,
        'resumen': resumen, 'motivos': [{'motivo': m, 'cantidad': n} for m, n in motivos],
        'historial': {'desde': primer_dia.isoformat(), 'hasta': ultimo_dia.isoformat(),
                      'dias': len(historico), 'atenciones': sum(r.total_atenciones for r in historico)},
        'aviso': 'Modelo experimental: exactitud de evaluación 43.64 %, igual a la referencia. Datos ficticios.'
    })
