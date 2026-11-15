"""Build regional feature artifacts offline from normalized provider snapshots."""

import argparse
from datetime import date
from pathlib import Path

from backend.app.application.prepare_inputs import ReviewedET0, same_zone_identity
from backend.app.infrastructure.cache import write_json
from backend.app.infrastructure.power import PARAMETERS
from backend.app.intelligence.feature_pipeline import (
    FarmContext, RegionConfig, daily_features, date_range, enso_features, hls_ndvi,
)
from backend.app.intelligence.features import build_season_features
from scripts.build_analogs import _oni_period_end, _read, build_pipeline, load_normalized_climate


def build_region(config, climate_files, oni_file, roni_file, *, et0_file=None, soil_file=None,
                 hls_file=None, farm_file=None):
    documents, provenance, days = load_normalized_climate(climate_files)
    zone, mock = documents[0]['zona'], documents[0]['_mock']
    if (zone['latitude'], zone['longitude']) != (config.aoi.latitude, config.aoi.longitude):
        raise ValueError('climate coordinates do not match region point')
    for document in documents:
        if any(document['units'].get(field) != unit for field, unit in PARAMETERS.values()):
            raise ValueError('climate units must use the normalized POWER contract')
    for document, record in zip(documents, provenance):
        header = document.get('provider_header') or {}
        record['product'] = {
            'provider': 'NASA POWER', 'api': header.get('api'),
            'source_products': header.get('sources', []),
            'time_standard': header.get('time_standard', header.get('timeStandard')),
            'observation_start': document.get('start'), 'observation_end': document.get('end'),
            'normalized_units': document['units'],
        }
    et0 = None
    if et0_file:
        payload, record = _read(et0_file)
        et0 = ReviewedET0.model_validate(payload)
        if et0.mock != mock or not same_zone_identity(et0.zona, zone) or et0.units != 'mm/day':
            raise ValueError('ET0 must match zone and mock status and use mm/day')
        provenance.append(record)
    farm = None
    if farm_file:
        payload, record = _read(farm_file)
        if payload['_mock'] != mock:
            raise ValueError('farm context must use the same mock status as climate')
        farm = FarmContext.model_validate({key: value for key, value in payload.items() if key != '_mock'})
        if farm.region_id != config.id or farm.available_on > config.as_of:
            raise ValueError('farm context must match the region and be available by the cutoff')
        provenance.append(record)
    daily, quality = daily_features(config, days, et0.values if et0 else {}, farm=farm)
    indices = {}
    for name, path in [('oni', oni_file), ('roni', roni_file)]:
        snapshot, record = _read(path)
        if snapshot['index'] != name or snapshot['_mock'] != mock or snapshot['units'] != 'degree_C_anomaly':
            raise ValueError(f'invalid normalized {name} snapshot')
        indices[name] = enso_features(snapshot['records'], _oni_period_end, config.as_of)
        provenance.append(record)
    optional = {}
    for name, path in [('soil', soil_file), ('vegetation', hls_file)]:
        if not path:
            optional[name] = {'status': 'unavailable'}
            continue
        snapshot, record = _read(path)
        if snapshot['_mock'] != mock or not same_zone_identity(snapshot['zona'], zone):
            raise ValueError(f'{name} must match the climate zone and mock status')
        provenance.append(record)
        if name == 'soil':
            optional[name] = {'status': snapshot['status'], 'kind': 'mapped_estimate',
                              'layers': snapshot['properties'], 'kernel_profile': snapshot['soil_profile']}
        else:
            scenes = [dict(scene_id=s['scene_id'], date=s['date'], **hls_ndvi(s['pixels']))
                      for s in snapshot['scenes'] if date.fromisoformat(s['date']) <= config.as_of]
            optional[name] = {'status': 'available' if any(s['valid_pixels'] for s in scenes) else 'unavailable',
                              'kind': 'satellite_derived', 'resolution_m': 30, 'scenes': scenes}
    features, analogs = build_pipeline(
        climate_files, oni_file, et0_file=et0_file if et0 and et0.reviewed else None,
        start_mmdd=config.season_start, end_mmdd=config.season_end, oni_season=config.oni_season,
        as_of=config.as_of, heat_threshold_c=config.heat_threshold_c, k=config.analog_k,
        strong_el_nino_k=config.strong_el_nino_k, analysis_start=config.start)
    # Export the feature matrix for technical review while leaving scenario
    # selection gated by the existing reviewed-ET0 contract.
    if et0 and not et0.reviewed:
        oni = {(r['year'], r['season']): r['anomaly_c'] for r in indices['oni']}
        provisional, excluded = [], []
        for year in sorted({day.year for day in days if config.start.year <= day.year <= config.as_of.year}):
            start = date.fromisoformat(f'{year}-{config.season_start}')
            end = date.fromisoformat(f'{year}-{config.season_end}')
            if start < config.start or end > config.as_of:
                continue
            try:
                rows = [days[day] | {'et0_mm': et0.values.get(day)} for day in date_range(start, end) if day in days]
                feature = build_season_features(rows, year=year, start=start, end=end,
                    oni=oni.get((year, config.oni_season)), oni_season=config.oni_season,
                    heat_threshold_c=config.heat_threshold_c, mock=mock)
                provisional.append(feature.to_dict())
            except ValueError as error:
                excluded.append({'year': year, 'reason': str(error)})
        features = features | {'status': 'provisional_et0', 'et0_reviewed': False,
                              'et0_model_version': et0.model_version,
                              'source_refs': sorted(set(features['source_refs'] + et0.source_refs)),
                              'provenance': provenance, 'features': provisional, 'excluded_years': excluded}
    metadata = {'schema_version': '1.0.0', '_mock': mock, 'region': config.model_dump(mode='json'),
                'provenance': provenance, 'et0_reviewed': et0.reviewed if et0 else False,
                'climate_kind': 'gridded_estimate', 'enso_kind': 'retrospective_index',
                'et0_kind': 'modeled', 'quality': quality,
                'nominal_resolution': {'power_meteorology_deg': [0.5, 0.625],
                                       'power_primary_solar_deg': [1, 1],
                                       'soilgrids_m': 250, 'hls_m': 30}}
    return metadata | {'daily': daily, 'enso': indices,
                       'farm': farm.model_dump(mode='json') if farm else None, **optional}, features, analogs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--region', type=Path, required=True)
    parser.add_argument('--climate', type=Path, nargs='+', required=True)
    for name in ('oni', 'roni', 'output-dir'):
        parser.add_argument(f'--{name}', type=Path, required=True)
    for name in ('et0', 'soil', 'hls', 'farm'):
        parser.add_argument(f'--{name}', type=Path)
    args = parser.parse_args()
    config = RegionConfig.model_validate_json(args.region.read_bytes())
    outputs = build_region(config, args.climate, args.oni, args.roni, et0_file=args.et0,
                           soil_file=args.soil, hls_file=args.hls, farm_file=args.farm)
    for name, output in zip(('regional-features', 'knn-features', 'analogs'), outputs):
        write_json(args.output_dir / f'{name}.json', output)
    print(f'{config.id}: {outputs[0]["quality"]["rows"]} daily rows; '
          f'{len(outputs[1]["features"])} KNN feature seasons; ET0 reviewed={outputs[0]["et0_reviewed"]}')


if __name__ == '__main__':
    main()
