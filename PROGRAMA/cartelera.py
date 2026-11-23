"""
REFERENCIA: scraping de la cartelera de Sensacine (requests + BeautifulSoup + pandas)

Patrones reutilizables:
  1. descargar()        -> petición + parseo + control de errores
  2. paginación         -> ?page=N hasta que no salen elementos nuevos
  3. regex sobre HTML   -> sacar códigos/ids de un bloque
  4. subir por el árbol -> de un dato suelto (la hora) a su "contenedor" (la sesión)
  5. recorrer en orden  -> las cabeceras (idioma) afectan a lo que viene después
  6. DataFrame + CSV    -> filas -> tabla -> groupby -> exportar
"""
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}   # sin esto algunas webs devuelven 403
BASE = "https://www.sensacine.com"
SEL_PELI = "h2 a[href*='/peliculas/pelicula-']"      # selector CSS: enlace dentro de un h2
HORA = re.compile(r"^\s*\d\d:\d\d")                   # texto que empieza por hh:mm
IDIOMA = re.compile(r"En\s+(V\.?\s?O|Versi[oó]n)[^\n]*", re.I)
FORMATOS = ["IMAX", "4DX", "3D", "SCREENX", "DBOX", "DOLBY"]


# 1. Descarga -----------------------------------------------------------------
def descargar(url, params=None):
    r = requests.get(url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()                  # lanza excepción si 4xx/5xx
    return BeautifulSoup(r.text, "html.parser")


# 2. Provincias y cines (con paginación) --------------------------------------
def lista_provincias():
    soup = descargar(BASE + "/cines/")
    # select("a[href*='texto']") = enlaces cuyo href CONTIENE ese texto
    return {a.get_text(strip=True): BASE + a["href"]
            for a in soup.select("a[href*='/cines/provincias-']")}


def cines_de_provincia(entrada):
    """{nombre_cine: codigo}. Recorre todas las páginas de la provincia."""
    provincias = lista_provincias()
    entrada = entrada.strip().lower()
    coincidencias = [n for n in provincias if entrada in n.lower()]
    if not coincidencias:
        print("Provincia no encontrada. Opciones:", list(provincias))
        return {}
    url = provincias[coincidencias[0]]

    cines, pagina = {}, 1
    while True:
        soup = descargar(url, params={"page": pagina})
        nuevos = {}
        for h3 in soup.select("h3"):                      # cada cine tiene un <h3>
            tarjeta = h3.find_parent("li")                # su contenedor
            if tarjeta is None:
                continue
            # 3. regex sobre el HTML de la tarjeta: código tipo E0291
            codigo = re.search(r"\bE\d{4}\b", str(tarjeta))
            nuevos[h3.get_text(strip=True)] = codigo.group() if codigo else None
        # condición de parada: página vacía o sin nada nuevo (evita bucle infinito)
        if not nuevos or set(nuevos) <= set(cines):
            break
        cines.update(nuevos)
        pagina += 1
    return cines


# 4. Subir por el árbol -------------------------------------------------------
def bloque_de_sesion(texto):
    """Desde el texto de la hora, sube al contenedor más grande que solo
    tiene UNA hora (botón + logo de formato). Idea general: subir mientras
    el padre siga conteniendo solo 'un elemento' de lo que buscas."""
    bloque = texto.parent
    while (bloque.parent is not None
           and len(bloque.parent.find_all(string=HORA)) == 1
           and not bloque.parent.select(SEL_PELI)):
        bloque = bloque.parent
    return bloque


def formato_de(bloque):
    """Busca el nombre del formato en el HTML del bloque (texto, alt, src, class)."""
    html = str(bloque).upper()
    encontrados = [f for f in FORMATOS if f in html]
    return "/".join(encontrados) if encontrados else "2D"     # sin etiqueta -> 2D


# 5. Recorrer en orden --------------------------------------------------------
def cartelera_de_cine(nombre, codigo):
    """Lista de filas (dicts): una por sesión."""
    soup = descargar(f"{BASE}/cines/cine/{codigo}/")
    filas = []
    for h2 in soup.select("h2"):
        if not h2.select_one(SEL_PELI):                   # h2 que no son películas
            continue
        pelicula = h2.get_text(strip=True)

        # tarjeta = HTML completo de esa película (sube mientras solo haya 1 película)
        tarjeta = h2
        while tarjeta.parent is not None and len(tarjeta.parent.select(SEL_PELI)) == 1:
            tarjeta = tarjeta.parent

        idioma = "?"
        # find_all(string=True) = todos los textos en orden de aparición
        for texto in tarjeta.find_all(string=True):
            m = IDIOMA.search(texto)
            if m:
                idioma = m.group().strip()     # la cabecera fija el idioma de lo siguiente
            elif HORA.match(texto):
                filas.append({
                    "cine": nombre,
                    "pelicula": pelicula,
                    "idioma": idioma,
                    "formato": formato_de(bloque_de_sesion(texto)),
                    "hora": texto.strip()[:5],
                })
    return filas


# 6. Tratamiento y exportación ------------------------------------------------
def extraer_cartelera(provincia, filtro=""):
    """Devuelve un DataFrame con todas las sesiones de los cines de la provincia
    cuyo nombre contenga 'filtro'. La puede importar main.py."""
    cines = cines_de_provincia(provincia)
    print(f"{len(cines)} cines encontrados")
    filtro = filtro.strip().lower()
    filas = []
    for nombre, codigo in cines.items():
        if filtro in nombre.lower() and codigo:
            filas += cartelera_de_cine(nombre, codigo)
            time.sleep(1)                      # pausa: no saturar el servidor
    return pd.DataFrame(filas).drop_duplicates()


if __name__ == "__main__":
    provincia = input("Provincia: ")
    filtro = input("Cine (vacío = todos): ")
    df = extraer_cartelera(provincia, filtro)

    if df.empty:
        print("No se encontraron sesiones.")
    else:
        df.to_csv("cartelera.csv", index=False, encoding="utf-8-sig")

        # sort=False mantiene el orden en que aparecen en la web
        for cine, d_cine in df.groupby("cine", sort=False):
            print(f"\nCartelera de hoy en {cine}:")
            for pelicula, d_peli in d_cine.groupby("pelicula", sort=False):
                print(f"  {pelicula}")
                for (idioma, formato), d_ses in d_peli.groupby(["idioma", "formato"], sort=False):
                    print(f"     {idioma} | {formato}: {d_ses['hora'].tolist()}")
