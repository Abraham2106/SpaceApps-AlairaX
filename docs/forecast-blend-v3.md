# Pronósticos abiertos y XGBoost: evaluación ejecutada

Se descargaron 150 fechas de emisión entre el 16 de marzo de 2024 y el 20 de diciembre de 2025 para el punto 10,55 N / 85,5 O. Cada fecha tiene siete días completos de ECMWF IFS y CHIRPS3-GEFS, sin errores de descarga registrados. El experimento se entrenó en CPU local con XGBoost 3.4.1; se verificó la recarga de los pesos. La ejecución anterior en Molab sigue conservada por separado.

Fuentes: [ECMWF mediante Single Runs de Open-Meteo](https://open-meteo.com/en/docs/single-runs-api), [CHIRPS-GEFS de UCSB](https://chc.ucsb.edu/data/chirps-gefs) y [NASA POWER diario](https://power.larc.nasa.gov/docs/services/api/temporal/daily/). Las respuestas originales y las muestras de raster quedan en la caché local con procedencia. El uso comercial de Open-Meteo requiere revisar sus condiciones.

## Qué se entrenó

Se añadieron a las 37 variables causales previas los acumulados previstos, diferencias entre fuentes, máximos diarios, días húmedos y medias previstas de temperatura, humedad y presión. XGBoost aprende a corregir el residuo de ECMWF, con 150 rondas fijadas y árboles de profundidad dos. Los predictores históricos tienen dos días de desfase. Los acumulados objetivo usan fechas UTC; la versión v2 anterior usaba LST y aparece como referencia aproximada.

Las etiquetas de entrenamiento terminan antes de agosto de 2024. La selección usa agosto–septiembre de 2024; la calibración, octubre–diciembre. El diagnóstico usa 2025 y cuenta 51 semanas sin solapamiento. Se purgan etiquetas que cruzan cortes. Hay 27 ventanas de entrenamiento y 21 de selección, algunas solapadas; selección y métricas finales usan semanas sin solapamiento. La selección efectiva tiene ocho semanas: evidencia limitada. Después de seleccionar, se reajusta XGBoost con las 48 ventanas anteriores a octubre. Los resultados de 2025 ya habían sido inspeccionados en otros experimentos y constituyen diagnóstico retrospectivo.

## Resultado sobre NASA POWER, acumulado de siete días

| Candidato | Error absoluto medio (mm) | Dentro de ±10 mm | Dentro de ±20 mm |
| --- | ---: | ---: | ---: |
| Mediana histórica mensual UTC | 28,25 | 52,94 % | 68,63 % |
| XGBoost v2, referencia LST aproximada | 30,69 | 45,10 % | 60,78 % |
| ECMWF | 31,07 | 47,06 % | 58,82 % |
| CHIRPS3-GEFS | 28,65 | 49,02 % | 62,75 % |
| Promedio de ambos pronósticos | 29,00 | 50,98 % | 60,78 % |
| XGBoost con pronósticos | 30,79 | 41,18 % | 62,75 % |

La regla definida antes del diagnóstico eligió la mediana mensual. El nuevo XGBoost no demuestra mejora y se conserva como experimento. La mediana mensual tiene un error mediano de 8,23 mm, pero el percentil 90 del error absoluto alcanza 83,80 mm. En época seca tiene 80 % de casos dentro de ±10 mm; en época húmeda, 35,48 %. El total anual oculta esa diferencia.

## Cómo entender las mediciones

- Un milímetro de lluvia equivale a un litro por metro cuadrado. Aquí se mide lluvia acumulada en siete días.
- MAE: tamaño promedio del error, sin importar si el pronóstico se pasó o se quedó corto. Un MAE de 30,79 mm no garantiza un margen de ±30,79 mm.
- Aciertos dentro de una tolerancia: 41,18 % significa 21 de las 51 semanas con error de hasta 10 mm. Es una regla de acierto definida, no una exactitud universal.
- RMSE: penaliza más las fallas grandes. El nuevo XGBoost tiene 63,13 mm; su error absoluto mediano es 12,53 mm y el percentil 90 es 71,46 mm.
- Sesgo: promedio del error con signo. En XGBoost es −6,88 mm, indicio de subestimación en este conjunto.
- Margen futuro: exige calibración y comprobar cobertura en nuevas predicciones. Los percentiles retrospectivos no garantizan el error de una semana futura.

## Auditoría y límite de uso

Se contrastaron las etiquetas con registros GHCN de Liberia, conservando las semanas completas y los controles de calidad del lector. POWER registra 736,43 mm el 30 de mayo de 2024 frente a 0 mm en la estación; el 11 de noviembre registra 513,15 mm frente a 22,6 mm. La cuadrícula y el punto tienen escalas espaciales y horarios distintos. Estas discrepancias requieren corroboración independiente; se conservaron los datos y no se eliminaron valores para mejorar las métricas.

La banda nominal del 90 %, calibrada con apenas doce semanas, dio ±890,55 mm por los extremos de 2024. Es demasiado amplia para servir como margen operativo. Su cobertura del 100 % en 2025 no demuestra utilidad. El informe marca explícitamente que no está validada operacionalmente.

Solo hay cuatro semanas locales completas sin solapamiento en el diagnóstico de 2025. El XGBoost nuevo obtiene 50,92 mm de MAE y cero de cuatro casos dentro de ±10 mm. La mediana mensual obtiene 16,40 mm y uno de cuatro. La muestra es insuficiente para establecer precisión de finca.

El avance queda en adquisición reproducible, entrenamiento, comparación y auditoría. Para recomendar riego todavía hacen falta etiquetas locales consistentes y validación prospectiva. El protocolo futuro y el modelo congelado originales permanecen conservados. Los archivos CHIRPS históricos fueron reprocesados y no representan necesariamente el archivo disponible en su fecha original.

## Archivos y reproducción

Resultado completo versionable: `datasets/processed/validation/forecast-blend-v3.json`. Pesos, predicciones semanales y reporte local: `outputs/molab/forecast-blend-v3-audited/`. Paquete reproducible: `outputs/molab/forecast-blend-v3.zip`.

```powershell
python -m scripts.ingest_forecast_comparison --start 2024-03-16 --end 2025-12-20 --step-days 7 --workers 3 --include-station-origins outputs/molab/field-validation/liberia.dly --output datasets/processed/climate/forecast-comparison-2024-2025.json
uv run --with xgboost==3.4.1 --with pandas --with numpy python -m scripts.train_forecast_blend --forecasts datasets/processed/climate/forecast-comparison-2024-2025.json --output outputs/molab/forecast-blend-v3-new-run
uv run --with xgboost==3.4.1 --with pandas --with numpy python -m scripts.predict_forecast_blend --model-dir outputs/molab/forecast-blend-v3-audited --forecasts datasets/processed/climate/forecast-comparison-2024-2025.json --climate outputs/molab/import/guanacaste-features.json --origin 2025-12-20
```

El paquete incluye las entradas normalizadas necesarias para entrenar y las fuentes de código. La caché de rasters parcial y las respuestas originales descargadas se conservan localmente fuera del paquete. La inferencia de ejemplo es retrospectiva.
