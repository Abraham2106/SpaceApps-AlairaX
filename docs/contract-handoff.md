# Contrato M1 · v0.1.0

Generar schemas, fixtures y mocks desde la raíz del repositorio:

```powershell
python -m pip install -r requirements.txt
python -m scripts.export_contracts
python -m unittest backend.tests.test_contracts -v
```

Los modelos Python en `backend/app/api/schemas/contracts.py` son la fuente del contrato. Sus cuatro JSON Schema están en `docs/contracts/`; el quinto schema, `ComparisonSetup`, procede de `backend/app/application/prepare_inputs.py`. Todos se regeneran con `python -m scripts.export_contracts`. Los campos desconocidos usan `null`; no se sustituyen por cero. Todos los sobres se serializan con `_mock`, `generado`, `zona`, `schema_version`, `source_refs` y `warnings`.

## Para Justin: entrada y salida del kernel

`datasets/examples/simulation-input.mock.json` contiene una temporada completa del 1 de abril al 31 de diciembre de 2015 (275 días consecutivos). Es clima **sintético**, con ET0, propiedades de suelo y referencias de parámetros aún desconocidos. Las fechas de cultivos son ejemplos provisionales para probar cobertura del contrato; Ant y Justin deben confirmar el calendario antes de una ejecución real.

La entrada conserva la firma acordada:

```python
request = SimulationInput.model_validate_json(payload)
result = simulate_rotation(
    climate=request.climate,
    soil=request.soil,
    rotation=request.rotation,
    assumptions=request.assumptions,
)
```

La integración envuelve la salida del kernel en `SimulationResult`: ID de rotación, escenario, año, métricas, balance diario, supuestos, fuentes y versión. El kernel debe reutilizar las mismas condiciones ambientales y manejo entre las alternativas de un mismo año. Se requiere revisión científica de Justin; el exportador no calcula ET0 ni balance hídrico.

`environment_id` identifica mediante SHA-256 el clima, suelo, manejo, zona y estado mock del experimento, excluyendo la rotación. La integración real debe usar el helper `environment_fingerprint(SimulationInput)`; las rotaciones de un mismo año deben compartir ese hash y la versión del modelo. Los ejemplos usan un hash determinista identificado como sintético por escenario y año, porque sus salidas no proceden de un kernel.

Todas las ejecuciones comparadas deben usar una sola versión del kernel, también entre años. `execute_comparison()` revalida el lote, protege las entradas frente a mutaciones del callback y verifica que la salida diaria cubra exactamente las fechas del clima. En resultados reales el balance diario es obligatorio; los mocks pueden omitirlo. Los días de estrés no pueden exceder la duración de la serie. El sobre de comparación valida que cada ejecución interna coincida en escenario, zona, estado mock, rotación y años listados.

Las unidades están en los nombres: agua y ET0 en mm, temperaturas en °C, humedad relativa en %, viento a 2 m en m/s, radiación en MJ/m²/día y fracciones volumétricas de suelo en m³/m³. Los días ausentes conservan su fecha con valores `null`. El fixture de salida usa balance diario vacío porque no contiene una simulación física.

`_mock=false` en la entrada exige zona validada, calendario confirmado, perfil de suelo completo, referencias de parámetros y manejo explícito. Cambiar solo el indicador del fixture produce un error de validación.

## Para Angelina: JSON estático

Leer `frontend/public/data/scenarios.json` para el selector y `rotations.json` para los nombres. Cada escenario apunta a `compare-{scenario_id}.json`, con tres rotaciones y k ejecuciones sintéticas por rotación. El fixture de Niño fuerte usa k=3; los otros usan k=5. Los cuatro escenarios utilizan valores de ejemplo del mismo generador: no representan diferencias climáticas reales ni una búsqueda KNN.

Mostrar un aviso visible mientras `_mock=true`; también revisar el indicador de cada ejecución. No presentar las referencias `synthetic-fixture-v1` como fuentes NASA/NOAA. No retirar el aviso hasta que las salidas reales y sus metadatos sustituyan estos fixtures.

Cada métrica tiene `p10`, `p50`, `p90` y `n`. `delta_vs_baseline` se calcula para cada año como alternativa menos `rice_melon`, y después se resume. Un delta negativo indica menor valor **modelado**. La banda p10–p90 es variación empírica entre análogos, no un intervalo de confianza ni un pronóstico. Cuando falla una métrica de algún año, el resumen correspondiente queda en `null` con advertencia para no cambiar silenciosamente la población comparada.

## Conectar análogos, kernel y export real

Cuando existan `analogos.json`, el kernel revisado de Justin y las entradas completas, ejecutar desde la raíz:

```powershell
python -m scripts.run_comparison --analogs datasets/processed/analogs/analogos.json --scenario neutral --inputs datasets/processed/simulation-inputs.json --kernel backend.app.simulation.kernel:simulate_rotation --output frontend/public/data/compare-neutral.json
```

`--kernel` recibe un módulo Python local importable y el nombre de su función separados por `:`. El ejemplo indica la ubicación acordada; el kernel debe existir antes de ejecutar. El callback recibe `climate=`, `soil=`, `rotation=` y `assumptions=` y devuelve los campos numéricos/metadatos documentados o un `SimulationResult` válido.

`--inputs` es un **array JSON** de objetos completos `SimulationInput`: un objeto por cada año análogo y cada una de las tres rotaciones. Se necesitan 3 × k entradas seleccionadas: 9 para k=3 o 15 para k=5. El mismo año usa clima, suelo y manejo idénticos en todas las alternativas. Los calendarios de cada cultivo corresponden a ese año; no se reutilizan fechas de otro año. En entradas reales todos los `_mock` son `false`, la zona y calendarios están confirmados y los parámetros tienen referencias válidas.

Un escenario con estado `unavailable` se rechaza antes de ejecutar el kernel. El pipeline también rechaza que análogos y entradas tengan distinto estado mock. Solo las pruebas sintéticas requieren añadir `--allow-mock`; ese indicador permite ejecutar mocks explícitos y conserva `_mock=true` en el resultado. No convierte datos sintéticos en observaciones. Las fuentes y advertencias de análogos, entradas y kernel se conservan en el JSON exportado.

## Estado del hito

Hay contrato ejecutable, schemas, fixture de temporada y JSON de integración. Faltan confirmación de zona y calendarios, parámetros agronómicos, ingesta real, selección KNN y kernel validado para cerrar M1 con el equipo y producir resultados científicos. Los mocks no prueban el hito M3 de integración real.
