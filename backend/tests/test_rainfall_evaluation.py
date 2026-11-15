from datetime import date, timedelta
import pytest

from scripts.evaluate_rainfall import STATION_ID, nonoverlapping, read_station


def station_row(*, day_one=123, measurement=' ', quality=' '):
    values = [f'{day_one:5d}{measurement}{quality}S'] + ['-9999   '] * 30
    return STATION_ID + '202301PRCP' + ''.join(values) + '\n'


def test_station_units_quality_and_missing_days(tmp_path):
    path = tmp_path / 'station.dly'
    path.write_text(station_row(), encoding='ascii')
    assert read_station(path) == {date(2023, 1, 1): 12.3}
    for kwargs in ({'quality': 'X'}, {'measurement': 'B'}, {'measurement': 'D'},
                   {'day_one': -9999}):
        path.write_text(station_row(**kwargs), encoding='ascii')
        assert read_station(path) == {}
    path.write_text(station_row(measurement='T', day_one=0), encoding='ascii')
    assert read_station(path) == {date(2023, 1, 1): 0}


def test_station_duplicate_dates_are_rejected(tmp_path):
    path = tmp_path / 'station.dly'
    path.write_text(station_row() * 2, encoding='ascii')
    with pytest.raises(ValueError, match='duplicate'):
        read_station(path)


def test_disjoint_weeks_do_not_share_target_dates():
    origins = [date(2023, 1, 1) + timedelta(days=n) for n in range(22)]
    rows = [{'date': origin, 'label_end': origin + timedelta(days=7)} for origin in origins]
    assert [row['date'] for row in nonoverlapping(rows)] == origins[::7]
