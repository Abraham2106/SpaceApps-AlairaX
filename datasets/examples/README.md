# `datasets/examples/`

Datos de ejemplo **solo para tests y desarrollo local**. No son datos de producción
ni representan una finca real.

## `power_liberia_urbano_2015_2025.csv`

- **Origen**: NASA POWER, punto **urbano** de Liberia, Guanacaste, Costa Rica.
- **Periodo**: 2015-01-01 a 2025-12-31, resolución diaria.
- **Columnas**: `fecha`, `PRECTOTCORR` (mm/día), `T2M_MAX` (°C), `T2M_MIN` (°C),
  `RH2M` (%), `WS2M` (m/s), `ALLSKY_SFC_SW_DWN` (MJ m-2 día-1), `EVPTRNS`,
  `GWETROOT`.
- **Advertencias**:
  - `EVPTRNS` **no es ET0**; no debe usarse como entrada del kernel.
  - `GWETROOT` solo sirve para chequear coherencia, nunca como entrada.
  - Es un punto urbano: sirve para ejercitar el pipeline, no como referencia
    agroclimática de una finca.
