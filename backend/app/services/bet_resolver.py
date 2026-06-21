"""
Resolves open simulated bets once a match finishes.
Called by the webhook endpoint that n8n triggers after syncing results.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.models.bankroll_history import BankrollEventType, BankrollHistory
from backend.app.models.match import Match, MatchStatus
from backend.app.models.simulated_bet import BetStatus, SimulatedBet


def _get_current_bankroll(db: Session) -> float:
    latest = (
        db.query(BankrollHistory)
        .order_by(BankrollHistory.id.desc())
        .first()
    )
    return latest.balance_after if latest else get_settings().initial_bankroll


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

    # Running bankroll: starts from the last resolved event (not from placement time).
    # Bankroll only changes at resolution, never at bet placement.
    running_balance = _get_current_bankroll(db)

    for bet in open_bets:
        status = _determine_outcome(bet, match)

        if status == BetStatus.WON:
            profit_loss = bet.stake_amount * (bet.decimal_odds - 1.0)
        elif status == BetStatus.LOST:
            profit_loss = -bet.stake_amount
        else:
            profit_loss = 0.0

        running_balance += profit_loss

        bet.status = status
        bet.profit_loss = profit_loss
        bet.bankroll_after = running_balance
        bet.resolved_at = now

        db.add(
            BankrollHistory(
                event_type=BankrollEventType.BET_RESOLVED,
                amount_change=profit_loss,
                balance_after=running_balance,
                reference_bet_id=bet.id,
                note=f"Match {match.id} resolved: {status.value}",
                created_at=now,
            )
        )

        resolved.append(bet)

    db.commit()

    if resolved:
        _notify_resolved(match, resolved, running_balance, db)

    return resolved


def _format_resolved_tweet(
    home: str, away: str, home_score: int, away_score: int,
    bet_data: list[dict], bankroll_after: float,
) -> str:
    all_won = all(b["status"] == "won" for b in bet_data)
    all_lost = all(b["status"] == "lost" for b in bet_data)
    icon = "✅" if all_won else "❌" if all_lost else "↔️"
    label = "WIN!" if all_won else "Loss" if all_lost else "Mixed"

    lines = [
        f"{icon} {label} · {home} {home_score}–{away_score} {away}",
        "World Cup 2026",
        "",
    ]
    for b in bet_data:
        outcome = b["outcome"]
        if outcome == "home":
            outcome = home
        elif outcome == "away":
            outcome = away
        elif outcome == "draw":
            outcome = "Draw"
        pl = b["profit_loss"]
        pl_str = f"+{pl:.0f}€" if pl >= 0 else f"{pl:.0f}€"
        lines.append(f"Kelly bet {outcome} @{b['decimal_odds']:.2f}")
        lines.append(f"Stake {b['stake_amount']:.0f}€ → {pl_str}")

    lines += [
        "",
        f"Bankroll: {bankroll_after:,.0f}€",
        "",
        "https://clubkelly.online/",
        "t.me/Club_Kelly",
        "#ClubKelly #WorldCup2026",
    ]
    tweet = "\n".join(lines)
    if len(tweet) > 280:
        tweet = tweet[:277] + "..."
    return tweet


def _notify_resolved(match: Match, bets: list[SimulatedBet], bankroll_after: float, db: Session) -> None:
    import logging
    log = logging.getLogger(__name__)

    settings = get_settings()

    bankroll_before = bankroll_after - sum(b.profit_loss for b in bets if b.profit_loss)
    bet_data = [
        {
            "outcome": b.prediction.outcome,
            "decimal_odds": b.decimal_odds,
            "stake_amount": b.stake_amount,
            "profit_loss": b.profit_loss or 0.0,
            "status": b.status.value if hasattr(b.status, "value") else str(b.status),
        }
        for b in bets
        if b.prediction and b.status.value in ("won", "lost")
    ]
    if not bet_data:
        return

    home = match.home_team.name if match.home_team else "?"
    away = match.away_team.name if match.away_team else "?"
    home_score = match.home_score or 0
    away_score = match.away_score or 0

    # Telegram
    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            from backend.app.services.telegram_notifier import notify_bet_resolved
            notify_bet_resolved(
                home_team=home,
                away_team=away,
                home_score=home_score,
                away_score=away_score,
                bets=bet_data,
                bankroll_before=bankroll_before,
                bankroll_after=bankroll_after,
                token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
            )
        except Exception as exc:
            log.warning("Telegram notify_resolved failed: %s", exc)

    # Twitter
    if settings.getxapi_key and settings.twitter_auth_token:
        try:
            from backend.app.services.twitter_poster import post_tweet
            tweet = _format_resolved_tweet(home, away, home_score, away_score, bet_data, bankroll_after)
            post_tweet(tweet, settings.getxapi_key, settings.twitter_auth_token,
                       settings.twitter_ct0, settings.twitter_twid)
        except Exception as exc:
            log.warning("Twitter notify_resolved failed: %s", exc)
