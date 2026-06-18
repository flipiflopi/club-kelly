"""
Offline training script for the Dixon-Coles model.

Usage:
    uv run python -m training.train_dixon_coles \
        --competition worldcup2026 \
        --min-date 2010-01-01 \
        --output training/data/params_worldcup2026.json

This script is NOT called during normal API operation.
The backend loads pre-trained parameters from the database.
After each World Cup match finishes, sync-results triggers an incremental re-fit.
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit Dixon-Coles model on historical data")
    parser.add_argument("--competition", default="worldcup2026")
    parser.add_argument("--min-date", default="2010-01-01", help="ISO date")
    parser.add_argument("--output", default="training/data/params.json")
    args = parser.parse_args()

    from adapters.historical.kaggle_international import KaggleInternationalSource
    from engine.models.dixon_coles import DixonColesModel

    min_date = datetime.fromisoformat(args.min_date)

    logger.info("Loading historical data from Kaggle CSV…")
    source = KaggleInternationalSource()
    historical = source.get_matches(min_date=min_date)
    logger.info("Loaded %d matches", len(historical))

    # Convert to MatchRecord format expected by the model
    today = datetime.utcnow()
    matches = [
        {
            "home_team": m.home_team,
            "away_team": m.away_team,
            "home_goals": m.home_goals,
            "away_goals": m.away_goals,
            "days_ago": (today - m.match_date.replace(tzinfo=None)).days,
        }
        for m in historical
        if m.match_date.replace(tzinfo=None) <= today
    ]

    logger.info("Fitting Dixon-Coles on %d matches…", len(matches))
    model = DixonColesModel(xi=0.0023)
    model.fit(matches)

    params = model.params
    output = {
        "competition": args.competition,
        "fitted_at": datetime.utcnow().isoformat(),
        "matches_used": len(matches),
        "home_advantage": params.home_advantage,
        "rho": params.rho,
        "teams": params.teams,
        "attack": params.attack,
        "defense": params.defense,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    logger.info("Parameters saved to %s", out_path)


if __name__ == "__main__":
    main()
