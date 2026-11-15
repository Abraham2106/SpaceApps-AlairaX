"""Cache point forecasts from CHIRPS3-GEFS and individual ECMWF runs."""

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import struct
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.ingest_chirps import TYPE_FORMATS, TYPE_SIZES, lzw_decode, point_cells
from scripts.evaluate_rainfall import read_station

LAT, LON = 10.55, -85.5
RAW = Path('datasets/raw/forecast-comparison')


def request(url, byte_range=None):
    headers = {'User-Agent': 'NandaView weather research'}
    if byte_range:
        headers['Range'] = byte_range
    with urlopen(Request(url, headers=headers), timeout=35) as response:
        if byte_range and response.status != 206:
            raise ValueError('server must support partial reads')
        return response.read(), dict(response.headers)


def chirps_day(origin, valid):
    url = (f'https://data.chc.ucsb.edu/products/CHIRPS-GEFS/v3/daily/global/'
           f'{origin:%Y/%m/%d}/c3g_{valid:%Y.%m.%d}.tif')
    cache = RAW / 'chirps' / f'{sha256(url.encode()).hexdigest()}.json'
    if cache.exists():
        return json.loads(cache.read_bytes())
    header, _ = request(url, 'bytes=0-7')
    if header[:4] != b'II*\x00':
        raise ValueError('expected little-endian classic TIFF')
    ifd = struct.unpack('<I', header[4:8])[0]
    start = max(0, ifd - 65536)
    metadata, source_headers = request(url, f'bytes={start}-')
    offset = ifd - start
    count = struct.unpack_from('<H', metadata, offset)[0]
    tags = {}
    for i in range(count):
        entry = metadata[offset+2+12*i:offset+14+12*i]
        tag, kind, n = struct.unpack('<HHI', entry[:8])
        if kind not in TYPE_FORMATS:
            continue
        size = n * TYPE_SIZES[kind]
        if size <= 4:
            data = entry[8:8+size]
        else:
            pointer = struct.unpack('<I', entry[8:12])[0] - start
            data = metadata[pointer:pointer+size] if pointer >= 0 else b''
        if len(data) == size:
            tags[tag] = struct.unpack('<' + TYPE_FORMATS[kind] * n, data)
    for key, expected in {258: 32, 259: 5, 277: 1, 278: 1, 339: 3}.items():
        if tags.get(key, (None,))[0] != expected:
            raise ValueError(f'unsupported TIFF tag {key}')
    if tags.get(317, (1,))[0] != 1:
        raise ValueError('unsupported TIFF predictor')
    rows, cols = point_cells(tags)
    if min(rows) < 0 or max(rows) >= tags[257][0] or min(cols) < 0 or max(cols) >= tags[256][0]:
        raise ValueError('point outside raster')
    offsets, lengths = tags[273], tags[279]
    first = offsets[min(rows)]
    last = offsets[max(rows)] + lengths[max(rows)] - 1
    pixels, _ = request(url, f'bytes={first}-{last}')
    values = []
    for row in rows:
        position = offsets[row] - first
        decoded = lzw_decode(pixels[position:position+lengths[row]])
        if len(decoded) != 4 * tags[256][0]:
            raise ValueError('unexpected decoded scanline size')
        values.extend(struct.unpack_from('<f', decoded, 4 * col)[0] for col in cols)
    value = sum(values) / len(values) if all(math.isfinite(v) and v >= 0 for v in values) else None
    record = {'origin': str(origin), 'valid_date': str(valid), 'precipitation_mm': value,
              'url': url, 'fetched_at': datetime.now(timezone.utc).isoformat(),
              'source_last_modified': source_headers.get('Last-Modified'),
              'cell_method': 'mean of cells touching point', 'rows': rows, 'cols': cols,
              'raw_ranges': [{'start': 0, 'base64': base64.b64encode(header).decode()},
                             {'start': start, 'base64': base64.b64encode(metadata).decode()},
                             {'start': first, 'base64': base64.b64encode(pixels).decode()}]}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(record), encoding='utf-8')
    return record


def ecmwf(origin):
    # 12 UTC run is issued on the origin's morning. Verify real release times in live use.
    run = f'{origin}T12:00'
    url = ('https://single-runs-api.open-meteo.com/v1/forecast?latitude=10.55&longitude=-85.5'
           f'&run={run}&models=ecmwf_ifs&hourly=precipitation,temperature_2m,relative_humidity_2m,'
           'surface_pressure&forecast_days=9&timezone=UTC')
    cache = RAW / 'ecmwf' / f'{sha256(url.encode()).hexdigest()}.json'
    if cache.exists():
        body = cache.read_bytes()
    else:
        body, _ = request(url)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(body)
    data = json.loads(body)
    if data['hourly_units']['precipitation'] != 'mm':
        raise ValueError('ECMWF precipitation must be hourly mm')
    daily, verification_indices = [], []
    for step in range(1, 8):
        day = origin + timedelta(days=step)
        # UTC date sums match the CHIRPS daily date labels.
        indices = [i for i, stamp in enumerate(data['hourly']['time']) if stamp.startswith(str(day))]
        verification_indices.extend(indices)
        rain = [data['hourly']['precipitation'][i] for i in indices]
        daily.append(sum(rain) if len(rain) == 24 and all(v is not None for v in rain) else None)
    weather = {}
    for variable, unit in {'temperature_2m': '°C', 'relative_humidity_2m': '%', 'surface_pressure': 'hPa'}.items():
        values = [data['hourly'].get(variable, [None] * len(data['hourly']['time']))[i]
                  for i in verification_indices]
        valid = (data['hourly_units'].get(variable) == unit and len(values) == 168
                 and all(isinstance(value, (int, float)) and math.isfinite(value) for value in values))
        weather[f'{variable}_mean'] = sum(values)/len(values) if valid else None
    return {'run': run, 'source_url': url, 'raw_sha256': sha256(body).hexdigest(),
            'precipitation_mm': sum(daily) if all(v is not None for v in daily) else None,
            'daily_mm': daily, 'weather': weather, 'grid_point': [data['latitude'], data['longitude']]}


def one_origin(origin):
    errors, record = [], {'origin': str(origin), 'end': str(origin + timedelta(days=7))}
    try:
        record['ecmwf'] = ecmwf(origin)
    except (HTTPError, OSError, ValueError, KeyError) as error:
        errors.append(f'ECMWF: {type(error).__name__}: {error}')
    try:
        days = [chirps_day(origin, origin + timedelta(days=i)) for i in range(1, 8)]
        values = [day['precipitation_mm'] for day in days]
        record['chirps_gefs'] = {
            'precipitation_mm': sum(values) if all(v is not None for v in values) else None,
            'daily_mm': values, 'source_urls': [d['url'] for d in days],
        }
    except (HTTPError, OSError, ValueError, KeyError, struct.error) as error:
        errors.append(f'CHIRPS: {type(error).__name__}: {error}')
    record['errors'] = errors
    print(str(origin), 'OK' if not errors else errors, flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=date.fromisoformat, required=True)
    parser.add_argument('--end', type=date.fromisoformat, required=True)
    parser.add_argument('--step-days', type=int, default=7)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--include-station-origins', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.end < args.start or args.step_days < 1 or not 1 <= args.workers <= 4:
        parser.error('invalid date range, step or worker count')
    origins = [args.start + timedelta(days=i) for i in range(0, (args.end-args.start).days+1, args.step_days)]
    if args.include_station_origins:
        station = read_station(args.include_station_origins)
        station_origins = [args.start + timedelta(days=i) for i in range((args.end-args.start).days+1)
                           if all(args.start + timedelta(days=i+j) in station for j in range(1, 8))]
        origins = sorted(set(origins + station_origins))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for record in pool.map(one_origin, origins):
            records.append(record)
            document = {'_mock': False, 'latitude': LAT, 'longitude': LON, 'date_labels': 'UTC forecast calendar dates',
                        'warnings': ['Station observing-day and POWER LST boundaries can differ from these UTC dates.',
                                     'CHIRPS-GEFS historical files are reprocessed archives, not original publication vintages.'],
                        'records': records}
            args.output.write_text(json.dumps(document, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
