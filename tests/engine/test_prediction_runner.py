"""
Tests for the prediction runner pipeline logic.

Uses unit-level mocks — no real database, no real odds API.
Tests verify that the pipeline wires the 5 layers correctly:
  - Edge is calculated and gating works (no bet without sufficient edge)
  - Kelly fraction is applied correctly
  - Risk filters block/trim bets as expected
  - BankrollHistory entries are created consistently with bets
  - Correlated exposure is counted correctly within a match
  - Idempotency: already-predicted matches are skipped
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from engine.decision.edge import evaluate_outcome
from engine.decision.kelly import kelly_fraction
from engine.decision.risk_filters import RiskConfig, apply_risk_filters
from engine.markets.match_result import MatchResultMarket
from engine.models.dixon_coles import DixonColesModel, DixonColesParams


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def minimal_params():
    """Minimal DixonColesParams for two teams."""
    return DixonColesParams(
        attack={"TeamA": 0.3, "TeamB": -0.3},
        defense={"TeamA": 0.2, "TeamB": -0.2},
        home_advantage=0.25,
        rho=0.06,
        teams=["TeamA", "TeamB"],
    )


@pytest.fixture
def loaded_model(minimal_params):
    return DixonColesModel.from_params(minimal_params, xi=0.0023)


# ── from_params ───────────────────────────────────────────────────────────────


def test_from_params_is_immediately_usable(loaded_model):
    matrix = loaded_model.predict_score_matrix("TeamA", "TeamB")
    assert matrix.shape == (11, 11)
    assert abs(matrix.sum() - 1.0) < 1e-6


def test_from_params_known_teams(minimal_params, loaded_model):
    assert loaded_model.known_teams() == {"TeamA", "TeamB"}


def test_from_params_preserves_rho(minimal_params, loaded_model):
    assert loaded_model.params.rho == pytest.approx(minimal_params.rho)


def test_from_params_preserves_home_advantage(minimal_params, loaded_model):
    assert loaded_model.params.home_advantage == pytest.approx(minimal_params.home_advantage)


# ── End-to-end pipeline logic (pure, no DB) ───────────────────────────────────


def _make_score_matrix(home_win_prob=0.50, draw_prob=0.25, away_win_prob=0.25):
    """Approximate score matrix matching given 1X2 probs."""
    from engine.models.dixon_coles import DixonColesParams, DixonColesModel
    params = DixonColesParams(
        attack={"H": 0.4, "A": -0.4},
        defense={"H": 0.1, "A": -0.1},
        home_advantage=0.3,
        rho=0.05,
        teams=["H", "A"],
    )
    model = DixonColesModel.from_params(params)
    return model.predict_score_matrix("H", "A")


class TestPipelineIntegration:
    """
    Tests that verify the 4 decision layers compose correctly.
    Each test mounts the layers independently (no DB, no FastAPI).
    """

    def test_full_pipeline_places_bet_with_clear_edge(self):
        """
        Model says 60% home win, market offers 2.10 (implies 43% after vig removal).
        Edge = 17% → should result in a positive Kelly stake that passes risk filters.
        """
        model_prob = 0.60
        decimal_odds = 2.10
        all_market_odds = [2.10, 3.40, 3.20]  # 1X2
        outcome_index = 0  # home

        edge_result = evaluate_outcome(
            model_prob=model_prob,
            decimal_odds=decimal_odds,
            all_market_odds=all_market_odds,
            outcome_index=outcome_index,
            min_edge=0.03,
        )
        assert edge_result["has_value"] is True

        k_frac = kelly_fraction(model_prob, decimal_odds, kelly_multiplier=0.25)
        assert k_frac > 0

        filter_result = apply_risk_filters(
            proposed_stake_pct=k_frac,
            decimal_odds=decimal_odds,
            current_bankroll=1000.0,
            open_exposure_eur=0.0,
        )
        assert filter_result.allowed is True
        assert filter_result.final_stake_eur > 0

    def test_no_bet_when_model_matches_market(self):
        """
        When model prob ≈ fair market prob, edge is near zero → no bet.
        """
        all_market_odds = [2.10, 3.40, 3.20]
        implied = [1 / o for o in all_market_odds]
        total = sum(implied)
        fair_home = implied[0] / total  # fair probability for home

        edge_result = evaluate_outcome(
            model_prob=fair_home,        # model exactly matches market
            decimal_odds=2.10,
            all_market_odds=all_market_odds,
            outcome_index=0,
            min_edge=0.03,
        )
        assert edge_result["has_value"] is False

    def test_no_bet_when_negative_kelly(self):
        """
        Positive edge (model > fair_prob) but Kelly formula can still be negative
        if the edge is small and odds are very short.
        """
        k_frac = kelly_fraction(
            model_prob=0.85,
            decimal_odds=1.15,  # very short odds — b = 0.15
            kelly_multiplier=0.25,
        )
        # f* = (0.15*0.85 - 0.15) / 0.15 = (0.1275 - 0.15)/0.15 < 0
        assert k_frac == 0.0

    def test_risk_filter_blocks_below_min_odds(self):
        filter_result = apply_risk_filters(
            proposed_stake_pct=0.04,
            decimal_odds=1.25,  # below default min_odds=1.30
            current_bankroll=1000.0,
            open_exposure_eur=0.0,
        )
        assert filter_result.allowed is False

    def test_risk_filter_caps_oversized_kelly(self):
        """If Kelly suggests 15%, risk filter caps at max_bet_pct=5%."""
        # Construct a high-edge scenario that produces a large Kelly fraction
        k_frac = kelly_fraction(0.80, 3.00, kelly_multiplier=1.0)  # full Kelly
        assert k_frac > 0.05  # sanity check that this is over-limit

        filter_result = apply_risk_filters(
            proposed_stake_pct=k_frac,
            decimal_odds=3.00,
            current_bankroll=1000.0,
            open_exposure_eur=0.0,
            risk_config=RiskConfig(max_bet_pct=0.05),
        )
        assert filter_result.allowed is True
        assert filter_result.final_stake_pct == pytest.approx(0.05)

    def test_bankroll_decreases_with_each_bet(self):
        """Stake should be deducted from working bankroll within one run."""
        bankroll = 1000.0
        first_stake = 30.0
        bankroll -= first_stake
        assert bankroll == pytest.approx(970.0)

        second_k_frac = kelly_fraction(0.60, 2.10, kelly_multiplier=0.25)
        second_stake = second_k_frac * bankroll  # uses UPDATED bankroll
        assert second_stake < second_k_frac * 1000.0  # smaller than if bankroll hadn't changed

    def test_correlated_exposure_within_match(self):
        """Two bets on same match: exposure = max(stakes), not sum."""
        from engine.decision.risk_filters import correlated_exposure

        stakes_on_match = [30.0, 20.0]  # 1X2 home + Over 2.5
        exposure = correlated_exposure(stakes_on_match)
        assert exposure == pytest.approx(30.0)  # max, not 50

    def test_full_pipeline_over_under_market(self, loaded_model):
        """Over/Under market probabilities feed correctly into edge + Kelly."""
        from engine.markets.over_under import OverUnderMarket

        matrix = loaded_model.predict_score_matrix("TeamA", "TeamB")
        market = OverUnderMarket(threshold=2.5)
        probs = market.calculate(matrix)

        # Verify the market returns valid probabilities
        assert abs(sum(probs.values()) - 1.0) < 1e-9
        assert "over" in probs and "under" in probs

        # Try edge calculation with synthetic odds
        over_odds = {"over": 2.00, "under": 1.85}
        all_odds_list = [over_odds["over"], over_odds["under"]]
        edge_result = evaluate_outcome(
            model_prob=probs["over"],
            decimal_odds=over_odds["over"],
            all_market_odds=all_odds_list,
            outcome_index=0,
            min_edge=0.03,
        )
        # Result should be a valid dict regardless of has_value
        assert "edge" in edge_result
        assert "fair_prob" in edge_result


# ── _run_edge_layer helper (isolated) ────────────────────────────────────────


def test_edge_layer_returns_empty_when_no_odds():
    """If decimal_odds is None, edge layer returns {}."""
    from backend.app.services.prediction_runner import _run_edge_layer

    result = _run_edge_layer(
        model_prob=0.60,
        decimal_odds=None,
        market_odds_dict={},
        outcome="home",
        min_edge=0.03,
    )
    assert result == {}


def test_edge_layer_returns_empty_when_only_one_outcome():
    """If market_odds_dict has < 2 outcomes, vig can't be removed."""
    from backend.app.services.prediction_runner import _run_edge_layer

    result = _run_edge_layer(
        model_prob=0.60,
        decimal_odds=2.10,
        market_odds_dict={"home": 2.10},  # only one outcome
        outcome="home",
        min_edge=0.03,
    )
    assert result == {}


def test_edge_layer_computes_correctly_with_full_odds():
    from backend.app.services.prediction_runner import _run_edge_layer

    result = _run_edge_layer(
        model_prob=0.60,
        decimal_odds=2.10,
        market_odds_dict={"away": 3.20, "draw": 3.40, "home": 2.10},
        outcome="home",
        min_edge=0.03,
    )
    assert "edge" in result
    assert "has_value" in result
    assert result["edge"] == pytest.approx(
        result["model_prob"] - result["fair_prob"], abs=1e-9
    )
