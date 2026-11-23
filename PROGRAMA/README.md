# Proyecto ATD – Planificador de una tarde de cine

## Descripción
El usuario escribe su ciudad y el programa le enseña:
1. **El tiempo de hoy** en esa ciudad (API de AEMET).
2. **Los cines de la ciudad** en una lista numerada para que elija uno (scraping de Sensacine).
3. **La cartelera de hoy** de ese cine: películas, idioma, formato y horas (scraping de Sensacine).
4. **Restaurantes, bares y cafeterías** cerca del cine, ordenados por valoración (API de Google Places).

## Flujo de interacción entre módulos
```
         ciudad                     ciudad -> código INE -> predicción
Usuario ────────► main.py ────────► tiempo.py      (AEMET, 2 peticiones)
                    │
                    │ ciudad        {nombre_cine: código}
                    ├─────────────► cartelera.py   (Sensacine: provincia -> cines)
  nº del cine ◄─────┤ lista numerada
                    │ código cine   sesiones en bruto
                    ├─────────────► cartelera.py   (Sensacine: ficha del cine)
                    │                     │
                    │                     ▼
                    │               limpieza.py    (idioma VE/VOSE, horas válidas, duplicados)
                    │ nombre cine + ciudad
                    ├─────────────► sitios.py      (Google: searchText -> coordenadas -> searchNearby)
                    │                     │
                    │                     ▼
                    │               limpieza.py    (precio €, valoración mínima, media bayesiana)
                    ▼
            datos/cartelera.csv   datos/sitios.csv
```
Cada módulo recibe lo que devuelve el anterior. Si una fuente extra falla (AEMET o Google),
el programa avisa y sigue con lo demás.

## Filtrado de datos (`limpieza.py`)
- **Cartelera**: "En Versión Original", "En V.O.S.E." → `VOSE`; "En Versión Española" → `VE`.
  Se descartan horas mal leídas y sesiones duplicadas.
- **Sitios**: `PRICE_LEVEL_MODERATE` → `€€`. Se quitan los sitios sin valoración, con menos de 3,5★
  o con menos de 20 reseñas, y se ordenan con una **media bayesiana** para que un 5★ con 3 reseñas
  no quede por encima de un 4,6★ con 1.600.

## Ejecución (Windows, PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # y edita .env con vuestras claves
python main.py
```
Cada módulo también se puede probar suelto: `python tiempo.py`, `python sitios.py`, `python cartelera.py`.
