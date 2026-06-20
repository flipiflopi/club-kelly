import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from backend.app.api.deps import get_db_session
from backend.app.models.bankroll_history import BankrollHistory
from backend.app.models.match import Match, MatchStatus
from backend.app.models.prediction import Prediction
from backend.app.models.simulated_bet import BetStatus, SimulatedBet
from backend.app.schemas.match import MatchFinished, MatchUpcoming

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/upcoming", response_model=list[MatchUpcoming])
def list_upcoming_matches(
    competition_slug: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db_session),
):
    """
    Upcoming and live matches with model predictions.
    Polled by the frontend every 30-60s.
    """
    q = (
        db.query(Match)
        .options(
            joinedload(Match.home_team),
            joinedload(Match.away_team),
            joinedload(Match.predictions).joinedload(Prediction.market_type),
            joinedload(Match.bets).joinedload(SimulatedBet.prediction).joinedload(Prediction.market_type),
        )
        .filter(
            Match.status.in_([MatchStatus.SCHEDULED, MatchStatus.LIVE]),
            Match.match_date >= datetime.now(timezone.utc) - timedelta(hours=3),
        )
        .order_by(Match.match_date.asc())
        .limit(limit)
    )
    if competition_slug:
        q = q.join(Match.competition).filter_by(slug=competition_slug)
    try:
        return q.all()
    except Exception:
        logger.exception("Error in /v1/matches/upcoming")
        raise


@router.get("/past", response_model=list[MatchFinished])
def list_past_matches(
    competition_slug: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: Session = Depends(get_db_session),
):
    """Finished matches with resolved bet outcomes. Used for history view."""
    q = (
        db.query(Match)
        .options(
            joinedload(Match.home_team),
            joinedload(Match.away_team),
        )
        .filter(Match.status == MatchStatus.FINISHED)
        .order_by(Match.match_date.desc())
        .offset(offset)
        .limit(limit)
    )
    if competition_slug:
        q = q.join(Match.competition).filter_by(slug=competition_slug)
    return q.all()


@router.get("/{match_id}/tweet-data")
def get_match_tweet_data(match_id: int, db: Session = Depends(get_db_session)):
    """
    Returns structured match + prediction + bet data for tweet generation.
    Called by n8n after run-predictions or sync-results to build the Claude prompt.
    """
    match = (
        db.query(Match)
        .options(
            joinedload(Match.home_team),
            joinedload(Match.away_team),
            joinedload(Match.competition),
            joinedload(Match.predictions).joinedload(Prediction.market_type),
            joinedload(Match.bets).joinedload(SimulatedBet.prediction).joinedload(Prediction.market_type),
        )
        .filter(Match.id == match_id)
        .first()
    )
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    latest_event = db.query(BankrollHistory).order_by(BankrollHistory.id.desc()).first()
    current_bankroll = latest_event.balance_after if latest_event else 0.0

    # Only match_result predictions
    mr_preds = [
        p for p in match.predictions
        if p.market_type and p.market_type.slug == "match_result"
    ]

    bets_data = []
    for bet in match.bets:
        market_slug = bet.prediction.market_type.slug if bet.prediction and bet.prediction.market_type else ""
        bets_data.append({
            "outcome": bet.prediction.outcome if bet.prediction else "",
            "market": market_slug,
            "stake_amount": round(bet.stake_amount, 2),
            "stake_pct": round(bet.stake_pct * 100, 1),
            "decimal_odds": round(bet.decimal_odds, 2),
            "status": bet.status.value if hasattr(bet.status, "value") else str(bet.status),
            "profit_loss": round(bet.profit_loss, 2) if bet.profit_loss is not None else None,
        })

    return {
        "match": {
            "id": match.id,
            "home_team": match.home_team.name,
            "away_team": match.away_team.name,
            "match_date": match.match_date.isoformat(),
            "round": match.round,
            "status": match.status.value if hasattr(match.status, "value") else str(match.status),
            "home_score": match.home_score,
            "away_score": match.away_score,
            "competition": match.competition.name if match.competition else "FIFA World Cup 2026",
        },
        "predictions": [
            {
                "outcome": p.outcome,
                "model_probability": round(p.model_probability * 100, 1),
                "market_odds": round(p.market_odds, 2) if p.market_odds else None,
                "edge_pct": round(p.edge * 100, 1) if p.edge else None,
            }
            for p in mr_preds
        ],
        "bets": bets_data,
        "current_bankroll": round(current_bankroll, 2),
        "has_bet": len(bets_data) > 0,
        "is_resolved": match.status == MatchStatus.FINISHED,
    }
