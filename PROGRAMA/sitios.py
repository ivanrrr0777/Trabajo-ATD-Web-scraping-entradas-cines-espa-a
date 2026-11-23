"""
MÓDULO SITIOS CERCANOS - Google Places API (New)

Entrada : nombre del cine + ciudad (del paso anterior)
Salida  : DataFrame con los sitios cercanos (restaurantes, bares...)

Dos llamadas encadenadas, como en AEMET:
  1) searchText   : "Kinépolis, Valencia" -> latitud y longitud del cine
  2) searchNearby : coordenadas + tipo    -> sitios en un radio
"""
import os

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()  # lee las claves del fichero .env y las mete en os.environ

RADIO_METROS = 500.0
TIPOS_INTERES = ["restaurant", "bar", "cafe"]


def _clave():
    clave = os.environ.get("GOOGLE_API_KEY")
    if not clave:
        raise RuntimeError('Falta la clave de Google. Añádela al fichero .env: GOOGLE_API_KEY=tu_clave')
    return clave


def obtener_coordenadas_cine(texto_busqueda):
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": _clave(),
        "X-Goog-FieldMask": "places.id,places.displayName,places.location",
    }
    payload = {"textQuery": texto_busqueda, "languageCode": "es"}
    respuesta = requests.post(url, headers=headers, json=payload, timeout=15).json()

    if respuesta.get("places"):
        lugar = respuesta["places"][0]
        return {
            "nombre_oficial": lugar.get("displayName", {}).get("text", texto_busqueda),
            "place_id_cine": lugar.get("id"),
            "lat": lugar["location"]["latitude"],
            "lng": lugar["location"]["longitude"],
        }
    print(f"[!] No se pudo localizar '{texto_busqueda}': "
          f"{respuesta.get('error', {}).get('message', 'sin resultados')}")
    return None


def buscar_sitios_cercanos(lat, lng, tipo, radio=RADIO_METROS):
    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": _clave(),
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,"
                            "places.rating,places.userRatingCount,places.priceLevel,places.types",
    }
    payload = {
        "includedTypes": [tipo],
        "maxResultCount": 20,
        "languageCode": "es",
        "locationRestriction": {"circle": {"center": {"latitude": lat, "longitude": lng},
                                           "radius": float(radio)}},
    }
    respuesta = requests.post(url, headers=headers, json=payload, timeout=15).json()
    if "error" in respuesta:
        print(f"[!] Error en Nearby Search ({tipo}): {respuesta['error'].get('message')}")
    return respuesta.get("places", [])


def sitios_cerca_de(nombre_cine, ciudad, tipos=TIPOS_INTERES):
    """FUNCIÓN QUE USA main.py. Devuelve un DataFrame (vacío si no hay nada)."""
    # Añadimos la ciudad a la búsqueda: "Cinesa Bonaire" solo es ambiguo, con ciudad no.
    info = obtener_coordenadas_cine(f"{nombre_cine}, {ciudad}")
    if not info:
        return pd.DataFrame()

    filas, vistos = [], {info["place_id_cine"]}  # 'vistos' evita repetir locales entre tipos
    for tipo in tipos:
        for s in buscar_sitios_cercanos(info["lat"], info["lng"], tipo):
            if s.get("id") in vistos:
                continue
            vistos.add(s.get("id"))
            filas.append({
                "cine": info["nombre_oficial"],
                "categoria": tipo,
                "nombre": s.get("displayName", {}).get("text"),
                "valoracion": s.get("rating"),
                "resenas": s.get("userRatingCount"),
                "precio": s.get("priceLevel"),
                "direccion": s.get("formattedAddress"),
                "etiquetas": ", ".join(s.get("types", [])),
            })
    return pd.DataFrame(filas)


if __name__ == "__main__":  # prueba suelta del módulo
    print(sitios_cerca_de(input("Cine: "), input("Ciudad: ")).head(10))
