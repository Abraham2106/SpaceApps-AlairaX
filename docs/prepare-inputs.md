# Preparar entradas del kernel desde artefactos revisados

`scripts/prepare_comparison.py` ensambla el clima histórico, ET0 revisada, suelo, manejo y calendarios explícitos en un array de `SimulationInput`. No estima ET0, fechas de siembra ni propiedades de suelo. La siguiente etapa, `scripts/run_comparison.py`, recibe ese array y ejecuta el kernel de Justin.

El archivo de ejemplo [comparison-setup.mock.json](../datasets/examples/comparison-setup.mock.json) contiene **solo configuración sintética** del año 2015 y tres rotaciones. Sus fechas son provisionales; suelo y referencias de parámetros siguen `null`. El punto de finca sigue sin validar. `reviewed_by` en ese fixture identifica que no es una revisión humana real. El schema de [ComparisonSetup](contracts/ComparisonSetup.schema.json) se genera desde `backend/app/application/prepare_inputs.py`. Tanto el fixture como el schema se regeneran con `python -m scripts.export_contracts`.

## CLI

Desde la raíz, cuando existan los artefactos revisados:

```powershell
$climateFiles = (Get-ChildItem datasets/processed/climate/power_*.json).FullName
python -m scripts.prepare_comparison --analogs datasets/processed/analogs/analogos.json --scenario neutral --climate $climateFiles --et0 datasets/processed/reviewed-et0.json --setup datasets/processed/comparison-setup.json --start-mmdd 04-01 --end-mmdd 12-31 --output datasets/processed/simulation-inputs-neutral.json
python -m scripts.run_comparison --analogs datasets/processed/analogs/analogos.json --scenario neutral --inputs datasets/processed/simulation-inputs-neutral.json --kernel backend.app.simulation.kernel:simulate_rotation --output frontend/public/data/compare-neutral.json
```

Son comandos de integración: los nombres `reviewed-et0.json` y `comparison-setup.json` indican los artefactos que debe entregar el equipo, no archivos reales ya validados. El kernel también debe existir y estar revisado. Los análogos reales actuales están `unavailable` por ET0 pendiente; esta preparación se detiene mientras el escenario seleccionado no esté disponible.

El tamaño del lote es **3 × k**, donde k procede del escenario seleccionado en `analogos.json`. No se fija un único tamaño para todos los escenarios: por ejemplo, si un escenario usa k=3 se generan 9 entradas, y si usa k=5 se generan 15. Cada año seleccionado requiere las tres rotaciones y su manejo explícito. El preparador no elige ni cambia k.

`--start-mmdd` y `--end-mmdd` delimitan la ventana de **simulación histórica** dentro de cada año. Puede ser más larga que la ventana de features usada para elegir análogos; debe cubrir todas las fechas de los cultivos y disponer de clima y ET0 en cada día. No cruza de año. La selección de análogos y la simulación son pasos distintos: elegir vecinos con abril–octubre no aporta automáticamente datos para simular hasta diciembre.

Para ensayos sintéticos se requiere `--allow-mock` tanto al preparar como al ejecutar. Los artefactos deben compartir `_mock=true`; los flags se conservan en las salidas. Añadir el flag no valida parámetros ni transforma mocks en datos reales.

La preparación escribe el array de entradas y un archivo lateral `*.manifest.json` con los hashes SHA-256 de los artefactos usados y del resultado. Rechaza rutas de salida, manifest o archivos temporales que sobrescribirían cualquiera de los insumos. Los metadatos `generado` registran la ejecución, por lo que las marcas de tiempo pueden cambiar aunque se reutilicen los mismos insumos.

## `ComparisonSetup`

| Campo | Contenido |
|---|---|
| `schema_version` | `0.1.0` |
| `_mock` | Booleano explícito; debe coincidir en todos los artefactos |
| `generado` | Fecha y hora con zona horaria |
| `zona` | Misma identidad de ubicación que en POWER, ET0 y análogos: ID, nombre, latitud y longitud. El setup puede registrar una validación posterior del punto |
| `source_refs` | Referencias de los artefactos o fuentes de configuración |
| `warnings` | Vacíos, supuestos y avisos que deben propagarse |
| `reviewed_by` | Identificador de quien revisó la configuración; una cadena no certifica por sí sola la revisión científica |
| `soil` | `field_capacity_m3_m3`, `wilting_point_m3_m3`, `rooting_depth_m`, `source_refs` |
| `rotations_by_year` | Objeto JSON cuyas claves son años y cuyos valores son arrays de tres `RotationSchedule` distintos |
| `assumptions_by_year` | Objeto JSON cuyas claves son años y cuyos valores son `ModelAssumptions` |

Las claves de año en JSON son cadenas, como `"2015"`; Pydantic las convierte a enteros en el modelo. Cada array de rotaciones contiene una vez `rice_melon`, `rice_legume` y `rice_sorghum`. Cada calendario debe listar arroz seguido de melón, leguminosa o sorgo, respectivamente, con siembra y cosecha válidas, sin solapamientos y dentro de la ventana de simulación.

En una configuración real, `calendar_status` debe ser `confirmed` y cada ciclo necesita `parameter_set_id`. El manejo de cada año especifica `irrigation_mode`, `irrigation_mm_by_date`, `initial_soil_water_fraction` y `notes`. Un calendario de riego requiere `irrigation_mode=scheduled`; sus fechas deben quedar dentro de la serie. Los mismos supuestos de manejo se aplican a las tres alternativas de un año. El suelo también es común: las propiedades desconocidas permanecen `null` en los mocks y bloquean entradas reales.

El ejemplo sintético no propone una práctica agronómica ni un manejo de riego. Para extenderlo a otros años se deben aportar sus calendarios revisados; el preparador no desplaza las fechas de 2015 ni inventa fechas para años análogos.

## Clima y ET0 requeridos

Los archivos climáticos son los JSON normalizados por `scripts/ingest_climate.py`. Deben coincidir en identidad de zona y estado mock. La validación posterior de la parcela se registra en el setup sin reescribir las fuentes originales que todavía dicen `validated=false`. La preparación preserva los insumos y propaga la zona revisada a las entradas. La ejecución comprueba su identidad contra los análogos originales y usa la zona de esas entradas; un cambio de coordenadas o identificador se rechaza. El preparador exige estas unidades:

| Campo | Unidad |
|---|---|
| `precipitation_mm` | `mm/day` |
| `tmin_c`, `tmax_c` | `C` |
| `relative_humidity_pct` | `%` |
| `wind_speed_2m_m_s` | `m/s` |
| `solar_radiation_mj_m2_day` | `MJ/m^2/day` |

No acepta ET0 incorporada directamente en POWER: ese campo debe seguir `null`. El artefacto externo de ET0 declara `_mock`, la misma identidad de `zona`, `reviewed=true`, `reviewed_by`, `model_version`, `units="mm/day"`, `source_refs` y `values`, un objeto de fechas ISO a valores diarios. Puede añadir `warnings`. `_mock` y `reviewed` deben ser booleanos literales, no cadenas ni números. La revisión declarada corresponde a Justin; el código valida el formato sin sustituir su revisión de ecuaciones y unidades.

En un lote real se requiere cada fecha, cada variable climática y cada ET0 de la ventana, con valores finitos y sin imputación. En un lote mock se permite conservar valores desconocidos explícitos. Los solapamientos climáticos idénticos se deduplican; los conflictivos se rechazan. La temporada y cada combinación de rotación/suelo/manejo se copian para mantener independientes sus estructuras de datos.

La salida conserva fuentes y advertencias del setup, ET0, análogos y clima. Después, la ejecución calcula el hash ambiental y valida la correspondencia con las respuestas del kernel. Consulte [el contrato](contract-handoff.md) y [el método científico](scientific_method.md) para las garantías y límites completos.

## Revisión humana pendiente

Ant y Justin todavía deben validar el punto agrícola, el perfil hídrico de suelo, los parámetros por cultivo, calendarios y manejo. Un timeout del servicio SoilGrids no confirma ninguna propiedad del suelo. La ingesta POWER y el formato válido de configuración tampoco constituyen esa validación. El checklist de [method-review.md](method-review.md) registra los pasos científicos pendientes.
