"""Chat selection is metadata; scientific values are always loaded by the server."""

from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from backend.app.api.schemas.contracts import Contract, ScenarioId


def latest_day() -> date:
    return datetime.now(ZoneInfo('America/Costa_Rica')).date() - timedelta(days=1)


class ChatSelection(Contract):
    canton_ids: list[str] = Field(min_length=1, max_length=5)
    start: date = Field(default_factory=lambda: latest_day() - timedelta(days=29))
    end: date = Field(default_factory=latest_day)
    scenario_id: ScenarioId | None = None
    metric: Literal['crop_water_demand_mm', 'modeled_water_deficit_mm',
                    'water_stress_days', 'precipitation_mm', 'et0_mm'] | None = None
    years: list[int] = Field(default_factory=list, max_length=2)

    @model_validator(mode='after')
    def valid_period(self):
        if len(set(self.canton_ids)) != len(self.canton_ids):
            raise ValueError('Duplicate cantons')
        if self.start < date(1981, 1, 1) or self.end < self.start:
            raise ValueError('Invalid historical interval')
        if self.end > latest_day() or (self.end - self.start).days > 365:
            raise ValueError('Select up to 366 historical days, ending before today')
        if len(set(self.years)) != len(self.years) or any(year < 2017 or year > latest_day().year for year in self.years):
            raise ValueError('Replay years must be distinct, from 2017 through the current year')
        return self


class ChatTurn(Contract):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=6000)


class FarmContext(Contract):
    crop: str | None = Field(default=None, max_length=120)
    growth_stage: str | None = Field(default=None, max_length=120)
    irrigation: str | None = Field(default=None, max_length=300)


class ChatRequest(Contract):
    question: str = Field(min_length=1, max_length=4000, pattern=r'\S')
    selection: ChatSelection
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)
    farm: FarmContext = Field(default_factory=FarmContext)
    language: Literal['es', 'en'] = 'es'


class ChatResponse(Contract):
    answer: str
    model: str
    thinking_level: Literal['low'] = 'low'
    context: dict
