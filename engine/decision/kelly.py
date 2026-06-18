"""
Layer 3 — Fractional Kelly criterion.

All functions are pure. The Kelly fraction is applied BEFORE risk filters;
risk filters (Layer 4) may further cap the stake.
"""


def kelly_fraction(
    model_prob: float,
    decimal_odds: float,
    kelly_multiplier: float = 0.25,
) -> float:
    """
    Compute the fractional Kelly stake as a proportion of bankroll.

    Full Kelly:  f* = (b*p - q) / b   where b = decimal_odds - 1, q = 1 - p
    Fractional:  f  = f* * kelly_multiplier

    Returns 0.0 if full Kelly is non-positive (no edge or negative edge).

    Parameters
    ----------
    model_prob : float
        Model probability for the outcome (0 < p < 1).
    decimal_odds : float
        Bookmaker's decimal odds (> 1).
    kelly_multiplier : float
        Fraction of full Kelly to use (default 0.25 = quarter Kelly).

    Returns
    -------
    Stake as a fraction of current bankroll (0.0 to 1.0).
    """
    if not (0 < model_prob < 1):
        raise ValueError(f"model_prob must be in (0, 1), got {model_prob}")
    if decimal_odds <= 1:
        raise ValueError(f"decimal_odds must be > 1, got {decimal_odds}")
    if not (0 < kelly_multiplier <= 1):
        raise ValueError(f"kelly_multiplier must be in (0, 1], got {kelly_multiplier}")

    b = decimal_odds - 1.0
    p = model_prob
    q = 1.0 - p

    f_full = (b * p - q) / b

    if f_full <= 0:
        return 0.0

    return f_full * kelly_multiplier


def kelly_stake(
    model_prob: float,
    decimal_odds: float,
    current_bankroll: float,
    kelly_multiplier: float = 0.25,
) -> float:
    """
    Compute the fractional Kelly stake in monetary units.

    Uses `current_bankroll` (not initial bankroll) so the sizing is always
    relative to today's capital.
    """
    if current_bankroll <= 0:
        raise ValueError(f"current_bankroll must be positive, got {current_bankroll}")
    fraction = kelly_fraction(model_prob, decimal_odds, kelly_multiplier)
    return fraction * current_bankroll
