"""
Layer 2 — Edge detection.

All functions are pure (no IO, no side effects).
Inputs and outputs are plain Python types so they are trivially testable.
"""


def remove_vig(implied_probs: list[float]) -> list[float]:
    """
    Normalize implied probabilities (1/odds) so they sum to 1.0.
    This removes the bookmaker's overround (vig/margin).

    Parameters
    ----------
    implied_probs : list of floats
        Each element is 1 / decimal_odds for one outcome.
        Example for 1X2: [1/2.10, 1/3.40, 1/3.20]

    Returns
    -------
    list of fair probabilities summing to 1.0, same order as input.
    """
    if not implied_probs:
        raise ValueError("implied_probs cannot be empty")
    total = sum(implied_probs)
    if total <= 0:
        raise ValueError("implied_probs must contain positive values")
    return [p / total for p in implied_probs]


def calculate_edge(model_prob: float, fair_market_prob: float) -> float:
    """
    Edge = model probability - fair market probability (after vig removal).
    Positive edge means the model thinks the outcome is more likely than the market.
    """
    return model_prob - fair_market_prob


def evaluate_outcome(
    model_prob: float,
    decimal_odds: float,
    all_market_odds: list[float],
    outcome_index: int,
    min_edge: float = 0.03,
) -> dict:
    """
    Full edge evaluation for one outcome within a market.

    Parameters
    ----------
    model_prob : float
        Model's probability for this outcome.
    decimal_odds : float
        Bookmaker's decimal odds for this outcome.
    all_market_odds : list[float]
        All decimal odds for the same market (used to compute vig-free probs).
        The outcome being evaluated must be at position `outcome_index`.
    outcome_index : int
        Index of this outcome in all_market_odds.
    min_edge : float
        Minimum edge threshold to flag as value bet.

    Returns
    -------
    dict with keys: implied_prob, fair_prob, model_prob, edge, vig_pct, has_value
    """
    implied = [1.0 / o for o in all_market_odds]
    vig_pct = sum(implied) - 1.0
    fair = remove_vig(implied)
    fair_prob = fair[outcome_index]
    edge = calculate_edge(model_prob, fair_prob)

    return {
        "implied_prob": implied[outcome_index],
        "fair_prob": fair_prob,
        "model_prob": model_prob,
        "edge": edge,
        "vig_pct": vig_pct,
        "has_value": edge >= min_edge,
    }
