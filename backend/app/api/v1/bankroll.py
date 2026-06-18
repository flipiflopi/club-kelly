from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db_session
from backend.app.config import get_settings
from backend.app.models.bankroll_history import BankrollHistory
from backend.app.models.simulated_bet import BetStatus, SimulatedBet
from backend.app.schemas.bankroll import BankrollEvent, BankrollSnapshot

router = APIRouter(prefix="/bankroll", tags=["bankroll"])


@router.get("/snapshot", response_model=BankrollSnapshot)
def get_bankroll_snapshot(db: Session = Depends(get_db_session)):
    """Current bankroll state and high-level P&L summary."""
    settings = get_settings()
    initial = settings.initial_bankroll

    latest_event = (
        db.query(BankrollHistory)
        .order_by(BankrollHistory.id.desc())
        .first()
    )
    current = latest_event.balance_after if latest_event else initial

    resolved = db.query(SimulatedBet).filter(
        SimulatedBet.status.in_([BetStatus.WON, BetStatus.LOST])
    )
    total_bets = resolved.count()
    won = resolved.filter(SimulatedBet.status == BetStatus.WON).count()
    lost = total_bets - won

    total_pl_row = db.query(func.sum(SimulatedBet.profit_loss)).filter(
        SimulatedBet.status.in_([BetStatus.WON, BetStatus.LOST])
    ).scalar()
    total_pl = float(total_pl_row or 0.0)

    return BankrollSnapshot(
        current_balance=current,
        initial_balance=initial,
        total_profit_loss=total_pl,
        roi_pct=(total_pl / initial * 100.0) if initial else 0.0,
        total_bets=total_bets,
        won=won,
        lost=lost,
    )


@router.get("/history", response_model=list[BankrollEvent])
def get_bankroll_history(
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    db: Session = Depends(get_db_session),
):
    """Chronological bankroll events for the chart."""
    return (
        db.query(BankrollHistory)
        .order_by(BankrollHistory.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
