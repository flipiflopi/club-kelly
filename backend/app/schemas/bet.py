from datetime import datetime

from pydantic import BaseModel

from backend.app.models.simulated_bet import BetStatus


class BetBrief(BaseModel):
    id: int
    status: BetStatus
    stake_amount: float
    stake_pct: float
    bankroll_before: float
    decimal_odds: float
    profit_loss: float | None = None
    outcome: str = ""        # from prediction.outcome via @property
    market_slug: str = ""   # from prediction.market_slug via @property

    model_config = {"from_attributes": True}


class BetDetail(BetBrief):
    match_id: int
    home_team_name: str = ""   # from simulated_bet.home_team_name property
    away_team_name: str = ""   # from simulated_bet.away_team_name property
    kelly_fraction: float
    reasoning_text: str | None = None
    bankroll_after: float | None = None
    resolved_at: datetime | None = None
    created_at: datetime

    prediction: "PredictionDetail"

    model_config = {"from_attributes": True}


from backend.app.schemas.prediction import PredictionDetail  # noqa: E402

BetDetail.model_rebuild()
