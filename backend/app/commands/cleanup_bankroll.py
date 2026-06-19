"""
One-time cleanup: remove all 'bet_placed' events from bankroll_history.

Paper trading semantics changed: bankroll now only moves on resolution (win/loss),
not when a bet is placed. Old 'bet_placed' rows distort the chart and snapshot.

Run on the server:
  docker exec <container> python -m backend.app.commands.cleanup_bankroll
"""

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    from backend.app.database import get_engine, get_session_factory
    from backend.app.models import Base  # noqa: F401
    from backend.app.models.bankroll_history import BankrollHistory

    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        rows = (
            db.query(BankrollHistory)
            .filter(BankrollHistory.event_type == "bet_placed")
            .all()
        )
        count = len(rows)
        if count == 0:
            logger.info("Nothing to clean up — no 'bet_placed' rows found.")
            return 0

        logger.info("Deleting %d 'bet_placed' rows from bankroll_history…", count)
        for row in rows:
            db.delete(row)
        db.commit()
        logger.info("Done. Bankroll history now starts at the initial deposit and only moves on resolution.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
