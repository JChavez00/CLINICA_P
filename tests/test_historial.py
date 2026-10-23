"""La sustitución conserva la cuenta y revierte una carga inconsistente."""
from contextlib import closing
import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from scripts.actualizar_historial import leer_paquete, aplicar_sqlite, RAIZ
from scripts.generar_historial import construir


class HistorialTests(unittest.TestCase):
    def test_identificadores_y_reproducibilidad(self):
        from datetime import date
        personas, atenciones, dias, _ = construir(fin=date(2026,10,22))
        paquete = leer_paquete()
        self.assertEqual(len(personas), 1000)
        self.assertEqual(len(atenciones), 9569)
        self.assertEqual(len(dias), 726)
        columnas = paquete['tablas']['pacientes']['columnas']
        self.assertEqual([p['dni'] for p in personas],
                         [p[columnas.index('dni')] for p in paquete['tablas']['pacientes']['filas']])
        self.assertTrue({'60','70','71'} <= {p['dni'][:2] for p in personas})
        self.assertTrue(all(p['telefono']==p['nombre_via']=='' for p in personas))

    def test_carga_respaldo_cuenta_y_rollback(self):
        paquete = leer_paquete()
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta)/'clinica.db'
            with closing(sqlite3.connect(RAIZ/'instance/policlinico_ficticio.db')) as origen:
                with closing(sqlite3.connect(destino)) as copia:
                    origen.backup(copia)
            with closing(sqlite3.connect(destino)) as c:
                cuenta = c.execute('SELECT * FROM cuenta_perfil').fetchall()
                tareas = c.execute('SELECT * FROM agente_tareas').fetchall()
                c.execute('DELETE FROM ml_pronosticos_v2'); c.commit()
            # Los respaldos de esta prueba permanecen exclusivamente en su carpeta temporal.
            with patch('scripts.actualizar_historial.RAIZ', Path(carpeta)):
                resultado = aplicar_sqlite(destino, paquete)
                self.assertTrue(Path(resultado['respaldo']).exists())
                with closing(sqlite3.connect(destino)) as c:
                    self.assertEqual(c.execute('SELECT * FROM cuenta_perfil').fetchall(), cuenta)
                    self.assertEqual(c.execute('SELECT * FROM agente_tareas').fetchall(), tareas)
                    self.assertEqual(c.execute('SELECT COUNT(*) FROM atenciones').fetchone()[0], 9569)
                    self.assertFalse(c.execute('PRAGMA foreign_key_check').fetchall())
                incorrecto = copy.deepcopy(paquete)
                datos = incorrecto['tablas']['ml_demanda_diaria']
                datos['filas'][0][datos['columnas'].index('total_atenciones')] = -1
                with self.assertRaises(ValueError):
                    aplicar_sqlite(destino, incorrecto)
                with closing(sqlite3.connect(destino)) as c:
                    self.assertEqual(c.execute('SELECT MIN(total_atenciones) FROM ml_demanda_diaria').fetchone()[0], 0)
                    self.assertEqual(c.execute('SELECT * FROM cuenta_perfil').fetchall(), cuenta)


if __name__ == '__main__':
    unittest.main()
