# Ingesta climática reproducible

Desde la raíz del repo, con Python 3.12 (solo biblioteca estándar):

```powershell
python scripts/ingest_climate.py --start 2024-01-01 --end 2024-01-05
```

Descarga las seis variables POWER y los archivos ONI/RONI completos. El punto
predeterminado `10.55, -85.50` es **provisional**: no se ha validado que sea una
finca ni que SoilGrids entregue un perfil utilizable. Cambiarlo con `--latitude`
y `--longitude`. Las consultas no requieren token ni API key.

Para reprocesar sin red, repetir la misma orden con `--offline`. `--refresh`
consulta nuevas versiones y conserva los cuerpos y metadatos anteriores.
`--skip-noaa` omite las descargas de índices. Los intervalos mayores de un año
se dividen por año y se ejecutan de forma secuencial; repetir la orden reutiliza
los intervalos completos en caché. No se descarga el histórico automáticamente.

Cuando se confirme el punto, este es el comando del histórico cerrado:

```powershell
python scripts/ingest_climate.py --start 1981-01-01 --end 2025-12-31
```

El seguimiento 2026 se descarga por separado, con una fecha final explícita
que no exceda la disponibilidad del proveedor. Un año incompleto no se trata
como temporada completa ni como candidato histórico KNN.

## Archivos

- `datasets/raw/climate/`: cuerpos originales `.body` nombrados por SHA-256,
  un índice por URL y sidecars de cada snapshot con URL, fecha UTC, hash,
  ETag y Last-Modified cuando estén disponibles.
- `datasets/processed/climate/power_<lat>_<lon>_<inicio>_<fin>.json`: fechas
  continuas, valores normalizados, unidades, QC y procedencia.
- `datasets/processed/climate/oni.json` y `roni.json`: índices separados con
  año, ventana de tres meses, mes central y anomalía en °C.

No publicar los datos crudos por defecto. El código no modifica `.gitignore`;
el responsable del repo debe mantener estas descargas fuera de commits masivos.

## Reglas de normalización

POWER se solicita con comunidad `AG`, `units=metric`, `time-standard=LST`.
LST es hora solar local del proveedor, no la zona horaria civil de Costa Rica.
Se validan las unidades de cada respuesta; unidades desconocidas detienen la
ingesta. Radiación `MJ/m^2/day` pasa sin conversión; si el proveedor informa
`kW-hr/m^2/day`, se convierte explícitamente multiplicando por 3.6.

Se conservan todos los días solicitados. Campos ausentes, fill value, NaN y
valores físicos inválidos se vuelven `null`, con un aviso QC por fecha y variable.
Una variable que el proveedor omite por completo para un período también queda
`null`; `provider_units` registra `null` si no se informó una unidad para ella.
No se convierten huecos a lluvia cero. Si Tmin supera Tmax, ambas quedan `null`.
`et0_mm` queda `null`: le corresponde al kernel de Justin calcular FAO-56.

La lluvia mayor de 500 mm/día se marca para revisión sin recortarla. El umbral
se configura con `--rain-warning-mm`; es un control operativo, no una afirmación
de imposibilidad física. No se aplica p99.9 ni se calibra la lluvia con el supuesto
sesgo +28% del WBS: requiere validar período, estación IMN y comparación espacial.

ONI usa `ANOM`, no la columna `TOTAL`. RONI se lee de su archivo propio, sin
intercambiar índices. `fase_temporada` conserva `AMJ` a `OND`; las otras ventanas
quedan identificadas por `season` con `fase_temporada=null`. Esto no constituye
una clasificación de episodios ENOS. Los índices solapados no son observaciones
mensuales independientes. Cada descarga preserva el snapshot para documentar
revisiones; el archivo actual de NOAA no permite reconstruir qué se sabía en una
fecha pasada sin archivos de publicación históricos.

## Validación

```powershell
python -m unittest backend.tests.test_ingestion -v
```

Incluye pérdida de días, sentinelas, lluvia extrema, unidades de radiación,
temperaturas inconsistentes, formatos ONI/RONI, caché offline y corrupción de hash.
Los fixtures de estas pruebas son sintéticos; no representan observaciones.

El navegador integrado y esta CLI confirmaron una consulta POWER real de cinco
días (`2024-01-01`–`2024-01-05`, punto provisional): 5 días, cero flags QC,
POWER API v2.10.3 y radiación en `MJ/m^2/day`. La CLI también descargó 921
observaciones de ONI y 921 de RONI. Ambos archivos terminaban en ASO 2026
(ONI 2.46 °C, RONI 1.97 °C) en ese snapshot. Un replay `--offline` reprodujo
los tres archivos, y las cinco filas POWER validaron con `ClimateDay`.
La red del shell requiere el permiso de ejecución externo del entorno.

### Histórico descargado el 14 de noviembre de 2026

La CLI completó los 46 intervalos anuales de `1981-01-01` a `2026-11-14`:
**16.754 días** solicitados y 1.117 flags QC (puede haber varios flags por día).
Las 16.754 filas validaron con el contrato `ClimateDay`.

- 1981–1983: POWER omite radiación solar (1.095 valores `null`). No se puede
  calcular ET0 con este conjunto de variables para esos años sin otra fuente.
- 1984–2025: las seis variables están disponibles en todas las fechas. Son
  42 años con entradas completas, antes de calcular ET0.
- `2020-11-03`: lluvia superior a 500 mm/día, preservada y marcada para revisión.
- 2026: 21 valores ausentes. La radiación falta el 7 de septiembre y del
  10 al 14 de noviembre; las seis variables faltan del 12 al 14 de noviembre.
  Última fecha meteorológica válida: 11 de noviembre; última radiación válida:
  9 de noviembre. El año de seguimiento sigue incompleto.

Pendientes científicos: validar punto y perfil de suelo con SoilGrids,
calcular ET0 en el kernel, revisar el extremo de precipitación y justificar
cualquier calibración contra una referencia local. La descarga no implica
que esos pasos estén resueltos.

## Fuentes primarias

- [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/)
- [NASA POWER: estándares temporales](https://power.larc.nasa.gov/docs/faqs/other/)
- [NOAA CPC ONI, archivo ASCII](https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt)
- [NOAA CPC RONI, archivo ASCII](https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt)
- [NOAA CPC: definición de las ventanas RONI](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/)
