"""
MÓDULO TIEMPO - API AEMET OpenData

Entrada : nombre de la ciudad (lo que escribe el usuario)
Salida  : dict con la predicción de HOY en esa ciudad

AEMET no entiende "Madrid", entiende el código INE "28079". Por eso hay dos pasos:
  1) ciudad -> código INE   (diccionario rápido o, si no está, maestro de municipios de AEMET)
  2) código INE -> predicción diaria
"""
import json
import os
import unicodedata
from datetime import date

import requests
from dotenv import load_dotenv

load_dotenv()  # lee las claves del fichero .env y las mete en os.environ

BASE_URL = "https://opendata.aemet.es/opendata/api"

# Atajo para las ciudades más habituales (evita una petición extra a AEMET)
CODIGOS_INE = {
    "madrid": "28079", "barcelona": "08019", "valencia": "46250", "sevilla": "41091",
    "zaragoza": "50297", "malaga": "29067", "murcia": "30030", "palma": "07040",
    "bilbao": "48020", "alicante": "03014", "cordoba": "14021", "valladolid": "47186",
    "vigo": "36057", "gijon": "33024", "granada": "18087", "a coruna": "15030",
}


def _sin_tildes(t):
    t = unicodedata.normalize("NFD", t.lower().strip())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _cabeceras():
    clave = os.environ.get("AEMET_API_KEY")
    if not clave:
        raise RuntimeError('Falta la clave de AEMET. Añádela al fichero .env: AEMET_API_KEY=tu_clave')
    return {"api_key": clave, "Accept": "application/json"}


def reparar_texto(obj):
    """Corrige el 'mojibake' (p. ej. 'ValÃ¨ncia' -> 'València'). Si ya está bien, lo deja igual."""
    if isinstance(obj, str):
        try:
            return obj.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return obj
    if isinstance(obj, list):
        return [reparar_texto(x) for x in obj]
    if isinstance(obj, dict):
        return {k: reparar_texto(v) for k, v in obj.items()}
    return obj


def decodificar_json(contenido: bytes):
    """Algunos ficheros de AEMET llegan en UTF-8 y otros en ISO-8859-1."""
    try:
        datos = json.loads(contenido.decode("utf-8"))
    except UnicodeDecodeError:
        datos = json.loads(contenido.decode("latin-1"))
    return reparar_texto(datos)


def pedir_datos(endpoint: str):
    """Petición en dos pasos de AEMET. Devuelve los datos ya decodificados."""
    r = requests.get(f"{BASE_URL}{endpoint}", headers=_cabeceras(), timeout=15)
    r.raise_for_status()
    respuesta = r.json()
    if respuesta.get("estado") != 200:
        raise RuntimeError(f"AEMET respondió {respuesta.get('estado')}: {respuesta.get('descripcion')}")
    d = requests.get(respuesta["datos"], timeout=15)
    d.raise_for_status()
    return decodificar_json(d.content)


def codigo_ine(ciudad):
    """'Valencia' -> '46250'. Primero el diccionario; si no está, el maestro de AEMET."""
    clave = _sin_tildes(ciudad)
    if clave in CODIGOS_INE:
        return CODIGOS_INE[clave]
    municipios = pedir_datos("/maestro/municipios")
    for m in municipios:
        if _sin_tildes(m.get("nombre", "")) == clave:
            return m["id"].replace("id", "")  # AEMET lo da como "id28079"
    return None


def del_dia(lista, clave):
    """Entrada del día completo (00-24) si tiene valor; si no (pasa con el día de hoy),
    la primera entrada que sí tenga valor."""
    con_valor = [x for x in (lista or []) if x.get(clave) not in (None, "")]
    for item in con_valor:
        if item.get("periodo") == "00-24":
            return item
    return con_valor[0] if con_valor else {}


def dato(item, clave):
    valor = item.get(clave)
    return valor if valor not in (None, "") else "sin dato"


def prediccion_municipio(codigo):
    """Lista de dicts limpios, un día por elemento."""
    pred = pedir_datos(f"/prediccion/especifica/municipio/diaria/{codigo}")[0]
    dias = []
    for dia in pred["prediccion"]["dia"]:
        temp = dia.get("temperatura", {})
        cielo = del_dia(dia.get("estadoCielo"), "descripcion")
        lluvia = del_dia(dia.get("probPrecipitacion"), "value")
        viento = del_dia(dia.get("viento"), "direccion")
        dias.append({
            "municipio": pred["nombre"], "fecha": dia["fecha"][:10],
            "temp_max": temp.get("maxima"), "temp_min": temp.get("minima"),
            "cielo": dato(cielo, "descripcion"), "prob_lluvia": dato(lluvia, "value"),
            "viento_dir": dato(viento, "direccion"), "viento_kmh": dato(viento, "velocidad"),
        })
    return dias


def tiempo_hoy(ciudad):
    """FUNCIÓN QUE USA main.py. Devuelve el dict de hoy, o None si no se encuentra la ciudad."""
    codigo = codigo_ine(ciudad)
    if not codigo:
        return None
    dias = prediccion_municipio(codigo)
    hoy = date.today().isoformat()
    return next((d for d in dias if d["fecha"] == hoy), dias[0] if dias else None)


if __name__ == "__main__":  # prueba suelta del módulo
    print(tiempo_hoy(input("Ciudad: ")))
