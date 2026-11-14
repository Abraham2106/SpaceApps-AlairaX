"""Export validated precomputed kernel results for the static frontend.

python -m scripts.compare_results --request request.json --analogs analogs.json \
    --runs runs.json --output frontend/public/data/compare-neutral.json
"""

import argparse
import json
from pathlib import Path

from backend.app.api.schemas.contracts import AnalogYear, CompareRequest, SimulationResult
from backend.app.intelligence.counterfactual import compare_runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('request', 'analogs', 'runs', 'output'):
        parser.add_argument(f'--{name}', required=True, type=Path)
    parser.add_argument('--allow-mock', action='store_true', help='explicitly allow synthetic runs')
    args = parser.parse_args()
    request = CompareRequest.model_validate_json(args.request.read_text(encoding='utf-8'))
    analogs = [AnalogYear.model_validate(a) for a in json.loads(args.analogs.read_text(encoding='utf-8'))]
    runs = [SimulationResult.model_validate(r) for r in json.loads(args.runs.read_text(encoding='utf-8'))]
    result = compare_runs(request, analogs, runs)
    if result.mock and not args.allow_mock:
        parser.error('mock results require --allow-mock; no output written')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.model_dump_json(by_alias=True, indent=2) + '\n', encoding='utf-8')
    print(f'Exported {args.output} (_mock={result.mock})')


if __name__ == '__main__':
    main()
