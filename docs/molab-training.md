# Entrenamiento de NandaView en Molab

El notebook tiene dos objetivos. **Lluvia** estima el acumulado de los siete días siguientes para el punto POWER de Guanacaste. Los predictores son variables climáticas disponibles al cierre del día de corte. **Surrogate** estima el déficit hídrico que produce FAO-56 al simular un escenario completo. El dataset de ejemplo para esta segunda opción es sintético y sirve para comprobar el flujo. La evaluación agrícola requiere etiquetas de campo y predictores disponibles al momento de decidir.

## Abrir en Molab

1. Extrae `outputs/molab/nandaview-molab.zip` e importa `nandaview_notebook.py` en Molab. El archivo original del notebook es `notebooks/train_molab.py`. En la barra superior, abre los recursos y selecciona **RTX PRO 6000 Blackwell**. [Guía de Molab](https://docs.marimo.io/guides/molab/)
2. Desde el explorador de archivos del notebook, carga `train_molab.py` y `guanacaste-features.json` del ZIP. Copia sus rutas tal como aparecen en Molab al formulario. Para el surrogate usa `surrogate-training.mock.json` del ZIP y el objetivo `surrogate`.
3. Para lluvia, conserva el inicio de validación en **2018-01-01** y el de prueba final en **2023-01-01**. Para el ejemplo del surrogate, usa **2014-01-01** y **2018-01-01**. Aplica la configuración y pulsa **Entrenar en Blackwell**. El notebook empieza con 500 rondas, hasta 600 segundos de entrenamiento y parada temprana tras 40 rondas sin mejora.
4. Descarga el ZIP con modelo nativo, curvas, métricas y predicciones antes de cerrar la sesión. El reporte registra el hash del dataset y del entrenador, los cortes, los parámetros y el hardware. El entrenador verifica CUDA y la recarga del modelo.

## Interpretar el progreso

XGBoost agrega árboles por ronda. El gráfico muestra MAE de entrenamiento y validación en mm. El checkpoint se elige por el menor MAE de validación. La tabla final compara el modelo con una mediana histórica por mes, calculada en entrenamiento, y muestra el error por año. Para el surrogate se usa la mediana global de entrenamiento.

El porcentaje informado es la proporción de casos cuyo error absoluto cae dentro de la tolerancia fijada antes de entrenar. Por ejemplo, una tolerancia de 10 mm agrupa aciertos dentro de ±10 mm. Compáralo junto al MAE, RMSE y cantidad de casos.

Para iterar con cortes históricos, usa varios cortes de validación dentro del histórico anterior a 2023 y compara el error por año. Mantén 2023 en adelante reservado hasta fijar las features y el modelo final. El código elimina filas cuya etiqueta cruza un corte. La lluvia es la de la celda NASA POWER. El intervalo de evaluación contiene ventanas semanales superpuestas, por lo que sus filas están correlacionadas. [NASA POWER diario](https://power.larc.nasa.gov/docs/services/api/temporal/daily/)

Más rondas pueden empeorar el error de validación, incluso cuando baja el de entrenamiento. Una GPU más rápida permite probar más configuraciones. La calidad de las etiquetas, los años independientes y la evaluación temporal determinan qué afirmaciones permite el resultado.

## Comprobación local

```powershell
python -m pytest backend/tests/test_molab_dataset.py -q
python -m marimo check notebooks/train_molab.py
```

Para una corrida CPU de prueba, instala las dependencias declaradas al inicio del notebook y usa `python -m scripts.train_molab` con la ruta del dataset, los dos cortes, `--device cpu` y un límite pequeño de rondas. XGBoost usa `device=cuda` y `tree_method=hist` en Blackwell. [Guía GPU de XGBoost](https://xgboost.readthedocs.io/en/stable/gpu/index.html)
