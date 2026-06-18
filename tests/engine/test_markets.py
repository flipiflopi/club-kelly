"""Tests for market modules — input is a score matrix, output is probabilities."""

import numpy as np
import pytest

from engine.markets.btts import BTTSMarket
from engine.markets.match_result import MatchResultMarket
from engine.markets.over_under import OverUnderMarket


def _uniform_matrix(size: int = 5) -> np.ndarray:
    """Uniform distribution over size×size outcomes — all equally likely."""
    m = np.ones((size, size))
    return m / m.sum()


def _certain_scoreline(home: int, away: int, size: int = 11) -> np.ndarray:
    """100% probability on a specific scoreline."""
    m = np.zeros((size, size))
    m[home, away] = 1.0
    return m


# ── MatchResultMarket ─────────────────────────────────────────────────────────


def test_match_result_sums_to_one(fitted_model):
    matrix = fitted_model.predict_score_matrix("Spain", "Germany")
    probs = MatchResultMarket().calculate(matrix)
    assert abs(sum(probs.values()) - 1.0) < 1e-9


def test_match_result_certain_home_win():
    matrix = _certain_scoreline(2, 0)
    probs = MatchResultMarket().calculate(matrix)
    assert probs["home"] == pytest.approx(1.0)
    assert probs["draw"] == pytest.approx(0.0)
    assert probs["away"] == pytest.approx(0.0)


def test_match_result_certain_draw():
    matrix = _certain_scoreline(1, 1)
    probs = MatchResultMarket().calculate(matrix)
    assert probs["draw"] == pytest.approx(1.0)


def test_match_result_certain_away_win():
    matrix = _certain_scoreline(0, 3)
    probs = MatchResultMarket().calculate(matrix)
    assert probs["away"] == pytest.approx(1.0)


# ── OverUnderMarket ───────────────────────────────────────────────────────────


def test_over_under_sums_to_one(fitted_model):
    matrix = fitted_model.predict_score_matrix("Spain", "Germany")
    probs = OverUnderMarket(threshold=2.5).calculate(matrix)
    assert abs(sum(probs.values()) - 1.0) < 1e-9


def test_over_2_5_certain_high_score():
    matrix = _certain_scoreline(3, 2)  # total = 5 > 2.5
    probs = OverUnderMarket(threshold=2.5).calculate(matrix)
    assert probs["over"] == pytest.approx(1.0)


def test_under_2_5_certain_low_score():
    matrix = _certain_scoreline(1, 1)  # total = 2 ≤ 2.5
    probs = OverUnderMarket(threshold=2.5).calculate(matrix)
    assert probs["under"] == pytest.approx(1.0)


def test_over_under_threshold_validation():
    with pytest.raises(ValueError, match="half-integer"):
        OverUnderMarket(threshold=2.0)


def test_over_under_slug():
    market = OverUnderMarket(threshold=2.5)
    assert market.slug == "over_under_2_5"
    market35 = OverUnderMarket(threshold=3.5)
    assert market35.slug == "over_under_3_5"


# ── BTTSMarket ────────────────────────────────────────────────────────────────


def test_btts_sums_to_one(fitted_model):
    matrix = fitted_model.predict_score_matrix("Germany", "Brazil")
    probs = BTTSMarket().calculate(matrix)
    assert abs(sum(probs.values()) - 1.0) < 1e-9


def test_btts_yes_both_scored():
    matrix = _certain_scoreline(1, 1)
    probs = BTTSMarket().calculate(matrix)
    assert probs["yes"] == pytest.approx(1.0)


def test_btts_no_clean_sheet():
    matrix = _certain_scoreline(2, 0)
    probs = BTTSMarket().calculate(matrix)
    assert probs["no"] == pytest.approx(1.0)


def test_btts_no_zero_zero():
    matrix = _certain_scoreline(0, 0)
    probs = BTTSMarket().calculate(matrix)
    assert probs["no"] == pytest.approx(1.0)


# ── MarketRegistry ────────────────────────────────────────────────────────────


def test_registry_has_all_builtin_markets():
    import engine.markets  # trigger auto-registration
    from engine.markets.registry import market_registry

    expected = {"match_result", "over_under_1_5", "over_under_2_5", "over_under_3_5", "btts"}
    for slug in expected:
        assert slug in market_registry, f"Missing market: {slug}"


def test_registry_raises_on_unknown():
    from engine.markets.registry import market_registry
    with pytest.raises(KeyError, match="Unknown market"):
        market_registry.get("nonexistent_market")
