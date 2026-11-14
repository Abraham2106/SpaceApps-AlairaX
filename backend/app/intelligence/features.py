"""Complete, explicitly aligned seasonal features; no imputation or ET0 model."""

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from math import isfinite
from statistics import fmean
from typing import Iterable, Mapping

FEATURE_NAMES = ('precipitation_mm', 'et0_mm', 'tmax_mean_c', 'heat_days', 'oni')
ONI_SEASONS = ('DJF', 'JFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDJ')


@dataclass(frozen=True)
class SeasonFeatures:
    year: int
    start: date
    end: date
    precipitation_mm: float
    et0_mm: float
    tmax_mean_c: float
    heat_days: int | float
    oni: float
    heat_threshold_c: float
    oni_season: str
    mock: bool = False

    def __post_init__(self):
        if not 1981 <= self.year <= 2026 or self.start.year != self.year or self.end.year != self.year or self.end < self.start:
            raise ValueError('feature season must be within its stated year, 1981–2026')
        for name in (*FEATURE_NAMES, 'heat_threshold_c'):
            _finite(getattr(self, name), name)
        if self.precipitation_mm < 0 or self.et0_mm < 0 or not 0 <= self.heat_days <= self.day_count:
            raise ValueError('negative water totals or invalid heat-day count')
        if self.oni in (-999, -99.99, -99.9) or self.tmax_mean_c == -999:
            raise ValueError('missing-data sentinels cannot become climate features')
        if self.oni_season not in ONI_SEASONS:
            raise ValueError('unknown ONI three-month season')

    @property
    def day_count(self):
        return (self.end - self.start).days + 1

    @property
    def window_key(self):
        return (self.start.month, self.start.day, self.end.month, self.end.day,
                self.heat_threshold_c, self.oni_season)

    def to_dict(self):
        values = asdict(self)
        values['start'], values['end'] = self.start.isoformat(), self.end.isoformat()
        return values


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f'{name} must be a finite number; missing data is not imputed')
    return float(value)


def _get(row, name):
    return row.get(name) if isinstance(row, Mapping) else getattr(row, name, None)


def build_season_features(days: Iterable, *, year: int, start: date, end: date,
                          oni: float, heat_threshold_c: float = 35.0,
                          oni_season: str = 'AMJ', mock: bool = False) -> SeasonFeatures:
    """Select a complete calendar window, rejecting missing/duplicate daily inputs.

    ONI is supplied for one explicitly named three-month period, never inferred
    from a phase label. ET0 must come from Justin's reviewed kernel.
    """
    if start.year != year or end.year != year or end < start:
        raise ValueError('season dates must be ordered and belong to year')
    _finite(oni, 'oni')
    _finite(heat_threshold_c, 'heat_threshold_c')
    selected = {}
    for row in days:
        day = _get(row, 'date')
        if isinstance(day, str):
            day = date.fromisoformat(day)
        if not isinstance(day, date):
            raise ValueError('every daily row must have an ISO date')
        if start <= day <= end:
            if day in selected:
                raise ValueError(f'duplicate date: {day}')
            selected[day] = row
    expected = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    if set(selected) != set(expected):
        raise ValueError('incomplete daily climate window; no partial-season extrapolation')
    rain, et0, tmax = [], [], []
    for day in expected:
        row = selected[day]
        precipitation = _finite(_get(row, 'precipitation_mm'), f'{day}.precipitation_mm')
        evaporation = _finite(_get(row, 'et0_mm'), f'{day}.et0_mm')
        maximum = _finite(_get(row, 'tmax_c'), f'{day}.tmax_c')
        if maximum == -999:
            raise ValueError(f'{day}.tmax_c contains a missing-data sentinel')
        if precipitation < 0 or evaporation < 0:
            raise ValueError('negative precipitation/ET0, including missing-data sentinels, is invalid')
        rain.append(precipitation)
        et0.append(evaporation)
        tmax.append(maximum)
    return SeasonFeatures(year, start, end, sum(rain), sum(et0), fmean(tmax),
                          sum(value >= heat_threshold_c for value in tmax), float(oni),
                          float(heat_threshold_c), oni_season, mock)
