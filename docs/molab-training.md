# Entrenamiento de NandaView en Molab

## Corrida completada el 15 de noviembre de 2026

Se entrenó XGBoost 3.4.1 para lluvia acumulada de los siguientes siete días en [este notebook de Molab](https://molab.marimo.io/notebooks/nb_d2o6w2EHJaKtuyCceYmxF8), con 4 CPU y 32 GiB. Se fijaron 500 rondas máximas, 120 segundos y parada tras 40 rondas sin mejora del MAE de validación. El entrenamiento registró 110 rondas y seleccionó la 70. Los cortes fueron 2018 para validación y 2023 para prueba, con 13.507, 1.819 y 1.404 ejemplos respectivamente y 14 filas excluidas por cruzar los cortes.

| Métrica de prueba | XGBoost | Mediana mensual de entrenamiento |
| --- | --- | --- |
| MAE en mm | 33,4043 | 34,2250 |
| RMSE en mm | 94,9375 | 101,8815 |
| Casos dentro de ±10 mm | 43,09 % | 52,78 % |

El MAE mejora un 2,40 %. La referencia mensual tiene más casos dentro de ±10 mm. La prueba final ya se utilizó en el smoke anterior y en esta evaluación, por lo que futuras iteraciones requieren un periodo nuevo reservado para sostener una evaluación independiente. Los datos corresponden a la lluvia de la celda POWER y sus ventanas semanales se superponen.

Se descargaron y comprobaron los pesos `model.ubj`, el reporte, la historia y las 1.404 predicciones. Se recalcularon localmente MAE, RMSE y tolerancia desde el CSV. La recarga del modelo quedó verificada durante la ejecución de Molab. El paquete local es `outputs/molab/cloud-rainfall-2026-11-15.zip` e incluye el entrenador, notebook y manifiesto SHA-256. El modelo queda como resultado experimental con integración en la aplicación pendiente.

El notebook tiene dos objetivos. **Lluvia** estima el acumulado de los siete días siguientes para el punto POWER de Guanacaste. Los predictores son variables climáticas disponibles al cierre del día de corte. **Surrogate** estima el déficit hídrico que produce FAO-56 al simular un escenario completo. El dataset de ejemplo para esta segunda opción es sintético y sirve para comprobar el flujo. La evaluación agrícola requiere etiquetas de campo y predictores disponibles al momento de decidir.

## Contraste con una estación de Liberia

Se descargó la estación NOAA GHCN `CS000078774`, situada en 10,600° N, 85,533° O, para evaluar las predicciones ya guardadas del modelo. Se conservaron 302 registros diarios de 2023–2025 con lluvia válida. El lector convierte décimas de mm a mm, descarta registros con marca de calidad y los acumulados horarios B/D, y exige siete fechas consecutivas para cada total semanal. La descarga y la descripción del formato se pueden consultar en [NOAA](https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/CS000078774.dly) y su [documentación de GHCN](https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt).

| Evaluación | Ventanas | MAE XGBoost en mm | MAE referencia mensual en mm |
| --- | --- | --- | --- |
| POWER, época seca diciembre–abril | 574 | 8,09 | 5,71 |
| POWER, época lluviosa mayo–noviembre | 830 | 50,91 | 53,95 |
| Estación, ventanas completas con solapamiento | 97 | 48,05 | 68,42 |
| Estación, semanas sin fechas compartidas | 19 | 44,35 | 64,65 |

La referencia mensual se calculó con POWER del entrenamiento anterior a 2018. Las 97 ventanas emparejadas caen en época lluviosa, entre 2023 y 2025. La serie observada carece de semanas secas completas en el período evaluado. En las 19 semanas sin solapamiento el modelo subestima 28,27 mm por semana en promedio, y 26,32 % de sus errores quedan dentro de ±10 mm. El registro tiene huecos y la selección de ventanas completas puede sesgar la muestra. La lluvia puntual, las fechas de observación de la estación y el día solar de POWER tienen diferencias espaciales y temporales que limitan el contraste.

El modelo mejora el error medio de la referencia en esta muestra lluviosa, mientras la referencia logra menor error en el período seco de POWER. Determinar utilidad para riego requiere además humedad del suelo, decisiones emitidas a tiempo y resultados de manejo. El [reporte reproducible](../datasets/processed/validation/rainfall-evaluation.json) contiene errores por año, sesgo, RMSE y cobertura. La [serie observada normalizada](../datasets/processed/validation/liberia-observed-rainfall.json) conserva fuente, hash y regla de calidad.

Se reproduce con `python -m scripts.evaluate_rainfall --predictions outputs/molab/cloud-rainfall-2026-11-15/predictions.csv --station outputs/molab/field-validation/liberia.dly --output outputs/molab/field-validation/evaluation.json`. El script también genera el CSV de las semanas emparejadas.

## Período nuevo reservado

Se congelaron los pesos de la ronda 70 y el esquema de entradas en [el protocolo temporal](../datasets/processed/validation/rainfall-holdout.json). El período de fechas de corte abarca el 15 de noviembre de 2026 al 14 de noviembre de 2027. Se eligió un año para cubrir ambas épocas. Cada predicción debe guardarse con sello temporal e insumos publicados antes del primer día que pretende pronosticar. Las fechas con insumos POWER aún sin publicar quedan excluidas. El cierre de todas las etiquetas de siete días será posterior al fin del período de corte.

La recopilación futura sigue pendiente. El protocolo registra cero predicciones emitidas y ninguna observación futura disponible. Los registros observados se contrastarán cuando existan. El histórico desde 2023 queda considerado evidencia de desarrollo por haber sido inspeccionado. El protocolo conserva hashes y el modelo congelado para comprobar que la evaluación futura usa los pesos registrados.

## Abrir en Molab

1. Extrae `outputs/molab/nandaview-molab.zip` e importa `nandaview_notebook.py` en Molab. El archivo original del notebook es `notebooks/train_molab.py`. En la barra superior, abre los recursos y selecciona **RTX PRO 6000 Blackwell**. [Guía de Molab](https://docs.marimo.io/guides/molab/)
2. Desde el explorador de archivos del notebook, carga `train_molab.py` y `guanacaste-features.json` del ZIP. Copia sus rutas tal como aparecen en Molab al formulario. Para el surrogate usa `surrogate-training.mock.json` del ZIP y el objetivo `surrogate`.
3. Para lluvia, conserva el inicio de validación en **2018-01-01** y el de prueba final en **2023-01-01**. Para el ejemplo del surrogate, usa **2014-01-01** y **2018-01-01**. Aplica la configuración y pulsa **Entrenar en Blackwell**. El notebook empieza con 500 rondas, hasta 600 segundos de entrenamiento y parada temprana tras 40 rondas sin mejora.
4. Descarga el ZIP con modelo nativo, curvas, métricas y predicciones antes de cerrar la sesión. El reporte registra el hash del dataset y del entrenador, los cortes, los parámetros y el hardware. El entrenador verifica CUDA y la recarga del modelo.

## Interpretar el progreso

XGBoost agrega árboles por ronda. El gráfico muestra MAE de entrenamiento y validación en mm. El checkpoint se elige por el menor MAE de validación. La tabla final compara el modelo con una mediana histórica por mes, calculada en entrenamiento, y muestra el error por año. Para el surrogate se usa la mediana global de entrenamiento.

El porcentaje informado es la proporción de casos cuyo error absoluto cae dentro de la tolerancia fijada antes de entrenar. Por ejemplo, una tolerancia de 10 mm agrupa aciertos dentro de ±10 mm. Compáralo junto al MAE, RMSE y cantidad de casos.

Para iterar con cortes históricos, usa varios cortes de validación dentro del histórico anterior a 2023 y compara el error por año. El período desde 2023 ya fue inspeccionado y se trata como evidencia de desarrollo. El protocolo futuro fija la evaluación nueva. El código elimina filas cuya etiqueta cruza un corte. La lluvia es la de la celda NASA POWER. El intervalo de evaluación contiene ventanas semanales superpuestas, por lo que sus filas están correlacionadas. [NASA POWER diario](https://power.larc.nasa.gov/docs/services/api/temporal/daily/)

Más rondas pueden empeorar el error de validación, incluso cuando baja el de entrenamiento. Una GPU más rápida permite probar más configuraciones. La calidad de las etiquetas, los años independientes y la evaluación temporal determinan qué afirmaciones permite el resultado.

## Comprobación local

```powershell
python -m pytest backend/tests/test_molab_dataset.py -q
python -m marimo check notebooks/train_molab.py
```

Para una corrida CPU de prueba, instala las dependencias declaradas al inicio del notebook y usa `python -m scripts.train_molab` con la ruta del dataset, los dos cortes, `--device cpu` y un límite pequeño de rondas. XGBoost usa `device=cuda` y `tree_method=hist` en Blackwell. [Guía GPU de XGBoost](https://xgboost.readthedocs.io/en/stable/gpu/index.html)
