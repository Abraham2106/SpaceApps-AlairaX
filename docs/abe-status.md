# Entrega de Abe · 14 noviembre 2026

Implementación de Abe asistida por Codex y tres subagentes. Estado comprobado mediante pruebas automáticas, consultas públicas reales y replay de la caché. Entrega preparada para la rama `main`.

Última verificación: **96 pruebas pasan** con `python -m unittest discover -s backend/tests -q`. Cubren contratos, ingesta, KNN, preparación, unidades de suelo observadas y comparación con fixtures; no validan las ecuaciones del kernel científico todavía pendiente.

| WBS | Entrega | Estado y dependencia |
|---|---|---|
| 1.3 | Contratos Pydantic, cinco JSON Schema (incluida configuración), fixture completo AMJ–OND, mocks | Implementado v0.1.0; fechas provisionales pendientes de Ant/Justin |
| 4.1 | POWER 1981–2026, ONI/RONI, caché, metadatos, unidades y QC | Descargado; punto agrícola/suelo y calibración local pendientes |
| 4.2 | Features por ventana equivalente y completa | Implementado y probado; requiere ET0 revisada de Justin |
| 4.3 | KNN ponderado, escalado histórico, cuatro escenarios, sensibilidad a k | Implementado; k=3 en Niño fuerte por decisión explícita y k=5 en los demás. Real `unavailable` por ET0 |
| 4.4 | Comparador por mismo año con kernel inyectable | Implementado; integración probada con callback sintético |
| 4.5 | Deltas pareados, p10/p50/p90, faltantes y límites | Implementado y probado; resultados físicos requieren kernel real |
| 6.1 | Preparación de entradas revisadas, export precalculado y orquestación análogos→kernel→JSON | Implementado; manifiesto SHA-256, protección de archivos y cuatro mocks disponibles para Angelina |
| 6.2 | Conexión hasta la UI con datos reales | Pendiente de UI, kernel y parámetros científicos |
| 7.2 (apoyo) | README, método científico y checklist de revisión | Documentados; revisión científica de Ant/Justin pendiente |
| 7.9 | Submit for Judging | Pendiente de los entregables del equipo y envío del Team Owner |

## Datos descargados

- 46 intervalos anuales, 16.754 fechas únicas desde 1981-01-01 hasta 2026-11-14.
- 42 años completos con las seis variables: 1984–2025. Radiación ausente en 1981–1983.
- QC: 1.117 avisos (1.095 radiaciones ausentes en 1981–1983, 21 valores ausentes en 2026 y una lluvia extrema preservada).
- Último dato meteorológico disponible: 2026-11-11; radiación: 2026-11-09, con un hueco adicional en septiembre.
- NOAA: 921 ventanas ONI y 921 RONI, conservadas por separado con snapshot y fecha.
- El archivo de prueba de cinco días de 2024 se solapa con el anual; el pipeline deduplica filas idénticas y rechaza conflictos.

## Para integrar

Justin entrega ET0 con el formato de [analog-method.md](analog-method.md), más el callback `simulate_rotation` de [contract-handoff.md](contract-handoff.md). Ant confirma finca, suelo, parámetros y calendarios. Angelina puede consumir ya `frontend/public/data/`, manteniendo visible `_mock: true`.

Los archivos reales `datasets/processed/analogs/` informan el bloqueo ET0. Los JSON de `frontend/public/data/` contienen fixtures sintéticos para desarrollar la interfaz; no se presentan como resultados reales. El kernel FAO-56, el frontend, el despliegue y la entrega final mantienen sus responsables del WBS.

## Avance posterior de integración

- `scripts/prepare_comparison.py` construye las tres rotaciones por análogo desde los artefactos revisados. Los calendarios y el manejo se entregan por año; no se generan fechas ni parámetros científicos por defecto. [Formato](prepare-inputs.md).
- El setup puede confirmar el mismo punto que se descargó como provisional, conservando intactos los snapshots originales. La identidad (ID, nombre y coordenadas) debe seguir coincidiendo.
- La inspección de cobertura real abril–octubre/ONI ASO cuenta tres años de Niño fuerte, 21 neutros y diez de Niña antes de disponer de ET0. La ventana 2026 incluye un hueco de radiación. [Decisión de k](decisions.md).
- Tras los primeros timeouts, SoilGrids respondió HTTP 200 en el navegador y en la CLI. Se descargaron textura y retención a 33/1500 kPa en seis profundidades; el reporte es `partial`. Capacidad de campo, marchitez y profundidad radicular para el kernel siguen `null` hasta revisión científica. [Evidencia](soil-readiness.md).
- [Método científico](scientific_method.md) y [revisión pendiente por responsable](method-review.md) redactados para apoyar a Ant.
