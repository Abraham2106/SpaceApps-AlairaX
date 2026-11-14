# Validación del kernel FAO-56

Este documento reúne lo que respalda (y lo que todavía no respalda) las métricas del kernel: la sensibilidad a sus parámetros (tarea 3.7) y la comparación manual con CROPWAT. Ninguna de las dos es validación de campo.

## Sensibilidad (tarea 3.7)

```powershell
python -m scripts.sensitivity --years 2013 2015 2023 --output-dir outputs/sensitivity
```

El script varía un parámetro a la vez frente a una base (suelo loam FAO-56, Dr0 = 0,5·TAW, secano) y corre las tres rotaciones en cada temporada mayo–abril. Escribe `sensitivity.csv` (formato largo, con valor, base, delta y delta %) y `sensitivity.md` (resumen). Tarda unos 5 s.

Última corrida: [docs/sensitivity/sensitivity.md](sensitivity/sensitivity.md) y [sensitivity.csv](sensitivity/sensitivity.csv). **Es preliminar:** la ET0 tiene `reviewed: false`. Hay que repetirla cuando se revise la ET0 y cuando Ant entregue suelo y calendarios.

Lectura de esa corrida:

- **Kc ±10 %** mueve ETc ±10 % y el déficit unos ±21 %. El orden entre rotaciones no cambia en déficit ni en riego.
- **θfc** es el parámetro más influyente. Con θfc ×1,2 el déficit baja 21 % y el orden por déficit cambia en los 3 años. El perfil de suelo revisado es la prioridad antes de interpretar diferencias de déficit entre rotaciones.
- **Dr inicial** casi no importa (≤4 %). Una temporada de mayo arranca con lluvias y el suelo se recarga pronto.
- **Lluvia ±28 %** (sesgo POWER vs IMN) mueve el déficit entre −14 % y +17 % sin cambiar el orden por déficit.
- **Días de estrés** cambian de orden en 1–2 años en varios casos. Las diferencias entre rotaciones en esa métrica son pequeñas, así que conviene reportarlas con su rango y no como ranking.

## Estrés térmico (tarea 3.6)

`simulate_rotation_detailed` agrega `heat_stress_days` por cultivo y para la rotación. Cuenta los días con `tmax ≥ heat_threshold_c` dentro de la etapa FAO `mid`, usada como aproximación de la floración. Solo el arroz tiene umbral citado (35 °C en antesis, Jagadish et al. 2007, en `crops.yaml`). Los cultivos sin umbral quedan `null`; nunca 0. Si falta `tmax` en algún día de la etapa, el valor queda `null` con un aviso. La métrica no forma parte del contrato v0.1.0.

## Comparación manual con CROPWAT

Pendiente. Correr CROPWAT 8.0 con los mismos insumos y llenar una fila por caso. Cada fila usa el suelo loam FAO-56 (θfc 0,25, θwp 0,12), salvo que se indique otro.

| Cultivo | Temporada | Siembra | Suelo | ETc CROPWAT (mm) | ETc kernel (mm) | Dif. % | Déficit o riego CROPWAT (mm) | Déficit o riego kernel (mm) | Dif. % | Notas |
|---|---|---|---|---|---|---|---|---|---|---|
| Arroz secano | 2015 | 15-may | loam | | | | | | | |
| Melón regado | 2015–16 | 01-dic | loam | | | | | | | |
| Caupí | 2015 | 15-oct | loam | | | | | | | |
| Sorgo | 2015 | 15-oct | loam | | | | | | | |

Los valores del kernel salen de `simulate_rotation_detailed(...)["per_crop"]`, campos `crop_water_demand_mm` y `modeled_water_deficit_mm`, y de `irrigation_requirement_mm` para el melón.

Diferencias esperadas, que hay que anotar antes de llamar error a una discrepancia:

- **ET0.** CROPWAT suele trabajar con ET0 mensual y la interpola. El kernel usa ET0 diaria Penman-Monteith. Para comparar ETc, cargar en CROPWAT la ET0 diaria o los promedios mensuales del mismo archivo `datasets/processed/et0/`.
- **Lluvia efectiva.** CROPWAT ofrece USDA SCS, porcentaje fijo y otros. El kernel usa D3 (RO = 0,3·max(0, P − 60)) y deja que el balance descarte el exceso por percolación. Usar en CROPWAT la opción "no effective rain" o la más parecida, y anotar cuál.
- **Etapas y Kc.** Usar las mismas duraciones y Kc de `crops.yaml`. CROPWAT ajusta Kc mid y end por clima si se le pide; desactivarlo o aplicar el mismo ajuste.
- **Zr.** El kernel usa Zr constante por ciclo (D4). CROPWAT hace crecer la raíz; fijar Zr inicial = Zr máximo.
- **Barbecho.** El kernel simula el barbecho entre cultivos (D5). CROPWAT corre cada cultivo aislado. Comparar por cultivo, no por rotación.

Criterio provisional: diferencias de ETc ≤5 % y de déficit ≤15 % se consideran consistentes. Las mayores se explican en Notas o se abren como issue.
