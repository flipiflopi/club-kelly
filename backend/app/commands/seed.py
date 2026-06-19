"""
One-shot seed command. Run this once after first deploy to bootstrap the system:

  uv run python -m backend.app.commands.seed --competition worldcup2026

What it does:
  1. Creates DB tables (idempotent — same as alembic upgrade head for fresh installs)
  2. Ensures the competition row exists
  3. Trains Dixon-Coles on the Kaggle CSV (if available) and saves params to DB
  4. Seeds the initial bankroll history entry (1000€ starting balance)
  5. Prints next-step instructions

The Kaggle CSV is optional: if not present, the model is skipped and a warning
is printed. You can always run this again after placing the CSV file.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the football prediction system")
    parser.add_argument("--competition", default="worldcup2026")
    parser.add_argument(
        "--historical-csv",
        default="training/data/results.csv",
        help="Path to the Kaggle international football results CSV",
    )
    parser.add_argument(
        "--min-date",
        default="2000-01-01",
        help="Only use matches on/after this date for model training",
    )
    parser.add_argument(
        "--skip-model",
        action="store_true",
        help="Skip model training (useful if you just want to seed competition + bankroll)",
    )
    parser.add_argument(
        "--elo-min-date",
        default="1990-01-01",
        help="Only use matches on/after this date for Elo training (default: 1990)",
    )
    args = parser.parse_args()

    # ── Step 1: DB tables ─────────────────────────────────────────────────────
    logger.info("Step 1/4 — Ensuring DB tables exist…")
    from backend.app.database import get_engine
    from backend.app.models import Base  # noqa: F401 — registers all models

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("DB tables OK")

    # ── Step 2: Competition row ───────────────────────────────────────────────
    logger.info("Step 2/4 — Seeding competition '%s'…", args.competition)
    from backend.app.database import get_session_factory
    from backend.app.services.fixture_sync import _ensure_competition, _load_config

    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        config = _load_config(args.competition)
        competition = _ensure_competition(args.competition, config, db)
        db.commit()
        competition_id = competition.id
    logger.info("Competition ID: %d", competition_id)

    # ── Step 3: Dixon-Coles training + params to DB ───────────────────────────
    if args.skip_model:
        logger.warning("--skip-model set, skipping model training")
    else:
        logger.info("Step 3/5 — Training Dixon-Coles model…")
        _train_and_save_dc(args, competition_id)

        logger.info("Step 4/5 — Training Elo model…")
        _train_and_save_elo(args, competition_id)

    # ── Step 5: Initial bankroll entry ────────────────────────────────────────
    logger.info("Step 5/5 — Seeding initial bankroll…")
    from backend.app.config import get_settings
    from backend.app.models.bankroll_history import BankrollEventType, BankrollHistory

    settings = get_settings()
    with SessionLocal() as db:
        existing = db.query(BankrollHistory).first()
        if existing is None:
            db.add(
                BankrollHistory(
                    event_type=BankrollEventType.INITIAL,
                    amount_change=settings.initial_bankroll,
                    balance_after=settings.initial_bankroll,
                    note=f"Initial paper bankroll: {settings.initial_bankroll}€",
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
            logger.info("Initial bankroll set to %.2f€", settings.initial_bankroll)
        else:
            logger.info("Bankroll already seeded (balance: %.2f€)", existing.balance_after)

    _print_next_steps(args)
    return 0


def _train_and_save_dc(args: argparse.Namespace, competition_id: int) -> None:
    csv_path = Path(args.historical_csv)
    if not csv_path.exists():
        logger.warning(
            "Kaggle CSV not found at '%s'. Skipping model training.\n"
            "To train the model:\n"
            "  1. Download from https://www.kaggle.com/datasets/martj42/international-football-results\n"
            "  2. Place results.csv at '%s'\n"
            "  3. Re-run this command",
            csv_path,
            csv_path,
        )
        return

    logger.info("Loading historical data from %s…", csv_path)
    from adapters.historical.kaggle_international import KaggleInternationalSource

    min_date = datetime.fromisoformat(args.min_date)
    source = KaggleInternationalSource(csv_path=csv_path)
    historical = source.get_matches(min_date=min_date)
    logger.info("Loaded %d historical matches (since %s)", len(historical), args.min_date)

    if not historical:
        logger.error("No historical matches found. Check --min-date and CSV path.")
        return

    today = datetime.now(timezone.utc)
    match_records = [
        {
            "home_team": m.home_team,
            "away_team": m.away_team,
            "home_goals": m.home_goals,
            "away_goals": m.away_goals,
            "days_ago": max(0, (today.replace(tzinfo=None) - m.match_date.replace(tzinfo=None)).days),
        }
        for m in historical
        if m.match_date.replace(tzinfo=None) <= today.replace(tzinfo=None)
    ]

    logger.info("Fitting Dixon-Coles on %d matches…", len(match_records))
    from backend.app.services.fixture_sync import _load_config
    config = _load_config(args.competition)
    xi: float = config["model"]["xi"]

    from engine.models.dixon_coles import DixonColesModel
    model = DixonColesModel(xi=xi)
    model.fit(match_records)
    params = model.params

    logger.info(
        "Fit complete: %d teams, home_adv=%.3f, rho=%.4f",
        len(params.teams),
        params.home_advantage,
        params.rho,
    )

    logger.info("Saving params to DB…")
    from backend.app.database import get_session_factory
    from backend.app.services.prediction_runner import save_model_params_to_db

    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        save_model_params_to_db(
            params=params,
            competition_id=competition_id,
            matches_used=len(match_records),
            db=db,
        )

    logger.info("Model params saved for %d teams", len(params.teams))


def _train_and_save_elo(args: argparse.Namespace, competition_id: int) -> None:
    csv_path = Path(args.historical_csv)
    if not csv_path.exists():
        logger.warning("Kaggle CSV not found — skipping Elo training")
        return

    from adapters.historical.kaggle_international import KaggleInternationalSource

    elo_min_date = datetime.fromisoformat(args.elo_min_date)
    source = KaggleInternationalSource(csv_path=csv_path)
    historical = source.get_matches(min_date=elo_min_date)
    logger.info("Elo training: %d matches since %s", len(historical), args.elo_min_date)

    if not historical:
        logger.error("No historical matches for Elo training.")
        return

    # Sort chronologically (oldest first — Elo is sequential)
    historical.sort(key=lambda m: m.match_date)

    match_records = [
        {
            "home_team": m.home_team,
            "away_team": m.away_team,
            "home_goals": m.home_goals,
            "away_goals": m.away_goals,
            "tournament": m.competition,
            "is_neutral": m.is_neutral,
        }
        for m in historical
    ]

    from engine.models.elo import EloModel
    elo = EloModel(home_advantage=65.0)
    elo.fit(match_records)
    params = elo.params

    logger.info(
        "Elo fit complete: %d teams rated. Top 5: %s",
        len(params.ratings),
        sorted(params.ratings.items(), key=lambda x: -x[1])[:5],
    )

    from backend.app.database import get_session_factory
    from backend.app.models.elo_rating import EloRating
    from backend.app.models.team import Team

    SessionLocal = get_session_factory()
    now = datetime.now(timezone.utc)
    saved = 0
    skipped = 0

    with SessionLocal() as db:
        for team_name, rating in params.ratings.items():
            team = db.query(Team).filter_by(name=team_name).first()
            if team is None:
                skipped += 1
                continue

            existing = db.query(EloRating).filter_by(team_id=team.id).first()
            if existing:
                existing.rating = rating
                existing.matches_played = params.matches_played.get(team_name, 0)
                existing.computed_at = now
            else:
                db.add(EloRating(
                    team_id=team.id,
                    rating=rating,
                    matches_played=params.matches_played.get(team_name, 0),
                    computed_at=now,
                ))
            saved += 1

        db.commit()

    logger.info("Elo ratings saved: %d teams. Skipped (not in teams table): %d", saved, skipped)
    if skipped > 0:
        logger.info("Note: run sync-fixtures first so all World Cup teams exist in DB")


def _print_next_steps(args: argparse.Namespace) -> None:
    print("\n" + "=" * 60)
    print("Seed complete. Next steps:")
    print()
    print("1. Sync World Cup fixtures (call from n8n or manually):")
    print("   curl -X POST http://localhost:8000/v1/webhooks/sync-fixtures")
    print()
    print("2. Run predictions (after fixtures are loaded):")
    print("   curl -X POST http://localhost:8000/v1/webhooks/run-predictions")
    print()
    print("3. Check the dashboard:")
    print("   http://localhost:3000")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
