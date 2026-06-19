"""
Prediction runner — orchestrates the full 5-layer decision pipeline.

Called by: POST /v1/webhooks/run-predictions (n8n triggers this after sync-fixtures)

Layer flow per match outcome:
  1  DixonColesModel.predict_score_matrix  → probability matrix
  1b MarketModule.calculate                → {outcome: probability} per market
  2  evaluate_outcome                      → edge vs fair market prob (vig-removed)
  3  kelly_fraction                        → fractional Kelly stake size
  4  apply_risk_filters                    → cap / block based on exposure limits
  [5  Claude API reasoning — NOT here, separate step after bet is created]

Design constraints:
  - Engine modules receive plain Python data; they never import from backend.*
  - DB interaction is confined to the private helpers in this file
  - Each Prediction row = one (match, market, outcome, model_version) evaluation
  - Each SimulatedBet row = one placed paper trade (only when all 4 layers pass)
  - A match is skipped if any Prediction with MODEL_VERSION already exists for it
    (re-run requires a version bump, which happens after model retrain)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.orm import Session, joinedload

from backend.app.config import get_settings
from backend.app.models.bankroll_history import BankrollHistory
from backend.app.models.competition import Competition
from backend.app.models.market_type import MarketType
from backend.app.models.match import Match, MatchStatus
from backend.app.models.model_params import ModelParams
from backend.app.models.prediction import Prediction
from backend.app.models.simulated_bet import BetStatus, SimulatedBet
from engine.decision.edge import evaluate_outcome, remove_vig
from engine.decision.kelly import kelly_fraction
from engine.decision.risk_filters import RiskConfig, apply_risk_filters, correlated_exposure
from engine.markets import market_registry
from engine.models.dixon_coles import DixonColesModel, DixonColesParams

logger = logging.getLogger(__name__)

COMPETITIONS_DIR = Path(__file__).parents[4] / "competitions"
MODEL_VERSION = "dixon_coles_v1"


# ── Result dataclass ──────────────────────────────────────────────────────────


@dataclass
class RunResult:
    matches_evaluated: int = 0
    predictions_saved: int = 0
    bets_placed: int = 0
    errors: list[str] = field(default_factory=list)


# ── Public entry point ────────────────────────────────────────────────────────


def run_predictions(db: Session) -> RunResult:
    """
    Run the prediction pipeline for all active competitions.
    Idempotent: already-predicted matches (same MODEL_VERSION) are skipped.
    """
    result = RunResult()
    active_competitions = db.query(Competition).filter_by(is_active=True).all()

    if not active_competitions:
        logger.warning("No active competitions found — nothing to predict")
        return result

    market_types = _seed_market_types(db)

    for competition in active_competitions:
        try:
            _run_for_competition(competition, market_types, db, result)
        except Exception as exc:
            msg = f"Competition {competition.slug}: {exc}"
            logger.error(msg, exc_info=True)
            result.errors.append(msg)

    logger.info(
        "run_predictions done: %d matches, %d predictions, %d bets, %d errors",
        result.matches_evaluated,
        result.predictions_saved,
        result.bets_placed,
        len(result.errors),
    )
    return result


# ── Public utility: called by training scripts to persist model params ────────


def save_model_params_to_db(
    params: DixonColesParams,
    competition_id: int,
    matches_used: int,
    db: Session,
) -> None:
    """
    Persist fitted Dixon-Coles parameters to the model_params table.
    Called once after training/train_dixon_coles.py finishes.
    Each call inserts new rows (history is kept; query latest by computed_at).
    """
    from backend.app.models.team import Team

    now = datetime.now(timezone.utc)

    # home_advantage and rho are the same for all teams in the same fit
    home_advantage = params.home_advantage
    rho = params.rho

    for team_name in params.teams:
        team = db.query(Team).filter_by(name=team_name).first()
        if team is None:
            logger.warning("Team not found in DB, skipping param save: %s", team_name)
            continue

        db.add(
            ModelParams(
                competition_id=competition_id,
                team_id=team.id,
                attack_strength=params.attack[team_name],
                defense_strength=params.defense[team_name],
                home_advantage=home_advantage,
                rho=rho,
                matches_used=matches_used,
                computed_at=now,
            )
        )

    db.commit()
    logger.info(
        "Saved model params for %d teams in competition_id=%d",
        len(params.teams),
        competition_id,
    )


# ── Private: per-competition orchestration ───────────────────────────────────


def _run_for_competition(
    competition: Competition,
    market_types: dict[str, MarketType],
    db: Session,
    result: RunResult,
) -> None:
    config = _load_config(competition.slug)
    model = _load_model_from_db(competition, config, db)

    risk_cfg = RiskConfig(
        max_bet_pct=config["risk"]["max_bet_pct"],
        max_daily_exposure_pct=config["risk"]["max_daily_exposure_pct"],
        min_odds=config["risk"]["min_odds"],
        max_odds=config["risk"]["max_odds"],
    )
    min_edge: float = config["edge"]["min_edge"]
    kelly_multiplier: float = config["kelly"]["multiplier"]

    upcoming = _get_unpredicted_matches(competition.id, db)
    logger.info(
        "Competition %s: %d unpredicted upcoming matches",
        competition.slug,
        len(upcoming),
    )

    # Lazily instantiate odds source (requires API key)
    odds_source = _build_odds_source()

    for match in upcoming:
        try:
            n_preds, n_bets = _process_match(
                match=match,
                model=model,
                market_types=market_types,
                risk_cfg=risk_cfg,
                min_edge=min_edge,
                kelly_multiplier=kelly_multiplier,
                odds_source=odds_source,
                db=db,
            )
            result.matches_evaluated += 1
            result.predictions_saved += n_preds
            result.bets_placed += n_bets
        except Exception as exc:
            msg = f"Match {match.id}: {exc}"
            logger.error(msg, exc_info=True)
            result.errors.append(msg)


# ── Private: per-match prediction logic ──────────────────────────────────────


def _process_match(
    match: Match,
    model: DixonColesModel,
    market_types: dict[str, MarketType],
    risk_cfg: RiskConfig,
    min_edge: float,
    kelly_multiplier: float,
    odds_source,
    db: Session,
) -> tuple[int, int]:
    """
    Run all 4 decision layers for one match.
    Returns (predictions_saved, bets_placed).
    """
    home_name = match.home_team.name
    away_name = match.away_team.name

    if home_name not in model.known_teams() or away_name not in model.known_teams():
        logger.warning(
            "Match %d: team not in model (%s vs %s) — skipping",
            match.id, home_name, away_name,
        )
        return 0, 0

    # Layer 1a: score probability matrix
    score_matrix = model.predict_score_matrix(
        home_name, away_name, is_neutral=match.is_neutral
    )

    # Fetch odds once per match (None if unavailable)
    odds_map = _fetch_odds_map(match, odds_source)

    current_bankroll = _get_current_bankroll(db)
    # Exposure from other matches today (exclude this match to handle correlation)
    base_exposure = _get_daily_exposure(db, exclude_match_id=match.id)

    # Track stakes being placed for this match (for intra-match correlation)
    this_match_stakes: list[float] = []

    n_preds = 0
    n_bets = 0

    for market_slug, market_type in market_types.items():
        if market_slug not in market_registry:
            continue

        # Layer 1b: market-specific probabilities
        market_module = market_registry.get(market_slug)
        outcome_probs: dict[str, float] = market_module.calculate(score_matrix)

        market_odds_dict: dict[str, float] = odds_map.get(market_slug, {})

        for outcome, model_prob in outcome_probs.items():
            decimal_odds = market_odds_dict.get(outcome)

            # Always save the prediction (full audit trail regardless of bet decision)
            eval_result = _run_edge_layer(
                model_prob=model_prob,
                decimal_odds=decimal_odds,
                market_odds_dict=market_odds_dict,
                outcome=outcome,
                min_edge=min_edge,
            )

            prediction = Prediction(
                match_id=match.id,
                market_type_id=market_type.id,
                outcome=outcome,
                model_probability=model_prob,
                market_odds=decimal_odds,
                market_probability=eval_result.get("fair_prob"),
                edge=eval_result.get("edge"),
                model_version=MODEL_VERSION,
            )
            db.add(prediction)
            db.flush()  # get prediction.id before creating bet
            n_preds += 1

            # Layers 3-4: sizing and risk — only if edge passes Layer 2
            if decimal_odds is None or not eval_result.get("has_value"):
                continue

            k_frac = kelly_fraction(
                model_prob=model_prob,
                decimal_odds=decimal_odds,
                kelly_multiplier=kelly_multiplier,
            )
            if k_frac <= 0:
                continue

            # Daily exposure = base (other matches) + correlated max for this match
            effective_exposure = base_exposure + correlated_exposure(this_match_stakes)

            filter_result = apply_risk_filters(
                proposed_stake_pct=k_frac,
                decimal_odds=decimal_odds,
                current_bankroll=current_bankroll,
                open_exposure_eur=effective_exposure,
                risk_config=risk_cfg,
            )

            if not filter_result.allowed:
                logger.debug(
                    "Match %d %s/%s blocked: %s (%s)",
                    match.id, market_slug, outcome,
                    filter_result.rejection_reason,
                    filter_result.note,
                )
                continue

            # Place the paper bet
            stake_eur = filter_result.final_stake_eur
            profit_if_win = stake_eur * (decimal_odds - 1.0)

            bet = SimulatedBet(
                prediction_id=prediction.id,
                match_id=match.id,
                stake_amount=stake_eur,
                stake_pct=filter_result.final_stake_pct,
                bankroll_before=current_bankroll,
                kelly_fraction=k_frac,
                decimal_odds=decimal_odds,
                status=BetStatus.OPEN,
            )
            db.add(bet)
            db.flush()

            # Paper trading: bankroll only changes at resolution (win/loss), not at placement.
            # We still update in-memory so subsequent bets in this run are sized correctly.
            this_match_stakes.append(stake_eur)
            current_bankroll -= stake_eur
            n_bets += 1

            logger.info(
                "BET placed: match=%d %s/%s @ %.2f | stake=%.2f€ edge=%.1f%% kelly=%.3f",
                match.id, market_slug, outcome, decimal_odds,
                stake_eur, (eval_result["edge"] * 100), k_frac,
            )

    db.commit()
    return n_preds, n_bets


# ── Private: edge layer wrapper ───────────────────────────────────────────────


def _run_edge_layer(
    model_prob: float,
    decimal_odds: float | None,
    market_odds_dict: dict[str, float],
    outcome: str,
    min_edge: float,
) -> dict:
    """
    Run Layer 2 edge detection. Returns an empty dict (no edge info) if odds are missing.
    """
    if decimal_odds is None or len(market_odds_dict) < 2:
        return {}

    # Build sorted list of all outcomes for vig removal (consistent ordering)
    sorted_outcomes = sorted(market_odds_dict.keys())
    all_odds = [market_odds_dict[o] for o in sorted_outcomes]
    outcome_index = sorted_outcomes.index(outcome)

    return evaluate_outcome(
        model_prob=model_prob,
        decimal_odds=decimal_odds,
        all_market_odds=all_odds,
        outcome_index=outcome_index,
        min_edge=min_edge,
    )


# ── Private: DB helpers ───────────────────────────────────────────────────────


def _seed_market_types(db: Session) -> dict[str, MarketType]:
    """
    Ensure every registered market module has a row in the market_types table.
    Returns a dict slug -> MarketType for convenient lookup.
    """
    import engine.markets  # noqa: F401 — triggers auto-registration

    result: dict[str, MarketType] = {}
    for slug in market_registry.all_slugs():
        mt = db.query(MarketType).filter_by(slug=slug).first()
        if mt is None:
            market_module = market_registry.get(slug)
            mt = MarketType(slug=slug, name=market_module.name, is_active=True)
            db.add(mt)
            logger.info("Seeded market_type: %s", slug)
    db.commit()

    for slug in market_registry.all_slugs():
        mt = db.query(MarketType).filter_by(slug=slug).first()
        if mt:
            result[slug] = mt

    return result


def _load_config(slug: str) -> dict:
    path = COMPETITIONS_DIR / f"{slug}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Competition config not found: {path}")
    with path.open() as f:
        return yaml.safe_load(f)


def _load_model_from_db(competition: Competition, config: dict, db: Session) -> DixonColesModel:
    """
    Reconstruct a DixonColesModel from the latest ModelParams rows in the DB.
    Raises RuntimeError if no params are found (run training first).
    """
    rows: list[ModelParams] = (
        db.query(ModelParams)
        .filter_by(competition_id=competition.id)
        .options(joinedload(ModelParams.team))
        .order_by(ModelParams.computed_at.desc())
        .all()
    )

    if not rows:
        raise RuntimeError(
            f"No model params found for competition '{competition.slug}'. "
            "Run training/train_dixon_coles.py and load params to DB first."
        )

    # Keep only the latest row per team
    by_team: dict[int, ModelParams] = {}
    for row in rows:
        if row.team_id not in by_team:
            by_team[row.team_id] = row  # already ordered desc by computed_at

    any_row = next(iter(by_team.values()))
    params = DixonColesParams(
        attack={r.team.name: r.attack_strength for r in by_team.values()},
        defense={r.team.name: r.defense_strength for r in by_team.values()},
        home_advantage=any_row.home_advantage,
        rho=any_row.rho,
        teams=sorted(r.team.name for r in by_team.values()),
    )

    xi: float = config["model"]["xi"]
    max_goals: int = config["model"].get("max_goals", 10)
    logger.info(
        "Loaded model for %s: %d teams, xi=%.4f",
        competition.slug, len(params.teams), xi,
    )
    return DixonColesModel.from_params(params, xi=xi, max_goals=max_goals)


def _get_unpredicted_matches(competition_id: int, db: Session) -> list[Match]:
    """
    Upcoming matches for a competition that have NOT yet been evaluated with the
    current MODEL_VERSION. Uses a NOT EXISTS subquery for efficiency.
    """
    from sqlalchemy import exists

    predicted_match_ids = (
        db.query(Prediction.match_id)
        .filter(Prediction.model_version == MODEL_VERSION)
        .subquery()
    )

    return (
        db.query(Match)
        .options(joinedload(Match.home_team), joinedload(Match.away_team))
        .filter(
            Match.competition_id == competition_id,
            Match.status.in_([MatchStatus.SCHEDULED, MatchStatus.LIVE]),
            ~Match.id.in_(predicted_match_ids),
        )
        .order_by(Match.match_date.asc())
        .all()
    )


def _get_current_bankroll(db: Session) -> float:
    latest = (
        db.query(BankrollHistory)
        .order_by(BankrollHistory.id.desc())
        .first()
    )
    return latest.balance_after if latest else get_settings().initial_bankroll


def _get_daily_exposure(db: Session, exclude_match_id: int | None = None) -> float:
    """
    Total open bet exposure for today, using correlated_exposure per match
    (worst-case stake per match, not sum of all stakes on the same match).
    """
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    open_bets: list[SimulatedBet] = (
        db.query(SimulatedBet)
        .filter(
            SimulatedBet.status == BetStatus.OPEN,
            SimulatedBet.created_at >= today_start,
        )
        .all()
    )

    by_match: dict[int, list[float]] = {}
    for bet in open_bets:
        if bet.match_id == exclude_match_id:
            continue
        by_match.setdefault(bet.match_id, []).append(bet.stake_amount)

    return sum(correlated_exposure(stakes) for stakes in by_match.values())


# ── Private: odds fetching ────────────────────────────────────────────────────


def _build_odds_source():
    """
    Instantiate the configured odds adapter.
    Returns None if no API key is set (odds step will be skipped).
    """
    settings = get_settings()
    if not settings.the_odds_api_key:
        logger.warning("THE_ODDS_API_KEY not set — predictions will have no odds/edge data")
        return None
    from adapters.odds.the_odds_api import TheOddsApiSource
    return TheOddsApiSource(api_key=settings.the_odds_api_key)


def _fetch_odds_map(match: Match, odds_source) -> dict[str, dict[str, float]]:
    """
    Returns {market_slug: {outcome: decimal_odds}} for the given match.
    Returns empty dict if odds_source is None or match has no external_id.
    """
    if odds_source is None or not match.external_id:
        return {}

    try:
        odds_list = odds_source.get_odds(
            external_match_ids=[match.external_id],
            market_slugs=market_registry.all_slugs(),
        )
    except Exception as exc:
        logger.warning("Could not fetch odds for match %d: %s", match.id, exc)
        return {}

    result: dict[str, dict[str, float]] = {}
    for dto in odds_list:
        result[dto.market_slug] = dto.outcomes
    return result
