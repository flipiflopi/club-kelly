import pytest

from engine.decision.risk_filters import (
    RejectionReason,
    RiskConfig,
    RiskFilterResult,
    apply_risk_filters,
    correlated_exposure,
)

DEFAULT_BANKROLL = 1000.0
DEFAULT_ODDS = 2.10


def test_allowed_bet_passes_all_filters():
    result = apply_risk_filters(
        proposed_stake_pct=0.03,       # 3% — within 5% limit
        decimal_odds=2.10,
        current_bankroll=DEFAULT_BANKROLL,
        open_exposure_eur=0.0,         # no existing exposure
    )
    assert result.allowed is True
    assert result.final_stake_eur == pytest.approx(30.0)
    assert result.rejection_reason is None


def test_odds_too_low_rejected():
    result = apply_risk_filters(0.03, decimal_odds=1.20, current_bankroll=1000.0, open_exposure_eur=0.0)
    assert result.allowed is False
    assert result.rejection_reason == RejectionReason.ODDS_TOO_LOW


def test_odds_too_high_rejected():
    result = apply_risk_filters(0.03, decimal_odds=7.00, current_bankroll=1000.0, open_exposure_eur=0.0)
    assert result.allowed is False
    assert result.rejection_reason == RejectionReason.ODDS_TOO_HIGH


def test_zero_stake_rejected():
    result = apply_risk_filters(0.0, decimal_odds=2.10, current_bankroll=1000.0, open_exposure_eur=0.0)
    assert result.allowed is False
    assert result.rejection_reason == RejectionReason.ZERO_STAKE


def test_stake_capped_at_per_match_limit():
    # Propose 10% — should be capped at 5% (max_bet_pct default)
    result = apply_risk_filters(0.10, decimal_odds=2.10, current_bankroll=1000.0, open_exposure_eur=0.0)
    assert result.allowed is True
    assert result.final_stake_pct == pytest.approx(0.05)
    assert result.final_stake_eur == pytest.approx(50.0)


def test_daily_exposure_limit_blocks():
    # Already 150€ open on a 1000€ bankroll → daily limit (15%) = 150€ → no more
    result = apply_risk_filters(
        proposed_stake_pct=0.03,
        decimal_odds=2.10,
        current_bankroll=1000.0,
        open_exposure_eur=150.0,       # exactly at the limit
    )
    assert result.allowed is False
    assert result.rejection_reason == RejectionReason.DAILY_EXPOSURE_LIMIT


def test_daily_exposure_trims_stake():
    # 120€ open, limit 150€ → only 30€ remaining capacity
    # propose 4% = 40€, which exceeds the 30€ remaining → trimmed to 30€
    result = apply_risk_filters(
        proposed_stake_pct=0.04,       # 40€ requested
        decimal_odds=2.10,
        current_bankroll=1000.0,
        open_exposure_eur=120.0,
    )
    assert result.allowed is True
    assert result.final_stake_eur == pytest.approx(30.0)
    assert "trimmed" in (result.note or "")


def test_custom_risk_config():
    cfg = RiskConfig(max_bet_pct=0.02, min_odds=1.50, max_odds=4.00)
    # Odds of 4.50 should be rejected with custom config
    result = apply_risk_filters(0.01, decimal_odds=4.50, current_bankroll=1000.0, open_exposure_eur=0.0, risk_config=cfg)
    assert result.allowed is False
    assert result.rejection_reason == RejectionReason.ODDS_TOO_HIGH


def test_correlated_exposure_takes_max():
    stakes = [30.0, 50.0, 20.0]
    assert correlated_exposure(stakes) == 50.0


def test_correlated_exposure_empty():
    assert correlated_exposure([]) == 0.0
