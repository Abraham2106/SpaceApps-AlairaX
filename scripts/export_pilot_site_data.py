"""Export the verified regional comparison matrix for the static frontend."""

import argparse
import json
from pathlib import Path

from backend.app.api.schemas.contracts import REGIONAL_PILOT_WARNING
from backend.app.infrastructure.cache import write_json
from backend.app.simulation.parameters import load_rotations
from scripts.build_analogs import SCENARIOS
from scripts.qa_scientific_release import verify_result

SCENARIO_NAMES = ('Niño fuerte', 'Neutro', 'Niña', 'Como 2026')
ROTATIONS_FILE = Path('research/parameters/rotations.yaml')
ROTATION_NAMES = {
    'rice_melon': 'Arroz → melón', 'rice_legume': 'Arroz → caupí',
    'rice_sorghum': 'Arroz → sorgo forrajero',
}


def export_site_data(analogs, comparisons_dir, destination):
    if comparisons_dir.resolve() == destination.resolve():
        raise ValueError('the output directory must differ from the source comparisons')
    metadata = {key: analogs[key] for key in ('schema_version', '_mock', 'generado', 'zona', 'source_refs')}
    metadata['warnings'] = [REGIONAL_PILOT_WARNING]
    results, choices = {}, []
    for scenario_id, name in zip(SCENARIOS, SCENARIO_NAMES):
        scenario = analogs['scenarios'][scenario_id]
        if scenario['status'] != 'available':
            raise ValueError(f'{scenario_id}: {scenario.get("reason", "unavailable")}')
        years = [neighbor['year'] for neighbor in scenario['neighbors']]
        filename = f'compare-{scenario_id}.json'
        payload = json.loads((comparisons_dir / filename).read_bytes())
        result = verify_result(payload, scenario_id, years, regional_pilot=True)
        results[filename] = result
        choices.append({
            'scenario_id': scenario_id, 'name': name, 'result_file': filename,
            'selection_status': 'available', 'k': len(years),
            'sample_warning': 'Cuantiles descriptivos de una muestra pequeña.' if len(years) < 5 else None,
        })

    rotations = load_rotations(ROTATIONS_FILE).rotations
    write_json(destination / 'rotations.json', metadata | {'rotations': [
        {'rotation_id': row.rotation_id, 'name': ROTATION_NAMES[row.rotation_id],
         'baseline': row.is_current}
        for row in rotations
    ]})
    for filename, result in results.items():
        # The static files contain the full daily series, so avoid repeated indentation.
        temporary = destination / f'{filename}.tmp'
        temporary.write_text(result.model_dump_json(by_alias=True) + '\n', encoding='utf-8')
        temporary.replace(destination / filename)
    write_json(destination / 'scenarios.json', metadata | {'scenarios': choices})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analogs', required=True, type=Path)
    parser.add_argument('--comparisons-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    export_site_data(json.loads(args.analogs.read_bytes()), args.comparisons_dir, args.output_dir)


if __name__ == '__main__':
    main()
