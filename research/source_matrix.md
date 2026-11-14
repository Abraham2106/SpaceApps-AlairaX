# Matriz de fuentes (tarea 2.1)

Fecha: 2026-11-14 · Autor: I3 / Ant. Datos en formato maquina: `research/procedencia.json` (misma informacion).

Estados: **verificado** = contrastado con la fuente en esta o en sesion previa; **parcial** = fuente correcta pero uso no local o celda sin confirmar; **no verificado** = sin fuente accesible.

| fuente | dato | valor | fecha | unidad | confiabilidad | estado | URL |
|---|---|---|---|---|---|---|---|
| FAO-56 Tabla 12 | rice Kc ini/mid/end | [1.05, 1.2, 0.9] | 1998 | adimensional | alta (fuente primaria) | verificado en fuente (paddy; upland no cubierto) | https://www.fao.org/3/x0490e/x0490e0b.htm |
| FAO-56 Tabla 11 | rice duracion de etapas | [30, 30, 60, 30] | 1998 | dias | alta, no local | parcial: fila Mediterranea, no Guanacaste | https://www.fao.org/3/x0490e/x0490e0b.htm |
| FAO-56 Tabla 22 | rice Zr max | 1.0 | 1998 | m | alta | parcial (extremo superior del rango, nota 1) | https://www.fao.org/3/x0490e/x0490e0e.htm |
| FAO-56 Tabla 22 | rice p | 0.2 | 1998 | fraccion de TAW | alta (arroz: 'de saturacion') | parcial | https://www.fao.org/3/x0490e/x0490e0e.htm |
| FAO-56 Tabla 12 | melon Kc ini/mid/end | [0.5, 1.05, 0.75] | 1998 | adimensional | alta (fuente primaria) | parcial (celda Kc ini de imagen para melon, cowpea, sorghum: solo valor de grupo) | https://www.fao.org/3/x0490e/x0490e0b.htm |
| FAO-56 Tabla 11 | melon duracion de etapas | [25, 35, 40, 20] | 1998 | dias | alta, no local | parcial: fila Mediterranea, no Guanacaste | https://www.fao.org/3/x0490e/x0490e0b.htm |
| FAO-56 Tabla 22 | melon Zr max | 1.5 | 1998 | m | alta | parcial (extremo superior del rango, nota 1) | https://www.fao.org/3/x0490e/x0490e0e.htm |
| FAO-56 Tabla 22 | melon p | 0.4 | 1998 | fraccion de TAW | alta | verificado en fuente | https://www.fao.org/3/x0490e/x0490e0e.htm |
| FAO-56 Tabla 12 | cowpea Kc ini/mid/end | [0.4, 1.05, 0.6] | 1998 | adimensional | alta (fuente primaria) | parcial (celda Kc ini de imagen para melon, cowpea, sorghum: solo valor de grupo) | https://www.fao.org/3/x0490e/x0490e0b.htm |
| FAO-56 Tabla 11 | cowpea duracion de etapas | [20, 30, 30, 20] | 1998 | dias | alta, no local | parcial: fila Mediterranea, no Guanacaste | https://www.fao.org/3/x0490e/x0490e0b.htm |
| FAO-56 Tabla 22 | cowpea Zr max | 1.0 | 1998 | m | alta | parcial (extremo superior del rango, nota 1) | https://www.fao.org/3/x0490e/x0490e0e.htm |
| FAO-56 Tabla 22 | cowpea p | 0.45 | 1998 | fraccion de TAW | alta | verificado en fuente | https://www.fao.org/3/x0490e/x0490e0e.htm |
| FAO-56 Tabla 12 | sorghum Kc ini/mid/end | [0.3, 1.05, 0.55] | 1998 | adimensional | alta (fuente primaria) | parcial (celda Kc ini de imagen para melon, cowpea, sorghum: solo valor de grupo) | https://www.fao.org/3/x0490e/x0490e0b.htm |
| FAO-56 Tabla 11 | sorghum duracion de etapas | [20, 35, 40, 30] | 1998 | dias | alta, no local | parcial: fila Mediterranea, no Guanacaste; suma 125 d vs 130 d citado: revisar | https://www.fao.org/3/x0490e/x0490e0b.htm |
| FAO-56 Tabla 22 | sorghum Zr max | 2.0 | 1998 | m | alta | parcial (extremo superior del rango, nota 1) | https://www.fao.org/3/x0490e/x0490e0e.htm |
| FAO-56 Tabla 22 | sorghum p | 0.55 | 1998 | fraccion de TAW | alta | verificado en fuente | https://www.fao.org/3/x0490e/x0490e0e.htm |
| Jagadish et al. 2007 via Shrestha et al. 2022 | rice heat_threshold_c | 35.0 | 2022 | grados C | media, cita secundaria | parcial: aplica a antesis | https://doi.org/10.3389/fpls.2022.1050599 |
| crops.yaml | mucuna/canavalia todos los parametros | null | 0.1.0 | - | - | null: sin fuente | - |
| crops.yaml | melon/cowpea/sorghum heat_threshold_c | null | 0.1.0 | grados C | - | null: sin fuente | - |
| rotations.yaml | fechas de siembra (rice 05-15, melon 12-01, cowpea 10-15, sorghum 10-15) | "ver YAML" | 0.1.0 | MM-DD | baja: por defecto, sin productores | no verificado; sin solape (el arroz de 150 d termina el 11-oct); antes 06-01 y 10-01 se solapaban | - |
| Manual FAO de riego No. 3 cap. 2 | percolacion arroz inundado | [4, 6, 8] | - | mm/dia | media (URL por confirmar) | parcial: capitulo posterior da 2/5/8; campo en Tailandia 0-3 | - |
| Manual FAO de riego No. 3 cap. 2 | rangos de ETc estacional (arroz 450-700, melon 400-600, sorgo 450-650) | null | - | mm/ciclo | media | parcial; la etiqueta 'Tabla 13' del kernel se corrigió a 'cap. 2' | - |
| NASA POWER daily AG | T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, humedad, viento, radiacion en 10.55,-85.50 | "16.754 dias 1981-14/11/2026" | descarga 2026-11-14 | mm/d, grados C, MJ/m2/d, m/s | media: grilla 0.5 grados, modelada/reanalisis | verificado en repo (cobertura); punto provisional; sin radiacion 1981-1983 | https://power.larc.nasa.gov/docs/services/api/ |
| NASA POWER | elevacion del punto | 94.64 | 2026-11-14 | m | media | verificado en la respuesta | https://power.larc.nasa.gov/docs/services/api/ |
| NASA POWER vs IMN AIDO Liberia | diferencia de lluvia anual | {"media": "+29.5 %", "mediana": "+26 %"} | 2005-2025 | % | indicativa; estacion puntual vs pixel 0.5 grados | parcial: consistente con '+28 %' del pitch, cuya fuente no esta verificada | https://www.imn.ac.cr |
| IMN AIDO Liberia (10 35 36 N, 85 32 40 W) | lluvia media anual | 1545.9 | 2005-2025 | mm/ano | alta (observada), estacion | verificado | https://www.imn.ac.cr |
| IMN | lluvia media anual 1,652.7 mm | 1652.7 | - | mm/ano | - | no verificado: no encontrada en fuente | https://www.imn.ac.cr |
| SoilGrids 2.0 (ISRIC) | wv0033 y wv1500 por 6 profundidades (÷1000) | null | descarga previa | m3/m3 | media: prediccion espacial 250 m, incertidumbre del modelo | parcial: perfil hidraulico sin aprobar | https://www.isric.org/explore/soilgrids |
| HLS (NASA) | imagen 30 m (uso previsto de contexto) | null | - | - | alta resolucion, no usada en el balance | no usado en calculos | https://hls.gsfc.nasa.gov/ |
| NOAA CPC ONI/RONI | anomalia ASO; fuertes Nino 1997, 2015, 2023 | "3 anios" | snapshot repo | grados C | alta; ONI exploratorio, RONI oficial | verificado en repo; version publicada por registrar | https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php |
| Proyecto (decisions.md) | k=3 en Nino fuerte, k=5 en los demas | null | 2026-11-14 | anios | decision de producto | decision registrada | docs/decisions.md |
| Proyecto (kernel) | RO = 0.3 max(0, P-60); barbecho kc 0.15 Zr 0.15 p 0.5 | "-" | kernel v0.1 | mm | convencion, no FAO-56 | supuesto declarado | - |
