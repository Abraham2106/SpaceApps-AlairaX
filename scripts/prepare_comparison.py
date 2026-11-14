"""Assemble reviewed artifacts into complete input objects for run_comparison."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from backend.app.application.prepare_inputs import ComparisonSetup, prepare_inputs
from backend.app.infrastructure.cache import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analogs', required=True, type=Path)
    parser.add_argument('--scenario', required=True, choices=['strong_el_nino', 'neutral', 'la_nina', 'like_2026'])
    parser.add_argument('--climate', required=True, type=Path, nargs='+')
    parser.add_argument('--et0', required=True, type=Path)
    parser.add_argument('--setup', required=True, type=Path)
    parser.add_argument('--start-mmdd', required=True, help='Start of the historical SIMULATION window')
    parser.add_argument('--end-mmdd', required=True, help='End of the historical SIMULATION window')
    parser.add_argument('--end-year-offset', type=int, choices=(0, 1), default=0,
                        help='Use 1 when the simulation ends in the following calendar year')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--allow-mock', action='store_true')
    args = parser.parse_args()
    paths = [args.analogs, args.et0, args.setup, *args.climate]
    def identity(path):
        resolved = str(path.resolve())
        return resolved.casefold() if os.name == 'nt' else resolved
    manifest = args.output.with_suffix('.manifest.json')
    destinations = [args.output, manifest, args.output.with_suffix(args.output.suffix + '.tmp'),
                    manifest.with_suffix(manifest.suffix + '.tmp')]
    protected = {identity(path) for path in paths}
    if len({identity(p) for p in destinations}) != len(destinations) or any(
            identity(path) in protected for path in destinations):
        parser.error('output, manifest and temporary files must not overwrite input artifacts')
    contents = {p: p.read_bytes() for p in paths}
    documents = {p: json.loads(body) for p, body in contents.items()}
    setup = ComparisonSetup.model_validate(documents[args.setup])
    if setup.mock and not args.allow_mock:
        parser.error('synthetic setup requires --allow-mock; no input batch was written')
    try:
        inputs = prepare_inputs(documents[args.analogs], args.scenario,
                                [documents[p] for p in args.climate], documents[args.et0], setup,
                                start_mmdd=args.start_mmdd, end_mmdd=args.end_mmdd,
                                end_year_offset=args.end_year_offset)
    except (ValueError, KeyError) as error:
        parser.error(str(error))
    values = [simulation.model_dump(mode='json', by_alias=True) for simulation in inputs]
    write_json(args.output, values)
    write_json(manifest, {
        '_mock': setup.mock, 'scenario_id': args.scenario, 'input_count': len(inputs),
        'simulation_window': {'start_mmdd': args.start_mmdd, 'end_mmdd': args.end_mmdd,
                              'end_year_offset': args.end_year_offset},
        'artifacts': [{'file': str(path), 'sha256': sha256(body).hexdigest()}
                      for path, body in contents.items()],
        'output_sha256': sha256(args.output.read_bytes()).hexdigest(),
    })
    print(f'Prepared {len(inputs)} inputs at {args.output} (_mock={setup.mock})')


if __name__ == '__main__':
    main()
