import hashlib
import io
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import patch, Mock
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from werkzeug.security import check_password_hash
import test_agentes
from models import (db, Perfil, TareaPerfil, Notificacion, ArchivoInforme,
                    EstadoProgramador, TareaIAEjecucion, ahora_utc)
from llm.perfil import crear, autenticar, actualizar, cambiar_clave, correo_valido
from llm.programacion import proxima, estado
from llm.tareas import ejecutar_programadas, reclamar
from llm.notificaciones import registrar, procesar, eventos_ejecucion


class CuentaTests(unittest.TestCase):
    setUp = test_agentes.AgentesTests.setUp
    tearDown = test_agentes.AgentesTests.tearDown
    post = test_agentes.AgentesTests.post
    informe = test_agentes.AgentesTests.informe
    crear_tarea = test_agentes.AgentesTests.crear_tarea

    def setUp(self):
        test_agentes.AgentesTests.setUp(self)
        from llm.cuenta_web import bp_cuenta
        self.app.register_blueprint(bp_cuenta)
        self.app.config.update(APP_USERNAME='principal',APP_PASSWORD='clave-existente')
        # Ninguna prueba puede enviar correos ni acceder a Supabase.
        self.env=patch.dict('os.environ',{'RESEND_API_KEY':'','MAIL_FROM':'','APP_PUBLIC_URL':'',
            'SUPABASE_URL':'','SUPABASE_SERVICE_ROLE_KEY':'','REPORTES_BUCKET':''})
        self.env.start()
        self.red=patch('requests.post',side_effect=AssertionError('Red externa no autorizada en prueba'))
        self.red.start()

    def tearDown(self):
        self.red.stop();self.env.stop();test_agentes.AgentesTests.tearDown(self)

    def test_acceso_perfil_y_notificaciones(self):
        self.assertEqual(self.c.get('/mi-perfil').status_code,200)
        self.assertEqual(self.c.get('/notificaciones').status_code,200)
        with self.c.session_transaction() as s:s.clear()
        self.assertEqual(self.c.get('/mi-perfil').status_code,302)
        self.assertEqual(self.c.get('/api/notificaciones').status_code,401)

    def test_migracion_credencial_sin_cambiar_acceso(self):
        self.assertIsNone(autenticar('principal','incorrecta'))
        self.assertIsNone(db.session.get(Perfil,1))
        p=autenticar('principal','clave-existente')
        self.assertTrue(check_password_hash(p.clave_hash,'clave-existente'))
        self.assertNotIn('clave-existente',p.clave_hash)
        self.assertEqual(Perfil.query.count(),1)

    def test_actualizar_perfil_csrf_correo_y_zona(self):
        d={'nombre':'Dra. Principal','correo':'medico@example.com','zona':'America/Lima','avisos':True,'eventos':['reporte_generado']}
        self.assertEqual(self.c.post('/api/perfil',json=d).status_code,403)
        self.assertEqual(self.post('/api/perfil',d).status_code,200)
        p=crear();self.assertEqual(p.nombre,d['nombre']);self.assertFalse(p.verificado)
        self.assertEqual(self.post('/api/perfil',{**d,'correo':'persona\r\nBcc: x@example.com'}).status_code,400)
        self.assertEqual(self.post('/api/perfil',{**d,'zona':'zona_falsa'}).status_code,400)
        self.assertEqual(self.post('/api/perfil',{**d,'eventos':['diagnostico']} ).status_code,400)

    def test_correos_invalidos(self):
        for valor in ('a','a@','a@@b.com','.a@b.com','a..b@c.com','a@b..com','a@b.com\n'):
            with self.subTest(valor=valor), self.assertRaises(ValueError):correo_valido(valor)

    def test_clave_actual_nueva_y_sesion(self):
        p=crear()
        with self.assertRaises(ValueError):cambiar_clave(p,'incorrecta','nueva-clave-segura')
        with self.assertRaises(ValueError):cambiar_clave(p,'clave-existente','corta')
        r=self.post('/api/perfil/clave',{'actual':'clave-existente','nueva':'nueva-clave-segura'})
        self.assertEqual(r.status_code,200)
        self.assertIsNone(autenticar('principal','clave-existente'))
        self.assertIsNotNone(autenticar('principal','nueva-clave-segura'))
        self.assertEqual(p.sesion_version,2)
        self.assertEqual(self.c.get('/mi-perfil').status_code,302)

    def test_zonas_y_proxima_semanal_mensual(self):
        despues=datetime(2026,10,25,12,tzinfo=timezone.utc)
        self.assertEqual(proxima({'frecuencia':'semanal','dia_semana':0,'hora':8},despues=despues),datetime(2026,10,26,13))
        self.assertEqual(proxima({'frecuencia':'mensual','dia_mes':1,'hora':8},despues=despues),datetime(2026,11,1,13))
        self.assertEqual(proxima({'frecuencia':'diaria','hora':8},'UTC',despues),datetime(2026,10,26,8))

    def test_propietario_confirmacion_y_edicion(self):
        t=self.crear_tarea();m=db.session.get(TareaPerfil,t.id);self.assertEqual(m.propietario_id,1)
        d={'configuracion':t.configuracion,'nombre':'Resumen semanal','zona':'America/Lima'}
        self.assertEqual(self.post('/api/agentes/tareas/'+t.id,d).status_code,400)
        self.assertEqual(self.post('/api/agentes/tareas/'+t.id,{**d,'confirmar':True}).status_code,200)
        self.assertEqual(m.nombre,'Resumen semanal')

    def test_migracion_repetible_conserva_tareas(self):
        t=self.crear_tarea()
        from llm.migraciones import migrar
        migrar();migrar()
        self.assertEqual(db.session.get(TareaPerfil,t.id).propietario_id,1)
        self.assertEqual(Perfil.query.count(),1)

    def test_automatico_reintentos_sin_duplicados(self):
        self.crear_tarea();ahora=datetime(2026,10,22,15,tzinfo=timezone.utc)
        self.assertEqual(len(ejecutar_programadas(ahora,origen='render_cron')),1)
        self.assertEqual(ejecutar_programadas(ahora,origen='render_cron'),[])
        self.assertEqual(TareaIAEjecucion.query.count(),1)
        self.assertEqual(EstadoProgramador.query.one().origen,'render_cron')

    def test_recuperacion_ejecucion_interrumpida(self):
        t=self.crear_tarea();e=reclamar(t,'2026-10-22');self.assertIsNone(reclamar(t,'2026-10-22'))
        e.iniciada_en=ahora_utc()-timedelta(minutes=11);db.session.commit()
        recuperada=reclamar(t,'2026-10-22');self.assertEqual(recuperada.id,e.id);self.assertEqual(recuperada.intentos,2)

    def test_ocurrencias_omitidas_se_recuperan(self):
        t=self.crear_tarea();ahora=datetime(2026,10,24,15,tzinfo=timezone.utc)
        for i in range(3):self.assertEqual(len(ejecutar_programadas(ahora)),1)
        self.assertEqual(ejecutar_programadas(ahora),[])
        self.assertEqual(TareaIAEjecucion.query.count(),3)

    def test_manual_no_acredita_cron(self):
        self.crear_tarea();ejecutar_programadas(manual=True)
        self.assertFalse(estado()['evidencia_cron_reciente'])

    def test_archivos_pdf_excel_persistentes_descarga(self):
        d=self.informe();self.assertEqual(ArchivoInforme.query.count(),2)
        for a in ArchivoInforme.query.all():
            self.assertEqual(a.estado,'base_persistente')
            self.assertEqual(hashlib.sha256(a.contenido).hexdigest(),a.sha256)
            r=self.c.get(f'/api/agentes/reportes/{d["id"]}/{a.formato}')
            self.assertEqual(r.status_code,200);self.assertEqual(r.data,a.contenido)
        with self.c.session_transaction() as s:s.clear()
        self.assertEqual(self.c.get(f'/api/agentes/reportes/{d["id"]}/pdf').status_code,401)

    def test_supabase_privado_mocks(self):
        self.informe();a=ArchivoInforme.query.first()
        from llm.almacenamiento import replicar
        respuesta=Mock();respuesta.json.return_value={'public':False};respuesta.status_code=200
        with patch.dict('os.environ',{'SUPABASE_URL':'https://ejemplo.supabase.co','SUPABASE_SERVICE_ROLE_KEY':'secreto-test','REPORTES_BUCKET':'privado'}), patch('requests.get',return_value=respuesta),patch('requests.post',return_value=respuesta) as subir:
            replicar(a);self.assertEqual(a.estado,'supabase_y_base')
            self.assertEqual(subir.call_args.kwargs['headers']['x-upsert'],'false')
            respuesta.json.return_value={'public':True};subir.reset_mock();replicar(a)
            self.assertEqual(a.estado,'error_bucket_no_privado');subir.assert_not_called()

    def test_fallo_storage_conserva_bytes(self):
        self.informe();a=ArchivoInforme.query.first()
        from llm.almacenamiento import replicar
        with patch.dict('os.environ',{'SUPABASE_URL':'https://ejemplo.supabase.co','SUPABASE_SERVICE_ROLE_KEY':'secreto-test','REPORTES_BUCKET':'privado'}),patch('requests.get',side_effect=RuntimeError('secreto')):
            replicar(a)
        self.assertEqual(a.estado,'base_replica_pendiente');self.assertTrue(a.contenido)

    def test_notificacion_interna_unica_leida(self):
        registrar('error_tarea','unica');registrar('error_tarea','unica')
        self.assertEqual(Notificacion.query.count(),1)
        n=Notificacion.query.one()
        self.assertEqual(self.post(f'/api/notificaciones/{n.id}/leer',{}).status_code,200)
        self.assertTrue(n.leida)

    def test_correo_no_configurado_y_no_verificado(self):
        p=crear();p.avisos=True;p.correo='medico@example.com';p.verificado=True;db.session.commit()
        registrar('error_tarea','correo');procesar()
        self.assertEqual(Notificacion.query.one().correo_estado,'pendiente_configuracion')
        p.verificado=False;db.session.commit();procesar()
        self.assertEqual(Notificacion.query.one().correo_estado,'pendiente_verificacion')

    def test_correo_mock_privado_e_idempotente(self):
        p=crear();p.avisos=True;p.verificado=True;p.correo='medico@example.com';db.session.commit()
        registrar('error_tarea','correo-mock');r=Mock();r.json.return_value={'id':'correo-test'}
        with patch.dict('os.environ',{'RESEND_API_KEY':'secreto-test','MAIL_FROM':'clinica@example.com','APP_PUBLIC_URL':'https://clinica.example.com'}),patch('requests.post',return_value=r) as enviar:
            procesar();procesar();self.assertEqual(enviar.call_count,1)
            self.assertIn('Idempotency-Key',enviar.call_args.kwargs['headers'])
            self.assertNotIn('DNI',enviar.call_args.kwargs['json']['text'])
        self.assertEqual(Notificacion.query.one().correo_estado,'aceptado_proveedor')

    def test_correo_fallo_no_simula_entrega(self):
        p=crear();p.avisos=True;p.verificado=True;p.correo='medico@example.com';db.session.commit()
        registrar('error_tarea','fallido')
        with patch.dict('os.environ',{'RESEND_API_KEY':'secreto-test','MAIL_FROM':'clinica@example.com','APP_PUBLIC_URL':'https://clinica.example.com'}):procesar()
        self.assertEqual(Notificacion.query.one().correo_estado,'error_proveedor')

    def test_verificacion_correo_expira_y_requiere_csrf(self):
        p=crear();p.correo='medico@example.com';p.verificacion_hash=hashlib.sha256(b'token-test').hexdigest();p.verificacion_hasta=ahora_utc()+timedelta(minutes=10);db.session.commit()
        self.assertEqual(self.c.get('/mi-perfil/verificar?token=token-test').status_code,200)
        self.assertFalse(p.verificado)
        self.assertEqual(self.c.post('/mi-perfil/verificar',data={'token':'token-test'}).status_code,400)
        self.assertEqual(self.c.post('/mi-perfil/verificar',data={'token':'token-test','csrf':'csrf-test'}).status_code,302)
        self.assertTrue(p.verificado);self.assertIsNone(p.verificacion_hash)

    def test_alerta_ml_unica_y_experimental(self):
        t=self.crear_tarea('alerta_alta');e=Mock(id='ejecucion',estado='ok',resultado={'alertas':[{'fecha':'2026-10-30','nivel':'ALTA'}]})
        eventos_ejecucion(t,e);eventos_ejecucion(t,e)
        self.assertEqual(Notificacion.query.count(),1)
        self.assertIn('experimental',self.c.get('/api/notificaciones').json['notificaciones'][0]['titulo'])

    def test_ddl_nuevas_tablas_postgresql(self):
        for m in (Perfil,TareaPerfil,Notificacion,ArchivoInforme,EstadoProgramador):
            self.assertIn('CREATE TABLE',str(CreateTable(m.__table__).compile(dialect=postgresql.dialect())))

    def test_login_real_e_invalidacion_de_otras_sesiones(self):
        # Otra aplicación aislada con el mismo login real y sin tocar la base clínica.
        from config import Config
        with patch.object(Config,'SQLALCHEMY_DATABASE_URI','sqlite:///:memory:'),patch.object(Config,'APP_USERNAME','principal'),patch.object(Config,'APP_PASSWORD','clave-existente'):
            from app import create_app
            aplicacion=create_app();aplicacion.config['TESTING']=True
        cliente=aplicacion.test_client();otro=aplicacion.test_client()
        for c in (cliente,otro):
            self.assertEqual(c.post('/login',data={'usuario':'principal','clave':'clave-existente'}).status_code,403)
            c.get('/login')
            with c.session_transaction() as s:token=s['login_csrf']
            self.assertEqual(c.post('/login',data={'csrf':token,'usuario':'principal','clave':'clave-existente'}).status_code,302)
        cliente.get('/mi-perfil')
        with cliente.session_transaction() as s:token=s['ia_csrf']
        respuesta=cliente.post('/api/perfil/clave',json={'actual':'clave-existente','nueva':'nueva-clave-integracion'},headers={'X-CSRF-Token':token})
        self.assertEqual(respuesta.status_code,200)
        self.assertEqual(otro.get('/mi-perfil').status_code,302)

    def test_cli_archivar_y_rechazar_sqlite_en_render(self):
        from argparse import Namespace
        from llm.cli import operar
        from llm.esquemas import ErrorAgente
        self.informe()
        with patch('llm.cli.contexto',return_value=self.app):
            self.assertEqual(operar(Namespace(comando='archivar-reportes',database=None))['informes_archivados'],1)
            with patch.dict('os.environ',{'RENDER_CRON_JOB':'true'}),self.assertRaises(ErrorAgente):
                operar(Namespace(comando='ejecutar',database=None))


if __name__=='__main__':unittest.main()
