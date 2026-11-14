"""PROVISIONAL — lo congela Abe en M1, issue 001.

Contrato de entrada/salida del kernel FAO-56 (Allen et al., 1998).
Ninguna función de este módulo elige rotaciones ni declara "mejor" escenario:
solo valida datos y describe números físicos y advertencias.

Convenciones de unidades (explícitas en nombres de campos y docstrings):
- agua: mm, mm/día
- radiación: MJ m-2 día-1
- temperatura: °C
- humedad relativa: %
- viento a 2 m: m/s
- contenido de agua del suelo: m3/m3

Referencias:
- FAO-56, Allen, Pereira, Raes & Smith (1998). Crop evapotranspiration.
  https://www.fao.org/3/x0490e/x0490e00.htm
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import ClassVar, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --------------------------------------------------------------------------- #
# Utilidades compartidas
# --------------------------------------------------------------------------- #

_MAX_GAP_DAYS = 3
_SENTINEL = -999.0


def _validate_mmdd(value: str) -> str:
    """Valida una fecha en formato ``MM-DD`` (año resuelto por temporada, D6)."""
    try:
        datetime.strptime(f"2000-{value}", "%Y-%m-%d")
    except ValueError as exc:  # pragma: no cover - mensaje claro
        raise ValueError(f"'{value}' no es una fecha MM-DD válida") from exc
    return value


def _nan_runs(mask: pd.Series) -> list[tuple[int, int]]:
    """Rachas de ``True`` en ``mask`` como pares ``(posición_inicial, longitud)``."""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for pos, flag in enumerate(mask.to_numpy()):
        if flag and start is None:
            start = pos
        elif not flag and start is not None:
            runs.append((start, pos - start))
            start = None
    if start is not None:
        runs.append((start, len(mask) - start))
    return runs


# --------------------------------------------------------------------------- #
# Entradas
# --------------------------------------------------------------------------- #


class SiteInfo(BaseModel):
    """Ubicación del sitio (grados decimales, elevación en m s.n.m.)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lat: float = Field(ge=-90, le=90, description="Latitud [°]")
    lon: float = Field(ge=-180, le=180, description="Longitud [°]")
    elevation_m: float = Field(ge=0, le=6000, description="Elevación [m s.n.m.]")
    source: str = Field(min_length=1, description="Fuente/origen de la coordenada")


class ClimateDaily:
    """Especificación de la serie climática diaria normalizada.

    No es un modelo por fila: es el esquema que valida :func:`validate_climate`.
    """

    COLUMNS: ClassVar[tuple[str, ...]] = (
        "date",
        "rain_mm",
        "tmax_c",
        "tmin_c",
        "rh_mean_pct",
        "wind2m_ms",
        "rs_mj_m2_day",
    )
    UNITS: ClassVar[dict[str, str]] = {
        "rain_mm": "mm/día",
        "tmax_c": "°C",
        "tmin_c": "°C",
        "rh_mean_pct": "%",
        "wind2m_ms": "m/s",
        "rs_mj_m2_day": "MJ m-2 día-1",
    }
    #: Rangos plausibles de datos diarios (§ validación de contrato, Fase 1).
    PLAUSIBLE_RANGES: ClassVar[dict[str, tuple[float, float]]] = {
        "tmax_c": (10.0, 45.0),
        "tmin_c": (5.0, 35.0),
        "rh_mean_pct": (5.0, 100.0),
        "wind2m_ms": (0.0, 20.0),
        "rs_mj_m2_day": (0.0, 35.0),
        "rain_mm": (0.0, 600.0),
    }
    MAX_GAP_DAYS: ClassVar[int] = _MAX_GAP_DAYS
    SENTINEL: ClassVar[float] = _SENTINEL


def _parse_dates(series: pd.Series) -> pd.Series:
    """Interpreta ISO (YYYY-MM-DD) o POWER (YYYYMMDD numérico)."""
    text = series.astype(str)
    if pd.api.types.is_numeric_dtype(series) or bool(text.str.fullmatch(r"\d{8}").all()):
        return pd.to_datetime(text, format="%Y%m%d", errors="coerce")
    return pd.to_datetime(series, errors="coerce")


def _format_dates(dates: pd.Series) -> str:
    stamps = [d.strftime("%Y-%m-%d") for d in dates.head(5)]
    extra = "" if len(dates) <= 5 else f" (+{len(dates) - 5} más)"
    return ", ".join(stamps) + extra


def validate_climate(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Valida y normaliza una serie climática diaria.

    Reglas (Fase 1):
    - ``-999`` → ``NaN``.
    - Huecos de hasta 3 días seguidos: interpolación lineal en T/RH/viento/Rs y
      ``rain_mm = 0``; cada relleno emite un warning.
    - Huecos de más de 3 días seguidos: ``ValueError``.
    - Rangos plausibles fuera de rango → warning con fechas (no se descarta).
    - Si la mediana de ``rs_mj_m2_day`` < 8 se asume kWh m-2 día-1 y se
      convierte a MJ m-2 día-1 multiplicando por 3.6 (warning).

    Devuelve ``(DataFrame_normalizado, warnings)``.
    """
    df = df.copy()
    missing = [col for col in ClimateDaily.COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            "Faltan columnas requeridas en la serie climática: " + ", ".join(missing)
        )

    df["date"] = _parse_dates(df["date"])
    if df["date"].isna().any():
        bad = df.loc[df["date"].isna(), "date"]
        raise ValueError(f"Hay fechas no interpretables ({len(bad)} filas).")
    df = df.sort_values("date").reset_index(drop=True)
    if df["date"].duplicated().any():
        dup = df.loc[df["date"].duplicated(), "date"]
        raise ValueError(f"Hay fechas duplicadas: {_format_dates(dup)}")

    value_columns = [c for c in ClimateDaily.COLUMNS if c != "date"]
    df[value_columns] = df[value_columns].apply(pd.to_numeric, errors="coerce")
    df[value_columns] = df[value_columns].mask(df[value_columns] == ClimateDaily.SENTINEL)

    warnings: list[str] = []
    rain_col = df.columns.get_loc("rain_mm")
    for col in value_columns:
        for start, length in _nan_runs(df[col].isna()):
            span = df["date"].iloc[[start, start + length - 1]]
            label = f"{span.iloc[0]:%Y-%m-%d} a {span.iloc[1]:%Y-%m-%d}"
            if length > ClimateDaily.MAX_GAP_DAYS:
                raise ValueError(
                    f"Hueco de {length} días seguidos en {col} ({label}); "
                    f"el máximo interpolable es {ClimateDaily.MAX_GAP_DAYS} días."
                )
            touches_edge = start == 0 or start + length == len(df)
            if col == "rain_mm":
                df.iloc[start : start + length, rain_col] = 0.0
                warnings.append(
                    f"Hueco de {length} día(s) en rain_mm ({label}): se asume lluvia 0."
                )
            else:
                note = (
                    " borde de la serie: se usó el valor válido más cercano"
                    if touches_edge
                    else "interpolación lineal"
                )
                warnings.append(f"Hueco de {length} día(s) en {col} ({label}): {note}.")
    interpolated = [c for c in value_columns if c != "rain_mm"]
    df[interpolated] = df[interpolated].interpolate(
        method="linear", limit_direction="both"
    )

    median_rs = df["rs_mj_m2_day"].median(skipna=True)
    if pd.notna(median_rs) and median_rs < 8:
        df["rs_mj_m2_day"] = df["rs_mj_m2_day"] * 3.6
        warnings.append(
            f"Mediana de rs_mj_m2_day = {median_rs:.2f} < 8: se interpretó como "
            "kWh m-2 día-1 y se convirtió a MJ m-2 día-1 (×3.6)."
        )

    for col, (low, high) in ClimateDaily.PLAUSIBLE_RANGES.items():
        outside = df[(df[col] < low) | (df[col] > high)]
        if not outside.empty:
            warnings.append(
                f"{col} fuera del rango plausible [{low:g}, {high:g}] "
                f"en {len(outside)} día(s): {_format_dates(outside['date'])}."
            )

    inverted = df[df["tmin_c"] > df["tmax_c"]]
    if not inverted.empty:
        warnings.append(
            "tmin_c > tmax_c en "
            f"{len(inverted)} día(s): {_format_dates(inverted['date'])}."
        )

    return df, warnings


_POWER_COLUMN_MAP: dict[str, str] = {
    "PRECTOTCORR": "rain_mm",
    "T2M_MAX": "tmax_c",
    "T2M_MIN": "tmin_c",
    "RH2M": "rh_mean_pct",
    "WS2M": "wind2m_ms",
    "ALLSKY_SFC_SW_DWN": "rs_mj_m2_day",
}


def from_power_csv(path: str | Path) -> tuple[pd.DataFrame, list[str]]:
    """Adapta un CSV diario de NASA POWER al esquema :class:`ClimateDaily`.

    Mapea ``PRECTOTCORR``→``rain_mm``, ``T2M_MAX``→``tmax_c``,
    ``T2M_MIN``→``tmin_c``, ``RH2M``→``rh_mean_pct``, ``WS2M``→``wind2m_ms``
    y ``ALLSKY_SFC_SW_DWN``→``rs_mj_m2_day``. Descarta ``EVPTRNS`` (no es ET0)
    y ``GWETROOT`` (solo chequeo de coherencia, nunca entrada).

    Devuelve ``(DataFrame_normalizado, warnings)``.
    """
    raw = pd.read_csv(path)
    if "fecha" in raw.columns:
        raw = raw.rename(columns={"fecha": "date"})
    if "date" not in raw.columns:
        raise ValueError("El CSV POWER debe traer una columna 'fecha' o 'date'.")

    absent = [col for col in _POWER_COLUMN_MAP if col not in raw.columns]
    if absent:
        raise ValueError("Faltan columnas POWER: " + ", ".join(absent))

    df = raw.rename(columns=_POWER_COLUMN_MAP)[["date", *_POWER_COLUMN_MAP.values()]]
    return validate_climate(df)


#: Contenido de agua típico por textura (FAO-56 Tabla 19): (θfc, θwp) como rangos.
SOIL_TEXTURE_WATER_CONTENT: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    "sand": ((0.07, 0.17), (0.02, 0.07)),
    "loamy sand": ((0.11, 0.19), (0.03, 0.10)),
    "sandy loam": ((0.18, 0.28), (0.06, 0.16)),
    "loam": ((0.20, 0.30), (0.07, 0.17)),
    "silt loam": ((0.22, 0.36), (0.09, 0.21)),
    "silt": ((0.28, 0.36), (0.12, 0.22)),
    "silt clay loam": ((0.30, 0.37), (0.17, 0.24)),
    "silty clay": ((0.30, 0.42), (0.17, 0.29)),
    "clay": ((0.32, 0.40), (0.20, 0.24)),
}


class SoilWaterProfile(BaseModel):
    """Perfil de suelo usado por la Eq. 82 de FAO-56: ``TAW = 1000(θfc − θwp)Zr``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    theta_fc: float = Field(gt=0, le=1, description="θ a capacidad de campo [m3/m3]")
    theta_wp: float = Field(gt=0, le=1, description="θ en punto de marchitez [m3/m3]")
    source: str = Field(min_length=1, description="Fuente de los valores de suelo")
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_order(self) -> SoilWaterProfile:
        if self.theta_wp >= self.theta_fc:
            raise ValueError(
                "theta_wp debe ser menor que theta_fc "
                f"(recibido θfc={self.theta_fc}, θwp={self.theta_wp})."
            )
        return self

    @classmethod
    def from_soilgrids(
        cls,
        wv0033: float | None,
        wv1500: float | None,
        texture: str = "loam",
    ) -> SoilWaterProfile:
        """Construye el perfil desde SoilGrids 2.0 (ISRIC).

        ``wv0033`` (33 kPa ≈ θfc) y ``wv1500`` (1500 kPa ≈ θwp) llegan en las
        unidades de mapa de SoilGrids: ``10^-3 cm3 cm-3``; se dividen entre 1000
        (ISRIC, SoilGrids FAQs: factor de conversión 1000). Si falta alguno, se
        cae a valores medios por textura de FAO-56 Tabla 19 con el warning
        ``"suelo estimado por textura"``.
        """
        if wv0033 is not None and wv1500 is not None:
            return cls(
                theta_fc=float(wv0033) / 1000.0,
                theta_wp=float(wv1500) / 1000.0,
                source=(
                    "SoilGrids 2.0 (ISRIC) wv0033/wv1500 en 10^-3 cm3/cm3, "
                    "convertido a m3/m3 (÷1000)"
                ),
            )

        key = texture.strip().lower()
        if key not in SOIL_TEXTURE_WATER_CONTENT:
            raise ValueError(
                f"Textura desconocida '{texture}'. Opciones: "
                + ", ".join(sorted(SOIL_TEXTURE_WATER_CONTENT))
            )
        (fc_low, fc_high), (wp_low, wp_high) = SOIL_TEXTURE_WATER_CONTENT[key]
        theta_fc = round((fc_low + fc_high) / 2, 3)
        theta_wp = round((wp_low + wp_high) / 2, 3)
        return cls(
            theta_fc=theta_fc,
            theta_wp=theta_wp,
            source=f"FAO-56 Tabla 19 ({key}, punto medio del rango)",
            warnings=[
                "suelo estimado por textura "
                f"('{key}': θfc={theta_fc}, θwp={theta_wp}); "
                "sin datos SoilGrids disponibles"
            ],
        )


class CropSegment(BaseModel):
    """Un cultivo dentro de una rotación, con siembra en ``MM-DD``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    crop_id: str = Field(min_length=1)
    sowing_mmdd: str
    irrigated: bool = False
    regime: Literal["upland", "flooded"] | None = None

    @field_validator("sowing_mmdd")
    @classmethod
    def _check_sowing(cls, value: str) -> str:
        return _validate_mmdd(value)


class RotationTemplate(BaseModel):
    """Secuencia de cultivos; ``is_current`` marca la rotación de referencia."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rotation_id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1)
    segments: list[CropSegment] = Field(min_length=1)
    is_current: bool = False
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_unique_crops(self) -> RotationTemplate:
        crops = [segment.crop_id for segment in self.segments]
        if len(crops) != len(set(crops)):
            raise ValueError(f"rotation_id '{self.rotation_id}' repite cultivos: {crops}")
        return self


class KernelAssumptions(BaseModel):
    """Supuestos explícitos del balance (D1–D6). Ninguno vive en las ecuaciones."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    initial_depletion_fraction: float = Field(0.5, ge=0, le=1)
    runoff_threshold_mm: float = Field(60.0, ge=0)
    runoff_fraction: float = Field(0.3, ge=0, le=1)
    kc_fallow: float = Field(0.15, ge=0, le=2)
    flooded_percolation_mm_day: float = Field(4.0, ge=0, le=50)
    irrigation_rule: Literal["refill_at_raw"] = "refill_at_raw"
    season_start_mmdd: str = "05-01"

    @field_validator("season_start_mmdd")
    @classmethod
    def _check_season_start(cls, value: str) -> str:
        return _validate_mmdd(value)


class CropParameters(BaseModel):
    """Parámetros agronómicos de un cultivo; ``null`` = falta fuente verificada."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    display_name: str = Field(min_length=1)
    kc_ini: float | None = Field(None, ge=0, le=2)
    kc_mid: float | None = Field(None, ge=0, le=2)
    kc_end: float | None = Field(None, ge=0, le=2)
    stage_days: list[int] | None = Field(
        None, description="[inicial, desarrollo, medio, final] en días"
    )
    root_depth_max_m: float | None = Field(None, gt=0, le=10)
    p_depletion: float | None = Field(None, ge=0, le=1)
    heat_threshold_c: float | None = Field(None, ge=0, le=60)
    source: str | None = None
    verified: bool = False
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("stage_days")
    @classmethod
    def _check_stage_days(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if len(value) != 4:
            raise ValueError("stage_days debe traer 4 valores [ini, dev, mid, late]")
        if any(days <= 0 for days in value):
            raise ValueError("stage_days solo admite enteros positivos")
        return value


class CropLibrary(BaseModel):
    """Contenido de ``research/parameters/crops.yaml``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    retrieved: str | None = None
    crops: dict[str, CropParameters]


class RotationLibrary(BaseModel):
    """Contenido de ``research/parameters/rotations.yaml``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    retrieved: str | None = None
    rotations: list[RotationTemplate]
