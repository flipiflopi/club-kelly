import pytest

from engine.decision.kelly import kelly_fraction, kelly_stake


def test_positive_edge_gives_positive_fraction():
    # Model prob 55%, odds 2.10 — clear positive Kelly value
    f = kelly_fraction(model_prob=0.55, decimal_odds=2.10, kelly_multiplier=0.25)
    assert f > 0


def test_negative_edge_gives_zero():
    # Model prob 40%, odds 2.10 → b=1.10, f* = (1.1*0.4 - 0.6)/1.1 < 0
    f = kelly_fraction(model_prob=0.40, decimal_odds=2.10, kelly_multiplier=0.25)
    assert f == 0.0


def test_full_kelly_is_4x_quarter_kelly():
    f_quarter = kelly_fraction(0.60, 2.00, kelly_multiplier=0.25)
    f_full = kelly_fraction(0.60, 2.00, kelly_multiplier=1.00)
    assert f_full == pytest.approx(f_quarter * 4, rel=1e-9)


def test_kelly_fraction_within_bounds():
    # Quarter Kelly should never exceed 25% of full Kelly → always < 0.25 in practice
    f = kelly_fraction(0.60, 2.00, kelly_multiplier=0.25)
    assert 0 < f < 0.25


def test_kelly_stake_scales_with_bankroll():
    stake_1000 = kelly_stake(0.55, 2.10, current_bankroll=1000.0)
    stake_2000 = kelly_stake(0.55, 2.10, current_bankroll=2000.0)
    assert stake_2000 == pytest.approx(stake_1000 * 2)


def test_kelly_stake_zero_when_no_edge():
    stake = kelly_stake(0.40, 2.10, current_bankroll=1000.0)
    assert stake == 0.0


def test_invalid_probability_raises():
    with pytest.raises(ValueError):
        kelly_fraction(0.0, 2.10)  # prob must be > 0
    with pytest.raises(ValueError):
        kelly_fraction(1.0, 2.10)  # prob must be < 1


def test_invalid_odds_raises():
    with pytest.raises(ValueError):
        kelly_fraction(0.5, 1.0)  # odds must be > 1


def test_invalid_multiplier_raises():
    with pytest.raises(ValueError):
        kelly_fraction(0.5, 2.0, kelly_multiplier=0.0)


def test_zero_bankroll_raises():
    with pytest.raises(ValueError):
        kelly_stake(0.55, 2.10, current_bankroll=0.0)
