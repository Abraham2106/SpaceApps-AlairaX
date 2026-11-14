"""Export daily FAO-56 Penman-Monteith ET0 for the normalized POWER files.

Writes the external ET0 artifact that ``scripts/build_analogs.py --et0`` reads
(format in ``docs/analog-method.md``). The file is always written with
``reviewed: false``: only Justin flips it to ``true`` after reviewing it.
Days with any missing input variable are exported as ``null``, never zero.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.simulation.et0 import et0_for_days  # noqa: E402
from backend.app.simulation.version import MODEL_VERSION  # noqa: E402

FAO56_REF = 'Allen et al. (1998) FAO-56, Eq. 6 (G = 0, Eq. 42); https://www.fao.org/3/x0490e/x0490e00.htm'


def _elevation(document):
    geometry = document.get('provider_geometry') or {}
    coordinates = geometry.get('coordinates') or []
    return float(coordinates[2]) if len(coordinates) >= 3 and coordinates[2] is not None else None


def build_et0(climate_files, *, elevation_m=None):
    documents = [json.loads(Path(path).read_text(encoding='utf-8')) for path in climate_files]
    if not documents:
        raise ValueError('at least one climate file is required')
    zone, mock = documents[0]['zona'], documents[0]['_mock']
    if any(doc['zona'] != zone or doc['_mock'] != mock for doc in documents):
        raise ValueError('climate files mix zones or mock status')

    warnings = []
    if elevation_m is None:
        elevations = {_elevation(doc) for doc in documents}
        if None in elevations or len(elevations) != 1:
            raise ValueError(f'POWER elevation missing or inconsistent ({sorted(map(str, elevations))}); pass --elevation-m')
        elevation_m = elevations.pop()
        elevation_source = 'POWER provider_geometry (MERRA-2 grid elevation)'
    else:
        elevation_source = 'manual --elevation-m'
        warnings.append(f'elevation set manually to {elevation_m} m')

    values, missing = {}, []
    for doc in documents:
        days = doc['days']
        for row, et0 in zip(days, et0_for_days(days, zone['latitude'], elevation_m)):
            if row['date'] in values and values[row['date']] != (None if et0 is None else round(et0, 3)):
                raise ValueError(f'conflicting overlapping day {row["date"]}')
            values[row['date']] = None if et0 is None else round(et0, 3)
            if et0 is None:
                missing.append(row['date'])
    if missing:
        warnings.append(f'{len(missing)} day(s) with missing POWER inputs exported as null')

    return {
        '_mock': mock,
        'zona': zone,
        'reviewed': False,
        'reviewed_by': None,
        'model_version': MODEL_VERSION,
        'units': 'mm/day',
        'method': 'FAO-56 Penman-Monteith daily ET0, G = 0, ea from RHmean (Eq. 19)',
        'latitude': zone['latitude'],
        'elevation_m': elevation_m,
        'elevation_source': elevation_source,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source_refs': [FAO56_REF] + sorted({ref for doc in documents for ref in doc.get('source_refs', [])}),
        'warnings': warnings,
        'values': dict(sorted(values.items())),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--climate', type=Path, nargs='+', required=True, help='Normalized POWER JSON files')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--elevation-m', type=float, help='Override POWER grid elevation')
    args = parser.parse_args()
    document = build_et0(args.climate, elevation_m=args.elevation_m)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    filled = sum(value is not None for value in document['values'].values())
    print(f'{args.output}: {filled}/{len(document["values"])} days, reviewed=false')


if __name__ == '__main__':
    main()
