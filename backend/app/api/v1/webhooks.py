"""
Webhook endpoints called by n8n.

n8n workflow responsibilities (NOT implemented here):
  - Cron: POST /v1/webhooks/sync-fixtures every 60s during active tournament
  - Cron: POST /v1/webhooks/sync-results every 5min to pick up finished matches
  - Cron: POST /v1/webhooks/run-predictions after each fixture sync
  - Twitter/X: n8n reads POST /v1/webhooks/new-bet and /v1/webhooks/bet-resolved
    to compose and publish tweets

All endpoints accept an optional X-API-Key header (see deps.verify_webhook_key).
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db_session, verify_webhook_key
from backend.app.models.match import Match, MatchStatus
from backend.app.services.bet_resolver import resolve_bets_for_match

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
    dependencies=[Depends(verify_webhook_key)],
)


class SyncFixturesResponse(BaseModel):
    status: str
    message: str


class SyncResultsResponse(BaseModel):
    status: str
    matches_updated: int
    bets_resolved: int


class RunPredictionsResponse(BaseModel):
    status: str
    matches_evaluated: int
    bets_placed: int


@router.post("/sync-fixtures", response_model=SyncFixturesResponse)
def sync_fixtures(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
):
    """
    Trigger: n8n calls this to refresh upcoming fixtures from the data source.
    The actual fetching happens in a background task so the webhook returns immediately.
    Full implementation: adapters/fixtures/worldcup2026.py (to be wired up next sprint).
    """
    # TODO: wire to adapters.fixtures.worldcup2026.WorldCup2026FixtureSource
    logger.info("sync-fixtures webhook received")
    return SyncFixturesResponse(status="accepted", message="Fixture sync queued")


@router.post("/sync-results", response_model=SyncResultsResponse)
def sync_results(db: Session = Depends(get_db_session)):
    """
    Trigger: n8n calls this after each result check.
    1. Fetches recent results from the data source
    2. Updates match scores and status in DB
    3. Resolves any open bets for newly finished matches
    4. Triggers model re-fit in background (incremental update)
    """
    # TODO: wire to adapters.fixtures.worldcup2026.WorldCup2026FixtureSource for results

    # For now: look for matches marked FINISHED with unresolved bets and resolve them
    finished_with_open_bets = (
        db.query(Match)
        .filter(Match.status == MatchStatus.FINISHED)
        .all()
    )

    total_resolved = 0
    for match in finished_with_open_bets:
        try:
            resolved = resolve_bets_for_match(match, db)
            total_resolved += len(resolved)
        except Exception as exc:
            logger.error("Failed to resolve bets for match %d: %s", match.id, exc)

    return SyncResultsResponse(
        status="ok",
        matches_updated=0,       # TODO: fill when fixture adapter is wired
        bets_resolved=total_resolved,
    )


@router.post("/run-predictions", response_model=RunPredictionsResponse)
def run_predictions(db: Session = Depends(get_db_session)):
    """
    Trigger: n8n calls this after sync-fixtures succeeds.
    Evaluates all upcoming matches without predictions yet, runs the full
    5-layer decision pipeline, and records any new simulated bets.
    Full implementation: backend/app/services/prediction_runner.py (next sprint).
    """
    # TODO: wire prediction pipeline
    logger.info("run-predictions webhook received")
    return RunPredictionsResponse(
        status="accepted",
        matches_evaluated=0,
        bets_placed=0,
    )
