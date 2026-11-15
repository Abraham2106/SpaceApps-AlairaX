"""Offline feature extraction from versioned regional snapshots."""

from collections import Counter
from datetime import date, timedelta
from math import isfinite
from statistics import fmean, pstdev
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from backend.app.api.schemas.contracts import ClimateDay, Contract
from backend.app.intelligence.features import ONI_SEASONS

WINDOWS = (7, 15, 30, 90)


class AreaOfInterest(Contract):
    crs: Literal['EPSG:4326'] = 'EPSG:4326'
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)


class RegionConfig(Contract):
    id: str = Field(pattern=r'^[a-z0-9-]+$')
    name: str
    aoi: AreaOfInterest
    timezone: str
    start: date
    as_of: date
    season_start: str
    season_end: str
    oni_season: str
    analog_k: int = Field(default=5, ge=1, le=45)
    strong_el_nino_k: int | None = Field(default=None, ge=1, le=45)
    heat_threshold_c: float
    reference_years: tuple[int, int]
    wet_months: list[int]
    crop_catalog: str
    sources: dict[str, str]

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError('timezone must be an installed IANA time zone') from None
        return value

    @model_validator(mode='after')
    def valid_periods(self):
        first, last = self.reference_years
        if self.start > self.as_of or first > last:
            raise ValueError('invalid analysis or baseline period')
        if self.oni_season not in ONI_SEASONS:
            raise ValueError('invalid ONI season')
        for mmdd in (self.season_start, self.season_end):
            date.fromisoformat(f'2001-{mmdd}')
        if any(month < 1 or month > 12 for month in self.wet_months):
            raise ValueError('wet_months must contain months 1–12')
        return self


class CropContext(Contract):
    species: str
    cultivar: str | None = None
    seed_lot: str | None = None
    sowing_date: date | None = None
    expected_cycle_days: int | None = Field(default=None, gt=0)
    density_plants_m2: float | None = Field(default=None, gt=0)
    parameter_set_id: str | None = None
    previous_crop: str | None = None
    rotation_sequence: list[str] = Field(default_factory=list)
    documented_tolerances: dict[str, str] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)


class FarmManagement(Contract):
    irrigation_mode: Literal['rainfed', 'scheduled', 'unspecified'] = 'unspecified'
    irrigation_capacity_mm: float | None = Field(default=None, ge=0)
    soil_management: str | None = None
    crop_history: list[str] = Field(default_factory=list)
    operational_constraints: list[str] = Field(default_factory=list)
    priorities: list[str] = Field(default_factory=list)


class FarmContext(Contract):
    region_id: str
    available_on: date
    crop: CropContext
    management: FarmManagement


def date_range(start, end):
    return (start + timedelta(days=i) for i in range((end - start).days + 1))


def complete_stat(values, stat):
    return stat(values) if values and all(value is not None for value in values) else None


def daily_features(config, rows, et0, farm=None):
    """Trailing features, each available after the corresponding day closes."""
    climate, invalid = {}, []
    for day, row in rows.items():
        if day > config.as_of:
            continue
        try:
            if any(isinstance(value, bool) or value == -999 for value in row.values()):
                raise ValueError('invalid climate sentinel')
            climate[day] = ClimateDay.model_validate(row)
        except ValueError:
            invalid.append(day.isoformat())
    if not climate:
        raise ValueError('no valid climate rows on or before the cutoff')
    start = max(config.start, min(climate))
    end = min(config.as_of, max(rows))
    if end < start:
        raise ValueError('no climate rows inside the regional analysis window')
    prior_days = {}
    output = []
    for day in date_range(min(climate), end):
        weather = climate.get(day)
        rain = weather.precipitation_mm if weather else None
        evaporation = et0.get(day)
        prior_days[day] = rain
        if day < start:
            continue
        values = {
            'date': day.isoformat(), 'wet_month': int(day.month in config.wet_months),
            'precipitation_mm': rain, 'et0_mm': evaporation,
            'climatic_deficit_mm': max(0, evaporation-rain) if rain is not None and evaporation is not None else None,
        }
        for key in ('tmin_c', 'tmax_c', 'relative_humidity_pct', 'wind_speed_2m_m_s', 'solar_radiation_mj_m2_day'):
            values[key] = getattr(weather, key, None)
        tmin, tmax = values['tmin_c'], values['tmax_c']
        values['tmean_c'] = (tmin + tmax) / 2 if tmin is not None and tmax is not None else None
        values['heat_day'] = int(tmax >= config.heat_threshold_c) if tmax is not None else None
        if farm:
            sowing = farm.crop.sowing_date if farm.available_on <= day else None
            values['days_after_planting'] = (day-sowing).days if sowing and day >= sowing else None
        for n in WINDOWS:
            window = list(date_range(day-timedelta(days=n-1), day))
            rain_values = [prior_days.get(d) for d in window]
            rain_total = complete_stat(rain_values, sum)
            values[f'rain_{n}d_mm'] = rain_total
            values[f'rain_{n}d_valid_days'] = sum(v is not None for v in rain_values)
            values[f'et0_{n}d_mm'] = complete_stat([et0.get(d) for d in window], sum)
            if n == 30:
                demand = values[f'et0_{n}d_mm']
                values['climatic_deficit_30d_mm'] = max(0, demand-rain_total) if demand is not None and rain_total is not None else None
                values['rain_30d_daily_sd_mm'] = complete_stat(rain_values, pstdev)
                baselines = []
                for year in range(config.reference_years[0], min(config.reference_years[1]+1, day.year)):
                    try:
                        reference = day.replace(year=year)
                    except ValueError:  # February 29
                        continue
                    total = complete_stat([prior_days.get(d) for d in date_range(reference-timedelta(days=29), reference)], sum)
                    if total is not None:
                        baselines.append(total)
                mean = fmean(baselines) if baselines else None
                values['rain_30d_reference_years'] = len(baselines)
                values['rain_30d_anomaly_pct'] = (rain_total/mean-1)*100 if rain_total is not None and mean else None
        output.append(values)
    missing = Counter(key for row in output for key, value in row.items() if value is None)
    return output, {'rows': len(output), 'invalid_climate_dates': sorted(invalid), 'null_counts': dict(missing)}


def enso_features(records, period_end, cutoff):
    """Retrospective phase features from completed CPC windows."""
    result, phase, streak, previous = [], None, 0, None
    records = sorted(records, key=lambda row: (row['year'], ONI_SEASONS.index(row['season'])))
    for row in records:
        end = period_end(row['year'], row['season'])
        if end > cutoff:
            break
        value = row['anomaly_c']
        current = None if value is None else 'warm' if value >= .5 else 'cold' if value <= -.5 else 'neutral'
        month = end.year*12 + end.month
        streak = streak + 1 if current is not None and current == phase and previous == month-1 else int(current is not None)
        result.append(dict(row, period_end=end.isoformat(), phase=current, consecutive_windows=streak,
                           months_since_phase_start=max(0, streak-1) if current else None,
                           intensity_abs_c=abs(value) if value is not None else None,
                           sustained_warm_or_cold=current in ('warm', 'cold') and streak >= 5))
        phase, previous = current, month
    return result


def hls_ndvi(pixels, low_ndvi=0.2):
    """Summarize AOI pixels with scaled red/NIR reflectance and HLS v2 Fmask."""
    values = []
    for pixel in pixels:
        red, nir, mask = (pixel[k] for k in ('red', 'nir', 'fmask'))
        if type(mask) is not int or not 0 <= mask < 255 or mask & 0b00111111 or mask >> 6 == 3:
            continue
        if any(type(v) not in (int, float) or not isfinite(v) or not 0 <= v <= 1 for v in (red, nir)):
            continue
        if red + nir > 0:
            values.append((nir-red)/(nir+red))
    return {'ndvi_mean': fmean(values) if values else None,
            'low_ndvi_fraction': sum(v < low_ndvi for v in values)/len(values) if values else None,
            'valid_pixels': len(values), 'total_pixels': len(pixels)}
