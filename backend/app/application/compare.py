"""Run each selected analog under identical soil and management inputs."""

from collections.abc import Callable
from datetime import datetime, timezone
from hashlib import sha256
import json

from backend.app.api.schemas.contracts import (
    REGIONAL_PILOT_WARNING, AnalogYear, CompareRequest, CompareResponse, SimulationInput, SimulationResult,
)
from backend.app.intelligence.counterfactual import compare_runs


def environment_fingerprint(simulation: SimulationInput) -> str:
    """Exclude rotation so alternative schedules share the same environment ID."""
    payload = simulation.model_dump(mode='json', by_alias=True)
    environment = {key: payload[key] for key in ('_mock', 'zona', 'climate', 'soil', 'assumptions')}
    if simulation.regional_pilot:
        environment['regional_pilot'] = True
    return sha256(json.dumps(environment, sort_keys=True, separators=(',', ':'),
                             allow_nan=False).encode()).hexdigest()


def execute_comparison(request: CompareRequest, analogs: list[AnalogYear],
                       inputs: list[SimulationInput], *,
                       simulate_rotation: Callable[..., SimulationResult | dict]) -> CompareResponse:
    """Kernel callback uses climate=, soil=, rotation= and assumptions=.

    It returns numerical fields (metrics, daily_balance, assumptions,
    source_refs, warnings, model_version), or a full validated SimulationResult.
    No ET0, water balance equation or crop parameter is implemented here.
    """
    request = CompareRequest.model_validate(request.model_dump())
    analogs = [AnalogYear.model_validate(a.model_dump()) for a in analogs]
    inputs = [SimulationInput.model_validate(i.model_dump()) for i in inputs]
    expected = {(r, a.year) for r in request.rotation_ids for a in analogs}
    indexed = {(i.rotation.rotation_id, i.climate.year): i for i in inputs}
    if len(indexed) != len(inputs) or set(indexed) != expected:
        raise ValueError('expected one input per requested rotation and analog year')
    # Validate the entire batch before running an expensive kernel.
    fingerprints = {}
    for simulation in inputs:
        SimulationInput.model_validate(simulation.model_dump())
        if simulation.scenario_id != request.scenario_id or simulation.zona != request.zona:
            raise ValueError('input scenario and zone must match the request')
        fingerprint = environment_fingerprint(simulation)
        year = simulation.climate.year
        if year in fingerprints and fingerprints[year] != fingerprint:
            raise ValueError('paired rotations must receive identical climate, soil and management')
        fingerprints[year] = fingerprint
    if len({i.mock for i in inputs}) != 1:
        raise ValueError('cannot mix mock and real inputs')
    if len({a.year for a in analogs}) != len(analogs) or len(analogs) != request.k:
        raise ValueError('expected k distinct analog years')
    runs = []
    for simulation in inputs:
        # Protect validated inputs from in-place mutation by a kernel implementation.
        safe = simulation.model_copy(deep=True)
        output = simulate_rotation(climate=safe.climate, soil=safe.soil,
                                   rotation=safe.rotation, assumptions=safe.assumptions)
        metadata = dict(mock=simulation.mock, generado=datetime.now(timezone.utc),
                        zona=simulation.zona, rotation_id=simulation.rotation.rotation_id,
                        scenario_id=simulation.scenario_id, year=simulation.climate.year,
                        environment_id=fingerprints[simulation.climate.year])
        if isinstance(output, SimulationResult):
            result = SimulationResult.model_validate(output.model_dump())
            for key in ('mock', 'zona', 'rotation_id', 'scenario_id', 'year', 'environment_id'):
                if getattr(result, key) != metadata[key]:
                    raise ValueError(f'kernel returned mismatched {key}')
        else:
            result = SimulationResult(**metadata, **output)
        if not simulation.mock or result.daily_balance:
            expected_dates = [day.date for day in simulation.climate.days]
            if [day.date for day in result.daily_balance] != expected_dates:
                raise ValueError('kernel daily balance must cover exactly the input climate dates')
        if (result.metrics.water_stress_days is not None and
                result.metrics.water_stress_days > len(simulation.climate.days)):
            raise ValueError('water stress days exceed input climate duration')
        pilot_warnings = [REGIONAL_PILOT_WARNING] if simulation.regional_pilot else []
        result.warnings = list(dict.fromkeys(pilot_warnings + simulation.warnings + result.warnings))
        result.source_refs = list(dict.fromkeys(simulation.source_refs + result.source_refs))
        runs.append(result)
    return compare_runs(request, analogs, runs)
