"""
Layer 4 — Risk filters.

Applied after Kelly sizing. Can block or reduce a bet even when edge is positive.
All functions are pure — no IO, no DB access.
"""

from dataclasses import dataclass
from enum import Enum


class RejectionReason(str, Enum):
    ODDS_TOO_LOW = "odds_too_low"
    ODDS_TOO_HIGH = "odds_too_high"
    DAILY_EXPOSURE_LIMIT = "daily_exposure_limit"
    ZERO_STAKE = "zero_stake"
    MODEL_MARKET_DEVIATION = "model_market_deviation"


@dataclass(frozen=True)
class RiskConfig:
    max_bet_pct: float = 0.03       # max 3% of bankroll per bet
    max_daily_exposure_pct: float = 0.15  # max 15% of bankroll open at once
    min_odds: float = 1.30
    max_odds: float = 5.00
    max_model_overestimate_ratio: float = 2.0  # block if model > 2x market consensus


@dataclass
class RiskFilterResult:
    allowed: bool
    final_stake_pct: float
    final_stake_eur: float
    rejection_reason: RejectionReason | None = None
    note: str | None = None


def apply_risk_filters(
    proposed_stake_pct: float,
    decimal_odds: float,
    current_bankroll: float,
    open_exposure_eur: float,
    risk_config: RiskConfig | None = None,
) -> RiskFilterResult:
    """
    Apply all risk filters to a proposed bet.

    Parameters
    ----------
    proposed_stake_pct : float
        Kelly-sized stake as a fraction of bankroll (from Layer 3).
    decimal_odds : float
        Bookmaker decimal odds.
    current_bankroll : float
        Current bankroll in euros.
    open_exposure_eur : float
        Sum of all unresolved bets placed today, in euros.
    risk_config : RiskConfig
        Risk parameters (uses defaults if None).

    Returns
    -------
    RiskFilterResult with final stake after applying all filters.
    """
    cfg = risk_config or RiskConfig()

    if proposed_stake_pct <= 0:
        return RiskFilterResult(
            allowed=False,
            final_stake_pct=0.0,
            final_stake_eur=0.0,
            rejection_reason=RejectionReason.ZERO_STAKE,
        )

    if decimal_odds < cfg.min_odds:
        return RiskFilterResult(
            allowed=False,
            final_stake_pct=0.0,
            final_stake_eur=0.0,
            rejection_reason=RejectionReason.ODDS_TOO_LOW,
            note=f"odds {decimal_odds:.2f} < min {cfg.min_odds:.2f}",
        )

    if decimal_odds > cfg.max_odds:
        return RiskFilterResult(
            allowed=False,
            final_stake_pct=0.0,
            final_stake_eur=0.0,
            rejection_reason=RejectionReason.ODDS_TOO_HIGH,
            note=f"odds {decimal_odds:.2f} > max {cfg.max_odds:.2f}",
        )

    # Cap at per-match limit
    capped_pct = min(proposed_stake_pct, cfg.max_bet_pct)
    capped_eur = capped_pct * current_bankroll

    # Check daily exposure limit
    max_daily_eur = cfg.max_daily_exposure_pct * current_bankroll
    remaining_capacity_eur = max_daily_eur - open_exposure_eur

    if remaining_capacity_eur <= 0:
        return RiskFilterResult(
            allowed=False,
            final_stake_pct=0.0,
            final_stake_eur=0.0,
            rejection_reason=RejectionReason.DAILY_EXPOSURE_LIMIT,
            note=f"daily exposure {open_exposure_eur:.2f}€ >= limit {max_daily_eur:.2f}€",
        )

    if capped_eur > remaining_capacity_eur:
        # Trim to remaining capacity
        final_eur = remaining_capacity_eur
        final_pct = final_eur / current_bankroll
        return RiskFilterResult(
            allowed=True,
            final_stake_pct=final_pct,
            final_stake_eur=final_eur,
            note=f"stake trimmed from {capped_eur:.2f}€ to {final_eur:.2f}€ (daily cap)",
        )

    return RiskFilterResult(
        allowed=True,
        final_stake_pct=capped_pct,
        final_stake_eur=capped_eur,
    )


def model_deviation_too_high(
    model_prob: float,
    fair_market_prob: float,
    max_ratio: float,
) -> bool:
    """
    True when the model is more than max_ratio times more confident than the market.

    A ratio > 2x almost always indicates a model error rather than a genuine
    inefficiency, especially in liquid markets like the World Cup. The market
    aggregates information from thousands of bettors; a simple moment-matching
    model is unlikely to be that much smarter.

    Example that would be blocked (ratio 2.3x):
      model_prob=0.39, fair_market_prob=0.17, max_ratio=2.0 → True
    Example that would be allowed (ratio 1.2x):
      model_prob=0.47, fair_market_prob=0.40, max_ratio=2.0 → False
    """
    if fair_market_prob <= 0 or max_ratio <= 0:
        return False
    return (model_prob / fair_market_prob) > max_ratio


def correlated_exposure(stakes_eur: list[float]) -> float:
    """
    For bets on the same match, treat them as a single unit of risk.
    Returns the maximum stake (worst-case loss) rather than the sum.

    Use this when checking daily exposure for correlated markets on one match
    (e.g. both 1X2 and Over/Under on Germany vs France).
    """
    return max(stakes_eur) if stakes_eur else 0.0
