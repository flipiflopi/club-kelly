from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from backend.app.api.deps import get_db_session
from backend.app.models.match import Match
from backend.app.models.prediction import Prediction
from backend.app.models.simulated_bet import BetStatus, SimulatedBet
from backend.app.schemas.bet import BetDetail

router = APIRouter(prefix="/bets", tags=["bets"])

_BET_LOADS = [
    joinedload(SimulatedBet.prediction).joinedload(Prediction.market_type),
    joinedload(SimulatedBet.match).joinedload(Match.home_team),
    joinedload(SimulatedBet.match).joinedload(Match.away_team),
]


@router.get("/", response_model=list[BetDetail])
def list_bets(
    status: BetStatus | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: Session = Depends(get_db_session),
):
    """All simulated bets, optionally filtered by status."""
    q = (
        db.query(SimulatedBet)
        .options(*_BET_LOADS)
        .order_by(SimulatedBet.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if status:
        q = q.filter(SimulatedBet.status == status)
    return q.all()


@router.get("/open", response_model=list[BetDetail])
def list_open_bets(db: Session = Depends(get_db_session)):
    """Currently open (unresolved) bets."""
    return (
        db.query(SimulatedBet)
        .options(*_BET_LOADS)
        .filter(SimulatedBet.status == BetStatus.OPEN)
        .order_by(SimulatedBet.created_at.desc())
        .all()
    )
