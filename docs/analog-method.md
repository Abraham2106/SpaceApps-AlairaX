# Features y años análogos (Abe, WBS 4.2–4.3)

`backend.app.intelligence.features.build_season_features` recibe días normalizados
(`ClimateDay` o diccionarios), año, inicio, fin y un ONI observado de trimestre
explícito. Genera lluvia acumulada [mm], ET0 acumulada [mm], Tmax media [°C],
días con Tmax ≥ umbral y ONI [°C]. El umbral por defecto de 35 °C es configurable
y sirve como descriptor climático; no demuestra daño agronómico. No calcula
ET0: requiere la implementación y revisión de Justin.

Cada fecha de la ventana debe aparecer exactamente una vez. Se rechazan valores
faltantes, centinelas, infinitos, NaN y lluvia/ET0 negativas. Los días fuera de la
ventana se ignoran, de modo que las consultas parciales de 2026 se comparan
contra exactamente los mismos meses/días históricos. No se extrapolan totales
parciales. El llamador debe seleccionar un trimestre ONI ya publicado para el
corte de información usado; el módulo no convierte ONI futuro en dato conocido.

## KNN reproducible

`find_analogs(candidates, target, k=5, weights=None)` usa distancia euclídea
ponderada después de escalar con media y desviación poblacional de candidatos
elegibles. Nunca ajusta el escalado con el objetivo, con su propio año, con años
posteriores ni con 2026. El resultado contiene años de ajuste, medias, escalas,
pesos, distancias y contribuciones de cada variable a la distancia al cuadrado.
Si una variable tiene varianza cero, su escala se fija en 1 y se declara. No se
mezclan ventanas, umbrales, trimestres ONI ni datos mock y reales.

Para pesos `w`, la distancia es
`sqrt(sum(w[j] * ((x[j]-target[j])/scale[j])**2) / sum(w))`.
Todos los pesos son 1 por defecto. Los empates se resuelven por año ascendente.
Se informa sensibilidad de vecinos para k−2, k y k+2, acotados al tamaño del
conjunto, con Jaccard frente a la selección solicitada. Las distancias expresan
similitud, sin interpretarse como probabilidades.

## Cuatro escenarios

`select_scenario` acepta:

- `like_2026`: requiere un `SeasonFeatures` de 2026 explícito y la misma ventana
  completa en el histórico. 2026 permanece fuera de los análogos. Los fixtures
  sintéticos son admitidos exclusivamente con `mock=True` en todas sus filas.
- `strong_el_nino`: filtra ONI trimestral ≥ 1,5 °C.
- `neutral`: filtra −0,5 < ONI trimestral < 0,5 °C.
- `la_nina`: filtra ONI trimestral ≤ −0,5 °C.

Los tres escenarios de fase construyen un centroide de features históricas del
grupo, escalan con la población histórica completa y seleccionan vecinos dentro
del grupo. El centroide es una consulta sintética explícita: su fecha de referencia
2026 solo permite usar todo el histórico hasta 2025, sin afirmar observaciones
de 2026. Las filas completas y observadas de los vecinos permanecen separadas.
Los umbrales son reglas exploratorias del producto para un trimestre; no
constituyen la clasificación de un evento sostenido de NOAA. No se rellenan
grupos con otra fase cuando hay menos de k años: se devuelve error explicativo.

El diseño responde a comparación retrospectiva. Las features de lluvia y ET0
de una temporada completa describen esa temporada; para pronosticar antes de
que termine haría falta otro protocolo. No infiere causalidad ni una rotación
ganadora, y no sustituye el balance FAO-56 ni la validación local.

## Uso

Desde la raíz del repo:

```powershell
python -m unittest backend.tests.test_analogs -v
```

La integración debe aportar clima con ET0 revisada, ONI con metadatos de fecha y
la misma ventana para cada año. POWER por sí solo todavía no cubre ET0. No se
generan resultados observados con datos faltantes o parámetros inventados.

## Pipeline de archivos normalizados

`scripts/build_analogs.py` une los JSON anuales generados por `ingest_climate.py`.
Requiere `days`, `zona`, `_mock`, `source_refs` y unidades normalizadas de lluvia
`mm/day` y temperatura `C`. Los días solapados idénticos se deduplican; cualquier
conflicto provoca error. Se rechazan mezclas de zonas o de datos mock y reales.
El archivo NOAA debe declarar `index: "oni"`; RONI se conserva por separado.

ET0 se importa exclusivamente desde un archivo externo de Justin con esta
estructura (el ejemplo usa cero solo como valor ilustrativo del formato):

```json
{
  "_mock": false,
  "zona": {"id": "MISMO_ID", "name": "MISMO_NOMBRE", "latitude": 10.55, "longitude": -85.5, "validated": false},
  "reviewed": true,
  "reviewed_by": "Justin",
  "model_version": "VERSION_REVISADA_DEL_KERNEL",
  "units": "mm/day",
  "source_refs": ["REFERENCIA_AL_ARTEFACTO_REVISADO"],
  "values": {"2015-04-01": 0.0}
}
```

La zona debe coincidir exactamente con la ingesta. `reviewed` declara que Justin
revisó ese artefacto; el pipeline comprueba el contrato y la procedencia, sin
certificar por sí mismo la revisión científica. No se admiten ET0 no nulas dentro
del archivo POWER para evitar saltarse esta entrega. Sin `--et0` se exportan
estados `unavailable` y razones por año: no se sustituyen nulos por ceros.

Ejemplo desde la raíz, con una ventana parcial elegida explícitamente:

```powershell
$climateFiles = (Get-ChildItem datasets/processed/climate/power_*.json).FullName
python scripts/build_analogs.py --climate $climateFiles --oni datasets/processed/climate/oni.json --et0 datasets/processed/reviewed-et0.json --start-mmdd 04-01 --end-mmdd 10-31 --oni-season ASO --as-of 2026-11-14 --k 5
```

`features.json` contiene features de años completos dentro de esa ventana y
`excluded_years` con la causa de cada exclusión. `analogos.json` añade los cuatro
escenarios con `status: available | unavailable`, vecinos, distancias, escalado y
sensibilidad. Nunca reduce k de forma implícita. Ambos conservan metadatos, hashes
SHA-256 de entradas y fuentes. Los productos se guardan por defecto en
`datasets/processed/analogs/`.

`--heat-threshold-c` permite fijar el umbral climático explícitamente (35 °C por
defecto); queda registrado en ambos productos. No es un umbral de daño validado.

El final de ventana y del trimestre ONI deben ser anteriores o iguales a `as_of`.
Por ejemplo, OND de 2026 termina en diciembre y no puede usarse como seguimiento
al 14 de noviembre. El final del trimestre no prueba su fecha de publicación:
las fuentes actuales son retrospectivas y sus revisiones no validan un backtest
en tiempo real. Ventanas que cruzan año y fechas MM-DD=02-29 se rechazan para
mantener este MVP reproducible entre años. Las fechas faltantes, ET0 sin revisar,
POWER sin radiación y ONI ausente mantienen años fuera del conjunto elegible.

Pruebas de integración:

```powershell
python -m unittest backend.tests.test_analog_pipeline -v
```

## Estado con la descarga real del 14 de noviembre de 2026

La infraestructura descargó 46 intervalos anuales/por año hasta el 14 de noviembre
de 2026, con 16.754 días. Los 42 años 1984–2025 tienen las seis variables POWER
completas; 1981–1983 carecen de radiación y 2026 tiene huecos y ventana parcial.
Esto describe cobertura de variables, sin certificar calidad agronómica ni ET0.

La ejecución real de este pipeline con `04-01`–`10-31`, ONI `ASO`, corte
`2026-11-14` y sin archivo de ET0 revisada generó **cero años elegibles y 46
exclusiones**. Los cuatro escenarios quedaron `unavailable`. Las salidas están
en `datasets/processed/analogs/`; después de la entrega de ET0 se deben regenerar
y revisar nuevas exclusiones. La prueba parcial de cinco días de enero de 2024
se deduplicó correctamente al unirla con su archivo anual completo.

## Decisión explícita de k por escenario (14 de noviembre)

En los archivos NOAA descargados, ONI `ASO >= 1.5 °C` solo tiene tres años
históricos con las seis entradas POWER completas en la ventana abril–octubre:
**1997 (2,04 °C), 2015 (2,02 °C) y 2023 (1,50 °C)**. No alcanza para k=5.
El usuario delegó la elección técnica y se decidió usar **k=3 exclusivamente
para `strong_el_nino`**, conservando **k=5** en los otros tres escenarios.

Los CLI `build_analogs.py` e `inspect_scenarios.py` declaran esa decisión mediante
`--strong-el-nino-k 3` por defecto. Se puede fijar otro valor explícitamente;
`--strong-el-nino-k 5` vuelve a exigir cinco años. No hay reducción dinámica ni
cambio de umbral para rellenar vecinos. La función genérica `select_scenario`
mantiene k=5; `build_pipeline(..., strong_el_nino_k=None)` y el inspector genérico
usan el mismo k general para todos hasta recibir un override explícito.

Los productos incluyen `k_by_scenario`, `requested_k` y `effective_k`; este último
es `null` si no se ejecutó KNN. Un conjunto de tres años debe mostrar una
advertencia de muestra pequeña y cuantiles descriptivos, sin interpretarlos como
intervalos de confianza calibrados. Esta decisión no elimina el bloqueo de ET0.

## Inspección de cobertura antes de ET0

```powershell
$climateFiles = (Get-ChildItem datasets/processed/climate/power_*.json).FullName
python scripts/inspect_scenarios.py --climate $climateFiles --oni datasets/processed/climate/oni.json --start-mmdd 04-01 --end-mmdd 10-31 --oni-season ASO --as-of 2026-11-14 --k 5 --strong-el-nino-k 3
```

`datasets/processed/readiness/scenarios.json` informa **cobertura climática y
ONI antes de ET0**, sin ejecutar KNN ni certificar suelo, cultivos o simulador.
Reutiliza el mismo lector, unión de fechas, comprobación de zonas y corte del
pipeline. Exige las seis unidades POWER correctas y cada día completo. Conserva
por año las fechas ausentes, conteos de campos inválidos y motivos de exclusión.

Resultado real para abril–octubre/ASO al corte indicado:

| Escenario | Años históricos con clima y ONI completos antes de ET0 | k decidido |
|---|---:|---:|
| Niño fuerte | 3 | 3 |
| Neutro | 21 | 5 |
| Niña | 10 | 5 |
| Como 2026 | 42 candidatos históricos; seguimiento incompleto | 5 |

El seguimiento de 2026 tiene un día sin radiación dentro de abril–octubre; así
que `like_2026` continúa sin ventana climática completa. Los otros escenarios
tienen suficiente cobertura para su k declarado, pero todos requieren ET0
revisada. Las reglas de fase omiten deliberadamente el intervalo de Niño débil
`0.5 <= ONI < 1.5` en los escenarios de fase; esos años pueden ser candidatos
históricos de `like_2026` cuando su seguimiento esté disponible.

Se corrigieron dos errores en la revisión: `select_scenario` ahora rechaza k no
positivo antes de acceder a un grupo vacío, y los centinelas NOAA (`-999`,
`-99.99`, `-99.9`) no pueden pasar como observaciones de Niña en features.
La regresión incluye esos casos además de los conteos y el override explícito.
