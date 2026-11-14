# Sensibilidad del kernel FAO-56

Generado con `python -m scripts.sensitivity`, kernel `fao56-kernel-0.1.0`, temporadas mayo–abril de 2013, 2015, 2023 (POWER, punto 10.55, −85.5).

Base: suelo loam FAO-56 Tabla 19, Dr0 = 0,5·TAW, secano (D1), siembras arroz 15-may, caupí y sorgo 15-oct, melón según `rotations.yaml`.

> **Preliminar:** la ET0 usada tiene `reviewed: false`. Repetir cuando Justin la revise.

Cada celda: cambio medio frente a la base (todas las rotaciones y años) · años en que cambia el orden entre rotaciones (de 3).

| Caso | ETc | Déficit | Días de estrés | Riego requerido |
|---|---|---|---|---|
| Kc ×0,9 | -10,0 % · 0 | -20,9 % · 0 | -5,2 % · 1 | -14,4 % · 0 |
| Kc ×1,1 | +10,0 % · 0 | +21,8 % · 0 | +6,1 % · 1 | +6,4 % · 0 |
| Dr0 = 0 (capacidad de campo) | +0,0 % · 0 | -3,6 % · 0 | -1,6 % · 0 | +0,0 % · 0 |
| Dr0 = 1·TAW (punto de marchitez) | +0,0 % · 0 | +1,7 % · 0 | +0,2 % · 0 | +0,0 % · 0 |
| θfc ×0,8 | +0,0 % · 0 | +27,8 % · 0 | +11,6 % · 1 | +1,4 % · 0 |
| θfc ×1,2 | +0,0 % · 0 | -21,2 % · 3 | -9,4 % · 2 | -0,8 % · 0 |
| θwp ×0,8 | +0,0 % · 0 | -11,0 % · 1 | -4,4 % · 2 | -3,1 % · 0 |
| θwp ×1,2 | +0,0 % · 0 | +12,4 % · 0 | +5,4 % · 1 | -0,9 % · 0 |
| Lluvia ×0,72 | +0,0 % · 0 | +16,7 % · 0 | +11,1 % · 1 | +0,7 % · 0 |
| Lluvia ×1,28 | +0,0 % · 0 | -14,3 % · 0 | -10,8 % · 1 | -3,8 % · 0 |

El riego requerido solo es distinto de cero en `rice_melon` (melón regado). Un cambio de orden con métricas casi iguales puede ser un empate roto por redondeo; revisar `sensitivity.csv` antes de interpretarlo.
