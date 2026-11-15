"""FAO-56 regional pilot for Guanacaste's eleven own climate/soil points.

Regional analog years and agronomic reference calendars are shared assumptions;
the point climate, elevation, soil and environment fingerprint are never copied
from the original Liberia pilot. No station/farm validation is implied.
"""

from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from functools import partial
import json
import math
from pathlib import Path
import tempfile
import threading
import time
from urllib.error import URLError
from zoneinfo import ZoneInfo

from pydantic import TypeAdapter

from backend.app.api.schemas.contracts import (
    AnalogYear, ClimateDay, ClimateSeason, CompareRequest, CompareResponse,
    DailyBalance, SimulationInput, SoilProfile, Zone,
)
from backend.app.application.compare import execute_comparison
from backend.app.application.prepare_inputs import ComparisonSetup
from backend.app.infrastructure.cache import RawCache
from backend.app.infrastructure.power import normalize_power, power_url
from backend.app.simulation.et0 import et0_for_days
from backend.app.simulation.kernel import simulate_rotation
from backend.app.simulation.version import MODEL_VERSION

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / 'backend/app/domain/cantons.json'
SOILS = ROOT / 'backend/app/domain/canton_soils.json'
SETUP = ROOT / 'configs/regions/guanacaste-pilot.setup.json'
ROTATIONS = ('rice_melon', 'rice_legume', 'rice_sorghum')
WARNINGS = [
    'Piloto regional de Guanacaste: punto de referencia del cantón, no una finca validada ni el promedio de todo el cantón.',
    'Clima NASA POWER y suelo SoilGrids del punto indicado; sin calibración local de lluvia ni validación de finca.',
    'Calendarios, profundidad de referencia de 1 m y manejo regional compartidos, provisionales; no son siembras observadas.',
    'Se simulan las tres rotaciones en secano con humedad inicial de referencia de 50 % del agua útil.',
]
REGIONAL_ANALOG_WARNING = (
    'Los años análogos y sus distancias son la selección regional del piloto de Guanacaste; '
    'no se recalculó similitud climática por cantón. Cada año se reproduce con clima y suelo del cantón seleccionado.'
)


class CantonSimulationError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class CantonSimulator:
    def __init__(self, *, cache=None, catalog_path: Path = CATALOG,
                 soils_path: Path = SOILS, setup_path: Path = SETUP,
                 today=None):
        self.cache = cache or RawCache(Path(tempfile.gettempdir()) / 'alairax-canton-power',
                                       timeout=25, attempts=1)
        self.catalog_path, self.soils_path, self.setup_path = catalog_path, soils_path, setup_path
        self.today = today or (lambda: datetime.now(ZoneInfo('America/Costa_Rica')).date())
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._results: OrderedDict[str, tuple[float, object]] = OrderedDict()

    def _memoized(self, key: str, build):
        with self._locks_guard:
            lock = self._locks.setdefault('result:' + key, threading.Lock())
        with lock:
            with self._locks_guard:
                found = self._results.get(key)
                if found and time.monotonic() - found[0] < 21600:
                    self._results.move_to_end(key)
                    return deepcopy(found[1])
            result = build()
            with self._locks_guard:
                self._results[key] = (time.monotonic(), deepcopy(result))
                self._results.move_to_end(key)
                while len(self._results) > 64:
                    self._results.popitem(last=False)
            return result

    def _revision(self, *paths: Path) -> list:
        try:
            return [(str(path), path.stat().st_mtime_ns) for path in paths]
        except OSError:
            raise CantonSimulationError(503, 'Falta un artefacto del piloto por cantón.') from None

    def _json(self, path: Path):
        try:
            return json.loads(path.read_bytes())
        except (OSError, ValueError):
            raise CantonSimulationError(503, 'Falta un artefacto del piloto por cantón.') from None

    def point(self, canton_id: str) -> tuple[dict, Zone, SoilProfile]:
        catalog = self._json(self.catalog_path)
        if canton_id not in catalog:
            raise CantonSimulationError(404, 'El cantón no pertenece al piloto de Guanacaste.')
        point = catalog[canton_id]
        soil = self._json(self.soils_path).get(canton_id)
        try:
            if (not isinstance(soil, dict) or soil.get('status') != 'map'
                    or (soil['latitude'], soil['longitude']) != (point['latitude'], point['longitude'])):
                raise ValueError('soil identity mismatch')
            zone = Zone(id=canton_id, name=point['name'], latitude=point['latitude'],
                        longitude=point['longitude'], validated=False)
            profile = SoilProfile(field_capacity_m3_m3=soil['field_capacity_m3_m3'],
                                  wilting_point_m3_m3=soil['wilting_point_m3_m3'],
                                  rooting_depth_m=soil['rooting_depth_m'], source_refs=soil['source_refs'])
            if any(value is None for value in (profile.field_capacity_m3_m3,
                                               profile.wilting_point_m3_m3, profile.rooting_depth_m)):
                raise ValueError('incomplete soil')
            if not math.isfinite(point['elevation_m']):
                raise ValueError('missing elevation')
        except (KeyError, TypeError, ValueError):
            raise CantonSimulationError(503, 'Suelo o elevación no disponibles para este cantón.') from None
        return point, zone, profile

    def _fetch(self, url: str):
        # RawCache uses deterministic temporary filenames; coalesce concurrent
        # consumers of the same climate URL within this service instance.
        with self._locks_guard:
            lock = self._locks.setdefault(url, threading.Lock())
        with lock:
            body, provenance = self.cache.get(url)
            fetched_at = datetime.fromisoformat(provenance['fetched_at'])
            if (datetime.now(timezone.utc) - fetched_at).total_seconds() > 21600:
                body, provenance = self.cache.get(url, refresh=True)
        return body, provenance

    def _climate(self, point: dict, zone: Zone, start: date, end: date,
                 *, trim_tail: bool = False, allow_gaps: bool = False) -> tuple[ClimateSeason, dict]:
        url = power_url(zone.latitude, zone.longitude, start, end)
        try:
            body, provenance = self._fetch(url)
            normalized = normalize_power(json.loads(body), start, end)
            rows = normalized['days']
            for row, et0 in zip(rows, et0_for_days(rows, zone.latitude, point['elevation_m'])):
                row['et0_mm'] = et0 if et0 is not None and math.isfinite(et0) else None
            missing_dates = [row['date'] for row in rows if any(value is None for value in row.values())]
            available_through = {
                field: next((row['date'] for row in reversed(rows) if row[field] is not None), None)
                for field in normalized['units']
            }
            source_available_through = max((day for day in available_through.values() if day), default=None)
            # Provider latency can remove a recent tail; never impute an internal
            # gap or silently present a full-year total from an incomplete year.
            if trim_tail:
                while rows and any(value is None for value in rows[-1].values()):
                    rows.pop()
            interior_gaps = [row['date'] for row in rows if any(value is None for value in row.values())]
            if not rows or (interior_gaps and not allow_gaps):
                raise ValueError('incomplete climate')
            last = date.fromisoformat(rows[-1]['date'])
            climate = ClimateSeason(year=start.year, start=start, end=last,
                                    days=[ClimateDay.model_validate(row) for row in rows])
            evidence = {'url': url, 'provenance': provenance,
                        'provider_geometry': normalized['provider_geometry'],
                        'quality_control': normalized['quality_control'],
                        'coverage_start': start.isoformat(), 'coverage_end': last.isoformat(),
                        'requested_end': end.isoformat(), 'missing_forcing_dates': missing_dates,
                        'interior_missing_forcing_dates': interior_gaps,
                        'source_available_through': source_available_through,
                        'available_through_by_field': available_through}
            return climate, evidence
        except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
            raise CantonSimulationError(503, 'Clima o ET0 incompletos para el cantón y período; no se sustituyen por datos de Liberia.') from None

    def compare(self, canton_id: str, request: CompareRequest, document: dict,
                inputs_dir: Path) -> CompareResponse:
        key = json.dumps(['compare', canton_id, request.model_dump(mode='json'),
                          document, self._revision(self.catalog_path, self.soils_path,
                                                   inputs_dir / f'{request.scenario_id}.json')],
                         sort_keys=True)
        return self._memoized(key, lambda: self._compare(canton_id, request, document, inputs_dir))

    def _compare(self, canton_id: str, request: CompareRequest, document: dict,
                 inputs_dir: Path) -> CompareResponse:
        point, zone, soil = self.point(canton_id)
        if request.zona != zone:
            raise CantonSimulationError(422, 'La zona solicitada debe coincidir con el punto del cantón.')
        scenario = document.get('scenarios', {}).get(request.scenario_id)
        if not isinstance(scenario, dict) or scenario.get('status') != 'available':
            raise CantonSimulationError(409, 'Escenario regional no disponible.')
        if document.get('_mock') is not False or scenario.get('_mock') is not False:
            raise CantonSimulationError(503, 'El piloto por cantón requiere artefactos reales.')
        try:
            analogs = [AnalogYear.model_validate(row, extra='ignore') for row in scenario['neighbors']]
            if len(analogs) != scenario['k'] or len({a.year for a in analogs}) != len(analogs):
                raise ValueError('invalid analog years')
            if request.k > len(analogs):
                raise CantonSimulationError(409, 'No hay suficientes años análogos regionales.')
            analogs = analogs[:request.k]
            templates = TypeAdapter(list[SimulationInput]).validate_python(
                self._json(inputs_dir / f'{request.scenario_id}.json'))
            selected = [item for item in templates if item.climate.year in {a.year for a in analogs}
                        and item.rotation.rotation_id in request.rotation_ids]
            expected = {(a.year, rotation) for a in analogs for rotation in request.rotation_ids}
            if ({(item.climate.year, item.rotation.rotation_id) for item in selected} != expected
                    or len(selected) != len(expected)
                    or any(item.mock or not item.regional_pilot for item in selected)):
                raise ValueError('incomplete regional templates')
            by_year = {item.climate.year: item for item in selected}
            with ThreadPoolExecutor(max_workers=4) as pool:
                climates = dict(zip(by_year, pool.map(
                    lambda year: self._climate(point, zone, by_year[year].climate.start,
                                               by_year[year].climate.end), by_year)))
            inputs = []
            for template in selected:
                climate, evidence = climates[template.climate.year]
                refs = [ref for ref in template.source_refs
                        if 'power.larc.nasa.gov/api/' not in ref and 'rest.isric.org/' not in ref]
                refs = sorted(set(refs + soil.source_refs + [evidence['url']]))
                payload = template.model_dump()
                climate_warnings = ([f'Control de calidad del clima {climate.year}: '
                    f'{len(evidence["quality_control"]["issues"])} avisos del proveedor/normalizador; revisar el artefacto fuente.']
                    if evidence['quality_control']['issues'] else [])
                payload.update(zona=zone, soil=soil, climate=climate, source_refs=refs,
                               generado=datetime.now(timezone.utc), warnings=WARNS_FOR_COMPARE + climate_warnings)
                inputs.append(SimulationInput.model_validate(payload))
            kernel = partial(simulate_rotation, elevation_m=point['elevation_m'],
                             latitude_deg=zone.latitude)
            result = execute_comparison(request, analogs, inputs, simulate_rotation=kernel)
            result.limitations.append(REGIONAL_ANALOG_WARNING)
            result.limitations.append('Las condiciones de suelo y clima son del punto de referencia, no observaciones de finca.')
            return result
        except CantonSimulationError:
            raise
        except (KeyError, TypeError, ValueError):
            raise CantonSimulationError(503, 'Artefactos regionales incompatibles; simulación no disponible.') from None

    def recent(self, canton_id: str, years: list[int] | None = None) -> dict:
        last_day = self.today() - timedelta(days=1)
        available = list(range(2017, min(2026, last_day.year) + 1))
        if years is not None and (not years or len(years) > 10
                                  or any(type(year) is not int or year not in available for year in years)
                                  or len(set(years)) != len(years)):
            raise CantonSimulationError(422, 'Selecciona años distintos entre 2017 y el último año disponible (hasta 2026).')
        selected = available if years is None else sorted(years)
        key = json.dumps(['recent', canton_id, selected, last_day.isoformat(),
                          self._revision(self.catalog_path, self.soils_path, self.setup_path)])
        return self._memoized(key, lambda: self._recent(canton_id, selected))

    def _recent(self, canton_id: str, years: list[int]) -> dict:
        point, zone, soil = self.point(canton_id)
        try:
            setup = ComparisonSetup.model_validate(self._json(self.setup_path))
            if setup.mock or not setup.regional_pilot:
                raise ValueError('expected real regional setup')
            base_year = min(setup.rotations_by_year)
            templates = setup.rotations_by_year[base_year]
            assumptions = setup.assumptions_by_year[base_year]
            if {r.rotation_id for r in templates} != set(ROTATIONS):
                raise ValueError('regional rotations missing')
        except (TypeError, ValueError, KeyError):
            raise CantonSimulationError(503, 'Calendario regional no disponible.') from None
        last_day = self.today() - timedelta(days=1)

        def replay(year):
            start, warmup = date(year, 1, 1), date(year - 1, 5, 1)
            requested_end = min(date(year, 12, 31), last_day)
            climate, evidence = self._climate(point, zone, warmup, requested_end,
                                               trim_tail=year == last_day.year, allow_gaps=True)
            if climate.end < start:
                raise CantonSimulationError(503, 'Aún no hay clima disponible en el año solicitado.')
            runs = []
            first_gap = next((index for index, day in enumerate(climate.days)
                              if any(value is None for value in day.model_dump().values())), None)
            prefix = climate.days if first_gap is None else climate.days[:first_gap]
            simulation_climate = (ClimateSeason(year=warmup.year, start=warmup, end=prefix[-1].date,
                                                days=prefix) if prefix else None)
            evidence['simulation_valid_through'] = prefix[-1].date.isoformat() if prefix else None
            gap_warning = ([f'Clima incompleto desde {climate.days[first_gap].date.isoformat()}: '
                            'el balance y el almacenamiento posteriores son desconocidos; no se imputan datos ni se reinicia la humedad del suelo.']
                           if first_gap is not None else [])
            for template in templates:
                # Repeat the documented reference calendar as the established
                # recent-season exporter does, including preceding-year warmup.
                rotation = template.model_copy(deep=True)
                cycles = []
                for crop_year in (year - 1, year):
                    for original in template.cycles:
                        cycle = original.model_copy(deep=True)
                        offset = crop_year - base_year
                        cycle.sowing_date = cycle.sowing_date.replace(year=cycle.sowing_date.year + offset)
                        cycle.harvest_date = cycle.harvest_date.replace(year=cycle.harvest_date.year + offset)
                        cycles.append(cycle)
                rotation.cycles = cycles
                result = (simulate_rotation(climate=simulation_climate, soil=soil, rotation=rotation,
                                            assumptions=assumptions, elevation_m=point['elevation_m'],
                                            latitude_deg=zone.latitude) if simulation_climate is not None else
                          {'daily_balance': [], 'warnings': [], 'source_refs': [],
                           'model_version': MODEL_VERSION, 'assumptions': []})
                balances = [DailyBalance.model_validate(day).model_dump(mode='json')
                            for day in result['daily_balance'] if day['date'].year == year]
                if first_gap is not None:
                    balances.extend(DailyBalance(date=day.date, crop_water_demand_mm=None,
                        modeled_water_deficit_mm=None, soil_water_storage_mm=None,
                        water_stress=None).model_dump(mode='json')
                        for day in climate.days[first_gap:] if day.date.year == year)
                runs.append({'rotation_id': rotation.rotation_id,
                             'daily_balance': balances,
                             'warnings': gap_warning + result['warnings'], 'source_refs': result['source_refs'],
                             'model_version': result['model_version'], 'assumptions': result['assumptions']})
            return {'year': year, 'start': start.isoformat(), 'end': climate.end.isoformat(),
                    'complete': climate.end == date(year, 12, 31) and first_gap is None, 'runs': runs,
                    'source_refs': [evidence['url']], 'evidence': evidence}

        with ThreadPoolExecutor(max_workers=4) as pool:
            seasons = list(pool.map(replay, years))
        return {'_mock': False, 'zona': zone.model_dump(mode='json'),
                'model_scope': 'regional_pilot', 'generado': datetime.now(timezone.utc).isoformat(),
                'model_version': MODEL_VERSION,
                'calendar': 'January-December; recent year through available data',
                'warmup': 'May 1 of the preceding year; local point soil and regional reference management',
                'warnings': WARNINGS,
                'source_refs': sorted(set(soil.source_refs + [ref for s in seasons for ref in s['source_refs']]
                    + [ref for ref in setup.source_refs
                       if 'power.larc.nasa.gov/api/' not in ref and 'rest.isric.org/' not in ref]
                    + [ref for season in seasons for run in season['runs'] for ref in run['source_refs']])),
                'assumptions': assumptions.model_dump(mode='json'), 'seasons': seasons}


WARNS_FOR_COMPARE = WARNINGS + [REGIONAL_ANALOG_WARNING]
