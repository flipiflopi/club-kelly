"""
Pre-match notification command.

Sends a tweet + Telegram message for matches kicking off in approximately
24 hours or 4 hours. Designed to run every 30 minutes via a scheduled task.

Each window is ±15 minutes around the target (24h / 4h), so with a 30-minute
cron interval every match gets exactly one notification per window.

Usage:
  uv run python -m backend.app.commands.notify_upcoming
  uv run python -m backend.app.commands.notify_upcoming --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

WINDOW_MINUTES = 15  # ±15 min around target → 30-min safe zone per cron cycle
TARGETS_HOURS = [24, 4]


def _window(hours: int, now: datetime) -> tuple[datetime, datetime]:
    delta = timedelta(hours=hours)
    margin = timedelta(minutes=WINDOW_MINUTES)
    return now + delta - margin, now + delta + margin


def _bet_line(bet) -> str:
    outcome = bet.outcome
    if outcome == "home" and bet.match:
        outcome = bet.match.home_team.name
    elif outcome == "away" and bet.match:
        outcome = bet.match.away_team.name
    elif outcome == "draw":
        outcome = "Draw"
    stake = bet.stake_amount
    potential = stake * (bet.decimal_odds - 1)
    return (
        f"Kelly backs {outcome} @{bet.decimal_odds:.2f}\n"
        f"Stake: {stake:.0f}€ · Potential: +{potential:.0f}€"
    )


def _format_tweet(match, bets: list, hours: int) -> str:
    home = match.home_team.name if match.home_team else "?"
    away = match.away_team.name if match.away_team else "?"
    round_label = f"{match.round} · " if match.round else ""

    header = f"⏰ {hours}h to go\n\n{home} 🆚 {away}\n{round_label}World Cup 2026\n\n"

    if bets:
        body = _bet_line(bets[0])
    else:
        body = "Kelly sees no clear edge here. No bet placed."

    footer = "\n\nhttps://clubkelly.online/\nt.me/Club_Kelly\n#ClubKelly #WorldCup2026"

    # Twitter limit is 280 chars — truncate team names if needed
    tweet = header + body + footer
    if len(tweet) > 280:
        tweet = tweet[:277] + "..."
    return tweet


def _format_telegram(match, bets: list, hours: int) -> str:
    home = match.home_team.name if match.home_team else "?"
    away = match.away_team.name if match.away_team else "?"
    kick_off = match.match_date.strftime("%H:%M UTC") if match.match_date else ""

    lines = [
        f"⏰ <b>{hours}h to kick-off</b>",
        f"",
        f"<b>{home} vs {away}</b>",
    ]
    if match.round:
        lines.append(f"{match.round} · {kick_off}")
    else:
        lines.append(kick_off)
    lines.append("")

    if bets:
        b = bets[0]
        outcome = b.outcome
        if outcome == "home" and match.home_team:
            outcome = match.home_team.name
        elif outcome == "away" and match.away_team:
            outcome = match.away_team.name
        elif outcome == "draw":
            outcome = "Draw"
        potential = b.stake_amount * (b.decimal_odds - 1)
        lines += [
            f"🎯 <b>Kelly has bet</b>",
            f"Pick: <b>{outcome}</b> @{b.decimal_odds:.2f}",
            f"Stake: <b>{b.stake_amount:.0f}€</b> · Potential: <b>+{potential:.0f}€</b>",
        ]
    else:
        lines += [
            "⚖️ <b>No bet placed</b>",
            "Kelly sees no clear edge on this match.",
        ]

    lines += ["", "🌐 https://clubkelly.online/", "#ClubKelly #WorldCup2026"]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Send pre-match notifications")
    parser.add_argument("--dry-run", action="store_true", help="Print messages without sending")
    parser.add_argument("--match-id", type=int, default=None, help="Force notification for a specific match ID (ignores time window)")
    parser.add_argument("--hours", type=int, default=24, help="Hours label to use in the message when --match-id is set (default: 24)")
    args = parser.parse_args()

    from backend.app.config import get_settings
    from backend.app.database import get_session_factory
    from backend.app.models.match import Match, MatchStatus
    from backend.app.models.simulated_bet import BetStatus, SimulatedBet
    from backend.app.services.telegram_notifier import _send as tg_send
    from backend.app.services.twitter_poster import post_tweet

    settings = get_settings()
    now = datetime.now(timezone.utc)
    SessionLocal = get_session_factory()
    sent = 0

    # ── Forced single-match mode ──────────────────────────────────────────────
    if args.match_id:
        with SessionLocal() as db:
            match = db.query(Match).filter(Match.id == args.match_id).first()
            if not match:
                logger.error("Match ID %d not found", args.match_id)
                return 1
            bets = (
                db.query(SimulatedBet)
                .filter(SimulatedBet.match_id == match.id, SimulatedBet.status == BetStatus.OPEN)
                .all()
            )
            for b in bets:
                b.match = match
            hours = args.hours
            tweet = _format_tweet(match, bets, hours)
            telegram_msg = _format_telegram(match, bets, hours)
            logger.info("Forced notification: %s vs %s (bets=%d)",
                        match.home_team.name if match.home_team else "?",
                        match.away_team.name if match.away_team else "?",
                        len(bets))
            if args.dry_run:
                print(f"\n{'='*60}")
                print(f"TWEET ({len(tweet)} chars):\n{tweet}")
                print(f"\nTELEGRAM:\n{telegram_msg}")
                return 0
            if settings.telegram_bot_token and settings.telegram_chat_id:
                tg_send(settings.telegram_bot_token, settings.telegram_chat_id, telegram_msg)
            post_tweet(tweet, settings.getxapi_key, settings.twitter_auth_token,
                       settings.twitter_ct0, settings.twitter_twid)
        return 0

    with SessionLocal() as db:
        for hours in TARGETS_HOURS:
            lo, hi = _window(hours, now)

            matches = (
                db.query(Match)
                .filter(
                    Match.status == MatchStatus.SCHEDULED,
                    Match.match_date >= lo,
                    Match.match_date <= hi,
                )
                .all()
            )

            if not matches:
                logger.info("%dh window: no matches found (%s → %s)", hours, lo.strftime("%H:%M"), hi.strftime("%H:%M"))
                continue

            for match in matches:
                bets = (
                    db.query(SimulatedBet)
                    .filter(
                        SimulatedBet.match_id == match.id,
                        SimulatedBet.status == BetStatus.OPEN,
                    )
                    .all()
                )
                # Attach match to each bet for name resolution
                for b in bets:
                    b.match = match

                tweet = _format_tweet(match, bets, hours)
                telegram_msg = _format_telegram(match, bets, hours)

                logger.info(
                    "%dh notification: %s vs %s (bets=%d)",
                    hours,
                    match.home_team.name if match.home_team else "?",
                    match.away_team.name if match.away_team else "?",
                    len(bets),
                )

                if args.dry_run:
                    print(f"\n{'='*60}")
                    print(f"TWEET ({len(tweet)} chars):\n{tweet}")
                    print(f"\nTELEGRAM:\n{telegram_msg}")
                    sent += 1
                    continue

                # Telegram
                if settings.telegram_bot_token and settings.telegram_chat_id:
                    tg_send(settings.telegram_bot_token, settings.telegram_chat_id, telegram_msg)
                else:
                    logger.warning("Telegram not configured — skipping")

                # Twitter
                ok = post_tweet(
                    tweet,
                    settings.getxapi_key,
                    settings.twitter_auth_token,
                    settings.twitter_ct0,
                    settings.twitter_twid,
                )
                if not ok:
                    logger.warning("Tweet not sent (check Twitter credentials in env vars)")

                sent += 1

    logger.info("Done. Notifications sent: %d", sent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
