from datetime import datetime

from pydantic import BaseModel

from backend.app.models.match import MatchStatus


class TeamBrief(BaseModel):
    id: int
    name: str
    short_name: str
    country_code: str | None = None

    model_config = {"from_attributes": True}


class MatchBase(BaseModel):
    id: int
    competition_id: int
    home_team: TeamBrief
    away_team: TeamBrief
    match_date: datetime
    status: MatchStatus
    home_score: int | None = None
    away_score: int | None = None
    round: str | None = None
    venue: str | None = None
    is_neutral: bool = False

    model_config = {"from_attributes": True}


class MatchUpcoming(MatchBase):
    """Match with model predictions and open bets attached."""
    predictions: list["PredictionBrief"] = []
    bets: list["BetBrief"] = []


class MatchFinished(MatchBase):
    """Finished match with result and bet outcome."""
    bets: list["BetBrief"] = []


from backend.app.schemas.prediction import PredictionBrief  # noqa: E402 (avoid circular import)
from backend.app.schemas.bet import BetBrief  # noqa: E402

MatchUpcoming.model_rebuild()
MatchFinished.model_rebuild()
