# Validación del kernel FAO-56

Este documento reúne lo que respalda (y lo que todavía no respalda) las métricas del kernel: la sensibilidad a sus parámetros (tarea 3.7) y la comparación manual con CROPWAT. Ninguna de las dos es validación de campo.

## Sensibilidad (tarea 3.7)

```powershell
python -m scripts.sensitivity --years 2013 2015 2023 --output-dir outputs/sensitivity
```

El script varía un parámetro a la vez frente a una base (suelo loam FAO-56, Dr0 = 0,5·TAW, secano) y corre las tres rotaciones en cada temporada mayo–abril. Escribe `sensitivity.csv` (formato largo, con valor, base, delta y delta %) y `sensitivity.md` (resumen). Tarda unos 5 s.

La corrida archivada en [sensitivity.md](sensitivity/sensitivity.md) y [sensitivity.csv](sensitivity/sensitivity.csv) es preliminar. Se ejecutó antes de la revisión de ET₀. La serie actual ya está revisada. Queda repetir la sensibilidad y revisar sus conclusiones con el suelo y los calendarios de referencia.

Lectura de esa corrida:

- **Kc ±10 %** mueve ETc ±10 % y el déficit unos ±21 %. El orden entre rotaciones no cambia en déficit ni en riego.
- **θfc** es el parámetro más influyente. Con θfc ×1,2 el déficit baja 21 % y el orden por déficit cambia en los 3 años. El perfil de suelo revisado es la prioridad antes de interpretar diferencias de déficit entre rotaciones.
- **Dr inicial** casi no importa (≤4 %). Una temporada de mayo arranca con lluvias y el suelo se recarga pronto.
- **Lluvia ±28 %** (sesgo POWER vs IMN) mueve el déficit entre −14 % y +17 % sin cambiar el orden por déficit.
- **Días de estrés** cambian de orden en 1–2 años en varios casos. Las diferencias entre rotaciones en esa métrica son pequeñas, así que conviene reportarlas con su rango y no como ranking.

## Estrés térmico (tarea 3.6)

`simulate_rotation_detailed` agrega `heat_stress_days` por cultivo y para la rotación. Cuenta los días con `tmax ≥ heat_threshold_c` dentro de la etapa FAO `mid`, usada como aproximación de la floración. Solo el arroz tiene umbral citado (35 °C en antesis, Jagadish et al. 2007, en `crops.yaml`). Los cultivos sin umbral quedan `null`; nunca 0. Si falta `tmax` en algún día de la etapa, el valor queda `null` con un aviso. La métrica no forma parte del contrato v0.1.0.

## Backtest de los análogos (tarea 4.6)

`python -m scripts.backtest --output-dir docs` corre el kernel con el clima histórico de 2015 y 2023 y lo compara con el ensamble de los k análogos de `find_analogs`. Solo entran como candidatos los años anteriores al objetivo. Las tablas y la gráfica evalúan los análogos frente al mismo kernel. La corrida archivada es preliminar y se ejecutó antes de la revisión de ET₀. [Resultados del backtest](backtest/backtest.md)

- **2015 (Niño fuerte y seco):**
  - Con k = 5, la verdad cae en el rango p10–p90 en 9 de 13 casos.
  - El p50 de los análogos queda más cerca que la climatología en 12 de 13 casos. El error en déficit baja de unos 220–240 mm a 55 mm.
  - Con k = 3 el rango es demasiado estrecho: la verdad solo cae dentro en 3 de 13 casos.
- **2023 (Niño con lluvia normal):**
  - El método falla: la verdad cae dentro en 0 de 13 casos con k = 3 y en 3 de 13 con k = 5.
  - El déficit queda sobreestimado entre 200 y 260 mm. La climatología lo hace mejor en casi todos los casos.
  - Los análogos (2015, 1997, 1987, 1990 y 1991) se parecen por ONI, calor y ET0, pero llovieron 280–735 mm en la ventana abril–octubre. 2023 llovió 1.019 mm.
- **Causas probables:**
  - Los pesos iguales hacen que la lluvia sea una de cinco features, y varias de las otras se mueven juntas con el ONI.
  - La lluvia de POWER antes de 2005 es la mitad de la de CHIRPS ([rain_bias.md](rain_bias.md)), así que los candidatos viejos parecen más secos de lo que fueron.
- **Qué hacer con esto:**
  - No usar k = 3 para el rango.
  - Mostrar la climatología junto al ensamble.
  - Antes de dar los análogos por validados, repetir el backtest con lluvia CHIRPS o con candidatos desde 2005.
  - La decisión del equipo sobre k (3 en Niño fuerte) merece revisarse a la luz de estos resultados.

## Comparación manual con CROPWAT

Se ejecutaron los cuatro casos de referencia del kernel `fao56-kernel-0.1.0`. Se contrastaron la ETc y el déficit estacional del arroz de secano con los módulos **CWR** y **Schedule** de [CROPWAT 8.0 de la FAO](https://www.fao.org/land-water/resources/tools/software/cropwat/en). Quedan los otros tres casos y la comparación día por día.

El archivo de ET₀ diario para el arroz abrió en **Daily measured ETo** con estación Liberia y año 2015. La captura de CROPWAT muestra 4,5, 4,7 y 4,8 mm/día del 1 al 3 de enero, 5,5 el 15 de mayo y 5,7 el 31 de diciembre. Los valores de control coinciden a la precisión visible. El archivo se abrió desde una ruta de 45 bytes porque CROPWAT limita a 120 bytes la ruta de entrada. La lluvia diaria cargó para la misma estación y año, con 918,4 mm de total anual. El cultivo abrió como **Dry crop**, con siembra el 15 de mayo y cosecha el 11 de octubre.

### Insumos y resultados del kernel

Se usó lluvia diaria NASA POWER del punto 10,55° N, 85,50° O y la [serie diaria de ET₀ revisada](../datasets/processed/et0/et0_10.55_-85.5.json), ambas completas en las ventanas de cultivo. Cada corrida empieza el día de la siembra con 50 % del agua útil en la zona radicular. El suelo de referencia es loam FAO-56, con θfc = 0,25 y θwp = 0,12 m³/m³, equivalentes a 130 mm de agua útil por metro de suelo. Los calendarios de la tabla corresponden a los casos históricos de este contraste.

| Cultivo | Ventana inclusiva | Días por etapa | Kc inicial / medio / final | Raíz (m) | p |
|---|---|---|---|---:|---:|
| Arroz secano | 2015-05-15 a 2015-10-11 | 30 / 30 / 60 / 30 | 1,05 / 1,20 / 0,90 | 1,0 | 0,20 |
| Melón regado | 2015-12-01 a 2016-03-29 | 25 / 35 / 40 / 20 | 0,50 / 1,05 / 0,75 | 1,5 | 0,40 |
| Caupí | 2015-10-15 a 2016-01-22 | 20 / 30 / 30 / 20 | 0,40 / 1,05 / 0,60 | 1,0 | 0,45 |
| Sorgo | 2015-10-15 a 2016-02-16 | 20 / 35 / 40 / 30 | 0,30 / 1,05 / 0,55 | 2,0 | 0,55 |

| Cultivo | ETc kernel (mm) | ETc CROPWAT (mm) | Segunda variable | Kernel (mm) | CROPWAT (mm) |
|---|---:|---:|---|---:|---:|
| Arroz secano | 810,073 | 845,4 | Déficit en secano | 362,200 | 384,1 |
| Melón regado | 615,129 | 644,2 | Riego neto | 665,632 | 668,7 |
| Caupí | 343,767 | 360,3 | Déficit en secano | 132,764 | 144,8 |
| Sorgo | 470,088 | 469,7 | Déficit en secano | 149,137 | 146,2 |

En arroz, **CWR** calculó **35,3 mm más de ETc** que el kernel. La diferencia es **4,18 %** respecto de CROPWAT y queda dentro del umbral provisional de 5 %. En media temporada, el reporte mostró **Kc = 1,27** con un Kc de entrada de **1,20**. Queda identificar el ajuste antes de atribuir toda la diferencia al kernel. **CWR** también mostró **538,1 mm** de lluvia efectiva y **450,4 mm** de requerimiento de riego por decenas.

En **Schedule → No irrigation (rainfed)**, la captura confirma ET potencial de **841,9 mm** y ET real de **457,8 mm** para la misma siembra y cosecha. El déficit de secano es **384,1 mm**, calculado con ambos totales de **Schedule**. Supera en **21,9 mm** los **362,2 mm** del kernel. La diferencia relativa de **5,70 %** respecto de CROPWAT queda dentro del umbral provisional de 15 %. El suelo tenía **130 mm/m** de agua disponible, **50 %** de agotamiento inicial, **100 cm** de profundidad máxima y **60 mm/día** de infiltración máxima. La redistribución de lluvia y los ajustes de Kc de CROPWAT siguen siendo diferencias entre los modelos.

**Caupí, preparación del caso.** Se generaron y verificaron los archivos diarios desde las series originales de ET₀ y lluvia. Los archivos de entrada conservan 2015 como año de visualización de CROPWAT y colocan enero de 2016 en las celdas de enero. Así, el ciclo de 100 días tiene octubre–diciembre de 2015 y enero de 2016. El control para el 1 de enero es **6,06 mm/día de ET₀ y 0,2 mm de lluvia**. Se reutilizó el suelo del arroz y se tomaron la altura y los factores de respuesta de rendimiento auxiliares del archivo genérico **Pulses** de CROPWAT. Estos campos auxiliares no aportan evidencia de rendimiento en finca. Se completó la lectura en CROPWAT.

**Caupí, resultado en CROPWAT 8.0.** CROPWAT leyó los cuatro archivos `CAUPI15` en la estación Liberia 15-16 con el modo *Daily measured ETo*. Las celdas de enero muestran los datos de 2016: el 1 de enero tiene 6,1 mm/día de ET₀ y 0,2 mm de lluvia, y el 22 de enero tiene 5,8 mm/día y 0,0 mm. Con siembra el 15/10, la cosecha calculada es el 22/01. **CWR** da un ETc estacional de **360,3 mm**, contra 343,767 mm del kernel: +4,6 %, dentro de la tolerancia de 5 %. CROPWAT mostró un Kc medio ajustado por clima de 1,10, frente al 1,05 de la entrada. **Schedule**, con *No irrigation (rainfed)*, da un uso potencial de **356,6 mm** y un uso real de **211,8 mm**. El déficit resultante es de **144,8 mm**, contra 132,764 mm del kernel: +8,3 %, dentro de la tolerancia de 15 %. Schedule también redistribuye la lluvia decadal entre los días 3 y 7, igual que en el arroz. Las capturas y el manifiesto están en `outputs/cropwat/caupi/`: `caupi_eto_verificacion.jpg`, `caupi_lluvia_verificacion.jpg`, `caupi_cwr.jpg` y `caupi_schedule_secano.jpg`. La comparación se hizo con `compare_results.py` en modo `rainfed`.

**Melón regado: el 29 de febrero en CROPWAT 8.0.** El ciclo va del 1 de diciembre de 2015 al 29 de marzo de 2016, son 120 días e incluye el 29 de febrero. Primero se probó `MELON16`, con 2016 como año de visualización y diciembre tomado de 2015. El archivo `.PMD` trae 7,13 mm/día el 29 de febrero, pero CROPWAT deja vacía esa celda: el programa usa un calendario fijo de 365 días y descarta el día bisiesto (`outputs/cropwat/melon/melon16_eto_29feb_vacio.jpg`). Por eso se usó `MELON15`: 2015 como año de visualización, diciembre de 2015 y enero y febrero de 2016. En marzo los valores se corren un día (`leap_shift` en el manifiesto). La celda del 1 de marzo guarda el 29 de febrero real, y la del 30 de marzo guarda el 29 de marzo real. Así, los 120 días de CROPWAT corresponden, uno a uno, a los 120 días reales del kernel. Fechas verificadas en pantalla: ET₀ de 4,5 mm/día el 1 de diciembre, 6,1 el 1 de enero, 7,1 en la celda del 1 de marzo (el 29 de febrero real) y 6,8 en la del 30 de marzo. La lluvia anual del archivo es de 1715,7 mm. Con siembra el 01/12, CROPWAT calcula la cosecha el 30/03. Esa fecha corresponde al 29 de marzo real, por el corrimiento. El suelo es loam, con 130 mm/m de agua disponible, 150 cm de profundidad máxima y 50 % de agotamiento inicial.

**Melón regado, resultado en CROPWAT 8.0.** **CWR** da un ETc estacional de **644,2 mm**, contra 615,129 mm del kernel: +29,1 mm y 4,51 % respecto de CROPWAT, dentro de la tolerancia de 5 %. La lluvia efectiva es de 23,7 mm y el requerimiento de riego de 620,4 mm. **Schedule** se corrió con *Irrigate at critical depletion* y *Refill soil to field capacity*, con eficiencia de 70 %. Da un **riego neto total de 668,7 mm**, contra 665,632 mm del kernel: +3,1 mm y 0,46 % respecto de CROPWAT, dentro de la tolerancia de 15 %. El riego bruto es de 955,3 mm, en 8 riegos. El primero cae el 1 de diciembre, porque el ciclo arranca con 51 % de agotamiento. El uso real es de 638,3 mm, el potencial de 638,7 mm y la reducción de rendimiento de 0,1 %. Las capturas y los manifiestos están en `outputs/cropwat/melon/`: `melon15_eto_verificacion.jpg`, `melon15_lluvia_verificacion.jpg`, `melon15_crop.jpg`, `melon_cwr.jpg` y `melon_schedule_riego.jpg`. El suelo se cargó desde `MELON16.SOI`, byte a byte idéntico a `MELON15.SOI`.

**Sorgo, resultado en CROPWAT 8.0.** Para `SORGO15` se usó 2015 como año de visualización, con octubre a diciembre de 2015 y enero y febrero de 2016. El ciclo no toca el 29 de febrero. Fechas verificadas en pantalla: ET₀ de 3,8 mm/día el 15 de octubre, 6,1 el 1 de enero y 6,9 el 16 de febrero; lluvia de 11,2 mm el 15 de octubre y 0,2 mm el 1 de enero. La lluvia anual del archivo es de 912,7 mm. Con siembra el 15/10 y etapas de 20/35/40/30 días, CROPWAT calcula la cosecha el 16/02, a los 125 días. El suelo es «Loam sorgo 200cm»: 130 mm/m, 200 cm de profundidad máxima, 60 mm/día de infiltración y 50 % de agotamiento inicial. **CWR** da un ETc de **506,8 mm**, contra 470,088 mm del kernel: +36,7 mm y 7,24 % respecto de CROPWAT, **fuera** de la tolerancia de 5 %. CROPWAT subió el Kc medio a **1,13**, frente al 1,05 de la entrada. El reporte muestra Kc de 1,13 en varias decenas de diciembre y enero. Con altura de 1,50 m, el ajuste climático pesa más que en caupí, cuyo Kc quedó en 1,10, y es la causa más probable de la diferencia. **Schedule**, con *No irrigation (rainfed)*, da un uso potencial de **502,5 mm** y un uso real de **324,7 mm**. El déficit es de **177,8 mm**, contra 149,137 mm del kernel: +28,7 mm y 16,12 % respecto de CROPWAT, **fuera** de la tolerancia de 15 %. La reducción de rendimiento es de 31,8 %. La lluvia total es de 312,1 mm, de la cual CROPWAT considera efectiva 207,6 mm, con 104,5 mm de pérdida. El kernel solo descuenta escorrentía por encima de 60 mm/día (D3), así que esta pérdida y el reparto decadal de la lluvia también separan a los modelos. Las capturas y el manifiesto están en `outputs/cropwat/sorgo/`: `sorgo15_eto_verificacion.jpg`, `sorgo15_lluvia_verificacion.jpg`, `sorgo15_crop.jpg`, `sorgo15_suelo.jpg`, `sorgo_cwr.jpg` y `sorgo_schedule_secano.jpg`.

**Sorgo, corrida sin ajuste climático del Kc.** CROPWAT ajusta el Kc medio y el final según la altura del cultivo. En el módulo **Crop**, ese campo dice *(optional)*. Se repitió la corrida con la altura en blanco y los demás datos sin cambios. Con eso, el Kc medio queda en **1,05**, igual al del kernel. **CWR** da un ETc de **469,7 mm**, contra 470,088 mm del kernel: −0,4 mm y 0,08 % respecto de CROPWAT, dentro de la tolerancia de 5 %. **Schedule**, con *No irrigation (rainfed)*, da un uso potencial de **465,9 mm** y un uso real de **319,7 mm**. El déficit es de **146,2 mm**, contra 149,137 mm del kernel: −2,9 mm y 2,01 % respecto de CROPWAT, dentro de la tolerancia de 15 %. La reducción de rendimiento es de 31,4 %. La diferencia de la primera corrida venía, entonces, del ajuste climático del Kc y no del balance del kernel. La tabla registra esta corrida, que usa los mismos Kc que el kernel. Las corridas de arroz, caupí y melón conservaron el ajuste: el Kc medio subió a 1,27 en arroz y a 1,10 en caupí. Aun así, quedaron dentro de la tolerancia. Evidencia en `outputs/cropwat/sorgo/`: `sorgo15_crop_sin_altura.jpg`, `sorgo_cwr_sin_ajuste_kc.jpg` y `sorgo_schedule_secano_sin_ajuste_kc.jpg`.

Para reproducir la tabla, cargar la temporada con `scripts.sensitivity.load_season(2015, et0["values"])` y usar `template_rotation` con las fechas `SOWING` de ese script. Ejecutar `simulate_rotation_detailed` con la ventana climática recortada a la siembra y cosecha del cultivo evaluado, el calendario completo de su rotación, suelo loam sin tope adicional de raíz e `initial_soil_water_fraction=0.5`. Leer ETc y déficit de la fila del cultivo en `per_crop`; para melón, leer `irrigation_requirement_mm` de la corrida manejada, que repone hasta capacidad de campo al alcanzar el umbral de agua fácilmente aprovechable.

Diferencias esperadas, que hay que anotar antes de llamar error a una discrepancia:

- **ET₀.** En CROPWAT, seleccionar **File → New → Climate/ETo → Daily measured ETo**. Pegar la serie diaria de ET₀ revisada y guardarla como `.PMD`. Este modo recibe la ET₀ como entrada directa, aunque la del piloto provenga de un cálculo previo.
- **Lluvia.** Cargar los datos diarios en el módulo **Rain** y guardarlos como `.CRD`. Según la ayuda de CROPWAT 8.0, **Schedule** suma la lluvia por decena y reparte cada total por igual entre los días tercero y séptimo, incluso con entradas diarias. También calcula escorrentía según la infiltración máxima del suelo. El kernel conserva las fechas de lluvia de POWER y aplica D3 (RO = 0,3·max(0, P − 60)). Documentar esta diferencia al interpretar déficit y riego. Para aislar su efecto, repetir el kernel con la distribución de lluvia de CROPWAT y registrar los supuestos de escorrentía de cada corrida.
- **Etapas y Kc.** Usar las mismas duraciones y Kc de `crops.yaml`. CROPWAT ajusta Kc mid y end por clima si se le pide; desactivarlo o aplicar el mismo ajuste.
- **Zr.** El kernel usa Zr constante por ciclo (D4). CROPWAT hace crecer la raíz; fijar Zr inicial = Zr máximo.
- **Barbecho.** El kernel simula el barbecho entre cultivos (D5). CROPWAT corre cada cultivo aislado. Comparar por cultivo, no por rotación.

Criterio provisional: diferencias de ETc ≤5 % y de déficit ≤15 % se consideran consistentes. Calcular la diferencia relativa contra CROPWAT cuando su valor sea distinto de cero y reportar también la diferencia en mm. Para secano, comparar ETc − ET real. Para melón, comparar el riego neto con la misma regla de reposición y registrar por separado las diferencias de riego. El caso del melón incluye el 29 de febrero de 2016; comprobar la duración de 120 días en el reporte de CROPWAT antes de interpretar la diferencia.

En **Schedule**, usar **No irrigation (rainfed)** para los cultivos de secano. Para el melón, elegir **Irrigate at critical depletion** y **Refill soil to field capacity** y exportar el riego neto. Guardar **Daily soil moisture balance** con la ET real y los campos de balance. La columna **Deficit** de CROPWAT expresa agotamiento del suelo respecto de capacidad de campo. El déficit del kernel se calcula como ETc − ET real.

## Validación en finca

Pendiente de observaciones de una parcela. El [piloto de Liberia](guanacaste-pilot.md) usa un perfil estimado a partir de SoilGrids y calendarios provisionales.

- **Parcela y suelo.** Registrar coordenadas, profundidad efectiva y capacidad de campo y punto de marchitez medidos por estrato. Medir la humedad al inicio de la corrida para inicializar el balance.
- **Manejo y clima.** Registrar cultivo y fechas efectivas de siembra y cosecha, lluvia local con fecha y riegos aplicados en mm por fecha. Identificar períodos sin medición.
- **Observaciones para el contraste.** Registrar humedad volumétrica por fecha y profundidad durante el ciclo. Integrar las observaciones en la misma zona radicular del modelo y reportar sesgo y error absoluto en mm para las fechas comparables. Guardar los insumos, la versión del kernel y la cobertura de observaciones.
