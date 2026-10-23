"""Escenario fijado antes de entrenar; no importa ni usa sklearn."""
import calendar
from datetime import date, timedelta, datetime
import math
import numpy as np
from dateutil.easter import easter

SEMILLA = 20261023
CAPACIDAD = 24
PREFIJOS = ("60", "70", "71", "40", "45", "48", "62", "73")
DISTRITOS = ("Yanahuanca", "Tápuc", "Vilcabamba", "Páucar")
NOMBRES = ("Ana", "Rosa", "María", "Elena", "Luz", "Carmen", "Diana", "Lucía",
           "José", "Luis", "Carlos", "Pedro", "Miguel", "Julio", "Raúl", "Juan")
SEGUNDOS = ("Mariela", "Patricia", "Alejandra", "Beatriz", "Estela", "Felicia", "Inés", "Leonor",
            "Andrés", "Alberto", "Antonio", "Enrique", "Eduardo", "Fernando", "Gabriel", "Héctor")
APELLIDOS = ("Quispe", "Huamán", "Rojas", "Córdova", "Palomino", "Salazar", "Paredes", "Flores",
             "Venturina", "Montesol", "Valdebrisa", "Solandino", "Campoluz", "Riosierra")
# Motivo, síntomas y diagnóstico ficticio forman una unidad coherente.
CUADROS = (
    (("Molestias respiratorias", "Congestión nasal", "Tos y malestar leve"), "Congestión y tos referidas", "Cuadro respiratorio inespecífico"),
    (("Molestia digestiva", "Malestar abdominal", "Ardor digestivo referido"), "Malestar digestivo sin signos documentados de alarma", "Síndrome dispéptico en evaluación"),
    (("Control preventivo", "Evaluación general", "Consulta de seguimiento preventivo"), "Sin síntomas nuevos referidos", "Evaluación preventiva general"),
    (("Molestia muscular", "Dolor de espalda referido", "Malestar musculoesquelético"), "Dolor muscular referido tras actividad habitual", "Dolor musculoesquelético inespecífico"),
    (("Control de presión arterial", "Seguimiento de presión", "Evaluación de presión arterial"), "Consulta de control programado", "Seguimiento de presión arterial"),
    (("Revisión de irritación cutánea", "Molestia de piel", "Consulta por prurito localizado"), "Prurito e irritación localizada referida", "Dermatitis inespecífica en evaluación"),
)


def nivel(cantidad):
    return "BAJA" if cantidad < 10 else "MEDIA" if cantidad < 18 else "ALTA"


def meses_antes(fecha, meses):
    total=fecha.year*12+fecha.month-1-meses
    y,m=divmod(total,12);m+=1
    return date(y,m,min(fecha.day,calendar.monthrange(y,m)[1]))


def calendario_peru(desde, hasta):
    fechas={}
    fijos=((1,1),(5,1),(6,7),(6,29),(7,23),(7,28),(7,29),(8,6),(8,30),(10,8),(11,1),(12,8),(12,9),(12,25))
    for y in range(desde.year,hasta.year+1):
        dias=[date(y,m,d) for m,d in fijos]+[easter(y)-timedelta(days=3),easter(y)-timedelta(days=2)]
        for f in dias:
            if desde<=f<=hasta:fechas[f.isoformat()]=True
    return {"fuente":"Calendario nacional gob.pe/feriados; fechas fijas y Jueves/Viernes Santo gregorianos.",
            "limitacion":"No incluye días compensables ni feriados regionales. Supuesto de actividad reducida, no cierre obligatorio.",
            "fechas":fechas}


def construir(fin=None, meses=24, pacientes=1000, semilla=SEMILLA):
    from ml.datos import hoy_peru
    hoy=hoy_peru();fin=fin or hoy-timedelta(days=1)
    if fin>=hoy or not 18<=meses<=24 or not 800<=pacientes<=1200:
        raise ValueError("Usa 18–24 meses cerrados y 800–1200 pacientes.")
    inicio=meses_antes(fin+timedelta(days=1),meses)
    rng=np.random.default_rng(semilla)
    calendario_cfg=calendario_peru(inicio,fin+timedelta(days=400))
    personas=[];identificadores=set();combinaciones=set()
    for i in range(1,pacientes+1):
        while True:
            dni=str(rng.choice(PREFIJOS))+f"{int(rng.integers(0,1000000)):06d}"
            if dni not in identificadores:break
        identificadores.add(dni)
        while True:
            genero=int(rng.integers(0,2));indices=rng.integers(genero*8,genero*8+8,size=2)
            nombres=NOMBRES[indices[0]]+" "+SEGUNDOS[indices[1]]
            apellidos=" ".join(rng.choice(APELLIDOS,size=2,replace=False))
            if (nombres,apellidos) not in combinaciones:break
        combinaciones.add((nombres,apellidos))
        nacimiento=inicio-timedelta(days=int(rng.integers(8*365,81*365)))
        personas.append({"id":i,"dni":dni,"nombres":nombres,"apellidos":apellidos,
            "fecha_nacimiento":nacimiento.isoformat(),"sexo":"Femenino" if genero==0 else "Masculino",
            "telefono":"","departamento":"Pasco","provincia":"Daniel Alcides Carrión",
            "distrito":str(rng.choice(DISTRITOS,p=[.65,.15,.1,.1])),"tipo_via":"",
            "nombre_via":"","latitud":None,"longitud":None,
            "creado_en":datetime.combine(inicio,datetime.min.time())})
    atenciones=[];dias=[];eventos=[];sin_informacion=[];latente=0.
    medias=(16,17,15,14,16,10,7)
    for i in range((fin-inicio).days+1):
        f=inicio+timedelta(days=i);feriado=f.isoformat() in calendario_cfg['fechas']
        if rng.random()<.008:
            sin_informacion.append(f.isoformat());continue
        latente=.45*latente+float(rng.normal(0,1.5))
        estacional=1.8*math.cos(2*math.pi*(f.timetuple().tm_yday-190)/365.25)
        media=max(1.,medias[f.weekday()]+estacional+latente-(3.5 if feriado else 0))
        n=int(rng.poisson(media))
        evento=float(rng.random())
        if evento<.006:
            n=0;eventos.append({"fecha":f.isoformat(),"tipo":"cierre_excepcional_simulado"})
        elif evento<.025:
            n+=int(rng.integers(4,9));eventos.append({"fecha":f.isoformat(),"tipo":"aumento_excepcional_simulado"})
        elif evento<.045:
            n=max(0,n-int(rng.integers(4,9)));eventos.append({"fecha":f.isoformat(),"tipo":"reduccion_excepcional_simulada"})
        n=min(CAPACIDAD,n)
        for j,pid in enumerate(rng.choice(np.arange(1,pacientes+1),size=n,replace=False)):
            edad=(f-date.fromisoformat(personas[int(pid)-1]['fecha_nacimiento'])).days/365.25
            opciones=list(range(len(CUADROS))) if edad>=18 else [0,1,2,3,5]
            cuadro=CUADROS[int(rng.choice(opciones))]
            minuto=8*60+j*20+int(rng.integers(0,9));hora=f'{minuto//60:02d}:{minuto%60:02d}'
            rng.integers(100000,1000000)  # Conservar la secuencia reproducible del historial.
            atenciones.append({"id":len(atenciones)+1,"paciente_id":int(pid),"fecha":f,"hora":hora,
                "motivo":str(rng.choice(cuadro[0])),"sintomas":cuadro[1],"diagnostico":cuadro[2],
                "receta":"",
                "notas":"",
                "estado":"Finalizado","creado_en":datetime.combine(f,datetime.strptime(hora,'%H:%M').time())})
        # Sólo se generan conteos aquí para describir el escenario; la carga ML
        # se reconstruye después por GROUP BY de atenciones persistidas.
        dias.append({"fecha":f,"es_feriado":feriado})
    manifiesto={"schema":1,"tipo":"sintetico","semilla":semilla,"generador":"numpy.default_rng PCG64",
        "desde":inicio.isoformat(),"hasta":fin.isoformat(),"meses":meses,"pacientes":pacientes,
        "capacidad_diaria":CAPACIDAD,"regla_etiquetas":{"BAJA":"0–9","MEDIA":"10–17","ALTA":"18–24"},
        "umbral_fijado_antes_de_entrenar":True,"regla_fuente":"Supuesto operativo: 24 turnos de 20 minutos entre 08:00 y 16:00; no es horario real del policlínico.",
        "medias_por_dia_semana":list(medias),"amplitud_estacional":1.8,"ruido":"Poisson; AR(1) 0.45 con innovación normal sigma 1.5",
        "sin_informacion":sin_informacion,"eventos":eventos,"calendario":calendario_cfg,
        "campos_no_disponibles":["servicio","profesional_responsable","costo"],
        "fuentes":["https://www.gob.pe/feriados","https://www.proviasdes.gob.pe/planes/pasco/pvpp/PVPP_Daniel_A_Carrion.pdf"],
        "limitacion":"Escenario académico con supuestos y ruido. No representa personas ni atenciones reales; no acredita validez externa."}
    return personas,atenciones,dias,manifiesto
