"""
Automatic model retrainer: triggered by sync_results whenever matches finish.

Elo update:  incremental — one Elo step per new result (fast, opponent-aware)
DC retrain:  full pass over CSV historical data + all World Cup DB results

After retraining, predictions for upcoming un-betted matches are deleted
so the next run_predictions call regenerates them with fresh model params.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

logger = logging.getLogger(__name__)

_CSV_PATH = Path("/app/training/data/results.csv")
_DC_MIN_DATE = datetime(2010, 1, 1)


def retrain_models_after_results(
    competition,
    newly_finished: list,
    db: Session,
) -> dict:
    """
    Entry point called after one or more matches transition to FINISHED.
    Returns {"dc_retrained": bool, "elo_updated": int, "predictions_invalidated": int}.
    """
    if not newly_finished:
        return {}

    stats: dict = {"dc_retrained": False, "elo_updated": 0, "predictions_invalidated": 0}

    for match in newly_finished:
        try:
            _update_elo_incremental(match, competition, db)
            stats["elo_updated"] += 1
        except Exception as exc:
            logger.warning("Elo update failed for match %d: %s", match.id, exc)

    try:
        stats["dc_retrained"] = _retrain_dc(competition, db)
    except Exception as exc:
        logger.warning("DC retrain failed: %s", exc, exc_info=True)

    try:
        stats["predictions_invalidated"] = _invalidate_stale_predictions(competition.id, db)
    except Exception as exc:
        logger.warning("Prediction invalidation failed: %s", exc)

    logger.info(
        "Retrain complete [%s]: DC=%s, Elo updated=%d, predictions cleared=%d",
        competition.slug,
        stats["dc_retrained"],
        stats["elo_updated"],
        stats["predictions_invalidated"],
    )
    return stats


def _update_elo_incremental(match, competition, db: Session) -> None:
    """Apply one Elo step for a just-finished match and persist updated ratings."""
    from backend.app.models.elo_rating import EloRating
    from backend.app.models.team import Team
    from engine.models.elo import _k_factor

    home_name = match.home_team.name
    away_name = match.away_team.name

    home_row = db.query(EloRating).join(Team).filter(Team.name == home_name).first()
    away_row = db.query(EloRating).join(Team).filter(Team.name == away_name).first()

    r_h = home_row.rating if home_row else 1500.0
    r_a = away_row.rating if away_row else 1500.0

    # World Cup matches are at neutral venues — no home advantage
    dr = r_h - r_a
    e_h = 1.0 / (1.0 + 10.0 ** (-dr / 400.0))

    h_goals = match.home_score or 0
    a_goals = match.away_score or 0
    if h_goals > a_goals:
        s_h = 1.0
    elif h_goals < a_goals:
        s_h = 0.0
    else:
        s_h = 0.5

    k = _k_factor(competition.name)
    new_r_h = r_h + k * (s_h - e_h)
    new_r_a = r_a + k * ((1.0 - s_h) - (1.0 - e_h))

    now = datetime.now(timezone.utc)

    if home_row:
        home_row.rating = new_r_h
        home_row.matches_played += 1
        home_row.computed_at = now
    else:
        home_team = db.query(Team).filter_by(name=home_name).first()
        if home_team:
            db.add(EloRating(team_id=home_team.id, rating=new_r_h, matches_played=1, computed_at=now))

    if away_row:
        away_row.rating = new_r_a
        away_row.matches_played += 1
        away_row.computed_at = now
    else:
        away_team = db.query(Team).filter_by(name=away_name).first()
        if away_team:
            db.add(EloRating(team_id=away_team.id, rating=new_r_a, matches_played=1, computed_at=now))

    db.commit()
    logger.info(
        "Elo updated: %s %.0f→%.0f, %s %.0f→%.0f (k=%.0f, result=%.1f-%.1f)",
        home_name, r_h, new_r_h,
        away_name, r_a, new_r_a,
        k, h_goals, a_goals,
    )


def _retrain_dc(competition, db: Session) -> bool:
    """
    Full Dixon-Coles retrain on CSV historical data + World Cup DB results.
    Returns True if retrain completed successfully.
    """
    from backend.app.models.match import Match, MatchStatus
    from backend.app.services.fixture_sync import _load_config
    from backend.app.services.prediction_runner import save_model_params_to_db
    from engine.models.dixon_coles import DixonColesModel

    today = datetime.now(timezone.utc)
    records: list[dict] = []

    if _CSV_PATH.exists():
        from adapters.historical.kaggle_international import KaggleInternationalSource

        source = KaggleInternationalSource(csv_path=_CSV_PATH)
        historical = source.get_matches(min_date=_DC_MIN_DATE)
        for m in historical:
            match_dt = m.match_date
            if getattr(match_dt, "tzinfo", None) is None:
                match_dt = match_dt.replace(tzinfo=timezone.utc)
            if match_dt > today:
                continue
            records.append({
                "home_team": m.home_team,
                "away_team": m.away_team,
                "home_goals": m.home_goals,
                "away_goals": m.away_goals,
                "days_ago": max(0, (today - match_dt).days),
            })
        logger.info("DC retrain: %d CSV records (since %s)", len(records), _DC_MIN_DATE.date())
    else:
        logger.warning("DC retrain: CSV not found at %s — using DB results only", _CSV_PATH)

    db_matches = (
        db.query(Match)
        .filter(
            Match.competition_id == competition.id,
            Match.status == MatchStatus.FINISHED,
            Match.home_score.isnot(None),
        )
        .options(joinedload(Match.home_team), joinedload(Match.away_team))
        .all()
    )
    for m in db_matches:
        match_dt = m.match_date
        if getattr(match_dt, "tzinfo", None) is None:
            match_dt = match_dt.replace(tzinfo=timezone.utc)
        records.append({
            "home_team": m.home_team.name,
            "away_team": m.away_team.name,
            "home_goals": m.home_score,
            "away_goals": m.away_score,
            "days_ago": max(0, (today - match_dt).days),
        })

    if not records:
        logger.warning("DC retrain: no training data — skipping")
        return False

    logger.info("DC retrain: %d total records (+%d from DB)", len(records), len(db_matches))

    config = _load_config(competition.slug)
    xi: float = config["model"]["xi"]
    model = DixonColesModel(xi=xi)
    model.fit(records)

    save_model_params_to_db(
        params=model.params,
        competition_id=competition.id,
        matches_used=len(records),
        db=db,
    )
    logger.info(
        "DC retrain complete: %d teams, home_adv=%.3f, rho=%.4f",
        len(model.params.teams),
        model.params.home_advantage,
        model.params.rho,
    )
    return True


def _invalidate_stale_predictions(competition_id: int, db: Session) -> int:
    """
    Delete predictions for upcoming matches that have NO open bets.
    Matches with open bets keep their predictions to avoid double-betting.
    """
    from backend.app.models.match import Match, MatchStatus
    from backend.app.models.prediction import Prediction
    from backend.app.models.simulated_bet import BetStatus, SimulatedBet

    match_ids_with_open_bets: set[int] = {
        row.match_id
        for row in db.query(SimulatedBet.match_id)
        .filter(SimulatedBet.status == BetStatus.OPEN)
        .all()
    }

    upcoming_unbetted_ids = [
        row.id
        for row in db.query(Match.id)
        .filter(
            Match.competition_id == competition_id,
            Match.status.in_([MatchStatus.SCHEDULED, MatchStatus.LIVE]),
            Match.id.notin_(match_ids_with_open_bets),
        )
        .all()
    ]

    if not upcoming_unbetted_ids:
        return 0

    deleted = (
        db.query(Prediction)
        .filter(Prediction.match_id.in_(upcoming_unbetted_ids))
        .delete(synchronize_session=False)
    )
    if deleted > 0:
        db.commit()
        logger.info("Invalidated %d predictions for upcoming un-betted matches", deleted)
    return deleted
