"""
MÓDULO LIMPIEZA / FILTRADO  (punto "Filtrado de datos" de la rúbrica)

Cada fuente escribe las cosas a su manera. Aquí se homogeneiza todo para que
main.py muestre datos uniformes:
  - Cartelera: idioma "En Versión Original subtitulada" / "En V.O.S.E." -> "VOSE"
  - Sitios   : "PRICE_LEVEL_MODERATE" -> "€€", quitar sitios sin valoración,
               ordenar por valoración ponderada por número de reseñas.
"""
import re
import unicodedata

import pandas as pd


def _sin_tildes(t):
    t = unicodedata.normalize("NFD", str(t).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------- CARTELERA
def normalizar_idioma(texto):
    t = _sin_tildes(texto)
    if re.search(r"original|v\.?\s?o", t):
        return "VOSE"
    if "espanol" in t or "version" in t:
        return "VE"
    return "Desconocido"


def limpiar_cartelera(df):
    if df.empty:
        return df
    df = df.copy()
    df["pelicula"] = df["pelicula"].str.strip()
    df["idioma"] = df["idioma"].map(normalizar_idioma)
    df["hora"] = df["hora"].str.strip()
    df = df[df["hora"].str.match(r"^\d\d:\d\d$")]          # descartar horas mal leídas
    df = df.drop_duplicates(subset=["cine", "pelicula", "idioma", "formato", "hora"])
    return df.sort_values(["pelicula", "hora"]).reset_index(drop=True)


# ---------------------------------------------------------------- SITIOS
PRECIOS = {
    "PRICE_LEVEL_FREE": "Gratis", "PRICE_LEVEL_INEXPENSIVE": "€",
    "PRICE_LEVEL_MODERATE": "€€", "PRICE_LEVEL_EXPENSIVE": "€€€",
    "PRICE_LEVEL_VERY_EXPENSIVE": "€€€€",
}


def limpiar_sitios(df, min_valoracion=3.5, min_resenas=20):
    if df.empty:
        return df
    df = df.copy()
    df["precio"] = df["precio"].map(PRECIOS).fillna("¿?")
    df = df.dropna(subset=["valoracion"])
    df = df[(df["valoracion"] >= min_valoracion) & (df["resenas"].fillna(0) >= min_resenas)]
    # Un 5.0 con 3 reseñas no vale lo mismo que un 4.6 con 1.600: ponderamos.
    # Cada sitio parte de m reseñas "imaginarias" con nota 'media'. Con pocas reseñas
    # reales pesa más la media; con muchas, su nota real. (Media bayesiana)
    m = 100      # nº de reseñas "de confianza"
    media = 4.0  # nota típica en Google; fija, para no depender de qué sitios han salido
    df["puntuacion"] = (df["resenas"] * df["valoracion"] + m * media) / (df["resenas"] + m)
    return df.sort_values("puntuacion", ascending=False).reset_index(drop=True)
