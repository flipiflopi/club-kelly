import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from backend.app.api.deps import get_db_session
from backend.app.models.match import Match, MatchStatus
from backend.app.models.prediction import Prediction
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
        )
        .filter(Match.status.in_([MatchStatus.SCHEDULED, MatchStatus.LIVE]))
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
