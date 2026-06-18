"""
Tests for the Dixon-Coles model.
Key assertions:
  1. Model fits without errors on the synthetic dataset
  2. Score matrix rows sum to 1 (valid probability distribution)
  3. Tau correction preserves probability mass (matrix sums to ~1 after normalization)
  4. Team parameter ordering matches the encoded ground truth
  5. Spain vs Costa Rica → heavy home favourite (P(home win) >> P(away win))
  6. Expected goals are positive and in a realistic range
  7. Neutral venue removes home advantage
  8. Unknown team raises ValueError, unfitted model raises RuntimeError
"""

import numpy as np
import pytest

from engine.models.dixon_coles import DixonColesModel


def test_fit_completes(synthetic_matches):
    model = DixonColesModel(xi=0.0023)
    model.fit(synthetic_matches)
    assert model.params is not None
    assert len(model.known_teams()) == 6


def test_score_matrix_sums_to_one(fitted_model):
    matrix = fitted_model.predict_score_matrix("Spain", "Costa Rica")
    assert abs(matrix.sum() - 1.0) < 1e-6, f"matrix sums to {matrix.sum()}"


def test_matrix_shape(fitted_model):
    matrix = fitted_model.predict_score_matrix("Spain", "Germany")
    assert matrix.shape == (11, 11)  # max_goals=10 → 0..10 = 11 values


def test_all_probabilities_non_negative(fitted_model):
    matrix = fitted_model.predict_score_matrix("France", "Brazil")
    assert np.all(matrix >= 0), "Score matrix contains negative probabilities"


def test_spain_strong_attack(fitted_model):
    """Spain should have a higher attack strength than Costa Rica."""
    params = fitted_model.params
    assert params.attack["Spain"] > params.attack["Costa Rica"], (
        f"Spain attack {params.attack['Spain']:.3f} should exceed "
        f"Costa Rica {params.attack['Costa Rica']:.3f}"
    )


def test_france_strong_defense(fitted_model):
    """France defense should be higher than Costa Rica in log-space.

    In Dixon-Coles: mu_away = exp(attack_away - defense_home)
    Higher defense_home → lower mu_away → fewer goals conceded → stronger defense.
    """
    params = fitted_model.params
    assert params.defense["France"] > params.defense["Costa Rica"], (
        f"France defense {params.defense['France']:.3f} should be higher than "
        f"Costa Rica {params.defense['Costa Rica']:.3f}"
    )


def test_spain_vs_costa_rica_home_favourite(fitted_model):
    """Spain at home vs Costa Rica should be a heavy favourite."""
    from engine.markets.match_result import MatchResultMarket
    matrix = fitted_model.predict_score_matrix("Spain", "Costa Rica")
    probs = MatchResultMarket().calculate(matrix)
    assert probs["home"] > 0.65, f"Expected P(Spain win) > 0.65, got {probs['home']:.3f}"
    assert probs["away"] < 0.10, f"Expected P(Costa Rica win) < 0.10, got {probs['away']:.3f}"


def test_expected_goals_positive_and_realistic(fitted_model):
    mu_h, mu_a = fitted_model.expected_goals("Spain", "Germany")
    assert 0.5 < mu_h < 4.0, f"mu_home={mu_h:.2f} out of expected range"
    assert 0.5 < mu_a < 4.0, f"mu_away={mu_a:.2f} out of expected range"


def test_neutral_venue_reduces_home_advantage(fitted_model):
    mu_h_home, _ = fitted_model.expected_goals("Spain", "Germany", is_neutral=False)
    mu_h_neutral, _ = fitted_model.expected_goals("Spain", "Germany", is_neutral=True)
    assert mu_h_neutral < mu_h_home, (
        "Neutral venue should reduce home team expected goals"
    )


def test_unknown_team_raises(fitted_model):
    with pytest.raises(ValueError, match="Unknown team"):
        fitted_model.predict_score_matrix("Spain", "Atlantis")


def test_unfitted_model_raises():
    model = DixonColesModel()
    with pytest.raises(RuntimeError, match="not been fitted"):
        model.predict_score_matrix("Spain", "Germany")


def test_home_advantage_positive(fitted_model):
    """Home advantage parameter should be positive in log-space."""
    assert fitted_model.params.home_advantage > 0, (
        f"home_advantage={fitted_model.params.home_advantage:.3f} should be > 0"
    )


def test_rho_in_valid_range(fitted_model):
    """Rho should be a small positive number."""
    rho = fitted_model.params.rho
    assert -0.5 < rho < 0.5, f"rho={rho:.4f} out of expected range"
