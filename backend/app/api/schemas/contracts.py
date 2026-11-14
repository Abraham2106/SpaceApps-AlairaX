"""M1 v0.1: units in field names; unknown scientific values stay null."""

from datetime import date, timedelta
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

NonNegative = Annotated[float, Field(ge=0)]
RotationId = Literal['rice_melon', 'rice_legume', 'rice_sorghum']
ScenarioId = Literal['strong_el_nino', 'neutral', 'la_nina', 'like_2026']
METRICS = ('crop_water_demand_mm', 'modeled_water_deficit_mm', 'water_stress_days')


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, populate_by_name=True)


class Zone(Contract):
    id: str
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    validated: bool = False


class Envelope(Contract):
    schema_version: Literal['0.1.0'] = '0.1.0'
    mock: bool = Field(alias='_mock', strict=True)
    generado: AwareDatetime
    zona: Zone
    source_refs: list[str]
    warnings: list[str]


class ClimateDay(Contract):
    date: date
    precipitation_mm: NonNegative | None
    tmin_c: float | None
    tmax_c: float | None
    relative_humidity_pct: Annotated[float, Field(ge=0, le=100)] | None
    wind_speed_2m_m_s: NonNegative | None
    solar_radiation_mj_m2_day: NonNegative | None
    et0_mm: NonNegative | None

    @model_validator(mode='after')
    def ordered_temperature(self):
        if self.tmin_c is not None and self.tmax_c is not None and self.tmin_c > self.tmax_c:
            raise ValueError('tmin_c must be <= tmax_c')
        return self


class ClimateSeason(Contract):
    year: int = Field(ge=1981, le=2026)
    start: date
    end: date
    days: list[ClimateDay] = Field(min_length=1)

    @model_validator(mode='after')
    def contiguous_calendar(self):
        if self.end < self.start or self.start.year != self.year:
            raise ValueError('invalid season boundaries')
        expected = [self.start + timedelta(days=i) for i in range((self.end-self.start).days+1)]
        if [day.date for day in self.days] != expected:
            raise ValueError('climate must contain each date exactly once, in order; use null for gaps')
        return self


class SoilProfile(Contract):
    field_capacity_m3_m3: Annotated[float, Field(gt=0, le=1)] | None
    wilting_point_m3_m3: Annotated[float, Field(ge=0, le=1)] | None
    rooting_depth_m: Annotated[float, Field(gt=0)] | None
    source_refs: list[str]

    @model_validator(mode='after')
    def soil_water_order(self):
        fc, wp = self.field_capacity_m3_m3, self.wilting_point_m3_m3
        if fc is not None and wp is not None and fc <= wp:
            raise ValueError('field capacity must exceed wilting point')
        return self


class CropCycle(Contract):
    crop_id: Literal['rice', 'melon', 'legume', 'sorghum']
    sowing_date: date
    harvest_date: date
    parameter_set_id: str | None

    @model_validator(mode='after')
    def dates_ordered(self):
        if self.harvest_date < self.sowing_date:
            raise ValueError('harvest precedes sowing')
        return self


class RotationSchedule(Contract):
    rotation_id: RotationId
    calendar_status: Literal['provisional', 'confirmed']
    cycles: list[CropCycle] = Field(min_length=1)

    @model_validator(mode='after')
    def calendar_valid(self):
        expected = {'rice_melon': ['rice', 'melon'], 'rice_legume': ['rice', 'legume'],
                    'rice_sorghum': ['rice', 'sorghum']}
        if [c.crop_id for c in self.cycles] != expected[self.rotation_id]:
            raise ValueError('cycles must match the rotation ID')
        for first, second in zip(self.cycles, self.cycles[1:]):
            if first.harvest_date >= second.sowing_date:
                raise ValueError('crop cycles overlap')
        return self


class ModelAssumptions(Contract):
    irrigation_mode: Literal['rainfed', 'scheduled', 'unspecified']
    irrigation_mm_by_date: dict[date, NonNegative]
    initial_soil_water_fraction: Annotated[float, Field(ge=0, le=1)] | None
    notes: list[str]

    @model_validator(mode='after')
    def irrigation_consistent(self):
        if self.irrigation_mode != 'scheduled' and self.irrigation_mm_by_date:
            raise ValueError('irrigation schedule requires scheduled mode')
        return self


class SimulationInput(Envelope):
    scenario_id: ScenarioId
    climate: ClimateSeason
    soil: SoilProfile
    rotation: RotationSchedule
    assumptions: ModelAssumptions

    @model_validator(mode='after')
    def coverage_and_readiness(self):
        for cycle in self.rotation.cycles:
            if not self.climate.start <= cycle.sowing_date <= cycle.harvest_date <= self.climate.end:
                raise ValueError('climate must cover every crop cycle')
        if any(not self.climate.start <= d <= self.climate.end
               for d in self.assumptions.irrigation_mm_by_date):
            raise ValueError('irrigation date outside climate coverage')
        if not self.mock:
            if not self.zona.validated or self.rotation.calendar_status != 'confirmed':
                raise ValueError('real simulation requires validated zone and confirmed calendar')
            if any(v is None for v in (self.soil.field_capacity_m3_m3,
                                       self.soil.wilting_point_m3_m3, self.soil.rooting_depth_m)):
                raise ValueError('real simulation requires complete soil profile')
            if any(c.parameter_set_id is None for c in self.rotation.cycles):
                raise ValueError('real simulation requires referenced crop parameters')
            if self.assumptions.irrigation_mode == 'unspecified' or self.assumptions.initial_soil_water_fraction is None:
                raise ValueError('real simulation requires explicit water management')
        return self


class Metrics(Contract):
    crop_water_demand_mm: NonNegative | None
    modeled_water_deficit_mm: NonNegative | None
    water_stress_days: Annotated[int, Field(ge=0, strict=True)] | None


class DailyBalance(Contract):
    date: date
    crop_water_demand_mm: NonNegative | None
    modeled_water_deficit_mm: NonNegative | None
    soil_water_storage_mm: NonNegative | None
    water_stress: bool | None


class SimulationResult(Envelope):
    rotation_id: RotationId
    scenario_id: ScenarioId
    year: int = Field(ge=1981, le=2026)
    environment_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    metrics: Metrics
    daily_balance: list[DailyBalance]
    assumptions: list[str]
    model_version: str = Field(min_length=1)

    @model_validator(mode='after')
    def daily_dates_unique(self):
        dates = [day.date for day in self.daily_balance]
        if dates != sorted(set(dates)):
            raise ValueError('daily balance dates must be unique and sorted')
        return self


class CompareRequest(Contract):
    zona: Zone
    scenario_id: ScenarioId
    baseline_rotation_id: RotationId = 'rice_melon'
    rotation_ids: list[RotationId] = Field(default_factory=lambda: ['rice_melon', 'rice_legume', 'rice_sorghum'], min_length=2)
    k: int = Field(default=5, ge=1, le=45)

    @model_validator(mode='after')
    def distinct_rotations(self):
        if len(set(self.rotation_ids)) != len(self.rotation_ids):
            raise ValueError('duplicate rotations')
        if self.baseline_rotation_id not in self.rotation_ids:
            raise ValueError('baseline must be included')
        return self


class AnalogYear(Contract):
    year: int = Field(ge=1981, le=2025)
    distance: NonNegative


class Quantiles(Contract):
    p10: float | None
    p50: float | None
    p90: float | None
    n: int = Field(ge=0)

    @model_validator(mode='after')
    def ordered(self):
        values = (self.p10, self.p50, self.p90)
        if self.n == 0:
            if any(v is not None for v in values):
                raise ValueError('empty sample requires null quantiles')
        elif any(v is None for v in values) or not self.p10 <= self.p50 <= self.p90:
            raise ValueError('quantiles must be complete and ordered')
        return self


class MetricSummary(Contract):
    crop_water_demand_mm: Quantiles
    modeled_water_deficit_mm: Quantiles
    water_stress_days: Quantiles


class RotationComparison(Contract):
    rotation_id: RotationId
    metrics: MetricSummary
    delta_vs_baseline: MetricSummary
    runs: list[SimulationResult]


class CompareResponse(Envelope):
    scenario_id: ScenarioId
    baseline_rotation_id: RotationId
    analog_years: list[AnalogYear] = Field(min_length=1)
    rotations: list[RotationComparison] = Field(min_length=2)
    limitations: list[str]
    uncertainty_method: Literal['empirical_linear_quantiles_across_analog_years']

    @model_validator(mode='after')
    def consistent_runs(self):
        years = {a.year for a in self.analog_years}
        rotations = [r.rotation_id for r in self.rotations]
        if len(years) != len(self.analog_years) or len(set(rotations)) != len(rotations):
            raise ValueError('duplicate analog years or rotations')
        if self.baseline_rotation_id not in rotations:
            raise ValueError('baseline rotation is missing')
        versions = set()
        environments = {}
        for rotation in self.rotations:
            if len(rotation.runs) != len(years) or {r.year for r in rotation.runs} != years:
                raise ValueError('each rotation must have exactly the listed analog years')
            for run in rotation.runs:
                if (run.mock != self.mock or run.zona != self.zona or
                        run.scenario_id != self.scenario_id or run.rotation_id != rotation.rotation_id):
                    raise ValueError('nested run metadata must match comparison envelope')
                versions.add(run.model_version)
                key = (run.environment_id, tuple(run.assumptions))
                if run.year in environments and environments[run.year] != key:
                    raise ValueError('paired runs must share environment and assumptions')
                environments[run.year] = key
        if len(versions) != 1:
            raise ValueError('comparison must use one kernel model version')
        return self
