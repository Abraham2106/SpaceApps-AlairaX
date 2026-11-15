from datetime import date, timedelta

from scripts.train_molab import rainfall_examples, split_rows


def test_rainfall_keeps_future_values_in_the_label_only():
    start = date(2020, 1, 1)
    rows = [{'date': (start + timedelta(days=i)).isoformat(), 'precipitation_mm': i,
             'rain_7d_mm': 99 + i, 'future_summary': 500} for i in range(9)]
    first, second = rainfall_examples({'daily': rows})
    assert first['features']['rain_7d_mm'] == 99
    assert 'future_summary' not in first['features']
    assert first['target'] == sum(range(1, 8))
    assert second['label_end'] == start + timedelta(days=8)


def test_split_purges_labels_that_reach_the_next_partition():
    def row(day, end):
        return {'date': date.fromisoformat(day), 'label_end': date.fromisoformat(end)}

    rows = [row('2017-12-20', '2017-12-27'), row('2017-12-27', '2018-01-03'),
            row('2018-01-01', '2018-01-08'), row('2022-12-25', '2023-01-01'),
            row('2023-01-01', '2023-01-08')]
    result, purged = split_rows(rows, date(2018, 1, 1), date(2023, 1, 1))
    assert purged == 2
    assert {name: len(values) for name, values in result.items()} == {'train': 1, 'validation': 1, 'test': 1}
