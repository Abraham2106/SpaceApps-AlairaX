# Revisión I2 → I3 (Ant): parámetros de cultivo Fase 1

Fecha: 2026-11-14 · Autor: I2 (kernel científico) · Destino: I3 / Ant, tarea 2.2
Estado: **todos los valores con `verified: false`**. Este archivo documenta la
comparación manual contra FAO-56 (Tablas 11 y 12) y lo que quedó en `null`.

## 1. Valores llenados (coinciden con FAO-56)

| cultivo | Kc ini / mid / end | FAO-56 Tabla 12 (fila) | etapas (días) | FAO-56 Tabla 11 (fila) |
|---|---|---|---|---|
| `rice` | 1.05 / 1.20 / 0.90 | Rice (end 0.90–0.60; se tomó 0.90) | 30/30/60/30 = 150 | Rice, trópicos/Mediterráneo |
| `melon` | 0.50 / 1.05 / 0.75 | Sweet Melons (ini = grupo Cucurbitaceae) | 25/35/40/20 = 120 | Sweet melons, May, Mediterráneo |
| `cowpea` | 0.40 / 1.05 / 0.60 | Green Gram and Cowpeas (ini = grupo Leguminosae; end 0.60–0.35) | 20/30/30/20 = 110 | Green gram, cowpeas, March, Mediterráneo |
| `sorghum` | 0.30 / 1.05 / 0.55 | Sorghum, grain (mid 1.00–1.10; se tomó 1.05) | 20/35/40/30 | Sorghum, May/June |

Zr y p (Tabla 22): rice 1.0 m / 0.20 · melon 1.5 m / 0.40 · cowpea 1.0 m / 0.45 ·
sorghum 2.0 m / 0.55. Se usó el extremo **superior** de Zr en todos los casos
(Tabla 22, nota 1: valores mayores para modelar secano).

## 2. Quedó en `null`

- `mucuna` y `canavalia`: **todos** los parámetros (`kc_*`, `stage_days`,
  `root_depth_max_m`, `p_depletion`, `heat_threshold_c`, `source`). FAO-56 no las
  lista en Tablas 11, 12 ni 22. No se inventó nada.
- `heat_threshold_c`: `null` en melón, caupí y sorgo (sin fuente citada).
  Solo arroz tiene valor (35 °C, ver punto 3).
- `source`: `null` en mucuna y canavalia.

## 3. Decisiones que necesitan revisión de I3

1. **Arroz `p_depletion = 0.20`**: Tabla 22, nota 4, lo define "de saturación"
   (paddy), no como fracción de TAW. Aplicar `p·TAW` en secano es extrapolación.
2. **Arroz Kc** (1.05/1.20/0.90): Tabla 12 los da para arroz de paddy con lámina
   de 0.10–0.20 m. La rotación usa `regime="upland"` (D2): mismo desajuste.
3. **Caupí `kc_end = 0.60`**: FAO da rango 0.60 (cosecha fresca/cobertura) y
   0.35 (grano seco). Se eligió 0.60 por el uso como cobertura en `rice_legume`.
4. **Sorgo grano vs forrajero**: las Tablas 12/11 tienen sorgo grano; la rotación
   dice "sorgo forrajero" (FAO forrajero: Kc mid 1.20, end 1.05). Hay warning.
5. **Etapas del melón**: fila "May, Mediterranean" de Tabla 11; Guanacaste no es
   mediterráneo y no hay fenología local en el repo.
6. **Umbral de calor del arroz**: 35 °C en antesis no es FAO-56; fuente
   Jagadish et al. (2007), citada en Shrestha et al. (2022). Aplica a un evento
   de antesis, no a un umbral diario genérico.

## 4. Fuentes

- FAO-56, Allen et al. (1998): Tabla 11 y 12 <https://www.fao.org/3/x0490e/x0490e0b.htm>,
  Tabla 19 <https://www.fao.org/3/x0490e/x0490e0c.htm>,
  Tabla 22 <https://www.fao.org/3/x0490e/x0490e0e.htm>.
- Shrestha et al. (2022), *Front. Plant Sci.*, doi:10.3389/fpls.2022.1050599.
