from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from backend.app.api.deps import get_db_session
from backend.app.models.prediction import Prediction
from backend.app.models.simulated_bet import BetStatus, SimulatedBet
from backend.app.schemas.bet import BetDetail

router = APIRouter(prefix="/bets", tags=["bets"])


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
        .options(
            joinedload(SimulatedBet.prediction).joinedload(Prediction.market_type),
        )
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
        .options(joinedload(SimulatedBet.prediction).joinedload(Prediction.market_type))
        .filter(SimulatedBet.status == BetStatus.OPEN)
        .order_by(SimulatedBet.created_at.desc())
        .all()
    )
