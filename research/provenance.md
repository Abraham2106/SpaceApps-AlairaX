# Procedencia, supuestos e incertidumbre (tarea 2.3)

Fecha: 2026-11-14 · Autor: I3 / Ant. Complementa `research/source_matrix.md`. Nada aquí es validación de campo.

## 1. Escalas espaciales y tipo de dato

| capa | resolución | tipo | límite principal |
|---|---|---|---|
| NASA POWER (clima diario) | 0.5° (~50 km) | reanálisis/modelo, no estación | un punto provisional (10.55, -85.50) representa una celda; lluvia puntual y eventos convectivos se suavizan |
| SoilGrids (suelo) | 250 m | predicción espacial por aprendizaje automático | incertidumbre del modelo no propagada; profundidad efectiva y capacidad de campo no medidas en finca |
| HLS | 30 m | imagen satelital | no entra al balance; sirve solo de contexto |
| IMN AIDO Liberia | puntual | observación | una estación frente a una celda de 0.5°; comparabilidad limitada |
| NOAA ONI/RONI | global (Niño 3.4) | índice | ONI se usa como característica exploratoria; RONI es el monitoreo oficial |

La finca real no está confirmada; el modelo describe un punto, no una parcela.

## 2. Matriz de incertidumbre

| fuente de incertidumbre | efecto sobre el resultado | cuantificada | estado |
|---|---|---|---|
| Resolución POWER 0.5° | sesgo y suavizado de lluvia | parcial: POWER ≈ +29.5 % sobre IMN (≈ +26 % con mediana, 2005-2025, AIDO) | el origen de la cifra "+28 %" del pitch no está verificado |
| Cambio de nivel POWER antes y después de 2001-2005 | posible discontinuidad en la serie | no | causa no verificada |
| Huecos: radiación 1981-1983 | esos años no tienen ET0 | sí (excluidos del conjunto, 42 años completos 1984-2025) | documentado en QC |
| Huecos del kernel | ≤ 3 días se interpolan (ET0) con lluvia 0; > 3 días anulan el balance | sí, con advertencia | convención D |
| SoilGrids 250 m | θfc, θwp sin intervalo | no | pendiente humano |
| Parámetros FAO no locales | Kc, etapas y Zr tomados de fila mediterránea y de arroz paddy | rango con sensibilidad ±28 % en `scripts.sensitivity` | calendarios locales sin verificar |
| Régimen de arroz | upland frente a paddy; p "de saturación" | no | decisión humana |
| Inundado simplificado | percolación 4 mm/d sin lámina ni saturación | rango 0-8 mm/d documentado | no modelado |
| Escorrentía RO = 0.3 max(0, P-60) | convención del proyecto | no | supuesto D3 |
| Muestra de análogos (k = 3 o 5) | cuantiles descriptivos, no intervalos de confianza | n visible | decisión del equipo |
| ET0 | calculada por Justin, revisión pendiente | no | `reviewed` falso hasta revisión humana |

## 3. Advertencias de uso

- Las métricas son modeladas. No se infiere rendimiento, ahorro ni rotación ganadora.
- La banda entre análogos no es toda la incertidumbre.
- El rango estacional de ETc del Manual FAO No. 3 se usó como control de razonabilidad: arroz 810 mm (rango 450-700) está por encima; ver `research/qa_cases.md`.
- IMN 1,652.7 mm/año: no verificado. La cifra verificada es 1,545.9 mm (AIDO, 2005-2025).
- Evento extremo del 2020-11-03: se conserva; no eliminar solo por superar 500 mm/día (pendiente de revisión humana).
- Sin validación de campo.
