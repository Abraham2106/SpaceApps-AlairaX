"""Local HTTP interface for catalog data and prepared historical comparisons."""

import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from pydantic import TypeAdapter

from backend.app.api.schemas.contracts import (
    AnalogYear, CompareRequest, CompareResponse, SimulationInput,
)
from backend.app.application.compare import execute_comparison
from backend.app.application.prepare_inputs import same_zone_identity
from backend.app.infrastructure.imagery import (
    ImageryInputError, ImageryUpstreamError, SentinelImagery,
)
from backend.app.simulation.kernel import FAO56_REF, simulate_rotation
from backend.app.simulation.parameters import load_rotations
from backend.app.simulation.version import MODEL_VERSION

ROOT = Path(__file__).resolve().parents[3]
PROCESSED = ROOT / 'datasets' / 'processed'
logger = logging.getLogger(__name__)
input_batch = TypeAdapter(list[SimulationInput])


def read_artifact(path: Path, label: str):
    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError) as error:
        logger.warning('Cannot read %s: %s', path, error)
        raise HTTPException(503, detail=f'{label} missing or unreadable') from error


def create_app(
    analogs_path: Path = PROCESSED / 'analogs' / 'analogos.json',
    inputs_dir: Path = ROOT / 'outputs' / 'inputs',
    *,
    allow_mock: bool = False,
    imagery: SentinelImagery | None = None,
) -> FastAPI:
    app = FastAPI(title='AlairaX', version=MODEL_VERSION)
    sentinel = imagery or SentinelImagery()
    # Imagery is public data without credentials, so only these routes allow any origin.
    open_cors = {'Access-Control-Allow-Origin': '*'}

    def imagery_error(error: Exception) -> HTTPException:
        if isinstance(error, ImageryInputError):
            return HTTPException(422, detail=str(error), headers=open_cors)
        logger.warning('Sentinel-2 imagery unavailable: %s', error)
        return HTTPException(502, detail=str(error), headers=open_cors)

    def catalog() -> dict:
        document = read_artifact(analogs_path, 'Analog catalog')
        if (not isinstance(document, dict) or type(document.get('_mock')) is not bool
                or not isinstance(document.get('scenarios'), dict)):
            raise HTTPException(503, detail='Invalid analog catalog')
        if document['_mock'] and not allow_mock:
            raise HTTPException(503, detail='Synthetic analog catalog is disabled')
        return document

    @app.get('/health')
    def health():
        return {'status': 'ok', 'model_version': MODEL_VERSION}

    @app.get('/rotations')
    def rotations():
        try:
            library = load_rotations(ROOT / 'research' / 'parameters' / 'rotations.yaml')
        except (OSError, ValueError) as error:
            logger.warning('Cannot load rotation catalog: %s', error)
            raise HTTPException(503, detail='Rotation catalog missing or invalid') from error
        return library

    @app.get('/scenarios')
    def scenarios():
        document = catalog()
        keys = ('schema_version', '_mock', 'generado', 'zona', 'warnings', 'scenarios')
        return {key: document[key] for key in keys if key in document}

    @app.get('/sources')
    def sources():
        document = catalog()
        soil = read_artifact(PROCESSED / 'soil' / 'soil_readiness_10.55_-85.5.json',
                             'Soil readiness artifact')
        return {
            '_mock': document['_mock'],
            'source_refs': sorted(set([FAO56_REF, *document.get('source_refs', []),
                                       *soil.get('source_refs', [])])),
        }

    @app.post('/compare', responses={404: {'description': 'Unknown zone'},
                                    409: {'description': 'Scenario or batch unavailable'},
                                    503: {'description': 'Invalid or missing artifact'}})
    def compare(request: CompareRequest) -> CompareResponse:
        document = catalog()
        try:
            same_zone = same_zone_identity(document.get('zona'), request.zona.model_dump())
        except ValueError as error:
            raise HTTPException(503, detail='Invalid zone in analog catalog') from error
        if not same_zone:
            raise HTTPException(404, detail='Zone is not in the analog catalog')
        scenario = document['scenarios'].get(request.scenario_id)
        if not isinstance(scenario, dict):
            raise HTTPException(503, detail='Scenario missing from analog catalog')
        if scenario.get('status') != 'available':
            raise HTTPException(409, detail=scenario.get('reason') or 'Scenario unavailable')
        if scenario.get('_mock') is not document['_mock']:
            raise HTTPException(503, detail='Inconsistent scenario mock flag')
        try:
            analogs = [AnalogYear.model_validate(row, extra='ignore')
                       for row in scenario['neighbors']]
            if len(analogs) != scenario['k'] or len({a.year for a in analogs}) != len(analogs):
                raise ValueError('unexpected analog count')
        except (KeyError, TypeError, ValueError) as error:
            logger.warning('Invalid analog selection for %s: %s', request.scenario_id, error)
            raise HTTPException(503, detail='Invalid analog selection') from error
        if request.k > len(analogs):
            raise HTTPException(409, detail=f'Only {len(analogs)} analog years available')

        analogs = analogs[:request.k]
        years = {analog.year for analog in analogs}
        path = inputs_dir / f'{request.scenario_id}.json'
        batch = read_artifact(path, 'Prepared input batch')
        try:
            inputs = input_batch.validate_python(batch)
            if any(item.mock != document['_mock'] for item in inputs):
                raise ValueError('analog catalog and prepared inputs disagree on mock status')
            selected = [item for item in inputs if item.climate.year in years
                        and item.rotation.rotation_id in request.rotation_ids]
            if not selected:
                raise ValueError('no prepared inputs match the selection')
            # Only the prepared setup may confirm that the provisional point was reviewed.
            zone = selected[0].zona
            if not same_zone_identity(document['zona'], zone.model_dump()):
                raise ValueError('prepared inputs use a different zone')
            result = execute_comparison(request.model_copy(update={'zona': zone}), analogs,
                                        selected, simulate_rotation=simulate_rotation)
        except ValueError as error:
            logger.warning('Cannot run comparison for %s: %s', request.scenario_id, error)
            raise HTTPException(409, detail='Prepared inputs are incomplete or incompatible') from error

        if result.mock:
            result.warnings.insert(0, 'SYNTHETIC MOCK: for QA only.')
        result.source_refs = sorted(set(result.source_refs + document.get('source_refs', [])))
        result.warnings = list(dict.fromkeys(
            result.warnings + document.get('warnings', []) + scenario.get('warnings', [])))
        return result

    @app.get('/imagery/search', responses={422: {'description': 'Bad date or place'},
                                           502: {'description': 'Catalog unavailable'}})
    def imagery_search(date: str, lon: float, lat: float, response: Response):
        try:
            result = sentinel.search(date, lon, lat)
        except (ImageryInputError, ImageryUpstreamError) as error:
            raise imagery_error(error) from error
        response.headers.update(open_cors)
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return result

    @app.get('/imagery/tiles/{scene_id}/{z}/{x}/{y}',
             response_class=Response,
             responses={200: {'content': {'image/png': {}}},
                        204: {'description': 'Tile outside the scene'},
                        422: {'description': 'Bad scene id or tile'},
                        502: {'description': 'Scene unreadable'}})
    def imagery_tile(scene_id: str, z: int, x: int, y: int):
        try:
            png = sentinel.tile(scene_id, z, x, y)
        except (ImageryInputError, ImageryUpstreamError) as error:
            raise imagery_error(error) from error
        headers = {**open_cors, 'Cache-Control': 'public, max-age=86400'}
        if png is None:
            return Response(status_code=204, headers=headers)
        return Response(png, media_type='image/png', headers=headers)

    return app


app = create_app(
    analogs_path=Path(os.getenv('ALAIRAX_ANALOGS', str(PROCESSED / 'analogs' / 'analogos.json'))),
    inputs_dir=Path(os.getenv('ALAIRAX_INPUTS_DIR', str(ROOT / 'outputs' / 'inputs'))),
)
