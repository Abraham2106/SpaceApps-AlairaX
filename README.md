# NandaView · AlairaX

Comparación explicable de tres rotaciones agrícolas de Guanacaste bajo el mismo clima histórico: `rice_melon`, `rice_legume` y `rice_sorghum`.

El código de Abe incluye contratos, ingesta con caché, features estacionales, búsqueda KNN, comparación pareada e incertidumbre empírica. El kernel FAO-56 y la interfaz de usuario se integran mediante estos contratos.

## Preparación

Python 3.12 o posterior. Desde la raíz:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m scripts.export_contracts
.venv\Scripts\python -m unittest discover -s backend/tests -v
```

Si ya tienes Python con Pydantic instalado, puedes usar `python` directamente.

## Entregas para el equipo

- **Angelina:** `frontend/public/data/scenarios.json` enumera los cuatro archivos `compare-*.json`; `rotations.json` contiene los IDs comunes. Todos los datos de estos archivos son **sintéticos**, con `_mock: true`; la UI debe mostrar el aviso mock.
- **Justin:** modelos en `backend/app/api/schemas/contracts.py`, firma y unidades en [el contrato de integración](docs/contract-handoff.md). `execute_comparison()` en `backend/app/application/compare.py` recibe su callback `simulate_rotation(climate=..., soil=..., rotation=..., assumptions=...)`.
- **Ant:** faltan validar el punto de finca, perfil de agua útil del suelo, parámetros por cultivo y calendarios. Las entradas reales rechazan estos campos pendientes.

Schemas JSON compartidos: `docs/contracts/`. Ejemplo de temporada sintética completa de abril a diciembre: `datasets/examples/simulation-input.mock.json`.

## Datos reales

Las consultas públicas POWER y NOAA no requieren claves. Descarga de prueba:

```powershell
python -m scripts.ingest_climate --start 2024-01-01 --end 2024-01-05
```

Descarga completa reanudable por año:

```powershell
python -m scripts.ingest_climate --start 1981-01-01 --end 2026-11-14
```

El punto inicial `10.55, -85.50` es provisional. Las respuestas originales y metadatos quedan en `datasets/raw/climate/` (ignorado por Git); los datos normalizados en `datasets/processed/climate/`. `--offline` reutiliza caché y `--refresh` obtiene una nueva versión conservando los originales. ET0 permanece `null` hasta que Justin la calcule. Se registran faltantes y lluvia extrema sin inventar valores ni aplicar una corrección IMN no validada.

Detalles: [ingesta y procedencia](docs/data-ingestion.md), [features y KNN](docs/analog-method.md), [plan del equipo](docs/wbs-field-shift.md).

La selección usa tres análogos en Niño fuerte y cinco en los demás escenarios, según la [decisión explícita del equipo](docs/decisions.md). El tamaño de muestra y las advertencias acompañan los resultados.

La descarga local ya contiene 16.754 días, 1981–14/11/2026, con 42 años completos de las seis variables (1984–2025). POWER no entregó radiación en 1981–1983. Las exclusiones y faltantes se conservan en QC. El pipeline real de análogos fue ejecutado y reporta `unavailable` por ET0 pendiente; sus archivos están en `datasets/processed/analogs/`.

## Comparación y exportación

`compare_runs()` recibe exactamente una ejecución por rotación y año análogo. Comprueba la ubicación, escenario, versión del kernel y hash del clima/suelo/manejo. Calcula diferencias contra `rice_melon` **por año antes** de calcular p10/p50/p90. Si falta una métrica, su resumen queda `null` y se emite una advertencia.

Exportar ejecuciones precalculadas del kernel:

```powershell
python -m scripts.compare_results --request request.json --analogs analogs.json --runs runs.json --output frontend/public/data/compare-neutral.json
```

El comando exige `--allow-mock` para exportar ejecuciones sintéticas. Generar ejemplos mock completos con `python -m scripts.export_contracts` sobrescribe los archivos de ejemplo y `frontend/public/data/`; úsalo solo para preparar o regenerar fixtures.

`python -m scripts.prepare_comparison` arma las entradas del kernel desde el clima, ET0 revisada y una configuración explícita de suelo, calendarios y manejo por año. Guarda un manifiesto SHA-256 de las fuentes y rechaza destinos que sobrescriban entradas. El [formato y los comandos de integración](docs/prepare-inputs.md) incluyen un ejemplo sintético; los valores científicos reales los entrega el equipo.

La [inspección de escenarios](datasets/processed/readiness/scenarios.json) cuenta cobertura de clima y ONI sin afirmar que se ejecutó KNN. La [inspección de suelo](docs/soil-readiness.md) ya obtuvo textura y retención por seis profundidades en SoilGrids; el perfil hidráulico para el kernel sigue pendiente de revisión científica.

Método implementado y revisión científica pendiente: [scientific_method.md](docs/scientific_method.md) y [method-review.md](docs/method-review.md).

## Límites

KNN busca temporadas parecidas; 2026 sirve de seguimiento y nunca entra como análogo. Se comparan ventanas temporales completas y equivalentes. Los cuantiles representan variación entre análogos, no probabilidades de éxito ni intervalos de confianza. Se reportan métricas modeladas; no se infiere rendimiento, rentabilidad, ahorro demostrado ni una rotación ganadora.

El demo científico real requiere integrar la ET0 y el balance FAO-56 de Justin, parámetros y calendarios revisados por Ant, y la UI de Angelina. Los fixtures no constituyen validación física ni de campo.

## Uso de IA

Codex y sus subagentes asistieron en la implementación de contratos, ingesta, KNN, comparador, fixtures, documentación y pruebas de Abe. El equipo debe completar la declaración por persona para la entrega del evento.
