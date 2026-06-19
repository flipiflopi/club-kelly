"""
Reset open bets and predictions for upcoming matches.

Deletes SimulatedBets (OPEN) and Predictions for all SCHEDULED/LIVE matches,
plus any bet_placed bankroll history events.  After running this, trigger
run-predictions again to re-evaluate with the current model parameters.

Safe to run at any time — only touches upcoming matches, never finished ones.

Usage:
  docker exec <backend-container> python -m backend.app.commands.reset_bets
"""

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    from backend.app.database import get_engine, get_session_factory
    from backend.app.models import Base  # noqa: F401
    from backend.app.models.bankroll_history import BankrollHistory
    from backend.app.models.match import Match, MatchStatus
    from backend.app.models.prediction import Prediction
    from backend.app.models.simulated_bet import BetStatus, SimulatedBet

    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        # 1. Find all upcoming match IDs (scheduled or live)
        upcoming_ids = [
            m.id
            for m in db.query(Match.id)
            .filter(Match.status.in_([MatchStatus.SCHEDULED, MatchStatus.LIVE]))
            .all()
        ]
        logger.info("Found %d upcoming matches", len(upcoming_ids))

        # 2. Delete open bets on those matches
        bets_deleted = (
            db.query(SimulatedBet)
            .filter(
                SimulatedBet.match_id.in_(upcoming_ids),
                SimulatedBet.status == BetStatus.OPEN,
            )
            .delete(synchronize_session=False)
        )
        logger.info("Deleted %d open SimulatedBets", bets_deleted)

        # 3. Delete predictions for those matches (so run-predictions re-evaluates them)
        preds_deleted = (
            db.query(Prediction)
            .filter(Prediction.match_id.in_(upcoming_ids))
            .delete(synchronize_session=False)
        )
        logger.info("Deleted %d Predictions", preds_deleted)

        # 4. Remove bet_placed bankroll history events (old accounting model)
        history_deleted = (
            db.query(BankrollHistory)
            .filter(BankrollHistory.event_type == "bet_placed")
            .delete(synchronize_session=False)
        )
        logger.info("Deleted %d bet_placed bankroll events", history_deleted)

        db.commit()

    logger.info(
        "Reset complete. Now trigger run-predictions via n8n or:\n"
        "  curl -X POST https://<your-domain>/api/v1/webhooks/run-predictions"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
