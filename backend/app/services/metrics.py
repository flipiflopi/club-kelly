"""
Validation metrics for the prediction model.
All functions are pure — they take lists of numbers and return numbers.
"""

import math


def brier_score(predictions: list[tuple[float, int]]) -> float:
    """
    Mean Brier score over a set of binary predictions.

    Parameters
    ----------
    predictions : list of (probability, outcome)
        probability: model's estimated probability for the outcome (0-1)
        outcome: 1 if the outcome occurred, 0 if not

    Returns
    -------
    Brier score in [0, 2]. Lower is better. 0 = perfect calibration.
    """
    if not predictions:
        return float("nan")
    return sum((p - o) ** 2 for p, o in predictions) / len(predictions)


def roi(total_profit_loss: float, total_staked: float) -> float:
    """Return on investment as a percentage."""
    if total_staked == 0:
        return 0.0
    return (total_profit_loss / total_staked) * 100.0


def clv(odds_at_bet: float, closing_odds: float) -> float:
    """
    Closing Line Value: how much better (or worse) our odds were vs closing line.
    Positive CLV means we got value vs where the market settled.
    Expressed as a percentage.
    """
    if closing_odds <= 0 or odds_at_bet <= 0:
        return 0.0
    implied_at_bet = 1.0 / odds_at_bet
    implied_close = 1.0 / closing_odds
    return (implied_close - implied_at_bet) / implied_close * 100.0


def win_rate_by_market(
    bets: list[dict],
) -> dict[str, dict]:
    """
    Group bets by market slug and compute win rate and ROI per group.

    Each dict in `bets` must have: market_slug (str), status (str: 'won'|'lost'|'void'),
    stake_amount (float), profit_loss (float | None).
    """
    groups: dict[str, list[dict]] = {}
    for bet in bets:
        slug = bet["market_slug"]
        groups.setdefault(slug, []).append(bet)

    result = {}
    for slug, group in groups.items():
        resolved = [b for b in group if b["status"] in ("won", "lost")]
        won = [b for b in resolved if b["status"] == "won"]
        total_staked = sum(b["stake_amount"] for b in resolved)
        total_pl = sum(b.get("profit_loss") or 0.0 for b in resolved)

        result[slug] = {
            "total_bets": len(resolved),
            "won": len(won),
            "win_rate": len(won) / len(resolved) if resolved else None,
            "roi_pct": roi(total_pl, total_staked),
        }

    return result
