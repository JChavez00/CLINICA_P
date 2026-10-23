"""Carga transaccional del historial académico en la SQLite principal.

python -m scripts.actualizar_historial --confirmar REEMPLAZAR_HISTORIAL
Para Supabase usar docs/SUPABASE_REEMPLAZAR_HISTORIAL.sql.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import sqlite3

RAIZ = Path(__file__).resolve().parents[1]
PAQUETE = RAIZ / 'datos' / 'historial.json.gz'
TABLAS = ('pacientes', 'atenciones', 'ml_demanda_diaria', 'ml_pronosticos_v2')
BORRAR = ('ml_pronosticos_v2', 'ml_predicciones_demanda', 'ml_demanda_diaria', 'atenciones', 'pacientes')


def leer_paquete(ruta=PAQUETE):
    with gzip.open(ruta, 'rt', encoding='utf-8') as archivo:
        paquete = json.load(archivo)
    pacientes = paquete['tablas']['pacientes']['filas']
    columnas = paquete['tablas']['pacientes']['columnas']
    documentos = [p[columnas.index('dni')] for p in pacientes]
    if (len(set(documentos)) != len(documentos)
            or any(len(d) != 8 or not d.isascii() or not d.isdigit() for d in documentos)):
        raise ValueError('Identificadores inválidos en el paquete.')
    return paquete


def validar_conexion(conexion, paquete):
    if conexion.execute('PRAGMA foreign_key_check').fetchall():
        raise ValueError('Relaciones inválidas: se revierte la operación.')
    for tabla in TABLAS:
        cantidad = conexion.execute(f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0]
        if cantidad != len(paquete['tablas'][tabla]['filas']):
            raise ValueError(f'Cantidad incorrecta en {tabla}.')
    errores = conexion.execute('''SELECT COUNT(*) FROM ml_demanda_diaria d
        WHERE d.total_atenciones != (SELECT COUNT(*) FROM atenciones a WHERE a.fecha=d.fecha)
        OR d.nivel_demanda != CASE WHEN d.total_atenciones<10 THEN 'BAJA'
                                 WHEN d.total_atenciones<18 THEN 'MEDIA' ELSE 'ALTA' END''').fetchone()[0]
    if errores:
        raise ValueError('Los agregados no corresponden a las atenciones.')


def aplicar_sqlite(destino, paquete):
    destino = Path(destino).resolve()
    if not destino.is_file():
        raise ValueError('Debe existir la base de destino con su esquema completo.')
    carpeta = RAIZ / 'instance' / 'respaldos'
    carpeta.mkdir(parents=True, exist_ok=True)
    sello = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    respaldo = carpeta / f'historial_antes_{sello}.sqlite3'
    with closing(sqlite3.connect(destino)) as conexion:
        conexion.execute('PRAGMA foreign_keys=ON')
        # Bloqueo antes del respaldo para impedir escrituras concurrentes.
        conexion.execute('BEGIN IMMEDIATE')
        try:
            with closing(sqlite3.connect(destino.as_uri()+'?mode=ro', uri=True)) as lectura:
                with closing(sqlite3.connect(respaldo)) as copia:
                    lectura.backup(copia)
            for tabla in BORRAR:
                conexion.execute(f'DELETE FROM "{tabla}"')
            for tabla in TABLAS:
                datos = paquete['tablas'][tabla]
                columnas = ','.join('"'+c+'"' for c in datos['columnas'])
                valores = ','.join('?' for _ in datos['columnas'])
                conexion.executemany(f'INSERT INTO "{tabla}" ({columnas}) VALUES ({valores})', datos['filas'])
            validar_conexion(conexion, paquete)
            conexion.commit()
        except Exception:
            conexion.rollback()
            raise
    return {'respaldo': str(respaldo), 'registros': {
        t: len(paquete['tablas'][t]['filas']) for t in TABLAS}}


def exportar_postgres(paquete, salida):
    def literal(valor, columna):
        if valor is None:
            return 'NULL'
        if columna == 'es_feriado':
            return 'TRUE' if valor else 'FALSE'
        if isinstance(valor, (int, float)):
            return str(valor)
        return "'"+str(valor).replace("'", "''")+"'"
    lineas = [
        '-- Historial sintético académico; reemplaza datos clínicos y pronósticos, conserva cuenta y tareas.',
        '-- Ejecutar completo en Supabase SQL Editor, una sola vez. Respaldo privado dentro de la transacción.',
        'BEGIN;', "SET LOCAL standard_conforming_strings = on;",
        'LOCK TABLE public.pacientes, public.atenciones, public.ml_demanda_diaria, public.ml_pronosticos_v2, public.ml_predicciones_demanda IN ACCESS EXCLUSIVE MODE;',
        'CREATE SCHEMA respaldo_historial_20261023;',
        'REVOKE ALL ON SCHEMA respaldo_historial_20261023 FROM PUBLIC, anon, authenticated;',
    ]
    for tabla in BORRAR:
        lineas.append(f'CREATE TABLE respaldo_historial_20261023."{tabla}" AS TABLE public."{tabla}";')
    for tabla in BORRAR:
        lineas.append(f'DELETE FROM public."{tabla}";')
    for tabla in TABLAS:
        datos = paquete['tablas'][tabla]
        columnas = ','.join('"'+c+'"' for c in datos['columnas'])
        for inicio in range(0, len(datos['filas']), 200):
            filas = datos['filas'][inicio:inicio+200]
            valores = ',\n'.join('('+','.join(literal(v,c) for c,v in zip(datos['columnas'], fila))+')' for fila in filas)
            lineas.append(f'INSERT INTO public."{tabla}" ({columnas}) VALUES\n{valores};')
        lineas.append(f"SELECT setval(pg_get_serial_sequence('public.{tabla}', 'id'), COALESCE(MAX(id),1), COUNT(*)>0) FROM public.\"{tabla}\";")
    lineas.append('DO $$ BEGIN')
    for tabla in TABLAS:
        esperado = len(paquete['tablas'][tabla]['filas'])
        lineas.append(f"IF (SELECT COUNT(*) FROM public.\"{tabla}\") <> {esperado} THEN RAISE EXCEPTION 'Conteo incorrecto: {tabla}'; END IF;")
    lineas.extend([
        "IF EXISTS (SELECT 1 FROM public.ml_demanda_diaria d WHERE d.total_atenciones <> (SELECT COUNT(*) FROM public.atenciones a WHERE a.fecha=d.fecha)) THEN RAISE EXCEPTION 'Agregados inconsistentes'; END IF;",
        'END $$;', 'COMMIT;',
    ])
    Path(salida).write_text('\n'.join(lineas)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default=str(RAIZ/'instance'/'policlinico_ficticio.db'))
    parser.add_argument('--confirmar', choices=['REEMPLAZAR_HISTORIAL'])
    parser.add_argument('--exportar-sql')
    args = parser.parse_args()
    paquete = leer_paquete()
    if args.exportar_sql:
        exportar_postgres(paquete, args.exportar_sql)
    elif args.confirmar:
        print(json.dumps(aplicar_sqlite(args.base, paquete), ensure_ascii=False, indent=2))
    else:
        parser.error('Indica --confirmar REEMPLAZAR_HISTORIAL o --exportar-sql RUTA.')


if __name__ == '__main__':
    main()
