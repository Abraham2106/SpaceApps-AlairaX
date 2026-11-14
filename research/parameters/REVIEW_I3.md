# Revisión I3 (Ant) de parámetros de cultivo, tarea 2.2

Fecha: 2026-11-14 · Revisa: `crops.yaml` y `rotations.yaml` v0.1.0 (con `REVIEW_I2.md`).
Regla aplicada: no se editó `crops.yaml`. Ninguna corrección tiene una cita primaria verificable de forma independiente en esta sesión (las celdas de Kc ini de FAO-56 Tabla 12 para melón, caupí y sorgo son imágenes en la copia web; solo se confirmaron los valores de grupo), así que todo cambio queda como **propuesta**. `verified` sigue en `false` en todos los cultivos.

Leyenda: **C** = confirmado contra fuente; **P** = propuesta, requiere decisión humana; **N** = null, sin fuente.

Fuentes: FAO-56 (Allen et al. 1998) Tablas 11 y 12 <https://www.fao.org/3/x0490e/x0490e0b.htm>, Tabla 22 <https://www.fao.org/3/x0490e/x0490e0e.htm>; Manual FAO No. 3 (arroz inundado), capítulo 2, URL exacta por confirmar; Shrestha et al. (2022), doi:10.3389/fpls.2022.1050599.

## Arroz (`rice`)

| parámetro | valor | estado | nota |
|---|---|---|---|
| Kc ini / mid / end | 1.05 / 1.20 / 0.90 | C para paddy; **P** para upland | Tabla 12 da 1.05 / 1.20 / 0.90-0.60 para arroz inundado. No hay Kc FAO-56 de arroz de secano. |
| Duraciones | 30/30/60/30 = 150 d | C (Tabla 11) | Fuera del rango de ciclo del Manual 3 si se compara la demanda: 810 mm frente a 450-700 (ver `qa_cases.md`). Calendario local no verificado. |
| Zr máx | 1.0 m | C (Tabla 22, rango 0.5-1.0) | Extremo superior por la nota 1 (secano). |
| p | 0.20 | C como cita; **P** de uso | La Tabla 22 lo da "de saturación", no fracción de TAW; usarlo como p·TAW en secano es extrapolación. Con p = 0.20 el estrés aparece muy temprano. Decisión humana: mantener, o usar un p de cereal de secano con cita. |
| Umbral de calor | 35 °C | C como cita secundaria | Jagadish et al. (2007) vía Shrestha et al. (2022); aplica a antesis, no a un día cualquiera. |
| Profundidad de lámina (flooded) | 100 mm (WL) | no modelado | El kernel simplifica el régimen inundado: Dr = 0 y demanda = ETc + percolación. |
| Percolación (flooded) | 4 mm/d | C solo contra Manual 3 (4/6/8 mm/d según suelo); **verificado: falso** como valor único | El capítulo posterior de FAO da 2/5/8; datos de campo en Tailandia, 0-3 mm/d. Saturación inicial de 200 mm (SAT) no modelada. Mantener 4 mm/d como supuesto declarado, con rango 0-8 para sensibilidad. |

## Melón (`melon`)

| parámetro | valor | estado | nota |
|---|---|---|---|
| Kc ini / mid / end | 0.50 / 1.05 / 0.75 | C parcial | mid y end de la fila Sweet Melons; el ini 0.50 es el valor de grupo Cucurbitaceae (la celda individual es imagen). |
| Duraciones | 25/35/40/20 = 120 d | C (Tabla 11) | Fila "May, Mediterráneo"; no es el clima de Guanacaste. Rango de ciclo FAO para el melón 400-600 mm; kernel 2015 da 615 mm (2.5 % por encima). |
| Zr máx | 1.5 m | C (Tabla 22, rango 0.8-1.5) | Extremo superior. |
| p | 0.40 | C (Tabla 22) | |
| Calor | null | N | Sin fuente. |

## Caupí (`cowpea`, sustituto de la leguminosa de cobertura)

| parámetro | valor | estado | nota |
|---|---|---|---|
| Kc ini / mid / end | 0.40 / 1.05 / 0.60 | C parcial | end 0.60 = cosecha fresca; 0.35 = grano seco. **P**: decidir el destino; para cobertura sin cosecha de grano 0.60 es defendible, pero es decisión de agronomía, no de FAO. |
| Duraciones | 20/30/30/20 = 110 d | C (Tabla 11) | Fila Mediterránea (marzo). |
| Zr máx | 1.0 m | C (Tabla 22, rango 0.6-1.0) | |
| p | 0.45 | C (Tabla 22) | |
| Calor | null | N | |

Riesgo: el rango estacional de ETc que usa el kernel para la leguminosa corresponde a "Bean" y no a caupí; no se emite veredicto con el 343.8 mm del snapshot.

## Sorgo (`sorghum`)

| parámetro | valor | estado | nota |
|---|---|---|---|
| Kc ini / mid / end | 0.30 / 1.05 / 0.55 | C parcial | ini 0.30 = valor de grupo Cereals; mid 1.00-1.10 (se tomó el punto medio). Valores de **grano**. |
| Duraciones | 20/35/40/30 = 125 d | C (Tabla 11) | Nota: `REVIEW_I2.md` y el YAML dicen 130 d en la fuente; la suma de las etapas listadas es 125. Revisar la fila de Tabla 11 (discrepancia aritmética detectada, no resuelta). |
| Zr máx | 2.0 m | C (Tabla 22, rango 1.0-2.0) | |
| p | 0.55 | C (Tabla 22) | |
| Forrajero | **P** | no aplicado | La rotación dice "sorgo forrajero"; FAO da para sorgo dulce/forrajero Kc mid 1.20, end 1.05, p 0.50. Cambiarlo es decisión humana: cambia la demanda. |

## Mucuna y canavalia

Todo `null` (N). FAO-56 no las lista. No hay fuente primaria aportada en esta revisión. No se inventa nada. La rotación `rice_legume` usa caupí como sustituto declarado; esto debe aparecer en el texto público.

## Rotaciones (`rotations.yaml`)

- Fechas: 05-15 arroz; 12-01 melón; 10-15 caupí; 10-15 sorgo. Todas **no verificadas** con productores ni con fuente local (IMN, MAG, INTA). Las fechas anteriores (arroz 06-01, sorgo 10-01) se solapaban: el arroz de 150 d terminaba el 28-oct y el kernel daba error. Se adelantó el arroz al 15-may (termina el 11-oct) y el sorgo pasó al 15-oct. Pendiente humano: validar con productores y citar.
- Régimen `upland`: es supuesto D2; FAO-56 no cubre arroz de secano.

## Lista de propuestas para decisión humana

1. Arroz: mantener p 0.20 o sustituir por un valor con cita para secano.
2. Arroz: ciclo 150 d y Kc de paddy; evaluar un ciclo local o más corto con fuente.
3. Caupí: kc_end 0.60 o 0.35 según el destino.
4. Sorgo: grano o forrajero; revisar la suma de etapas (125 frente a 130).
5. Calendarios con fuente local (el solape ya se corrigió).
6. ~~Corregir la etiqueta "Tabla 13" en `kernel.py`~~: hecho, ahora dice "cap. 2".
