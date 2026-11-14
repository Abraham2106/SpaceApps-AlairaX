"""Connect analog selection to Justin's kernel and export a static comparison."""

import argparse
from importlib import import_module
import json
from pathlib import Path

from backend.app.api.schemas.contracts import AnalogYear, CompareRequest, SimulationInput
from backend.app.application.compare import execute_comparison
from backend.app.application.prepare_inputs import same_zone_identity


def compare_from_analogs(document, scenario_id, inputs, *, simulate_rotation):
    scenario = document['scenarios'][scenario_id]
    if scenario['status'] != 'available':
        raise ValueError(f'analog selection unavailable: {scenario.get("reason", "unspecified")}')
    if type(document.get('_mock')) is not bool or scenario.get('_mock') != document['_mock']:
        raise ValueError('analog envelope and scenario mock flags must agree')
    analogs = [AnalogYear(year=a['year'], distance=a['distance']) for a in scenario['neighbors']]
    request = CompareRequest(zona=document['zona'], scenario_id=scenario_id, k=scenario['k'])
    years = {a.year for a in analogs}
    selected = [i for i in inputs if i.climate.year in years and i.rotation.rotation_id in request.rotation_ids]
    if selected:
        reviewed_zone = selected[0].zona
        if not same_zone_identity(document['zona'], reviewed_zone.model_dump(mode='json')):
            raise ValueError('analog selection and reviewed inputs must use the same zone identity')
        # Keep the original ingestion snapshot provisional while using the point
        # confirmation attached to the reviewed simulation setup.
        request.zona = reviewed_zone.model_copy(deep=True)
    if any(i.mock != document['_mock'] for i in selected):
        raise ValueError('analogs and kernel inputs must share mock status')
    result = execute_comparison(request, analogs, selected, simulate_rotation=simulate_rotation)
    result.source_refs = sorted(set(result.source_refs + document.get('source_refs', [])))
    result.warnings = list(dict.fromkeys(result.warnings + document.get('warnings', []) + scenario.get('warnings', [])))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analogs', required=True, type=Path)
    parser.add_argument('--scenario', required=True, choices=['strong_el_nino', 'neutral', 'la_nina', 'like_2026'])
    parser.add_argument('--inputs', required=True, type=Path, help='JSON array of complete SimulationInput objects')
    parser.add_argument('--kernel', required=True, help='Installed local module:function, e.g. backend.app.simulation.kernel:simulate_rotation')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--allow-mock', action='store_true')
    args = parser.parse_args()
    document = json.loads(args.analogs.read_text(encoding='utf-8'))
    inputs = [SimulationInput.model_validate(i) for i in json.loads(args.inputs.read_text(encoding='utf-8'))]
    if (document.get('_mock') or any(i.mock for i in inputs)) and not args.allow_mock:
        parser.error('synthetic data requires --allow-mock; no kernel was run')
    module, separator, name = args.kernel.partition(':')
    if not separator or not module or not name:
        parser.error('--kernel must be module:function')
    kernel = getattr(import_module(module), name)
    result = compare_from_analogs(document, args.scenario, inputs, simulate_rotation=kernel)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.model_dump_json(by_alias=True, indent=2) + '\n', encoding='utf-8')
    print(f'Exported {args.output} (_mock={result.mock})')


if __name__ == '__main__':
    main()
