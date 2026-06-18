import math

import pytest

from backend.app.services.metrics import brier_score, clv, roi, win_rate_by_market


def test_brier_score_perfect():
    # Model always says 1.0 for outcomes that occur → Brier = 0
    preds = [(1.0, 1), (1.0, 1), (0.0, 0)]
    assert brier_score(preds) == pytest.approx(0.0)


def test_brier_score_worst():
    # Always completely wrong → Brier = 1.0
    preds = [(0.0, 1), (1.0, 0)]
    assert brier_score(preds) == pytest.approx(1.0)


def test_brier_score_uniform():
    # Uniform 50% on binary outcome → Brier = 0.25
    preds = [(0.5, 1), (0.5, 0)]
    assert brier_score(preds) == pytest.approx(0.25)


def test_brier_score_empty_returns_nan():
    result = brier_score([])
    assert math.isnan(result)


def test_roi_positive():
    assert roi(50.0, 500.0) == pytest.approx(10.0)


def test_roi_negative():
    assert roi(-100.0, 1000.0) == pytest.approx(-10.0)


def test_roi_zero_staked():
    assert roi(0.0, 0.0) == 0.0


def test_clv_positive():
    # We got odds 2.10 and line closed at 1.90 → we got more value
    result = clv(odds_at_bet=2.10, closing_odds=1.90)
    assert result > 0


def test_clv_negative():
    # We got worse odds than market closed at
    result = clv(odds_at_bet=1.90, closing_odds=2.10)
    assert result < 0


def test_win_rate_by_market():
    bets = [
        {"market_slug": "match_result", "status": "won", "stake_amount": 50.0, "profit_loss": 55.0},
        {"market_slug": "match_result", "status": "lost", "stake_amount": 50.0, "profit_loss": -50.0},
        {"market_slug": "over_under_2_5", "status": "won", "stake_amount": 30.0, "profit_loss": 27.0},
    ]
    result = win_rate_by_market(bets)

    assert "match_result" in result
    assert result["match_result"]["total_bets"] == 2
    assert result["match_result"]["won"] == 1
    assert result["match_result"]["win_rate"] == pytest.approx(0.5)

    assert "over_under_2_5" in result
    assert result["over_under_2_5"]["win_rate"] == pytest.approx(1.0)
