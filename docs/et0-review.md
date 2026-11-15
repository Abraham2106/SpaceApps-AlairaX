# Revisión técnica de ET₀ en Guanacaste

ET₀ es la evapotranspiración diaria de una superficie de referencia, expresada
en mm/día. El kernel usa ET₀ y el coeficiente de cultivo Kc para estimar la
demanda de agua del cultivo. La ET₀ también entra en las variables con las que
se seleccionan los años análogos.

Se recalculó el archivo con `scripts.export_et0.build_et0` sobre los 47 JSON
normalizados de NASA POWER que coinciden con
`datasets/processed/climate/power_10.55_-85.5_*.json`. El cálculo usa
Penman–Monteith FAO‑56 y la elevación de cuadrícula POWER de 94,64 m.

- Los 16 754 valores diarios coinciden con el archivo existente, incluidos
  los nulos. Solo difiere la fecha de generación.
- Hay 15 653 valores entre 1,141 y 9,225 mm/día y 1 101 fechas nulas.
- Hay 42 ventanas históricas completas en ET₀, desde el 1 de abril del año
  base hasta el 30 de abril del año siguiente.
- En la ventana de consulta abril–octubre de 2026 falta ET₀ el **7 de
  septiembre**. El insumo POWER de radiación solar de ese día es nulo.

El archivo evaluado antes de registrar la aprobación es
`datasets/processed/et0/et0_10.55_-85.5.json`
(SHA-256 `b82718134bf7986df24414fd19ed4b2b05179bb742cdddab4869454ec8d042d1`).
El recálculo demuestra reproducibilidad. El 14 de noviembre de 2026,
Abraham confirmó el método para este artefacto. Se registró
`reviewed: true` y `reviewed_by: "Abraham2106"`. El SHA-256 con esos dos
campos actualizados es
`6e0782d51a82a73bf0a1e1c91e9bf9d36579cc89abf5d766216421152640eaf6`.
La aprobación cubre el método. El contraste con observaciones de una
estación local sigue pendiente.

El catálogo operativo se regeneró para abril–octubre con ONI ASO.
Quedaron disponibles Niño fuerte, Neutro y Niña. «Como 2026» requiere
recuperar la radiación del 7 de septiembre o acordar y documentar una
ventana distinta.
