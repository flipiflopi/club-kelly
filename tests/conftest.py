"""
Shared pytest fixtures.
The match dataset here is a simplified but realistic set of international
results used to verify that Dixon-Coles converges to sensible parameters.

Team strength ground truth (encoded in the synthetic data):
  - Spain: strong attack (~1.8 goals/game), solid defense
  - Germany: strong attack, average defense
  - France: average attack, strong defense
  - Brazil: above average both sides
  - Senegal: below average attack, below average defense
  - Costa Rica: weak attack, weak defense

After fitting on this data, the tests check that the relative ordering
of attack/defense parameters matches these priors.
"""

import pytest

# ~60 synthetic international matches with realistic scorelines
# Format: {home_team, away_team, home_goals, away_goals, days_ago}
SYNTHETIC_MATCHES = [
    # Spain vs others — strong attacker
    {"home_team": "Spain", "away_team": "Germany", "home_goals": 2, "away_goals": 1, "days_ago": 400},
    {"home_team": "Spain", "away_team": "France", "home_goals": 3, "away_goals": 1, "days_ago": 380},
    {"home_team": "Spain", "away_team": "Senegal", "home_goals": 3, "away_goals": 0, "days_ago": 350},
    {"home_team": "Germany", "away_team": "Spain", "home_goals": 1, "away_goals": 2, "days_ago": 320},
    {"home_team": "France", "away_team": "Spain", "home_goals": 0, "away_goals": 1, "days_ago": 300},
    {"home_team": "Brazil", "away_team": "Spain", "home_goals": 1, "away_goals": 1, "days_ago": 280},
    {"home_team": "Spain", "away_team": "Costa Rica", "home_goals": 4, "away_goals": 0, "days_ago": 260},
    {"home_team": "Spain", "away_team": "Brazil", "home_goals": 2, "away_goals": 0, "days_ago": 240},
    {"home_team": "Spain", "away_team": "Senegal", "home_goals": 2, "away_goals": 1, "days_ago": 220},
    {"home_team": "Costa Rica", "away_team": "Spain", "home_goals": 0, "away_goals": 3, "days_ago": 200},
    # Germany — strong attack
    {"home_team": "Germany", "away_team": "France", "home_goals": 2, "away_goals": 0, "days_ago": 410},
    {"home_team": "Germany", "away_team": "Senegal", "home_goals": 3, "away_goals": 1, "days_ago": 390},
    {"home_team": "Germany", "away_team": "Brazil", "home_goals": 2, "away_goals": 2, "days_ago": 360},
    {"home_team": "France", "away_team": "Germany", "home_goals": 1, "away_goals": 2, "days_ago": 340},
    {"home_team": "Brazil", "away_team": "Germany", "home_goals": 1, "away_goals": 1, "days_ago": 310},
    {"home_team": "Germany", "away_team": "Costa Rica", "home_goals": 4, "away_goals": 1, "days_ago": 290},
    {"home_team": "Senegal", "away_team": "Germany", "home_goals": 0, "away_goals": 2, "days_ago": 270},
    {"home_team": "Germany", "away_team": "France", "home_goals": 1, "away_goals": 0, "days_ago": 250},
    # France — strong defense
    {"home_team": "France", "away_team": "Senegal", "home_goals": 1, "away_goals": 0, "days_ago": 420},
    {"home_team": "France", "away_team": "Brazil", "home_goals": 1, "away_goals": 0, "days_ago": 400},
    {"home_team": "France", "away_team": "Costa Rica", "home_goals": 2, "away_goals": 0, "days_ago": 370},
    {"home_team": "Senegal", "away_team": "France", "home_goals": 0, "away_goals": 1, "days_ago": 345},
    {"home_team": "Brazil", "away_team": "France", "home_goals": 1, "away_goals": 1, "days_ago": 325},
    {"home_team": "Costa Rica", "away_team": "France", "home_goals": 0, "away_goals": 2, "days_ago": 305},
    # Brazil — balanced
    {"home_team": "Brazil", "away_team": "Senegal", "home_goals": 2, "away_goals": 1, "days_ago": 415},
    {"home_team": "Brazil", "away_team": "Costa Rica", "home_goals": 3, "away_goals": 0, "days_ago": 395},
    {"home_team": "Senegal", "away_team": "Brazil", "home_goals": 1, "away_goals": 1, "days_ago": 365},
    {"home_team": "Costa Rica", "away_team": "Brazil", "home_goals": 0, "away_goals": 2, "days_ago": 335},
    {"home_team": "Brazil", "away_team": "Germany", "home_goals": 1, "away_goals": 3, "days_ago": 315},
    {"home_team": "Brazil", "away_team": "France", "home_goals": 0, "away_goals": 0, "days_ago": 295},
    # Senegal — below average
    {"home_team": "Senegal", "away_team": "Costa Rica", "home_goals": 1, "away_goals": 1, "days_ago": 430},
    {"home_team": "Costa Rica", "away_team": "Senegal", "home_goals": 0, "away_goals": 1, "days_ago": 405},
    {"home_team": "Senegal", "away_team": "Costa Rica", "home_goals": 2, "away_goals": 0, "days_ago": 375},
    # Costa Rica — weakest
    {"home_team": "Costa Rica", "away_team": "Germany", "home_goals": 0, "away_goals": 4, "days_ago": 440},
    {"home_team": "Costa Rica", "away_team": "France", "home_goals": 0, "away_goals": 1, "days_ago": 420},
    {"home_team": "Germany", "away_team": "Costa Rica", "home_goals": 3, "away_goals": 0, "days_ago": 380},
    # Recent matches (lower days_ago → higher weight)
    {"home_team": "Spain", "away_team": "France", "home_goals": 1, "away_goals": 0, "days_ago": 30},
    {"home_team": "Germany", "away_team": "Brazil", "home_goals": 2, "away_goals": 1, "days_ago": 20},
    {"home_team": "France", "away_team": "Senegal", "home_goals": 2, "away_goals": 0, "days_ago": 15},
    {"home_team": "Spain", "away_team": "Germany", "home_goals": 3, "away_goals": 1, "days_ago": 10},
]


@pytest.fixture
def synthetic_matches() -> list[dict]:
    return SYNTHETIC_MATCHES


@pytest.fixture
def fitted_model(synthetic_matches):
    """Dixon-Coles model fitted on the synthetic dataset."""
    from engine.models.dixon_coles import DixonColesModel
    model = DixonColesModel(xi=0.0023)
    model.fit(synthetic_matches)
    return model
