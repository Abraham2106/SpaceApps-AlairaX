# Feature engineering de NandaView

El pipeline regional ejecuta los adaptadores de archivos normalizados de POWER y NOAA que ya usa el proyecto. Genera features diarias, índices ENOS por periodo, capas opcionales de suelo y vegetación, y la matriz estacional del KNN. El exportador de entrenamiento recibe los objetos `SimulationInput` existentes y obtiene sus etiquetas directamente del kernel. Adquisición y extracción se ejecutan por separado. Los artefactos locales y sus hashes permiten repetir la extracción sin conexión.

`configs/regions/` define el punto WGS84, la zona horaria IANA, la ventana de datos, los meses lluviosos, el calendario de features, el periodo ONI, los valores de k, el umbral térmico y el catálogo previsto. Las fechas climáticas conservan el día solar local de POWER. Los datos se vinculan a un punto y a la resolución nativa de cada producto. El adaptador HLS recibe pixels de un área de interés ya recortada y alineada en el proceso del proveedor.

## Ejecución sin conexión

```powershell
$climate = (Get-ChildItem datasets/processed/climate/power_*.json).FullName
python -m scripts.build_region_features --region configs/regions/guanacaste.json --climate $climate --oni datasets/processed/climate/oni.json --roni datasets/processed/climate/roni.json --et0 datasets/processed/et0/et0_10.55_-85.5.json --soil datasets/processed/soil/soil_readiness_10.55_-85.5.json --output-dir datasets/processed/features/guanacaste

$climate = (Get-ChildItem datasets/processed/climate-davis/power_*.json).FullName
python -m scripts.build_region_features --region configs/regions/davis.json --climate $climate --oni datasets/processed/climate/oni.json --roni datasets/processed/climate/roni.json --et0 datasets/processed/climate-davis/et0.json --output-dir datasets/processed/features/davis

python -m scripts.build_surrogate_dataset --demo --output datasets/examples/surrogate-training.mock.json
python -m pytest backend/tests/test_feature_pipeline.py -q
```

El primer comando produjo 16.754 filas diarias y 42 temporadas con las cinco variables de KNN completas. ET0 lleva `reviewed=false`, por lo que estas filas estacionales están marcadas como provisionales y el archivo de análogos mantiene los escenarios indisponibles. «Como 2026» tiene un faltante de radiación y ET0 el 7 de septiembre. El segundo comando usa 106 días reales de POWER de Davis, del 1 de enero al 15 de abril de 2024, y ET0 calculada por el mismo exportador FAO‑56. Davis demuestra la extracción geográfica. Su muestra corta carece de climatología propia y el trimestre FMA termina después del corte.

El tercer comando produce 27 filas de prueba con clima, suelo y manejo sintéticos y etiquetas calculadas por el kernel. Se excluyen seis filas de temporadas que cruzan un límite de partición. Para generar un dataset con escenarios preparados, utilizar `--inputs SIMULATION_INPUTS.json`. Cada registro contiene `features` y `labels` como objetos separados. Las columnas se pueden aplanar con `pandas.json_normalize` y las categorías se codifican aprendiendo únicamente del conjunto de entrenamiento. `climate_year`, `location_id`, `environment_id` y `split` identifican los grupos. El script usa partición temporal con exclusión de temporadas en el límite. Una evaluación entre fincas debe reservar ubicaciones completas cuando exista una muestra suficiente.

## Diccionario de features

| Campo | Unidad y cálculo | Origen y disponibilidad |
|---|---|---|
| `precipitation_mm` | mm acumulados en el día solar | POWER diario |
| `rain_{7,15,30,90}d_mm` | mm, suma móvil inclusiva | Al cierre del día con ventana completa |
| `rain_*d_valid_days` | Conteo de días con lluvia disponible | Al cierre del día, incluso con faltantes |
| `rain_30d_anomaly_pct` | 100 × (lluvia de 30 días / media histórica − 1) | Ventanas equivalentes del mismo mes/día de años anteriores, dentro de la referencia regional. Devuelve null si falta referencia o la media es cero |
| `rain_30d_reference_years`, `rain_30d_daily_sd_mm` | Conteo y desviación estándar poblacional de lluvia diaria | Referencia previa y ventana móvil completa |
| `tmin_c`, `tmax_c`, `tmean_c` | °C. La media aproxima (mínima + máxima)/2 | POWER al cierre del día |
| `heat_day`, `wet_month` | 0/1. Tmax alcanza umbral regional, o mes pertenece al calendario lluvioso | POWER y configuración regional |
| `relative_humidity_pct`, `wind_speed_2m_m_s`, `solar_radiation_mj_m2_day` | %, m/s, MJ/m²/día | POWER diario |
| `et0_mm`, `et0_*d_mm` | mm diarios y acumulados completos | Artefacto FAO‑56 con estado de revisión |
| `climatic_deficit_mm`, `climatic_deficit_30d_mm` | mm, max(0, ET0 − lluvia) en el periodo | Al cierre del periodo. El déficit del cultivo se calcula en el kernel |
| `anomaly_c`, `phase`, `intensity_abs_c` | °C, categoría por ±0,5 °C, magnitud absoluta | ONI y RONI por separado, periodo de tres meses cerrado |
| `consecutive_windows`, `months_since_phase_start`, `sustained_warm_or_cold` | Conteos de ventanas consecutivas, meses transcurridos y flag tras cinco ventanas | Serie retrospectiva CPC. La fecha de cierre es un límite inferior de disponibilidad. Para probar pronósticos históricos hacen falta las publicaciones originales de cada fecha |
| `soil.layers` | Textura en % masa, retención por tensión en m³/m³, por profundidad | Predicciones SoilGrids. La asignación a capacidad de campo y marchitez requiere revisión |
| `ndvi_mean`, `low_ndvi_fraction`, `valid_pixels` | Media de (NIR − rojo)/(NIR + rojo), fracción bajo 0,2 y conteo | HLS v2. El adaptador descarta relleno, nubes, adyacencia, sombra, nieve, agua y aerosol alto. La fracción es un descriptor óptico |
| `farm.crop`, `farm.management`, `days_after_planting` | Especie, cultivar, lote, duración, densidad, referencia de parámetros, fecha, cultivos previos, riego e historial. Días desde siembra | Contexto declarado por el productor y disponible desde `available_on`. El catálogo conserva etapas, Kc y profundidad radicular |
| `precipitation_mm`, `et0_mm`, `tmax_mean_c`, `heat_days`, `oni` estacionales | Suma de lluvia, suma ET0, media Tmax, conteo térmico y anomalía ONI | Ventanas equivalentes completas. El KNN escala en candidatos históricos y usa distancia euclidiana ponderada, con contribuciones por variable |
| `labels.*` | Demanda y déficit en mm, estrés en días | Kernel FAO‑56, `label_source=simulation`. Los resultados representan un escenario completo |

`--farm` acepta un JSON con `_mock`, `region_id`, `available_on`, `crop` y `management`. `--hls` acepta `_mock`, `zona`, `source_refs` y `scenes`, con fecha ISO, identificador y pixels `red`, `nir` y `fmask`. Las reflectancias entran escaladas. Los IDs y fechas deben corresponder al gránulo original. `regional-features.json` conserva el reporte de nulos y procedencia. Las variables de clima, suelo y manejo se entregan al kernel mediante `prepare_comparison`.

## Fuentes, cobertura y pendientes

| Fuente | Cobertura y acceso | Evidencia de esta entrega |
|---|---|---|
| [NASA POWER](https://power.larc.nasa.gov/docs/services/) | Diario desde 1981, meteorología de 0,5° × 0,625° y solar principal de 1°. API pública | Snapshots Guanacaste y consulta nueva de Davis. El snapshot de Guanacaste empieza a cubrir radiación en 1984 |
| [NOAA CPC ONI](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/) y [RONI](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/) | Niño 3.4, ventanas móviles de tres meses, actualización mensual y acceso público | Snapshots versionados del repo. RONI es la referencia oficial de monitoreo de CPC |
| [ISRIC SoilGrids](https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_01.html) | Mapas de 250 m por profundidad, inventario por producto, REST público | Textura y retención del punto en seis capas. SOC y pH disponibles en catálogo, faltan en este snapshot. Profundidad efectiva y drenaje requieren evidencia local |
| [NASA HLS v2](https://hls.gsfc.nasa.gov/data-products/) | 30 m. L30 desde 2013 y S30 desde 2015 según plataforma. Por pasada, afectado por nubes | CMR encontró `HLS.S30.T16PFS.2026277T160119.v2.0` el 4 de octubre de 2026. La descarga parcial sin sesión devolvió HTTP 401. NDVI real pendiente de acceso Earthdata y extracción |
| [GPM IMERG Early V07](https://doi.org/10.5067/GPM/IMERG/3B-HH-E/07) | 0,1°, media hora, desde 2000 según el servicio consultado. Descarga GES DISC con Earthdata | Candidato para contraste de lluvia. Falta validar granulado, QC y agregación local |
| [SMAP SPL3SMP V9](https://nsidc.org/data/spl3smp/versions/9) | Diario, 36 km desde marzo de 2015. Earthdata Login | Candidato a humedad superficial regional |
| [ECOSTRESS LSTE V002](https://doi.org/10.5067/ECOSTRESS/ECO_L2T_LSTE.002) | 70 m, adquisición instantánea según pasada de la EEI desde 2018, Earthdata. [NASA anunció V003](https://www.earthdata.nasa.gov/data/alerts-outages/ecostress-version-3-level-2-data-products-released) | Falta verificar gránulos y máscara para la parcela antes de construir una serie térmica |
| [FAO-56](https://www.fao.org/4/x0490e/x0490e00.htm) e [IMN Liberia](https://www.imn.ac.cr/documents/10179/38326/Climatologia_MRLB24/fd20cc9c-01d4-44d5-bb77-3fb87c429ef0) | Parámetros de literatura y climatología de estación | Se conserva la estación seca de Liberia como contexto regional junto con las rotaciones de arroz, melón, caupí y sorgo del catálogo provisional |

Quedan pendientes la descarga y alineación de bandas HLS, climatología NDVI, precipitación efectiva, riesgo térmico por fase y agua disponible del perfil. Estos últimos requieren calendarios, umbrales y un perfil hidráulico revisados o las salidas del simulador. El exportador excluye escenarios reales con lluvia o ET₀ incompleta. La evaluación de un modelo XGBoost con etiquetas simuladas mide fidelidad al simulador. Validar predicciones agrícolas exige observaciones de campo.
