"""
Resolves open simulated bets once a match finishes.
Called by the webhook endpoint that n8n triggers after syncing results.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.models.bankroll_history import BankrollEventType, BankrollHistory
from backend.app.models.match import Match, MatchStatus
from backend.app.models.simulated_bet import BetStatus, SimulatedBet


def _determine_outcome(bet: SimulatedBet, match: Match) -> BetStatus:
    """Check if the bet outcome matches the actual result."""
    prediction = bet.prediction
    outcome = prediction.outcome
    market_slug = prediction.market_type.slug

    if match.home_score is None or match.away_score is None:
        return BetStatus.VOID

    home = match.home_score
    away = match.away_score
    total = home + away

    if market_slug == "match_result":
        if outcome == "home":
            return BetStatus.WON if home > away else BetStatus.LOST
        if outcome == "draw":
            return BetStatus.WON if home == away else BetStatus.LOST
        if outcome == "away":
            return BetStatus.WON if away > home else BetStatus.LOST

    if market_slug.startswith("over_under_"):
        # slug format: over_under_2_5 → threshold = 2.5
        threshold = float(market_slug.replace("over_under_", "").replace("_", "."))
        if outcome == "over":
            return BetStatus.WON if total > threshold else BetStatus.LOST
        if outcome == "under":
            return BetStatus.WON if total < threshold else BetStatus.LOST

    if market_slug == "btts":
        btts = home >= 1 and away >= 1
        if outcome == "yes":
            return BetStatus.WON if btts else BetStatus.LOST
        if outcome == "no":
            return BetStatus.WON if not btts else BetStatus.LOST

    return BetStatus.VOID


def resolve_bets_for_match(match: Match, db: Session) -> list[SimulatedBet]:
    """
    Resolve all open bets for a finished match.
    Returns the list of resolved bets (for logging / webhook payload).
    """
    if match.status != MatchStatus.FINISHED:
        raise ValueError(f"Match {match.id} is not finished (status={match.status})")

    open_bets: list[SimulatedBet] = (
        db.query(SimulatedBet)
        .filter(
            SimulatedBet.match_id == match.id,
            SimulatedBet.status == BetStatus.OPEN,
        )
        .all()
    )

    now = datetime.now(timezone.utc)
    resolved = []

    for bet in open_bets:
        status = _determine_outcome(bet, match)

        if status == BetStatus.WON:
            profit_loss = bet.stake_amount * (bet.decimal_odds - 1.0)
        elif status == BetStatus.LOST:
            profit_loss = -bet.stake_amount
        else:
            profit_loss = 0.0

        bankroll_after = bet.bankroll_before + profit_loss

        bet.status = status
        bet.profit_loss = profit_loss
        bet.bankroll_after = bankroll_after
        bet.resolved_at = now

        db.add(
            BankrollHistory(
                event_type=BankrollEventType.BET_RESOLVED,
                amount_change=profit_loss,
                balance_after=bankroll_after,
                reference_bet_id=bet.id,
                note=f"Match {match.id} resolved: {status.value}",
                created_at=now,
            )
        )

        resolved.append(bet)

    db.commit()
    return resolved
