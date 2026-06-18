from datetime import datetime

from pydantic import BaseModel

from backend.app.models.bankroll_history import BankrollEventType


class BankrollSnapshot(BaseModel):
    current_balance: float
    initial_balance: float
    total_profit_loss: float
    roi_pct: float
    total_bets: int
    won: int
    lost: int

    model_config = {"from_attributes": True}


class BankrollEvent(BaseModel):
    id: int
    event_type: BankrollEventType
    amount_change: float
    balance_after: float
    note: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
