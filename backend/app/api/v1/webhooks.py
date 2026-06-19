"""
Webhook endpoints called by n8n.

n8n workflow responsibilities (NOT implemented here):
  - Cron: POST /v1/webhooks/sync-fixtures   every 60s during active tournament
  - Cron: POST /v1/webhooks/sync-results    every 5 min to pick up finished matches
  - Cron: POST /v1/webhooks/run-predictions after each fixture sync
  - Twitter/X: n8n reads the bet events from the response body and posts to X

All endpoints accept an optional X-API-Key header (see deps.verify_webhook_key).
"""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db_session, verify_webhook_key
from backend.app.services import fixture_sync as _fixture_sync
from backend.app.services.prediction_runner import RunResult, run_predictions

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
    dependencies=[Depends(verify_webhook_key)],
)


# ── Response models ───────────────────────────────────────────────────────────


class SyncFixturesResponse(BaseModel):
    status: str
    competition: str
    teams_created: int
    matches_created: int
    matches_updated: int
    errors: list[str] = []


class SyncResultsResponse(BaseModel):
    status: str
    competition: str
    matches_updated: int
    bets_resolved: int
    errors: list[str] = []


class RunPredictionsResponse(BaseModel):
    status: str
    matches_evaluated: int
    predictions_saved: int
    bets_placed: int
    errors: list[str] = []


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/sync-fixtures", response_model=SyncFixturesResponse)
def webhook_sync_fixtures(
    competition: str = Query(default="worldcup2026"),
    db: Session = Depends(get_db_session),
):
    """
    Fetch upcoming fixtures from the data source and upsert into DB.
    Creates the competition row and team rows if they don't exist.
    n8n should call this every 60s during an active tournament.
    """
    stats = _fixture_sync.sync_fixtures(competition_slug=competition, db=db)
    status = "ok" if not stats.errors else "partial_error"
    return SyncFixturesResponse(
        status=status,
        competition=competition,
        teams_created=stats.teams_created,
        matches_created=stats.matches_created,
        matches_updated=stats.matches_updated,
        errors=stats.errors[:5],
    )


@router.post("/sync-results", response_model=SyncResultsResponse)
def webhook_sync_results(
    competition: str = Query(default="worldcup2026"),
    days_back: int = Query(default=3, ge=1, le=30),
    db: Session = Depends(get_db_session),
):
    """
    Fetch recent finished matches, update scores/status in DB,
    and resolve any open paper bets for newly finished matches.
    n8n should call this every 5 minutes.
    """
    stats = _fixture_sync.sync_results(
        competition_slug=competition, db=db, days_back=days_back
    )
    status = "ok" if not stats.errors else "partial_error"
    return SyncResultsResponse(
        status=status,
        competition=competition,
        matches_updated=stats.matches_updated,
        bets_resolved=stats.bets_resolved,
        errors=stats.errors[:5],
    )


@router.post("/run-predictions", response_model=RunPredictionsResponse)
def webhook_run_predictions(db: Session = Depends(get_db_session)):
    """
    Run the full 5-layer prediction pipeline for all active competitions.
    Idempotent: already-evaluated matches (same model version) are skipped.
    n8n should call this after sync-fixtures succeeds.
    """
    result: RunResult = run_predictions(db)
    status = "ok" if not result.errors else "partial_error"
    if result.errors:
        logger.warning(
            "run-predictions completed with %d errors: %s",
            len(result.errors),
            result.errors[:3],
        )
    return RunPredictionsResponse(
        status=status,
        matches_evaluated=result.matches_evaluated,
        predictions_saved=result.predictions_saved,
        bets_placed=result.bets_placed,
        errors=result.errors[:5],
    )
