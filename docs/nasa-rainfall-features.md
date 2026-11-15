# Variables NASA para el modelo de lluvia

El objetivo es estimar el acumulado de precipitación de los siete días siguientes en el punto 10,55° N, 85,50° O de Guanacaste. Se revisaron productos y unidades en las fuentes primarias de NASA el 15 de noviembre de 2026.

| Producto | Información aprovechable | Disponibilidad e implicación para el experimento |
| --- | --- | --- |
| POWER meteorología | Lluvia previa, temperatura, humedad, presión, punto de rocío, agua precipitable y componentes del viento | NASA indica unos dos días de latencia para GEOS-IT y revisiones posteriores del histórico. El experimento usa predictores hasta fecha de corte menos dos días. La latencia real debe comprobarse al emitir cada pronóstico. [Fuente](https://power.larc.nasa.gov/docs/methodology/data/sources_meteorology/) |
| POWER radiación | Energía solar y señal indirecta de nubosidad | La documentación describe flujos de baja latencia de varios días, aproximadamente una semana. Las variantes nuevas usan las variables meteorológicas con su propio desfase. La disponibilidad de radiación exige otro calendario de publicación. [Fuente](https://power.larc.nasa.gov/docs/methodology/data/sources_fluxes/) |
| IMERG | Lluvia satelital reciente con detalle temporal de media hora | Early ofrece latencia aproximada de cuatro horas, Late de doce a catorce horas y Final de unos tres meses y medio. Para un experimento operativo se debe guardar el producto y versión realmente disponible en la fecha de emisión. La incorporación al entrenamiento queda pendiente. [Fuente](https://gpm.nasa.gov/resources/faq/what-determines-latency-imerg) |
| GEOS-FP | Análisis y pronósticos meteorológicos de diez días | Permite incorporar el estado atmosférico previsto, guardando cada inicialización y plazo. NASA describe estos pronósticos como experimentales de investigación. La descarga de archivos de pronóstico emitidos y su evaluación quedan pendientes. [Fuente](https://gmao.gsfc.nasa.gov/gmao-products/geos-near-real-time-data-products/) |

La API diaria devuelve datos UTC o LST y conserva la resolución de la fuente. Se mantiene LST para coincidir con las series del proyecto. Las variables corresponden a celdas de productos atmosféricos. El contraste con una estación local se reporta por separado. [API diaria de POWER](https://power.larc.nasa.gov/docs/services/api/temporal/daily/)

## Descarga comprobada

Se consultaron 22 bloques anuales entre 2005 y el 14 de noviembre de 2026, con dos peticiones simultáneas y caché por contenido. El archivo `datasets/processed/climate/ml-atmosphere-guanacaste.json` reúne 7.988 fechas y la procedencia de cada respuesta. Las unidades se validan antes de guardar.

| Variable | Unidad devuelta | Uso de ingeniería de variables |
| --- | --- | --- |
| PS | kPa | Presión, media de siete días y variación en tres días |
| T2MDEW | °C | Punto de rocío y cambios de humedad |
| QV2M | g/kg | Humedad específica y persistencia |
| PW | cm | Columna de agua precipitable y su variación |
| U2M | m/s | Componente este del viento y su tendencia |
| V2M | m/s | Componente norte del viento y su tendencia |

PW tiene 76 fechas sin valor, y cada una de las otras cinco variables tiene dos. Los rellenos de NASA se convierten en nulos, que se conservan durante el entrenamiento. La lluvia desconocida invalida los acumulados de su ventana. La temperatura, humedad y viento originales se complementan con medias recientes. La fecha se representa mediante seno y coseno anual y semianual. Se incluyen lluvia acumulada, máximo, variabilidad, cantidad de días con al menos 1 mm y duración del período seco hasta treinta días.

## Experimento

`scripts.improve_rainfall` compara seis variantes con datos completos desde 1984 o desde 2005, ingeniería de variables, variables atmosféricas NASA y objetivos de error cuadrático o absoluto. Una variante usa la mediana mensual de entrenamiento durante diciembre–abril. Su política estacional se evalúa dentro del desarrollo.

La selección usa validaciones exteriores 2014–2017 y 2018–2022. Cada una elige las rondas mediante los dos años previos a su corte y luego reajusta con el histórico anterior completo. Se eliminan ejemplos cuya etiqueta de siete días cruce los límites. El criterio fijado es el menor MAE combinado de ambas validaciones exteriores. El conjunto desde 2023 fue inspeccionado previamente y se reporta como diagnóstico de desarrollo. El período futuro y el modelo v1 congelados mantienen su registro original. El modelo nuevo se guarda en otro directorio.

La ejecución usa CPU, un máximo de 800 rondas, cuarenta rondas de paciencia y treinta segundos por ajuste. Cada variante conserva sus resultados. El modelo elegido exporta los pesos, esquema de variables, medianas mensuales, parámetros, curvas e identidad de las fuentes. Se comprueba la recarga. La predicción desde un snapshot se realiza con `scripts.predict_rainfall`.

Estos resultados son retrospectivos con un desfase explícito. Confirmar la calidad de un pronóstico emitido exige registrar el instante de publicación de los datos y guardar la predicción antes de su período objetivo.

## Resultados ejecutados

Se ejecutaron los experimentos en CPU local con XGBoost 3.4.1. Los pesos y la inferencia se verificaron por recarga.

| Variante de desarrollo POWER | MAE combinado en mm |
| --- | --- |
| Predictores básicos, histórico desde 1984 | 25,58 |
| Ingeniería de variables, desde 1984, error absoluto | 24,56 |
| Ingeniería de variables, desde 2005 | 24,99 |
| Atmósfera NASA, desde 2005, error absoluto | 24,72 |
| Atmósfera NASA, desde 2005, error cuadrático | 26,42 |
| Atmósfera y mediana mensual en época seca | 24,64 |

La variante elegida tiene 37 variables y 283 rondas. Reduce un 3,98 % el MAE del modelo básico en la validación exterior. El diagnóstico ya inspeccionado de 2023–2026 da un MAE de 32,06 mm, RMSE de 97,39 mm y 47,58 % de casos dentro de ±10 mm, frente a una referencia mensual de 34,03 mm de MAE. La versión anterior había dado 33,40 mm, RMSE de 94,94 mm y 43,09 % dentro de ±10 mm. Las diferencias entre versiones también incluyen el período de entrenamiento y la latencia de los predictores.

El archivo `outputs/molab/nasa-features-v2/report.json` conserva la tabla completa y los ajustes. La consulta atmosférica se evaluó por ablación y quedó como dato disponible para experimentos posteriores. El modelo seleccionado usa las variables derivadas de las series que ya existían.

### Contraste local

El modelo POWER nuevo presenta 54,39 mm de MAE en las 19 semanas observadas sin solapamiento. Una corrección de residuos elegida con 2018–2022 reduce ese valor a 46,36 mm y el sesgo de −42,29 a −15,48 mm. La versión anterior tenía 44,35 mm de MAE y sesgo de −28,27 mm en esas mismas semanas. El error medio local no mejora respecto de esa versión.

Se entrenaron además dos variantes directamente con lluvia observada de Liberia como objetivo. Las etiquetas son semanas completas de GHCN desde 1984. La selección usa 254 semanas en los bloques de desarrollo 2014–2017 y 2018–2022 y elige error cuadrático. En el diagnóstico de 97 ventanas desde 2023, su MAE es 50,55 mm frente a 56,22 mm de la climatología mensual calculada con registros de la estación previos a 2023. En las 19 semanas sin solapamiento, el MAE es 48,07 frente a 49,69 mm y 31,58 % de errores quedan dentro de ±10 mm. Es una mejora pequeña frente a su referencia local con evidencia limitada. Se conserva en `outputs/molab/nasa-station-v2/`.

La mejora del modelo de cuadrícula y el desempeño local se registran en [la comparación v2](../datasets/processed/validation/rainfall-v2-comparison.json). El modelo continúa como experimento y la validación prospectiva del protocolo original sigue pendiente.

## Reproducción e inferencia

```powershell
python -m scripts.ingest_ml_nasa
uv run --with xgboost==3.4.1 --with pandas --with numpy python -m scripts.improve_rainfall --output outputs/molab/nasa-features-v2-new-run
uv run --with xgboost==3.4.1 --with pandas --with numpy python -m scripts.predict_rainfall --model-dir outputs/molab/nasa-features-v2 --climate outputs/molab/import/guanacaste-features.json --atmosphere datasets/processed/climate/ml-atmosphere-guanacaste.json --origin 2026-11-07
```

La última orden comprueba inferencia retrospectiva sobre datos existentes. Para el modelo supervisado de la estación se usa `--model-dir outputs/molab/nasa-station-v2`. El campo `target` identifica el objetivo de cada modelo.
