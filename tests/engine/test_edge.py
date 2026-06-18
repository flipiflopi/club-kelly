import pytest

from engine.decision.edge import calculate_edge, evaluate_outcome, remove_vig


def test_remove_vig_basic():
    # 1X2: 2.10 / 3.40 / 3.20 → overround ≈ 109%
    odds = [2.10, 3.40, 3.20]
    implied = [1 / o for o in odds]
    fair = remove_vig(implied)
    assert abs(sum(fair) - 1.0) < 1e-9
    assert all(f > 0 for f in fair)


def test_remove_vig_with_no_margin():
    # Perfect market: implied probs already sum to 1
    implied = [0.5, 0.3, 0.2]
    fair = remove_vig(implied)
    assert fair == pytest.approx(implied)


def test_remove_vig_empty_raises():
    with pytest.raises(ValueError):
        remove_vig([])


def test_calculate_edge_positive():
    edge = calculate_edge(model_prob=0.50, fair_market_prob=0.45)
    assert edge == pytest.approx(0.05)


def test_calculate_edge_negative():
    edge = calculate_edge(model_prob=0.30, fair_market_prob=0.40)
    assert edge == pytest.approx(-0.10)


def test_evaluate_outcome_has_value():
    # Model says 55% chance of home win; market implies 45% after vig removal
    result = evaluate_outcome(
        model_prob=0.55,
        decimal_odds=2.10,
        all_market_odds=[2.10, 3.40, 3.20],
        outcome_index=0,
        min_edge=0.03,
    )
    assert result["has_value"] is True
    assert result["edge"] > 0.03


def test_evaluate_outcome_no_value():
    # Model prob roughly matches market — no edge
    result = evaluate_outcome(
        model_prob=0.44,
        decimal_odds=2.10,
        all_market_odds=[2.10, 3.40, 3.20],
        outcome_index=0,
        min_edge=0.03,
    )
    assert result["has_value"] is False


def test_evaluate_outcome_vig_is_positive():
    result = evaluate_outcome(
        model_prob=0.50,
        decimal_odds=2.10,
        all_market_odds=[2.10, 3.40, 3.20],
        outcome_index=0,
        min_edge=0.03,
    )
    assert result["vig_pct"] > 0
