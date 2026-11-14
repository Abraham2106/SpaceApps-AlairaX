"""Behavioral checks for alignment, missing data and temporal leakage."""

import math
import unittest
from dataclasses import replace
from datetime import date

from backend.app.intelligence.analog_knn import find_analogs, select_scenario
from backend.app.intelligence.features import FEATURE_NAMES, build_season_features


def season(year, rain=1.0, oni=0.0, *, mock=False):
    return build_season_features([
        {'date': date(year, 4, day), 'precipitation_mm': rain,
         'et0_mm': 4.0, 'tmax_c': 34.0 + day}
        for day in range(1, 4)
    ], year=year, start=date(year, 4, 1), end=date(year, 4, 3),
       oni=oni, heat_threshold_c=36.0, mock=mock)


class FeatureChecks(unittest.TestCase):
    def test_oni_sentinel_is_not_a_la_nina_observation(self):
        for sentinel in (-999, -99.99, -99.9):
            with self.assertRaises(ValueError):
                season(2015, oni=sentinel)

    def test_aggregate_units_and_threshold(self):
        value = season(2015, rain=2.0, oni=1.7)
        self.assertEqual(value.precipitation_mm, 6)
        self.assertEqual(value.et0_mm, 12)
        self.assertEqual(value.tmax_mean_c, 36)
        self.assertEqual(value.heat_days, 2)
        self.assertEqual(value.oni, 1.7)

    def test_missing_and_duplicate_days_are_rejected(self):
        rows = [{'date': '2015-04-01', 'precipitation_mm': 1, 'et0_mm': 2, 'tmax_c': 30}]
        for data in (rows, rows * 3):
            with self.assertRaises(ValueError):
                build_season_features(data, year=2015, start=date(2015, 4, 1),
                                      end=date(2015, 4, 3), oni=0)

    def test_missing_et0_and_nonfinite_input_are_rejected(self):
        for et0 in (None, -999.0, float('nan'), float('inf')):
            with self.subTest(et0=et0), self.assertRaises(ValueError):
                build_season_features([{'date': '2015-04-01', 'precipitation_mm': 1,
                                        'et0_mm': et0, 'tmax_c': 30}],
                    year=2015, start=date(2015, 4, 1), end=date(2015, 4, 1), oni=0)


class AnalogChecks(unittest.TestCase):
    def test_phase_selector_rejects_nonpositive_k_before_empty_bucket(self):
        for k in (0, -1, True):
            with self.assertRaisesRegex(ValueError, 'positive integer'):
                select_scenario([season(2010)], 'strong_el_nino', k=k)

    def test_2026_never_enters_candidates_or_scaler(self):
        history = [season(2010, 1), season(2011, 3)]
        target = season(2026, 2)
        first = find_analogs(history, target, k=2)
        second = find_analogs(history + [season(2026, 100000)], target, k=2)
        self.assertEqual(first, second)
        self.assertEqual(first['scaler']['fit_years'], [2010, 2011])
        self.assertEqual(first['scaler']['mean']['precipitation_mm'], 6)

    def test_target_and_future_cannot_shift_historical_backtest(self):
        target = season(2015, 2)
        history = [season(2010, 1), season(2011, 3)]
        a = find_analogs(history, target, k=2)
        b = find_analogs(history + [target, season(2016, 10000)], target, k=2)
        self.assertEqual(a, b)

    def test_distance_contributions_and_tie_break_are_reproducible(self):
        result = find_analogs([season(2011, 3), season(2010, 1)], season(2026, 2), k=2)
        self.assertEqual([row['year'] for row in result['neighbors']], [2010, 2011])
        for row in result['neighbors']:
            self.assertAlmostEqual(sum(row['squared_distance_contributions'].values()), row['distance'] ** 2)

    def test_window_threshold_and_oni_period_must_match(self):
        target = season(2026)
        for changed in (replace(season(2010), heat_threshold_c=40),
                        replace(season(2010), oni_season='OND'),
                        replace(season(2010), end=date(2010, 4, 2))):
            with self.assertRaises(ValueError):
                find_analogs([changed], target, k=1)

    def test_invalid_weights_and_insufficient_years_fail(self):
        for weights in ({}, {name: 0 for name in FEATURE_NAMES},
                        {name: math.inf for name in FEATURE_NAMES}):
            with self.assertRaises(ValueError):
                find_analogs([season(2010)], season(2026), k=1, weights=weights)
        with self.assertRaises(ValueError):
            find_analogs([season(2010)], season(2026), k=5)

    def test_like_2026_requires_tracking_and_preserves_mock_status(self):
        history = [season(2010, mock=True), season(2011, mock=True)]
        with self.assertRaises(ValueError):
            select_scenario(history, 'like_2026', k=1)
        result = select_scenario(history, 'like_2026', tracking_2026=season(2026, mock=True), k=1)
        self.assertTrue(result['_mock'])
        with self.assertRaises(ValueError):
            find_analogs(history, season(2026), k=1)

    def test_phase_bucket_only_returns_eligible_years(self):
        history = [season(1981 + i, i + 1, oni=2.0) for i in range(5)]
        history += [season(2000 + i, 1, oni=-1.0) for i in range(5)]
        result = select_scenario(history, 'strong_el_nino', k=5)
        self.assertEqual({row['year'] for row in result['neighbors']}, set(range(1981, 1986)))
        self.assertEqual(result['scaler']['fit_years'], list(range(1981, 1986)) + list(range(2000, 2005)))
        self.assertEqual(result['target_kind'], 'historical_bucket_centroid')
        self.assertEqual(result['k_sensitivity'][-1]['k'], 5)


if __name__ == '__main__':
    unittest.main()
