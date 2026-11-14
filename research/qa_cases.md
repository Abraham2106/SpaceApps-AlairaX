# QA del kernel FAO-56: casos manuales, unidades y rangos de ciclo (tarea 2.4)

Autor: I3 / Ant (agente de apoyo) · Fecha: 2026-11-14 · Estado: revisión técnica; **no sustituye la aprobación científica escrita** (pendiente humana).

Los tres casos se calcularon a mano con aritmética exacta (fracciones) en un script independiente, sin leer la salida del kernel, y se compararon después **sin corregir el kernel**. Resultado: los tres coinciden con el kernel en todas las series (tolerancia 1e-3 mm, por el redondeo a 4 decimales de la salida diaria). Están codificados en `backend/tests/test_kernel_qa.py` (`AntHandCalculatedCasesTests`, 3 tests, ya sin `expectedFailure`).

## 0. Ecuaciones y convenciones (FAO-56, Allen et al. 1998)

- ETc = Kc · ET0. Kc por etapa con interpolación lineal (Eq. 66), indexada por día de ciclo desde 0.
- TAW = 1000 (θfc − θwp) Zr (Eq. 82); RAW = p · TAW (Eq. 83).
- Ks = (TAW − Dr) / ((1 − p) TAW) si Dr > RAW, si no 1 (Eq. 84); se usa el Dr del **inicio** del día.
- Dr(i) = Dr(i−1) − (P − RO) − I + ETa + DP, con 0 ≤ Dr ≤ TAW (Eq. 85). DP = exceso por debajo de 0.
- Convención del proyecto (no FAO-56): RO = 0.3 · max(0, P − 60) (decisión D3). Barbecho: Kc 0.15, Zr 0.15 m, p 0.5 (D5). Al cambiar Zr, Dr se reescala por TAW_nuevo / TAW_anterior.
- Entradas comunes: ET0 = 5.0 mm/día constante, θfc = 0.30, θwp = 0.15 (m³/m³), secano, 1 de mayo de 2020 como día 0.
- "Almacenamiento" = TAW − Dr (mm).

## 1. Caso 1: sin estrés (Kc por etapas, lluvia pequeña)

Entradas: Kc (ini, mid, end) = (0.4, 1.2, 0.6); etapas [2, 2, 2, 2] días; Zr = 1.0 m; p = 0.5; agua inicial 80 % de TAW; lluvia 10 mm el día 2; 8 días de cultivo.

- TAW = 1000 · 0.15 · 1.0 = 150 mm; RAW = 75 mm; Dr0 = 0.2 · 150 = 30 mm (almacenamiento 120).
- Kc por día: 0.4, 0.4, 0.4, 0.8, 1.2, 1.2, 1.2, 0.9 (ini plano; desarrollo de 0.4 a 1.2 en 2 días; mid; fin de 1.2 a 0.6 en 2 días, que empieza en 1.2 y baja a 0.9).
- ETc = Kc · 5 = 2, 2, 2, 4, 6, 6, 6, 4.5 mm.
- Dr máximo = 52.5 < RAW = 75, así que Ks = 1 todos los días y ETa = ETc.
- 10 mm < 60 mm, RO = 0.

| día | lluvia | ETc | Dr inicio | Dr fin | almacenamiento |
|---|---|---|---|---|---|
| 0 | 0 | 2.0 | 30 | 32 | 118 |
| 1 | 0 | 2.0 | 32 | 34 | 116 |
| 2 | 10 | 2.0 | 34 | 26 | 124 |
| 3 | 0 | 4.0 | 26 | 30 | 120 |
| 4 | 0 | 6.0 | 30 | 36 | 114 |
| 5 | 0 | 6.0 | 36 | 42 | 108 |
| 6 | 0 | 6.0 | 42 | 48 | 102 |
| 7 | 0 | 4.5 | 48 | 52.5 | 97.5 |

Totales: demanda 32.5 mm, déficit 0, días de estrés 0. Kernel: coincide.

## 2. Caso 2: estrés con Ks y percolación profunda tras lluvia con escorrentía

Entradas: Kc = 1.0 plano; etapas [2, 1, 2, 1]; Zr = 0.4 m; p = 0.5; agua inicial 60 %; lluvia 80 mm el día 4; 6 días de cultivo.

- TAW = 1000 · 0.15 · 0.4 = 60 mm; RAW = 30 mm; Dr0 = 0.4 · 60 = 24 mm. ETc = 5 mm/día.
- Día 0: Dr 24 ≤ 30, Ks = 1, Dr = 29. Día 1: Dr 29 ≤ 30, Ks = 1, Dr = 34 (almacenamiento 26).
- Día 2: Dr inicio 34 > 30. Ks = (60 − 34) / (0.5 · 60) = 26/30 = 0.866667. ETa = 4.333333. Dr = 38.333333.
- Día 3: Ks = (60 − 38.333333)/30 = 0.722222. ETa = 3.611111. Dr = 41.944444.
- Día 4: Ks = (60 − 41.944444)/30 = 0.601852. ETa = 3.009259. RO = 0.3 · (80 − 60) = 6; infiltración = 74. Dr = 41.944444 − 74 + 3.009259 = −29.046296, que se acota a 0: **DP = 29.046296**, Dr = 0.
- Día 5: Ks = 1, ETa = 5, Dr = 5 (almacenamiento 55).
- Déficit (ETc − ETa): día 2 = 2/3, día 3 = 25/18, día 4 = 215/108; total 437/108 = 4.046296 mm.
- Días con Ks < 1: 3 (días 2, 3, 4). Demanda total = 6 · 5 = 30 mm.

| día | Ks | ETa | déficit | Dr fin | almacenamiento |
|---|---|---|---|---|---|
| 0 | 1 | 5 | 0 | 29 | 31 |
| 1 | 1 | 5 | 0 | 34 | 26 |
| 2 | 0.866667 | 4.333333 | 0.666667 | 38.333333 | 21.666667 |
| 3 | 0.722222 | 3.611111 | 1.388889 | 41.944444 | 18.055556 |
| 4 | 0.601852 | 3.009259 | 1.990741 | 0 | 60 |
| 5 | 1 | 5 | 0 | 5 | 55 |

Kernel: coincide, incluidos RO = 6 y DP = 29.046296 el día 4.

## 3. Caso 3: cambio de Zr al pasar a barbecho (reescalado de Dr)

Entradas: Kc = 0.8 plano; etapas [1, 1, 1, 1]; Zr = 0.6 m; p = 0.5; agua inicial 50 %; lluvia 20 mm el día 1 y 30 mm el día 5; 4 días de cultivo y 3 de barbecho.

- Cultivo: TAW = 1000 · 0.15 · 0.6 = 90 mm; RAW = 45; Dr0 = 45; ETc = 0.8 · 5 = 4 mm.
- Día 0: Ks = 1, Dr = 49 (almacenamiento 41).
- Día 1: Dr inicio 49 > 45; Ks = (90 − 49)/45 = 0.911111; ETa = 3.644444; Dr = 49 − 20 + 3.644444 = 32.644444; déficit 16/45 = 0.355556.
- Día 2: Ks = 1, Dr = 36.644444. Día 3: Ks = 1, Dr = 40.644444 (almacenamiento 2221/45 = 49.355556).
- Cambio a barbecho (Zr 0.15 m): TAW = 22.5 mm; Dr = 40.644444 · 22.5/90 = 10.161111. RAW = 11.25; Ks = 1.
- Día 4 (barbecho): ETc = 0.15 · 5 = 0.75; Dr = 10.911111 (almacenamiento 11.588889).
- Día 5: Dr = 10.911111 − 30 + 0.75 = −18.338889, acotado a 0: **DP = 18.338889**, almacenamiento 22.5.
- Día 6: Dr = 0.75 (almacenamiento 21.75).
- Métricas (solo días de cultivo): demanda 16.0 mm; déficit 16/45 = 0.355556 mm; 1 día de estrés. El estrés queda `None` en barbecho. El kernel emite una advertencia de reescalado.

Kernel: coincide en todas las series.

## 4. Revisión de coherencia de unidades

| magnitud | unidad en el código | fuente / transformación | observación |
|---|---|---|---|
| ET0, ETc, ETa, P, RO, I, DP, Dr, TAW, RAW | mm (por día en flujos) | Eq. 6, 66, 82–85 | coherente en todo el balance |
| θfc, θwp | m³/m³ | SoilGrids `wv0033`, `wv1500` ÷ 1000 (el producto los entrega en 10⁻³ cm³/cm³) | el factor 1/1000 es el de la documentación de SoilGrids; confirmar al ingerir |
| Zr | m | Tabla 22 (m) | TAW pasa a mm por el factor 1000 de Eq. 82 |
| p | adimensional (fracción de TAW) | Tabla 22 | el p del arroz es "de saturación", ver REVIEW_I3 |
| Kc, Ks | adimensional | Tabla 12 / Eq. 84 | |
| Tmax, umbral de calor | °C | POWER `T2M_MAX` | |
| elevación | m | 94.64 m, POWER | usada en presión atmosférica de ET0 |

Hallazgo de etiquetado (corregido): `kernel.py` rotulaba como "Tabla 13" los rangos estacionales de ETc; su origen es el cuadro de necesidades hídricas estacionales aproximadas del Manual FAO de Riego No. 3, cap. 2. La etiqueta ahora dice "cap. 2".

## 5. Rangos de ciclo FAO frente al snapshot 2015

Rangos de ETc estacional (Manual FAO No. 3, cap. 2): arroz 450–700 mm, melón 400–600 mm, sorgo 450–650 mm. Valores del snapshot `backend/tests/snapshots/kernel_metrics_2015.json` (demanda ETc de las métricas del kernel; secano, una sola temporada):

| cultivo | kernel 2015 (mm) | rango FAO (mm) | veredicto |
|---|---|---|---|
| arroz | 810.073 | 450–700 | **por encima** (+16 % sobre el tope) |
| melón | 615.129 | 400–600 | ligeramente por encima (+2.5 %) |
| leguminosa (caupí) | 343.767 | no verificado aquí (el rango del código corresponde a "Bean") | sin veredicto |
| sorgo | 470.088 | 450–650 | dentro |

Aproximación de control (derivada, no medida): con los Kc del YAML la suma ponderada de Kc de un ciclo es de unos 168.75 días-equivalentes en arroz (30·1.05 + 30·1.125 + 60·1.2 + 30·1.05), de modo que 810 mm implica una ET0 media cercana a 4.8 mm/día durante 150 días. El exceso del arroz se explica por el ciclo de 150 días con Kc de paddy (1.05–1.20) aplicado a secano; el rango FAO corresponde a ciclos más cortos y a otras condiciones. Es una señal de revisión del parámetro, no un error de ecuaciones; el balance reproduce las ecuaciones citadas en los 3 casos manuales.

## 6. Hallazgos de calendario

- Con las fechas anteriores, el caupí (15-oct) y el sorgo (01-oct) se solapaban con un ciclo de arroz sembrado el 01-jun de 150 días (terminaba el 28-oct), y `template_rotation('rice_legume', 2015)` lanzaba un error de solape. Se aplicó: arroz el 15-may (termina el 11-oct) y sorgo el 15-oct. El calendario local sigue sin verificar.

## 7. Qué queda pendiente (humano)

- Aprobación científica final por escrito de Ant y Justin (no marcada).
- Comparación con CROPWAT u otra referencia equivalente (tarea del plan, no hecha aquí).
- Decidir los parámetros de arroz.
