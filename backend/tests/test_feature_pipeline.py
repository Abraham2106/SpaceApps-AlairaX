from datetime import date
from pathlib import Path

import pytest

from backend.app.intelligence.feature_pipeline import RegionConfig, daily_features, hls_ndvi
from scripts.build_region_features import build_region
from scripts.build_surrogate_dataset import build_dataset
from scripts.smoke_kernel import smoke_inputs


def test_real_davis_snapshot_replays_and_excludes_future_enso():
    config = RegionConfig.model_validate_json(Path('configs/regions/davis.json').read_bytes())
    climate = sorted(Path('datasets/processed/climate-davis').glob('power_*.json'))
    sources = Path('datasets/processed/climate')
    output, seasonal, analogs = build_region(config, climate, sources/'oni.json', sources/'roni.json',
        et0_file=Path('datasets/processed/climate-davis/et0.json'))
    assert output['quality']['rows'] == 106
    assert output['daily'][-1]['rain_90d_mm'] is not None
    assert all(row['period_end'] <= '2024-04-15' for rows in output['enso'].values() for row in rows)
    assert output['et0_reviewed'] is False
    assert seasonal['features'] == []  # FMA ends after the April 15 cutoff.
    assert all(row['status'] == 'unavailable' for row in analogs['scenarios'].values())


def test_trailing_window_retains_gaps_and_ignores_future_rows():
    config = RegionConfig.model_validate_json(Path('configs/regions/davis.json').read_bytes())
    config = config.model_copy(update={'as_of': date(2024, 1, 8)})
    rows = {}
    for n in (1, 2, 3, 5, 6, 7, 8, 9):
        day = date(2024, 1, n)
        rows[day] = dict(date=day.isoformat(), precipitation_mm=2, tmin_c=10, tmax_c=20,
            relative_humidity_pct=50, wind_speed_2m_m_s=2, solar_radiation_mj_m2_day=10, et0_mm=None)
    output, _ = daily_features(config, rows, {})
    assert len(output) == 8
    assert output[-1]['rain_7d_mm'] is None
    assert output[-1]['rain_7d_valid_days'] == 6
    assert output[-1]['tmean_c'] == 15


def test_crs_and_hls_quality_mask():
    raw = Path('configs/regions/guanacaste.json').read_text(encoding='utf-8')
    with pytest.raises(ValueError, match='EPSG:4326'):
        RegionConfig.model_validate_json(raw.replace('EPSG:4326', 'EPSG:3857'))
    pixels = [{'red': .2, 'nir': .6, 'fmask': mask} for mask in (0, 2, 4, 8, 16, 32, 192, 255)]
    pixels += [{'red': -9999, 'nir': .5, 'fmask': 0}]
    assert hls_ndvi(pixels) == pytest.approx(dict(ndvi_mean=.5, low_ndvi_fraction=0, valid_pixels=1, total_pixels=9))


def test_surrogate_groups_rotations_and_purges_shared_weather_at_boundary():
    dataset = build_dataset(smoke_inputs((2012, 2013, 2014, 2018)), validation_start=2014, test_start=2018)
    assert dataset['_mock']
    assert {row['year'] for row in dataset['rejected']} == {2013}
    assert {row['climate_year']: row['split'] for row in dataset['rows']} == {
        2012: 'train', 2014: 'validation', 2018: 'test'}
    for row in dataset['rows']:
        assert row['label_source'] == 'simulation'
        assert not row['features'].keys() & row['labels'].keys()
