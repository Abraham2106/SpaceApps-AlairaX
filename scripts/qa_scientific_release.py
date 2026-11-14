"""Verify the scientific comparison matrix and the built Pages artifact."""

import argparse
from pathlib import Path
from typing import get_args

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from backend.app.api.main import PROCESSED, ROOT, create_app
from backend.app.api.schemas.contracts import METRICS, CompareResponse, RotationId, ScenarioId


def verify_result(payload, scenario_id, years):
    result = CompareResponse.model_validate(payload)
    if result.mock or not result.zona.validated:
        raise ValueError('expected a scientific result for a confirmed zone')
    if result.scenario_id != scenario_id or [a.year for a in result.analog_years] != years:
        raise ValueError('scenario or analog years differ from the catalog')
    if {r.rotation_id for r in result.rotations} != set(get_args(RotationId)):
        raise ValueError('comparison must cover all three rotations')
    for rotation in result.rotations:
        for metric in METRICS:
            if any(getattr(summary, metric).n != len(years)
                   for summary in (rotation.metrics, rotation.delta_vs_baseline)):
                raise ValueError(f'{rotation.rotation_id}.{metric} has incomplete quantiles')
        if any(run.mock or not run.daily_balance for run in rotation.runs):
            raise ValueError(f'{rotation.rotation_id} has synthetic runs or missing daily balances')
    return result


def verify_release(client, dist):
    failures = []
    pages = None
    base = '/SpaceApps-AlairaX'
    if not (dist / 'index.html').is_file():
        failures.append(f'Production build missing at {dist}')
    else:
        site = FastAPI()
        site.mount(base, StaticFiles(directory=dist, html=True))
        pages = TestClient(site)
        landing = pages.get(f'{base}/')
        if landing.status_code != 200 or 'Página provisional' in landing.text:
            failures.append('Production homepage is unavailable or contains the Pages placeholder')

    response = client.get('/scenarios')
    if response.status_code != 200:
        return failures + [f'Scenario catalog: HTTP {response.status_code} {response.json()}']
    catalog = response.json()
    for scenario_id in get_args(ScenarioId):
        scenario = catalog['scenarios'].get(scenario_id, {})
        if scenario.get('status') != 'available':
            failures.append(f'{scenario_id}: {scenario.get("reason", "missing or unavailable")}')
            continue
        response = client.post('/compare', json={
            'zona': catalog['zona'], 'scenario_id': scenario_id, 'k': scenario['k'],
        })
        if response.status_code != 200:
            failures.append(f'{scenario_id}: HTTP {response.status_code} {response.json()}')
            continue
        try:
            years = [row['year'] for row in scenario['neighbors']]
            actual = verify_result(response.json(), scenario_id, years)
            if pages is None:
                print(f'{scenario_id}: API verified across 3 rotations × {len(years)} analogs')
                continue
            published = pages.get(f'{base}/data/compare-{scenario_id}.json')
            if published.status_code != 200:
                raise ValueError(f'published comparison returned HTTP {published.status_code}')
            public = verify_result(published.json(), scenario_id, years)
            # Timestamps reflect separate executions of the same input batch.
            exclude = {'generado': True, 'rotations': {'__all__': {
                'runs': {'__all__': {'generado'}},
            }}}
            if actual.model_dump(exclude=exclude) != public.model_dump(exclude=exclude):
                raise ValueError('published comparison differs from the API calculation')
        except (OSError, ValueError) as error:
            failures.append(f'{scenario_id}: {error}')
        else:
            print(f'{scenario_id}: 3 rotations × {len(years)} analogs verified')
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analogs', type=Path, default=PROCESSED / 'analogs' / 'analogos.json')
    parser.add_argument('--inputs-dir', type=Path, default=ROOT / 'outputs' / 'inputs')
    parser.add_argument('--dist', type=Path, default=ROOT / 'frontend' / 'dist')
    args = parser.parse_args()
    client = TestClient(create_app(args.analogs, args.inputs_dir))
    failures = verify_release(client, args.dist)
    for failure in failures:
        print(f'BLOCKED: {failure}')
    if not failures:
        print('Scientific release: 12 comparisons matched the production artifact')
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
