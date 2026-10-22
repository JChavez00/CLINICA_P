"""Pruebas con copia de agregados existentes; sin generar historial ficticio nuevo."""
import copy
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "isolated-test-session"

from flask import Flask
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from models import db, MLDemandaDiaria, MLPronostico
from ml.datos import preparar, cargar_datos, caracteristicas, validar_fecha, hoy_peru, CARACTERISTICAS
from ml.entrenar_modelo import entrenar, medir
from ml.artefactos import cargar, metadatos, _cargar
from ml.predecir_demanda import predecir, predecir_demanda
from ml.pronosticos import generar, consultar

RAIZ = Path(__file__).resolve().parent.parent


def agregados():
    # Datos ya existentes, sólo lectura; no se generan ni se exportan datos personales.
    archivo = RAIZ / "instance" / "policlinico_ficticio.db"
    if not archivo.exists():
        raise unittest.SkipTest("Requiere el dataset local existente de 273 días; no se inventa uno.")
    with sqlite3.connect(archivo.as_uri() + "?mode=ro", uri=True) as c:
        filas = c.execute("select fecha,total_atenciones,nivel_demanda,es_feriado from ml_demanda_diaria order by fecha").fetchall()
    return [{"fecha": date.fromisoformat(f), "total_atenciones": n, "nivel_demanda": e, "es_feriado": bool(h)} for f,n,e,h in filas]


class DatosTests(unittest.TestCase):
    def test_fechas(self):
        for f in [None, "2026-02-30", "1999-01-01", "20260101", "2026-1-2", datetime_invalido()]:
            with self.assertRaises(ValueError): validar_fecha(f)
        with self.assertRaises(ValueError): validar_fecha(hoy_peru(), futura=True)

    def test_caracteristicas_sin_objetivos(self):
        x = caracteristicas(date(2026, 1, 4), True)
        self.assertEqual(x["fin_semana"], 1)
        self.assertEqual(set(x), set(CARACTERISTICAS))
        self.assertNotIn("total_atenciones", x)
        self.assertNotIn("nivel_demanda", x)

    def test_validacion_dataset(self):
        datos = agregados()
        for campo, valor in [("total_atenciones", -1), ("total_atenciones", None), ("nivel_demanda", "OTRA"), ("es_feriado", None)]:
            malos = copy.deepcopy(datos); malos[0][campo] = valor
            with self.assertRaises(ValueError): preparar(malos)
        with self.assertRaises(ValueError): preparar(datos + [datos[0]])
        with self.assertRaises(ValueError): preparar([])

    def test_ausencias_no_son_ceros(self):
        datos = agregados(); df, a = preparar(datos[:2] + datos[3:])
        self.assertEqual(len(df), len(datos)-1)
        self.assertEqual(a["dias_faltantes"], 1)
        self.assertEqual(a["dias_cero_explicitos"], 0)

    def test_metricas_constante(self):
        self.assertIsNone(medir("regresion", [2,2], [2,2])["r2"])


def datetime_invalido():
    from datetime import datetime
    return datetime(2026, 1, 1)


class IntegracionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.entorno = patch.dict(os.environ, {"ML_MODEL_DIR": str(Path(cls.tmp.name) / "modelos")})
        cls.entorno.start()
        cls.app = Flask("test_ml", template_folder=str(RAIZ / "templates"))
        cls.app.config.update(SQLALCHEMY_DATABASE_URI="sqlite:///:memory:", SECRET_KEY="test", TESTING=True)
        db.init_app(cls.app)
        cls.ctx = cls.app.app_context(); cls.ctx.push(); db.create_all()
        for r in agregados():
            db.session.add(MLDemandaDiaria(**r, dia_semana=r["fecha"].weekday(), mes=r["fecha"].month))
        db.session.commit()
        cls.df, cls.audit = cargar_datos()
        cls.meta = entrenar(cls.df, cls.audit)
        from ml.demanda_web import bp_demanda
        cls.app.register_blueprint(bp_demanda)
        cls.fecha = hoy_peru() + timedelta(days=1)

    @classmethod
    def tearDownClass(cls):
        db.session.remove(); cls.ctx.pop(); _cargar.cache_clear(); cls.entorno.stop(); cls.tmp.cleanup()

    def test_carga_y_auditoria(self):
        self.assertEqual(len(self.df), 273)
        self.assertEqual(int(self.df.total_atenciones.sum()), 1000)
        self.assertEqual(self.audit["discrepancias_con_atenciones"], 273)  # DB aislada sin fichas

    def test_diez_modelos_persistidos(self):
        paquete, meta = cargar()
        for o in ["clasificacion", "regresion"]:
            self.assertEqual(len(paquete["modelos"][o]), 5)
            self.assertEqual(len(meta["resultados"][o]["validacion"]), 6)
            self.assertIn(meta["resultados"][o]["ganador"], paquete["modelos"][o])
        self.assertEqual(meta["version"], self.meta["version"])

    def test_seleccion_solo_validacion(self):
        c = self.meta["resultados"]["clasificacion"]
        nombres = [n for n in c["validacion"] if n != "Referencia"]
        mejor = max(nombres, key=lambda n: (c["validacion"][n]["f1_macro"],c["validacion"][n]["accuracy"],c["validacion"][n]["recall_macro"]))
        self.assertEqual(c["ganador"], mejor)
        r = self.meta["resultados"]["regresion"]
        self.assertEqual(r["ganador"],min((n for n in r["validacion"] if n != "Referencia"),key=lambda n:(r["validacion"][n]["mae"],r["validacion"][n]["rmse"])))

    def test_orden_temporal_y_scaler(self):
        for v in self.meta["ventanas"]:
            self.assertLess(v["fin_entrenamiento"], v["inicio_validacion"])
            self.assertLess(v["fin_validacion"], self.meta["corte"]["inicio_prueba"])
        p, _ = cargar()
        scaler = p["modelos"]["regresion"]["Ridge"].named_steps["standardscaler"]
        self.assertEqual(scaler.n_samples_seen_, int(len(self.df)*.8))
        import numpy as np
        np.testing.assert_allclose(scaler.mean_, self.df.iloc[:int(len(self.df)*.8)][CARACTERISTICAS].mean().to_numpy())

    def test_prediccion_sin_entrenar(self):
        with patch("ml.entrenar_modelo.entrenar", side_effect=AssertionError("No reentrenar")):
            p = predecir(self.fecha, True)
        self.assertEqual(len(p["resultados"]["clasificacion"]), 5)
        self.assertEqual(len(p["resultados"]["regresion"]), 5)
        self.assertGreaterEqual(p["cantidad"], 0)
        self.assertTrue(p["feriado"]["confirmado"])
        self.assertAlmostEqual(sum(next(iter(p["resultados"]["clasificacion"].values()))["probabilidades"].values()), 1.)
        self.assertEqual(predecir_demanda(self.fecha)["version"], self.meta["version"])

    def test_horizontes_idempotentes(self):
        for dias in [7,15,30]:
            generar(dias, self.fecha); generar(dias, self.fecha)
            self.assertEqual(MLPronostico.query.count(), dias*2)
        with self.assertRaises(ValueError): generar(8)
        with self.assertRaises(ValueError): generar(7, hoy_peru())

    def test_historico_compara_emisiones(self):
        generar(7, self.fecha)
        r = MLDemandaDiaria(fecha=self.fecha,total_atenciones=4,nivel_demanda="MEDIA",dia_semana=self.fecha.weekday(),mes=self.fecha.month,es_feriado=False)
        db.session.add(r); db.session.commit()
        try:
            d = consultar(self.fecha,7)[0]
            self.assertEqual(d["tipo"], "histórico")
            self.assertEqual(d["total"],4)
            self.assertTrue(d["pronosticos_anteriores"])
            self.assertTrue(all(p["estado"]=="observado" for p in d["pronosticos_anteriores"]))
        finally: db.session.delete(r); db.session.commit()

    def test_api_protegida_parametros_y_lecturas(self):
        c=self.app.test_client()
        for url in ['/api/demanda','/api/ml/modelos','/api/ml/comparacion','/api/ml/pronosticos','/api/ml/metricas','/api/ml/predecir']:
            self.assertEqual(c.get(url).status_code,401)
        with c.session_transaction() as s: s['autenticado']=True
        for url in ['/api/ml/modelos','/api/ml/comparacion','/api/ml/metricas',f'/api/ml/pronosticos?fecha={self.fecha}',f'/api/ml/predecir?fecha={self.fecha}']:
            self.assertEqual(c.get(url).status_code,200,url)
        for url in ['/api/demanda?fecha=mal','/api/demanda?dias=2','/api/ml/predecir?fecha=2026-01-01',f'/api/ml/predecir?fecha={self.fecha}&feriado=otro']:
            self.assertEqual(c.get(url).status_code,400,url)
        antes=MLPronostico.query.count()
        self.assertEqual(c.get('/api/demanda').status_code,200)
        self.assertEqual(MLPronostico.query.count(),antes)
        d=c.get('/api/demanda').get_data(as_text=True)
        self.assertNotIn('telefono',d); self.assertNotIn('dni',d)

    def test_modelo_ausente_y_corrupto(self):
        with tempfile.TemporaryDirectory() as t, patch.dict(os.environ,{'ML_MODEL_DIR':t}):
            with self.assertRaises(FileNotFoundError): predecir(self.fecha)
            c=self.app.test_client()
            with c.session_transaction() as s:s['autenticado']=True
            self.assertEqual(c.get('/api/ml/modelos').status_code,503)
        ruta=Path(os.environ['ML_MODEL_DIR'])/self.meta['version']/'modelos.joblib'
        with patch('ml.artefactos.metadatos',return_value={**self.meta,'sha256':'incorrecto'}):
            with self.assertRaises(ValueError): cargar()

    def test_ddl_postgres(self):
        sql=str(CreateTable(MLPronostico.__table__).compile(dialect=postgresql.dialect()))
        self.assertIn('uq_ml_pronostico_diario',sql)
        self.assertIn('JSON',sql)

    def test_version_runtime_incompatible(self):
        with patch('ml.artefactos.metadatos',return_value={**self.meta,'sklearn':'otra-version'}):
            with self.assertRaises(ValueError): cargar()

    def test_dataset_insuficiente(self):
        with self.assertRaises(ValueError): entrenar(self.df.iloc[:30],self.audit)


class AplicacionTests(unittest.TestCase):
    def test_rutas_existentes_y_dashboard(self):
        # DATABASE_URL fue fijada en memoria antes de importar: no toca Supabase.
        from app import app
        c=app.test_client()
        self.assertEqual(c.get('/demanda').status_code,302)
        with c.session_transaction() as s:s['autenticado']=True
        for url in ['/','/nueva-atencion','/pacientes-hoy','/reportes','/asistente-ia','/demanda']:
            r=c.get(url)
            self.assertEqual(r.status_code,200,url)
        self.assertIn('¿Cómo funcionan los modelos?',c.get('/demanda').get_data(as_text=True))


if __name__ == '__main__': unittest.main()
