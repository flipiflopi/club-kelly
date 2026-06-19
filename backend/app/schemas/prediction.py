from datetime import datetime

from pydantic import BaseModel


class PredictionBrief(BaseModel):
    id: int
    market_slug: str
    outcome: str
    model_probability: float
    market_probability: float | None = None  # fair prob after vig removal
    market_odds: float | None = None
    edge: float | None = None

    model_config = {"from_attributes": True}


class PredictionDetail(PredictionBrief):
    closing_odds: float | None = None
    model_version: str
    created_at: datetime
