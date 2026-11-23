"""
PROYECTO ATD - Planificador de una tarde de cine

FLUJO (cada paso usa lo que devuelve el anterior):

  1. Usuario escribe la ciudad
  2. tiempo.py     -> tiempo de hoy en esa ciudad                (API AEMET)
  3. cartelera.py  -> lista numerada de cines de la ciudad       (scraping Sensacine)
  4. Usuario elige un cine por número
  5. cartelera.py  -> películas y horarios de ese cine           (scraping Sensacine)
  6. sitios.py     -> restaurantes/bares cerca de ese cine       (API Google Places)
  limpieza.py      -> homogeneiza y filtra los datos de 5 y 6
  Todo se guarda en la carpeta datos/

Antes de ejecutar: copia .env.example como .env y pon vuestras claves.
    python main.py
"""
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # lee las claves del fichero .env y las mete en os.environ

import cartelera
import limpieza
import sitios
import tiempo

CARPETA = Path("datos")


def pedir_numero(mensaje, maximo):
    """Repite la pregunta hasta que el usuario escriba un número válido (validar la entrada)."""
    while True:
        texto = input(mensaje).strip()
        if texto.isdigit() and 1 <= int(texto) <= maximo:
            return int(texto)
        print(f"  Escribe un número entre 1 y {maximo}.")


def mostrar_tiempo(ciudad):
    try:
        t = tiempo.tiempo_hoy(ciudad)
    except Exception as e:  # si AEMET falla, el programa sigue: el tiempo es un extra
        print(f"  (No se pudo consultar el tiempo: {e})")
        return None
    if not t:
        print("  (AEMET no reconoce esa ciudad, seguimos sin el tiempo)")
        return None
    print(f"\n  Tiempo hoy en {t['municipio']}: {t['temp_min']}–{t['temp_max']} °C, "
          f"{t['cielo']}, lluvia {t['prob_lluvia']} %")
    if str(t["prob_lluvia"]).isdigit() and int(t["prob_lluvia"]) >= 50:
        print("  ¡Coge paraguas!")
    return t


def elegir_cine(ciudad):
    cines = cartelera.cines_de_provincia(ciudad)           # {nombre: codigo}
    cines = {n: c for n, c in cines.items() if c}          # sin código no podemos scrapear
    if not cines:
        return None, None

    # Si hay muchos (Madrid, Barcelona...), dejamos filtrar por parte del nombre
    if len(cines) > 15:
        filtro = input(f"\nHay {len(cines)} cines. Escribe parte del nombre para filtrar "
                       "(Intro = ver todos): ").strip().lower()
        filtrados = {n: c for n, c in cines.items() if filtro in n.lower()}
        cines = filtrados or cines

    nombres = list(cines)
    print()
    for i, n in enumerate(nombres, 1):
        print(f"  {i:>2}. {n}")
    elegido = nombres[pedir_numero("\nElige el número del cine: ", len(nombres)) - 1]
    return elegido, cines[elegido]


def mostrar_cartelera(nombre, codigo):
    df = limpieza.limpiar_cartelera(pd.DataFrame(
        cartelera.cartelera_de_cine(nombre, codigo),
        columns=["cine", "pelicula", "idioma", "formato", "hora"]))
    if df.empty:
        print("\n  Este cine no tiene sesiones publicadas para hoy.")
        return df
    print(f"\n  CARTELERA DE HOY - {nombre}")
    for peli, d in df.groupby("pelicula", sort=False):
        print(f"  • {peli}")
        for (idioma, formato), s in d.groupby(["idioma", "formato"], sort=False):
            print(f"      {idioma} {formato}: {', '.join(s['hora'])}")
    return df


def mostrar_sitios(nombre, ciudad):
    try:
        df = limpieza.limpiar_sitios(sitios.sitios_cerca_de(nombre, ciudad))
    except Exception as e:
        print(f"  (No se pudo consultar Google Maps: {e})")
        return None
    if df.empty:
        print("\n  No se encontraron sitios bien valorados cerca del cine.")
        return df
    print(f"\n  DÓNDE COMER CERCA (mejor valorados, radio {int(sitios.RADIO_METROS)} m)")
    for _, s in df.head(10).iterrows():
        print(f"  • {s['nombre']:<35} {s['valoracion']}★ ({int(s['resenas'])}) {s['precio']:<5} "
              f"[{s['categoria']}]")
    return df


def main():
    CARPETA.mkdir(exist_ok=True)
    print("=== PLANIFICADOR DE CINE ===")
    ciudad = input("¿En qué ciudad estás? ").strip()

    mostrar_tiempo(ciudad)

    nombre, codigo = elegir_cine(ciudad)
    if not nombre:
        print("No se encontraron cines en esa ciudad.")
        return

    df_cartelera = mostrar_cartelera(nombre, codigo)
    df_sitios = mostrar_sitios(nombre, ciudad)

    # Guardar lo que ha visto el usuario (sirve para la memoria y para depurar)
    if not df_cartelera.empty:
        df_cartelera.to_csv(CARPETA / "cartelera.csv", index=False, encoding="utf-8-sig")
    if df_sitios is not None and not df_sitios.empty:
        df_sitios.to_csv(CARPETA / "sitios.csv", index=False, encoding="utf-8-sig")
    print(f"\nDatos guardados en la carpeta '{CARPETA}/'. ¡Disfruta de la peli!")


if __name__ == "__main__":
    main()
