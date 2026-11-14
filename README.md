# NandaView · AlairaX

La conexión con el kernel de Justin puede comprobarse con `python -m scripts.smoke_kernel`: genera un ejemplo de tres rotaciones y dos temporadas sintéticas usando el motor real. La [guía de integración](docs/kernel-integration.md) explica la prueba, las temporadas que cruzan año y la auditoría de calendarios.

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
- **Ant:** entregó la revisión de parámetros, matriz de fuentes, procedencia, casos QA y fichas de evidencia en `research/`. Faltan validar el punto de finca, perfil de agua útil del suelo, calendarios y la aprobación científica escrita. Las entradas reales rechazan estos campos pendientes.

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

## Kernel FAO-56 (Justin)

`backend.app.simulation.kernel:simulate_rotation` es el callback que espera `execute_comparison`. Recibe `climate`, `soil`, `rotation` y `assumptions` del contrato M1 y devuelve `metrics`, `daily_balance` (un registro por fecha de clima), `assumptions`, `source_refs`, `warnings` y `model_version`. Usa ET0 FAO-56 Penman-Monteith (Eq. 6) y el balance de agotamiento (Eq. 82–85) con estas decisiones:

- D1: las métricas salen de una corrida de secano; el requerimiento de riego, de una corrida manejada aparte.
- D2: arroz de secano, no inundado.
- D3: escorrentía RO = 0.3·max(0, P − 60).
- D4: Zr constante por ciclo.
- D5: barbecho con kc 0.15, Zr 0.15 m, p 0.5.
- D7: se simula toda la ventana de clima.
- D8: el contrato de Abe es la única salida.

- Las métricas cuentan solo días de cultivo. El barbecho entra al balance, pero `water_stress` queda `null` en esos días.
- Huecos de clima de ≤3 días: ET0 interpolada, lluvia 0, con aviso. Si el hueco es mayor, el balance queda `null` desde ese día y las métricas también.
- `assumptions` solo trae supuestos metodológicos, idénticos entre rotaciones del mismo año, porque `compare_runs` lo exige. Lo específico del calendario va en `warnings`.
- `simulate_rotation_detailed` agrega `irrigation_requirement_mm` (corrida managed, D1), `heat_stress_days` y `per_crop`. Estos campos están fuera del contrato v0.1.0.
- `heat_stress_days` cuenta días con `tmax ≥ heat_threshold_c` en la etapa `mid`. Solo el arroz tiene umbral citado; los demás cultivos quedan `null`.

Sensibilidad a Kc, Dr inicial, θfc, θwp y lluvia (±28 %): `python -m scripts.sensitivity`. Resultados preliminares y plantilla de comparación con CROPWAT en [kernel_validation.md](docs/kernel_validation.md).

Validación de los análogos y de la lluvia (Fase 8, preliminar mientras la ET0 tenga `reviewed: false`):

- `python -m scripts.backtest --output-dir docs` compara el kernel con el clima real de 2015 y 2023 contra el ensamble de sus análogos. Resultados en [docs/backtest/](docs/backtest/backtest.md) y lectura en [kernel_validation.md](docs/kernel_validation.md).
- `python -m scripts.ingest_chirps` baja la lluvia mensual CHIRPS v3 en el punto (unos 10 MB, por rango HTTP), y `python -m scripts.rain_bias --output-dir docs` la compara con POWER y con IMN. La nota está en [rain_bias.md](docs/rain_bias.md): POWER da la mitad de la lluvia antes de 2005.
- Las gráficas usan `matplotlib`.

ET0 diaria para los análogos:

```powershell
python -m scripts.export_et0 --climate datasets/processed/climate/power_10.55_-85.5_*.json --output datasets/processed/et0/et0_10.55_-85.5.json
```

El archivo sale con `reviewed: false`; `build_analogs.py` lo rechaza hasta que Justin lo revise y ponga `reviewed: true` y `reviewed_by`. Ejecutar de punta a punta con el kernel real:

```powershell
python -m scripts.run_comparison --analogs analogs.json --scenario neutral --inputs inputs.json --kernel backend.app.simulation.kernel:simulate_rotation --output out.json --allow-mock
```

### Cómo correr los tests

Desde la raíz del repo, con el entorno virtual activo:

```powershell
python -m pytest backend/tests -q
python -m unittest discover -s backend/tests
python -m pytest backend/tests -q --cov=backend/app/simulation --cov-report=term-missing
```

La cobertura de `backend/app/simulation/` está en 96 %. `test_kernel_qa.py` cubre:

- Cambio de etapa y cambio de cultivo.
- Huecos de clima.
- Suelo `null` o poco profundo.
- Parámetros incompletos.
- Temporada bisiesta.
- El snapshot de regresión de 2015 (`backend/tests/snapshots/kernel_metrics_2015.json`). Si un cambio científico es intencional, regenéralo con `UPDATE_SNAPSHOTS=1` y explica el cambio en el PR.

Los 3 casos calculados a mano de Ant (`research/qa_cases.md`, tarea 2.4) pasan contra el kernel: sin estrés, estrés con percolación y reescalado de Zr al pasar a barbecho.

## Despliegue y CI

- `.github/workflows/backend-tests.yml` corre `pytest` con cobertura en cada PR y en cada push a `main`.
- `.github/workflows/pages.yml` publica en GitHub Pages en cada push a `main`, y también se puede lanzar a mano desde *Actions*:
  - Si existe `frontend/package.json`, usa Node 22, corre `npm ci` y `npm run build`, y publica `frontend/dist`. Vite debe usar `base: "/SpaceApps-AlairaX/"` y HashRouter.
  - Si todavía no existe, publica `.github/pages-placeholder/index.html` junto con `frontend/public/data/`. Así se prueba el pipeline antes de que llegue la UI.
- El dueño del repo debe activar una vez *Settings → Pages → Source: GitHub Actions*. La URL queda en `https://abraham2106.github.io/SpaceApps-AlairaX/`. Pruébala en ventana privada y en el celular.

## Límites

KNN busca temporadas parecidas; 2026 sirve de seguimiento y nunca entra como análogo. Se comparan ventanas temporales completas y equivalentes. Los cuantiles representan variación entre análogos, no probabilidades de éxito ni intervalos de confianza. Se reportan métricas modeladas; no se infiere rendimiento, rentabilidad, ahorro demostrado ni una rotación ganadora.

El demo científico real requiere integrar la ET0 y el balance FAO-56 de Justin, parámetros y calendarios revisados por Ant, y la UI de Angelina. Los fixtures no constituyen validación física ni de campo.

## Uso de IA

Codex y sus subagentes asistieron en la implementación de contratos, ingesta, KNN, comparador, fixtures, documentación y pruebas de Abe. El equipo debe completar la declaración por persona para la entrega del evento.
