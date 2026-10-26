"""
Admin API — manual management of bets and bankroll.
Every endpoint requires the X-API-Key header (ADMIN_API_KEY, or WEBHOOK_API_KEY as fallback).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query  # noqa: F401
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from backend.app.api.deps import get_db_session, verify_admin_key
from backend.app.models.bankroll_history import BankrollEventType, BankrollHistory
from backend.app.models.match import Match, MatchStatus
from backend.app.models.prediction import Prediction
from backend.app.models.simulated_bet import BetStatus, SimulatedBet

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin_key)],
)


# ── Schemas ───────────────────────────────────────────────────────────────────


class ResolveMatchRequest(BaseModel):
    home_score: int
    away_score: int


class AdjustRequest(BaseModel):
    amount: float       # positive = deposit, negative = withdrawal
    note: str = ""


class VoidResponse(BaseModel):
    ok: bool
    bet_id: int
    note: str


class AdjustResponse(BaseModel):
    ok: bool
    balance_before: float
    balance_after: float


# ── Helpers ───────────────────────────────────────────────────────────────────


def _current_bankroll(db: Session) -> float:
    latest = db.query(BankrollHistory).order_by(BankrollHistory.id.desc()).first()
    if latest:
        return latest.balance_after
    from backend.app.config import get_settings
    return get_settings().initial_bankroll


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/open-bets")
def list_open_bets(db: Session = Depends(get_db_session)):
    """All open bets with match and prediction details."""
    bets = (
        db.query(SimulatedBet)
        .filter(SimulatedBet.status == BetStatus.OPEN)
        .options(
            joinedload(SimulatedBet.prediction).joinedload(Prediction.market_type),
            joinedload(SimulatedBet.match).joinedload(Match.home_team),
            joinedload(SimulatedBet.match).joinedload(Match.away_team),
        )
        .order_by(SimulatedBet.created_at.desc())
        .all()
    )
    return [
        {
            "id": b.id,
            "match_id": b.match_id,
            "home_team": b.match.home_team.name if b.match and b.match.home_team else "",
            "away_team": b.match.away_team.name if b.match and b.match.away_team else "",
            "match_date": b.match.match_date.isoformat() if b.match else "",
            "outcome": b.prediction.outcome if b.prediction else "",
            "market": b.prediction.market_type.slug if b.prediction and b.prediction.market_type else "",
            "stake_amount": b.stake_amount,
            "stake_pct": b.stake_pct,
            "decimal_odds": b.decimal_odds,
            "created_at": b.created_at.isoformat() if b.created_at else "",
        }
        for b in bets
    ]


@router.post("/bets/{bet_id}/void", response_model=VoidResponse)
def void_bet(bet_id: int, db: Session = Depends(get_db_session)):
    """
    Void an open bet. Bankroll is unaffected (it never changed at placement).
    Only OPEN bets can be voided here — resolved bets require manual DB adjustment.
    """
    bet = db.query(SimulatedBet).filter_by(id=bet_id).first()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    if bet.status != BetStatus.OPEN:
        raise HTTPException(
            status_code=400,
            detail=f"Solo se pueden anular apuestas abiertas (estado actual: {bet.status})",
        )

    bet.status = BetStatus.VOID
    bet.profit_loss = 0.0
    bet.resolved_at = datetime.now(timezone.utc)
    db.commit()

    return VoidResponse(ok=True, bet_id=bet_id, note="Apuesta anulada manualmente")


@router.post("/bankroll/adjust", response_model=AdjustResponse)
def adjust_bankroll(body: AdjustRequest, db: Session = Depends(get_db_session)):
    """
    Manually adjust the bankroll (deposit, withdrawal, or correction).
    Creates a new ADJUSTMENT entry in the bankroll history ledger.
    """
    if body.amount == 0:
        raise HTTPException(status_code=400, detail="El importe no puede ser 0")

    current = _current_bankroll(db)
    new_balance = current + body.amount
    if new_balance < 0:
        raise HTTPException(
            status_code=400,
            detail=f"El ajuste dejaría el bankroll en negativo ({new_balance:.2f}€)",
        )

    note = body.note or f"Ajuste manual: {body.amount:+.2f}€"
    db.add(
        BankrollHistory(
            event_type=BankrollEventType.ADJUSTMENT,
            amount_change=body.amount,
            balance_after=new_balance,
            note=note,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    return AdjustResponse(ok=True, balance_before=current, balance_after=new_balance)


@router.post("/matches/{match_id}/resolve")
def resolve_match(match_id: int, body: ResolveMatchRequest, db: Session = Depends(get_db_session)):
    """
    Manually set a match result and resolve all open bets for it.
    Use when the scores API is unavailable (e.g. The Odds API free tier).
    """
    from backend.app.services.bet_resolver import resolve_bets_for_match

    match = db.query(Match).filter_by(id=match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.status == MatchStatus.FINISHED:
        open_bets = db.query(SimulatedBet).filter_by(match_id=match_id, status=BetStatus.OPEN).count()
        if open_bets == 0:
            raise HTTPException(status_code=400, detail="Match already finished and no open bets to resolve")

    match.home_score = body.home_score
    match.away_score = body.away_score
    match.status = MatchStatus.FINISHED
    db.flush()

    resolved = resolve_bets_for_match(match, db)

    return {
        "ok": True,
        "match_id": match_id,
        "score": f"{body.home_score}-{body.away_score}",
        "bets_resolved": len(resolved),
        "results": [
            {"bet_id": b.id, "status": b.status.value, "profit_loss": b.profit_loss}
            for b in resolved
        ],
    }


@router.get("/matches-with-open-bets")
def list_matches_with_open_bets(db: Session = Depends(get_db_session)):
    """Matches that have at least one open bet — for manual resolution."""
    open_match_ids = (
        db.query(SimulatedBet.match_id)
        .filter(SimulatedBet.status == BetStatus.OPEN)
        .distinct()
        .subquery()
    )
    rows = (
        db.query(Match)
        .filter(Match.id.in_(open_match_ids))
        .options(
            joinedload(Match.home_team),
            joinedload(Match.away_team),
        )
        .order_by(Match.match_date.asc())
        .all()
    )
    return [
        {
            "id": m.id,
            "home_team": m.home_team.name if m.home_team else "",
            "away_team": m.away_team.name if m.away_team else "",
            "match_date": m.match_date.isoformat() if m.match_date else "",
            "status": m.status.value if hasattr(m.status, "value") else str(m.status),
            "home_score": m.home_score,
            "away_score": m.away_score,
        }
        for m in rows
    ]


@router.get("/activity")
def get_activity(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db_session),
):
    """Recent bankroll events (newest first)."""
    events = (
        db.query(BankrollHistory)
        .order_by(BankrollHistory.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "amount_change": e.amount_change,
            "balance_after": e.balance_after,
            "note": e.note,
            "created_at": e.created_at.isoformat() if e.created_at else "",
        }
        for e in events
    ]
