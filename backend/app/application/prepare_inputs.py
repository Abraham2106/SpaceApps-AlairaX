"""Build a kernel input batch from explicit, reviewed team artifacts."""

from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from pydantic import Field

from backend.app.api.schemas.contracts import (
    AnalogYear, ClimateDay, ClimateSeason, Contract, Envelope, ModelAssumptions,
    RotationSchedule, ScenarioId, SimulationInput, SoilProfile, Zone,
)


class ComparisonSetup(Envelope):
    """Calendar dates and management are supplied per historical year, never inferred."""

    reviewed_by: str = Field(min_length=1)
    soil: SoilProfile
    rotations_by_year: dict[int, list[RotationSchedule]]
    assumptions_by_year: dict[int, ModelAssumptions]


class ReviewedET0(Contract):
    mock: bool = Field(alias='_mock', strict=True)
    zona: dict
    reviewed: Annotated[bool, Field(strict=True)]
    reviewed_by: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    units: str
    source_refs: list[str] = Field(min_length=1)
    values: dict[date, Annotated[float, Field(ge=0)] | None]
    warnings: list[str] = Field(default_factory=list)


def same_zone_identity(first: dict, second: dict) -> bool:
    # The setup can confirm a point originally retrieved as provisional. Preserve
    # source artifacts unchanged; only the setup carries the later validation.
    try:
        a = Zone.model_validate(first).model_dump(exclude={'validated'})
        b = Zone.model_validate(second).model_dump(exclude={'validated'})
    except ValueError as error:
        raise ValueError('invalid zone identity in an input artifact') from error
    return a == b


def prepare_inputs(analog_document: dict, scenario_id: ScenarioId,
                   climate_documents: list[dict], et0_document: dict,
                   setup: ComparisonSetup, *, start_mmdd: str, end_mmdd: str) -> list[SimulationInput]:
    """Use the same climate, soil and management for all rotations within a year.

    The simulation calendar is explicit and may differ from the shorter feature
    window used to select analogs. Historical crops must fit this full replay
    window. No sowing dates, soil values, ET0 or irrigation are guessed.
    """
    setup = ComparisonSetup.model_validate(setup.model_dump())
    et0 = ReviewedET0.model_validate(et0_document)
    scenario = analog_document['scenarios'][scenario_id]
    if scenario['status'] != 'available':
        raise ValueError(f'analog scenario unavailable: {scenario.get("reason", "unspecified")}')
    if (type(analog_document.get('_mock')) is not bool or
            type(scenario.get('_mock')) is not bool or
            scenario.get('_mock') != setup.mock or analog_document['_mock'] != setup.mock or
            et0.mock != setup.mock):
        raise ValueError('all artifacts must have the same explicit mock status')
    zone = setup.zona.model_dump(mode='json')
    if not same_zone_identity(et0.zona, zone) or not same_zone_identity(analog_document['zona'], zone):
        raise ValueError('analog selection, ET0 and setup must use the same zone')
    if not et0.reviewed or et0.units != 'mm/day':
        raise ValueError('ET0 must be reviewed with units=mm/day')
    if type(scenario.get('k')) is not int or not 1 <= scenario['k'] <= 45:
        raise ValueError('k must be an integer from 1 to 45')
    analogs = [AnalogYear.model_validate({'year': a['year'], 'distance': a['distance']})
               for a in scenario['neighbors']]
    years = [a.year for a in analogs]
    if len(set(years)) != len(years) or len(years) != scenario['k']:
        raise ValueError('analog selection must contain k distinct historical years')
    climate = {}
    sources = set(setup.source_refs + et0.source_refs + analog_document.get('source_refs', []))
    warnings = setup.warnings + et0.warnings + analog_document.get('warnings', []) + scenario.get('warnings', [])
    required_units = {'precipitation_mm': 'mm/day', 'tmin_c': 'C', 'tmax_c': 'C',
                      'relative_humidity_pct': '%', 'wind_speed_2m_m_s': 'm/s',
                      'solar_radiation_mj_m2_day': 'MJ/m^2/day'}
    for document in climate_documents:
        if document.get('_mock') is not setup.mock or not same_zone_identity(document.get('zona'), zone):
            raise ValueError('climate must use the same zone and mock status as setup')
        if any(document.get('units', {}).get(field) != unit for field, unit in required_units.items()):
            raise ValueError('climate must have the normalized contract units')
        sources.update(document.get('source_refs', []))
        warnings.extend(document.get('warnings', []))
        for row in document['days']:
            validated = ClimateDay.model_validate(row)
            if validated.et0_mm is not None:
                raise ValueError('climate ET0 must remain null; use the reviewed ET0 artifact')
            if validated.date in climate and climate[validated.date] != validated:
                raise ValueError(f'conflicting climate overlap on {validated.date}')
            climate[validated.date] = validated
    prepared = []
    for year in years:
        start, end = date.fromisoformat(f'{year}-{start_mmdd}'), date.fromisoformat(f'{year}-{end_mmdd}')
        if end < start:
            raise ValueError('simulation window must end after it starts within the same year')
        if year not in setup.rotations_by_year or year not in setup.assumptions_by_year:
            raise ValueError(f'{year}: reviewed rotation calendars and management are required')
        rotations = setup.rotations_by_year[year]
        if {r.rotation_id for r in rotations} != {'rice_melon', 'rice_legume', 'rice_sorghum'} or len(rotations) != 3:
            raise ValueError(f'{year}: exactly three distinct rotation calendars are required')
        days = []
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            if day not in climate:
                raise ValueError(f'missing climate date: {day}')
            row = climate[day].model_dump()
            row['et0_mm'] = et0.values.get(day)
            if not setup.mock and any(value is None for value in row.values()):
                raise ValueError(f'{day}: incomplete real climate or ET0; no imputation is applied')
            days.append(ClimateDay.model_validate(row))
        season = ClimateSeason(year=year, start=start, end=end, days=days)
        for rotation in rotations:
            prepared.append(SimulationInput(
                mock=setup.mock, generado=datetime.now(timezone.utc), zona=setup.zona.model_copy(deep=True),
                source_refs=sorted(sources), warnings=list(dict.fromkeys(warnings)),
                scenario_id=scenario_id, climate=season.model_copy(deep=True), soil=setup.soil.model_copy(deep=True),
                rotation=rotation.model_copy(deep=True),
                assumptions=setup.assumptions_by_year[year].model_copy(deep=True)))
    return prepared
