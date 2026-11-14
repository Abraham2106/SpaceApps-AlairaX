# Método científico y estado de la implementación

Documento de trabajo del 14 de noviembre de 2026, hora de Costa Rica. Describe el código y los artefactos locales disponibles en esta fecha. La comparación agrícola real todavía depende del kernel científico, los parámetros y el calendario revisados por el equipo.

## Pregunta y alcance

NandaView compara `rice_melon`, `rice_legume` y `rice_sorghum` bajo los mismos escenarios de clima, suelo y manejo. La línea base es `rice_melon`. La pregunta es cuánto cambian la demanda hídrica, el déficit hídrico modelado y los días de estrés entre alternativas cuando se mantienen esas condiciones comunes.

La implementación de Abe cubre ingesta y procedencia, contratos, features estacionales, selección de años análogos, ejecución del callback del kernel y comparación pareada. No incluye todavía una implementación numérica revisada de ET0 ni del balance FAO-56. Las respuestas `frontend/public/data/compare-*.json` son fixtures sintéticos explícitos: no son resultados agronómicos.

## Datos y cobertura comprobada

El punto `10.55, -85.50` es una ubicación provisional de trabajo. La descarga no demuestra que corresponda a una finca ni que el suelo del píxel represente una parcela. La API diaria POWER entrega datos solares y meteorológicos en la resolución espacial de sus fuentes; el proyecto no los presenta como mediciones de estación en la finca. Se solicita comunidad `AG`, unidades métricas y hora solar local `LST`, que debe distinguirse de la hora civil de Costa Rica. Véase [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/).

Variables normalizadas:

| POWER | Campo interno | Unidad |
|---|---|---|
| `PRECTOTCORR` | `precipitation_mm` | mm/día |
| `T2M_MIN`, `T2M_MAX` | `tmin_c`, `tmax_c` | °C |
| `RH2M` | `relative_humidity_pct` | % |
| `WS2M` | `wind_speed_2m_m_s` | m/s a 2 m |
| `ALLSKY_SFC_SW_DWN` | `solar_radiation_mj_m2_day` | MJ/m²/día |

El snapshot local incluye 46 intervalos de `1981-01-01` a `2026-11-14`, con **16.754 días únicos**. El pequeño archivo de prueba de enero de 2024 solapa el archivo anual; no se suma otra vez. Hay 1.117 flags QC: 1.116 por valores ausentes y uno por lluvia extrema. Un flag es una combinación de fecha, variable y motivo; no equivale necesariamente a un día distinto.

**42 años, 1984–2025, tienen las seis variables POWER completas. Esto no significa que haya 42 años de features ni simulaciones.** El proveedor omitió radiación en 1981–1983. En 2026 hay huecos y el año es parcial. ET0 permanece `null` en todos los datos de ingesta porque falta el artefacto revisado de Justin.

La ejecución real de `scripts/build_analogs.py`, con ventana `04-01`–`10-31`, ONI `ASO` y corte `2026-11-14`, produjo **cero años de features y 46 exclusiones por ET0 pendiente**. Los cuatro escenarios están `unavailable` en `datasets/processed/analogs/analogos.json`. Es un estado explícito de insumos pendientes; no se reemplaza ET0 por cero ni se publican vecinos inventados. Los datos y contadores se pueden auditar en los JSON locales de `datasets/processed/climate/` y `datasets/processed/analogs/`.

## Procedencia y control de calidad

`backend/app/infrastructure/` conserva cuerpos originales por SHA-256, índice por URL y metadatos de descarga UTC. Cuando existen, se registran ETag y Last-Modified. El modo offline verifica la integridad de la caché; una descarga nueva conserva snapshots anteriores. Los productos de análogos añaden hashes de los archivos exactos de entrada. Reprocesar el mismo snapshot permite reproducir sus datos; refrescar una fuente puede cambiar las revisiones históricas.

La normalización conserva todas las fechas solicitadas. Fill values, números no finitos, humedad fuera de rango, valores negativos físicamente inválidos y temperaturas invertidas se convierten a `null`, con un motivo QC. No se convierten faltantes en días secos. Se valida la unidad informada; la radiación en kWh/m²/día se multiplica por 3,6 únicamente si esa unidad está declarada. Unidades desconocidas detienen la ingesta.

La lluvia superior a 500 mm/día se marca para revisión y se preserva. Es un umbral operativo configurable, no una prueba de que la observación sea imposible. No hay recorte p99,9 ni corrección automática de lluvia. El supuesto sesgo de POWER citado en el WBS debe contrastarse contra una referencia local y períodos compatibles antes de calibrar. El código mantiene `bias_correction=null`.

## ONI, RONI y fecha de información

Se descargan por separado [ONI ASCII](https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt) y [RONI ASCII](https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt). El parser usa `ANOM`, conserva año y trimestre, y no intercambia ONI y RONI. La feature actual usa **ONI** por decisión del método del MVP. La documentación actual de [NOAA CPC ONI](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/) indica que RONI se usa para el monitoreo y pronóstico oficial de ENOS; el equipo debe revisar y justificar la elección exploratoria de ONI. No se atribuye clasificación oficial a los escenarios del producto.

Las ventanas trimestrales se identifican explícitamente: por ejemplo, ASO cubre agosto–octubre. OND de 2026 no está completo al corte del 14 de noviembre y el pipeline lo rechaza como información futura. El cierre del trimestre tampoco prueba que su valor se hubiera publicado en ese momento. La [documentación RONI de NOAA](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/) advierte además que los valores recientes pueden revisarse. Los archivos descargados hoy son retrospectivos, **no archivos de publicación histórica**. Preservar su hash documenta lo usado, pero no convierte un backtest en evaluación válida de una decisión tomada con información disponible entonces.

## Features y ventanas equivalentes

Para cada ventana completa se construye:

`X = [lluvia acumulada, ET0 acumulada, Tmax media, días de calor, ONI]`.

La unidad es mm para los acumulados hídricos y °C para Tmax y ONI. Los días de calor cuentan Tmax ≥ umbral explícito; el valor predeterminado de 35 °C es un descriptor climático configurable, sin validación como umbral de daño de los cultivos.

Cada fecha debe aparecer exactamente una vez y cada feature debe ser finita. No se imputa ni extrapola una temporada incompleta. ET0 solo se incorpora mediante un archivo externo con unidades, zona, versión, fuentes y declaración de revisión. Que el archivo diga `reviewed=true` verifica su contrato, sin certificar por sí mismo la revisión científica.

El seguimiento 2026 requiere una ventana ya completa y la misma combinación de meses y días en todos los candidatos históricos. Por ejemplo, una consulta abril–octubre no se compara con totales anuales. Se rechazan ventanas que crucen año y extremos `02-29` en el pipeline actual. Usar el clima completo de una temporada es exploración retrospectiva; no demuestra capacidad de pronóstico antes de esa temporada.

## Selección KNN

`find_analogs()` ajusta media y desviación poblacional únicamente con candidatos elegibles anteriores al año objetivo. Excluye el propio año, años posteriores y todo 2026. Una feature de varianza cero usa escala 1 y queda identificada en metadatos. Se exige coincidencia de ventana, umbral de calor, trimestre ONI y estado mock.

La distancia es euclídea estandarizada y ponderada:

`d(x, q) = sqrt(sum_j(w_j * ((x_j - q_j) / scale_j)^2) / sum_j(w_j))`.

Los pesos predeterminados son iguales, se publican y deben ser finitos y no negativos, con suma positiva. Se devuelven los años del escalado, medias, escalas, contribuciones de features, distancias y vecinos. Los empates se resuelven por año ascendente. La distancia no es una probabilidad.

Los escenarios `strong_el_nino`, `neutral` y `la_nina` agrupan por ONI trimestral ≥1,5; entre −0,5 y 0,5 sin incluir extremos; y ≤−0,5 °C, respectivamente. Son reglas exploratorias de producto. Cada consulta usa el centroide histórico del grupo, escala con la población histórica y selecciona vecinos dentro de ese grupo. La etiqueta de referencia 2026 del centroide permite considerar el histórico hasta 2025; no representa clima observado de 2026. `like_2026` usa una feature de seguimiento explícita y mantiene 2026 fuera de los candidatos.

La función KNN base usa k=5 por defecto. El CLI permite fijarlo por escenario y configura explícitamente k=3 para Niño fuerte; los otros escenarios conservan k=5. La decisión se registra en metadatos, junto con el tamaño solicitado y efectivo. Si faltan años elegibles se declara el escenario no disponible, sin rellenarlo con otra fase ni reducir k automáticamente. Se publica sensibilidad para k−2, k y k+2, acotados al conjunto, mediante conjuntos de vecinos y Jaccard frente al k elegido. Esto informa estabilidad de selección, sin demostrar precisión predictiva ni estabilidad de las métricas agrícolas.

## Kernel y comparación pareada

El contrato invoca `simulate_rotation(climate=..., soil=..., rotation=..., assumptions=...)`. La metodología física de referencia que Justin debe implementar y revisar es [FAO Irrigation and Drainage Paper 56, Allen et al. (1998)](https://www.fao.org/4/x0490e/x0490e00.htm), que trata ET0, coeficientes de cultivo y condiciones de estrés. Citar FAO-56 no valida un código ni resuelve los supuestos particulares del arroz inundado.

Para cada año análogo se ejecutan las tres rotaciones con el mismo clima, suelo y manejo. `environment_fingerprint()` registra esos insumos con SHA-256, excluyendo el calendario de la rotación. La orquestación revalida el lote y evita que el callback modifique las entradas originales. Se exige la misma versión del kernel en todos los años y rotaciones; los resultados diarios reales deben cubrir exactamente las fechas de entrada. El número de días de estrés no puede exceder la duración del clima.

El comparador requiere una ejecución por rotación y año. Primero calcula, para cada métrica y año:

`delta_año = métrica(alternativa, año) − métrica(rice_melon, año)`.

Después resume esos deltas pareados. No resta dos medianas ya resumidas. Un delta negativo indica menor valor modelado bajo esos supuestos, sin demostrar ahorro real ni efecto causal. Se comparan los mismos años; ninguna alternativa elige su clima más favorable.

## Cuantiles e interpretación

Se publican p10, p50 y p90 por métrica y para el delta pareado. El cálculo ordena las n ejecuciones e interpola linealmente en la posición `(n−1) × p`. Si falta una métrica en cualquier año, el resumen afectado queda `null`, `n=0` y una advertencia: no se elimina silenciosamente un año y cambia la población comparada. `n=0` aquí indica que no se publica un resumen completo, no que no exista ninguna ejecución válida.

La banda p10–p90 refleja variación empírica entre análogos seleccionados. Con k=3 para Niño fuerte y k=5 para los demás, según [la decisión explícita](decisions.md), describe muestras pequeñas y condicionadas a esa selección. El resultado con menos de cinco análogos añade un aviso de evidencia limitada. No es intervalo de confianza, probabilidad de éxito, distribución climática completa ni incertidumbre total del sistema. No incorpora automáticamente incertidumbre de Kc, suelo, calendario, sesgo de fuente o estructura del modelo.

## Límites y revisión pendiente

Los parámetros agronómicos, las fechas de siembra y cosecha, el perfil de suelo y el manejo siguen pendientes de revisión. [ISRIC describe SoilGrids como predicciones espaciales de propiedades del suelo](https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs.html); no debe presentarse como una medición local ni suponerse que textura por sí sola completa el perfil hídrico del contrato.

Los tests actuales verifican controles de integración, unidades, faltantes, fechas, separación temporal, mocks y aritmética de comparación. Sus callbacks sintéticos no constituyen validación de ET0, balance de masa, respuesta del arroz ni validación de campo. No se infieren rendimiento, rentabilidad, mejora de carbono/nitrógeno ni una rotación ganadora. Las pruebas retrospectivas científicas, referencias manuales y análisis de sensibilidad agronómica quedan documentados como pendientes en [method-review.md](method-review.md).

La presentación pública debe mostrar: **«Estimaciones de modelo. Requieren validación local.»** Mientras los JSON sean sintéticos también debe mostrar el aviso mock.

## Reproducción y uso de IA

Comandos y formatos detallados: [ingesta y caché](data-ingestion.md), [features y KNN](analog-method.md) y [contrato y exportación](contract-handoff.md). Las salidas reales de análogos están separadas de los fixtures públicos. `scripts.export_contracts` regenera mocks y sobrescribe los archivos de ejemplo; no debe usarse para publicar resultados científicos ya calculados.

En la parte de **Abe**, Codex y sus subagentes asistieron en contratos, ingesta, features, KNN, comparador, fixtures, documentación y pruebas. Esta declaración no atribuye herramientas ni trabajo de IA a los otros integrantes. El equipo debe completar por separado su declaración final por persona y revisar los resultados bajo responsabilidad humana.
