"""Per-canton regional pilot evidence; no fallback to the original pilot point."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import tempfile
from urllib.error import URLError

from backend.app.api.schemas.chat import ChatSelection
from backend.app.infrastructure.cache import RawCache
from backend.app.infrastructure.power import normalize_power, power_url
from backend.app.simulation.et0 import et0_for_days

CATALOG = Path(__file__).resolve().parents[1] / 'domain' / 'cantons.json'
WARNINGS = [
    'Piloto regional: cada cantón se representa por un punto de referencia, no por una finca validada.',
    'NASA POWER es una estimación de rejilla sin calibración local; cantones cercanos pueden compartir celdas.',
    'No es un pronóstico. La disponibilidad reciente puede tener retraso.',
    'La interpretación de rotaciones, déficit de suelo y estrés requiere el bloque de simulación del cantón; ET0 sola no permite inferirlos.',
    'Los totales parciales no representan el total del período; los faltantes no son cero.',
]


class CantonContext:
    def __init__(self, cache=None, catalog_path: Path = CATALOG):
        self.catalog_path = catalog_path
        self.cache = cache or RawCache(Path(tempfile.gettempdir()) / 'alairax-chat-power',
                                       timeout=20, attempts=1)

    def catalog(self) -> dict:
        return json.loads(self.catalog_path.read_text(encoding='utf-8'))

    def build(self, selection: ChatSelection) -> dict:
        catalog = self.catalog()
        unknown = set(selection.canton_ids) - catalog.keys()
        if unknown:
            raise ValueError('Selecciona cantones del catálogo disponible.')
        # One worker per distinct point; bounded by the request's five-canton limit.
        with ThreadPoolExecutor(max_workers=len(selection.canton_ids)) as pool:
            cantons = list(pool.map(lambda key: self._point(key, catalog[key], selection),
                                    selection.canton_ids))
        return {
            'model_scope': 'regional_pilot', '_mock': False,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'selection': selection.model_dump(mode='json'),
            'cantons': cantons, 'warnings': WARNINGS,
            'sources': [source for canton in cantons for source in canton.get('sources', [])],
        }

    def _point(self, key: str, point: dict, selection: ChatSelection) -> dict:
        latitude, longitude = point['latitude'], point['longitude']
        url = power_url(latitude, longitude, selection.start, selection.end)
        result = {'id': key, **point, 'validated': False, 'model_scope': 'regional_pilot',
                  'requested_start': selection.start.isoformat(),
                  'requested_end': selection.end.isoformat()}
        try:
            body, provenance = self.cache.get(url)
            fetched_at = datetime.fromisoformat(provenance['fetched_at'])
            # Refresh even the same URL: recent missing days may arrive later.
            if (datetime.now(timezone.utc) - fetched_at).total_seconds() > 21600:
                body, provenance = self.cache.get(url, refresh=True)
            normalized = normalize_power(json.loads(body), selection.start, selection.end)
            days = normalized['days']
            elevation = point.get('elevation_m')
            if elevation is not None:
                for day, et0 in zip(days, et0_for_days(days, latitude, elevation)):
                    day['et0_mm'] = et0 if et0 is not None and math.isfinite(et0) else None
            summary = {}
            for field in ('precipitation_mm', 'et0_mm', 'tmin_c', 'tmax_c',
                          'relative_humidity_pct', 'wind_speed_2m_m_s',
                          'solar_radiation_mj_m2_day'):
                pairs = [(day['date'], day[field]) for day in days if day[field] is not None]
                values = [value for _, value in pairs]
                summary[field] = {
                    'available_days': len(values), 'expected_days': len(days),
                    'coverage_start': pairs[0][0] if pairs else None,
                    'coverage_end': pairs[-1][0] if pairs else None,
                    'complete': len(values) == len(days),
                    'total': sum(values) if values and field in ('precipitation_mm', 'et0_mm') else None,
                    'mean': sum(values) / len(values) if values else None,
                    'min': min(values) if values else None, 'max': max(values) if values else None,
                }
            result.update({
                'status': 'available' if all(s['complete'] for s in summary.values()) else 'partial',
                'summary': summary, 'daily': days, 'units': normalized['units'],
                'quality_control': normalized['quality_control'],
                'provenance': provenance, 'provider_geometry': normalized['provider_geometry'],
                'sources': [{'id': f'power:{key}', 'url': url, 'provider': 'NASA POWER'}],
                'limitations': [] if elevation is not None else [
                    'ET0 no calculada: no hay elevación de referencia documentada para este punto.'],
            })
            if elevation is not None:
                result['sources'].append({'id': f'et0:{key}',
                    'url': 'https://www.fao.org/4/x0490e/x0490e00.htm',
                    'provider': 'FAO-56 Penman-Monteith; RH media, G=0; elevación de referencia del catálogo'})
            if not any(s['available_days'] for s in summary.values()):
                result['status'] = 'unavailable'
        except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
            result.update({'status': 'unavailable', 'sources': [],
                           'limitations': ['NASA POWER no devolvió datos utilizables para este punto y período.']})
        return result


def prompt_context(context: dict) -> dict:
    """Return bounded evidence summaries for the model and chat HTTP responses."""
    cantons = []
    for original in context['cantons']:
        canton = {key: value for key, value in original.items() if key != 'daily'}
        # Recent daily values support questions about short-term changes. Full
        # Full daily simulation outputs remain available via the simulator routes.
        if original.get('daily'):
            canton['last_31_days'] = original['daily'][-31:]
        if 'comparison' in original:
            comparison = original['comparison']
            canton['comparison'] = {**comparison, 'rotations': [
                {**rotation, 'runs': [
                    {**{key: value for key, value in run.items() if key != 'daily_balance'},
                     'period_start': run['daily_balance'][0]['date'] if run['daily_balance'] else None,
                     'period_end': run['daily_balance'][-1]['date'] if run['daily_balance'] else None}
                    for run in rotation['runs']]}
                for rotation in comparison['rotations']]}
        if 'replays' in original:
            replays = original['replays']
            cutoff = min((season['end'][5:] for season in replays['seasons']), default='12-31')
            seasons = []
            for season in replays['seasons']:
                runs = []
                for run in season['runs']:
                    rows = [row for row in run['daily_balance'] if row['date'][5:] <= cutoff]
                    metrics = {}
                    for field in ('crop_water_demand_mm', 'modeled_water_deficit_mm'):
                        values = [row[field] for row in rows if row[field] is not None]
                        metrics[field] = {'total': sum(values) if values else None,
                                          'available_days': len(values), 'expected_days': len(rows),
                                          'complete': len(values) == len(rows)}
                    stress_values = [row['water_stress'] for row in rows if row['water_stress'] is not None]
                    metrics['water_stress_days'] = {
                        'total': sum(value is True for value in stress_values) if stress_values else None,
                        'available_days': len(stress_values), 'expected_days': len(rows),
                        'complete': len(stress_values) == len(rows),
                    }
                    runs.append({'rotation_id': run['rotation_id'], 'metrics': metrics,
                                 'summary_start': rows[0]['date'] if rows else None,
                                 'summary_end': rows[-1]['date'] if rows else None})
                seasons.append({**season, 'runs': runs})
            canton['replays'] = {**replays, 'seasons': seasons,
                                 'comparison_cutoff_mmdd': cutoff,
                                 'summary_method': 'Both selected years use the same month-day cutoff, as in the simulation table.'}
        cantons.append(canton)
    return {**context, 'cantons': cantons}
