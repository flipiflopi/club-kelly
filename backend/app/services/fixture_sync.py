"""
Fixture synchronisation service.

Bridges the data adapters (adapters/) and the DB (backend/app/models/).
Called by the sync-fixtures and sync-results webhooks.

Responsibilities:
  sync_fixtures  — fetch upcoming/all fixtures → upsert competition, teams, matches
  sync_results   — fetch recent finished results → update match scores/status + resolve bets
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from adapters.base import FixtureDTO
from backend.app.config import get_settings
from backend.app.models.competition import Competition
from backend.app.models.match import Match, MatchStatus
from backend.app.models.team import Team

logger = logging.getLogger(__name__)

COMPETITIONS_DIR = Path(__file__).parents[3] / "competitions"


# ── Result dataclass ──────────────────────────────────────────────────────────


@dataclass
class SyncStats:
    competition_slug: str = ""
    teams_created: int = 0
    matches_created: int = 0
    matches_updated: int = 0
    bets_resolved: int = 0
    retrain: dict | None = None
    resolved_match_ids: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ── Public: sync upcoming fixtures ───────────────────────────────────────────


def sync_fixtures(competition_slug: str, db: Session) -> SyncStats:
    """
    Fetch all fixtures (scheduled + live + finished) from the source adapter
    and upsert them into the DB.
    Creates the competition row and team rows on first run if they don't exist.
    """
    stats = SyncStats(competition_slug=competition_slug)

    config = _load_config(competition_slug)
    competition = _ensure_competition(competition_slug, config, db)
    source = _build_fixture_source(config)

    try:
        fixtures = source.get_upcoming_fixtures()
        # Also fetch recently finished to keep status current
        finished = source.get_recent_results(days_back=30)
        all_fixtures = {f.external_id: f for f in fixtures}
        all_fixtures.update({f.external_id: f for f in finished})
    except Exception as exc:
        msg = f"Failed to fetch fixtures from source: {exc}"
        logger.error(msg, exc_info=True)
        stats.errors.append(msg)
        return stats

    for fixture in all_fixtures.values():
        try:
            _upsert_fixture(fixture, competition, db, stats)
        except Exception as exc:
            msg = f"Fixture {fixture.external_id}: {exc}"
            logger.warning(msg)
            stats.errors.append(msg)

    db.commit()
    logger.info(
        "sync_fixtures [%s]: +%d teams, +%d matches, ~%d updated, %d errors",
        competition_slug,
        stats.teams_created,
        stats.matches_created,
        stats.matches_updated,
        len(stats.errors),
    )
    return stats


# ── Public: sync results + resolve bets ──────────────────────────────────────


def sync_results(competition_slug: str, db: Session, days_back: int = 3) -> SyncStats:
    """
    Fetch recently finished matches, update their scores/status in the DB,
    and trigger bet resolution + model retraining for any that just finished.

    Primary source: competition config fixture_source (e.g. The Odds API /scores).
    Fallback source: results_source (e.g. football-data.org, free tier).
    """
    from backend.app.services.bet_resolver import resolve_bets_for_match

    stats = SyncStats(competition_slug=competition_slug)

    config = _load_config(competition_slug)
    competition = _ensure_competition(competition_slug, config, db)
    source = _build_fixture_source(config)

    recent = source.get_recent_results(days_back=days_back)

    # If primary source returned nothing, try the fallback results source
    if not recent and config.get("data", {}).get("results_source"):
        logger.info("Primary source returned 0 results — trying fallback results_source")
        try:
            fallback = _build_results_source(config)
            if fallback:
                recent = fallback.get_recent_results(days_back=days_back)
        except Exception as exc:
            logger.warning("Fallback results source failed: %s", exc)

    newly_finished: list[Match] = []

    for fixture in recent:
        if fixture.status != "finished":
            continue
        try:
            # Try external_id match first, then fall back to team names + date
            match = db.query(Match).filter_by(external_id=fixture.external_id).first()
            if match is None:
                match = _find_match_by_teams(fixture, competition, db)

            if match is None:
                logger.warning(
                    "No DB match found for %s vs %s on %s",
                    fixture.home_team_name, fixture.away_team_name,
                    fixture.match_date.date(),
                )
                continue

            was_finished = match.status == MatchStatus.FINISHED

            # Update score and status
            match.home_score = fixture.home_score
            match.away_score = fixture.away_score
            match.status = MatchStatus.FINISHED
            db.flush()

            # Resolve bets only if the match just transitioned to finished
            if not was_finished:
                resolved = resolve_bets_for_match(match, db)
                stats.bets_resolved += len(resolved)
                stats.matches_updated += 1
                newly_finished.append(match)
                stats.resolved_match_ids.append(match.id)
                logger.info(
                    "Match %d finished %d-%d, resolved %d bets",
                    match.id,
                    fixture.home_score or 0,
                    fixture.away_score or 0,
                    len(resolved),
                )

        except Exception as exc:
            msg = f"Result {fixture.external_id}: {exc}"
            logger.warning(msg)
            stats.errors.append(msg)

    db.commit()

    # Retrain models whenever new results arrive
    if newly_finished:
        logger.info("Retraining models after %d new result(s)…", len(newly_finished))
        try:
            from backend.app.services.model_retrainer import retrain_models_after_results

            retrain_stats = retrain_models_after_results(competition, newly_finished, db)
            stats.retrain = retrain_stats
        except Exception as exc:
            msg = f"Model retrain failed: {exc}"
            logger.error(msg, exc_info=True)
            stats.errors.append(msg)

    logger.info(
        "sync_results [%s]: %d updated, %d bets resolved, retrain=%s, %d errors",
        competition_slug,
        stats.matches_updated,
        stats.bets_resolved,
        getattr(stats, "retrain", None),
        len(stats.errors),
    )
    return stats


# ── Private: upsert helpers ───────────────────────────────────────────────────


def _upsert_fixture(
    fixture: FixtureDTO,
    competition: Competition,
    db: Session,
    stats: SyncStats,
) -> None:
    """Insert or update one fixture (match + teams)."""
    if not fixture.external_id:
        return
    if fixture.home_team_name == "TBD" or fixture.away_team_name == "TBD":
        # Skip TBD matches (knockout rounds not yet determined)
        return

    home_team = _ensure_team(fixture.home_team_name, db, stats)
    away_team = _ensure_team(fixture.away_team_name, db, stats)

    existing = db.query(Match).filter_by(external_id=fixture.external_id).first()

    if existing is None:
        match = Match(
            competition_id=competition.id,
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            match_date=fixture.match_date,
            status=MatchStatus(fixture.status),
            home_score=fixture.home_score,
            away_score=fixture.away_score,
            external_id=fixture.external_id,
            round=fixture.round,
            venue=fixture.venue,
            is_neutral=fixture.is_neutral,
        )
        db.add(match)
        stats.matches_created += 1
    else:
        # Update mutable fields only
        existing.status = MatchStatus(fixture.status)
        existing.home_score = fixture.home_score
        existing.away_score = fixture.away_score
        existing.match_date = fixture.match_date
        if fixture.round:
            existing.round = fixture.round
        if fixture.venue:
            existing.venue = fixture.venue
        stats.matches_updated += 1


def _ensure_team(name: str, db: Session, stats: SyncStats) -> Team:
    """Find team by name or create it."""
    team = db.query(Team).filter_by(name=name).first()
    if team is None:
        team = Team(
            name=name,
            short_name=name[:10],
            team_type="national",
        )
        db.add(team)
        db.flush()  # get team.id
        stats.teams_created += 1
        logger.info("Created team: %s", name)
    return team


def _ensure_competition(slug: str, config: dict, db: Session) -> Competition:
    """Find competition by slug or create it from YAML config."""
    competition = db.query(Competition).filter_by(slug=slug).first()
    if competition is None:
        competition = Competition(
            slug=slug,
            name=config["name"],
            competition_type=config["competition_type"],
            season=str(config["season"]),
            is_active=True,
            config=config,
        )
        db.add(competition)
        db.flush()
        logger.info("Created competition: %s (%s)", slug, config["name"])
    return competition


# ── Private: config + adapter factory ────────────────────────────────────────


def _load_config(slug: str) -> dict:
    path = COMPETITIONS_DIR / f"{slug}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Competition config not found: {path}")
    with path.open() as f:
        return yaml.safe_load(f)


def _build_fixture_source(config: dict):
    """Instantiate the right fixture adapter based on competition config."""
    source_name: str = config["data"]["fixture_source"]
    sport_key: str = config["data"].get("odds_sport_key", "soccer_fifa_world_cup")
    settings = get_settings()

    if source_name == "OddsApiFixtureSource":
        from adapters.fixtures.odds_api_fixture import OddsApiFixtureSource
        return OddsApiFixtureSource(api_key=settings.the_odds_api_key, sport_key=sport_key)

    if source_name == "WorldCup2026FixtureSource":
        from adapters.fixtures.worldcup2026 import WorldCup2026FixtureSource
        return WorldCup2026FixtureSource(github_token=settings.github_token)

    raise ValueError(f"Unknown fixture_source: {source_name}")


def _build_results_source(config: dict):
    """Instantiate the optional fallback results adapter (e.g. football-data.org)."""
    source_name: str = config.get("data", {}).get("results_source", "")
    if not source_name:
        return None

    settings = get_settings()

    if source_name == "FootballDataFixtureSource":
        from adapters.fixtures.football_data_fixture import FootballDataFixtureSource
        competition_code = config.get("data", {}).get("results_competition_code", "WC")
        team_aliases = config.get("team_aliases", {})
        return FootballDataFixtureSource(
            api_key=settings.football_data_api_key,
            competition_code=competition_code,
            team_aliases=team_aliases,
        )

    logger.warning("Unknown results_source: %s", source_name)
    return None


def _find_match_by_teams(fixture: "FixtureDTO", competition: "Competition", db: Session) -> "Match | None":
    """
    Find a DB match by home/away team names + date (±1 day tolerance).
    Used when the fixture comes from a different source than the one that
    created the DB record (different external_id schemes).
    """
    from datetime import timedelta
    from backend.app.models.team import Team

    home_team = db.query(Team).filter_by(name=fixture.home_team_name).first()
    away_team = db.query(Team).filter_by(name=fixture.away_team_name).first()
    if not home_team or not away_team:
        return None

    lo = fixture.match_date - timedelta(hours=26)
    hi = fixture.match_date + timedelta(hours=26)

    return (
        db.query(Match)
        .filter(
            Match.competition_id == competition.id,
            Match.home_team_id == home_team.id,
            Match.away_team_id == away_team.id,
            Match.match_date >= lo,
            Match.match_date <= hi,
        )
        .first()
    )
