"""
Elo rating model for football match outcome prediction.

Trained sequentially on chronological match history. Each result
updates both teams' ratings proportionally to how surprising the
outcome was relative to what the ratings predicted.

Complements Dixon-Coles in the ensemble: Elo naturally captures
opponent quality (beating Brazil is worth more than beating Andorra),
which the moment-matching DC estimator misses entirely.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EloParams:
    ratings: dict[str, float]        # team_name → current Elo rating
    matches_played: dict[str, int]   # team_name → matches processed
    home_advantage: float = 65.0     # Elo-point equivalent for home pitch


class EloModel:
    """
    Standard Elo model with:
      - K-factor scaled by match importance (World Cup > friendly)
      - Home advantage as a fixed Elo-point boost
      - 3-way probability conversion for the 1X2 market
    """

    DEFAULT_RATING = 1500.0

    def __init__(self, home_advantage: float = 65.0) -> None:
        self.home_advantage = home_advantage
        self._params: EloParams | None = None

    @classmethod
    def from_params(cls, params: EloParams) -> "EloModel":
        model = cls(home_advantage=params.home_advantage)
        model._params = params
        return model

    # ── Training ──────────────────────────────────────────────────────────────

    def fit(self, matches: list[dict]) -> None:
        """
        Train on match history (must be sorted chronologically — oldest first).

        Each dict must contain:
          home_team (str), away_team (str), home_goals (int), away_goals (int),
          tournament (str, used for K-factor), is_neutral (bool)
        """
        ratings: dict[str, float] = {}
        played: dict[str, int] = {}

        for m in matches:
            home = m["home_team"]
            away = m["away_team"]

            r_h = ratings.get(home, self.DEFAULT_RATING)
            r_a = ratings.get(away, self.DEFAULT_RATING)

            adv = 0.0 if m.get("is_neutral", False) else self.home_advantage
            dr = r_h - r_a + adv
            e_h = 1.0 / (1.0 + 10.0 ** (-dr / 400.0))

            h_goals = m["home_goals"]
            a_goals = m["away_goals"]
            if h_goals > a_goals:
                s_h = 1.0
            elif h_goals < a_goals:
                s_h = 0.0
            else:
                s_h = 0.5
            s_a = 1.0 - s_h

            k = _k_factor(m.get("tournament", ""))
            ratings[home] = r_h + k * (s_h - e_h)
            ratings[away] = r_a + k * (s_a - (1.0 - e_h))
            played[home] = played.get(home, 0) + 1
            played[away] = played.get(away, 0) + 1

        self._params = EloParams(
            ratings=ratings,
            matches_played=played,
            home_advantage=self.home_advantage,
        )

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict_outcome_probs(
        self,
        home_team: str,
        away_team: str,
        is_neutral: bool = False,
    ) -> dict[str, float]:
        """Return {"home": p, "draw": p, "away": p} for the 1X2 market."""
        if self._params is None:
            raise RuntimeError("EloModel has not been fitted.")
        p = self._params
        r_h = p.ratings.get(home_team, self.DEFAULT_RATING)
        r_a = p.ratings.get(away_team, self.DEFAULT_RATING)
        return _elo_to_outcome_probs(r_h, r_a, p.home_advantage, is_neutral)

    def known_teams(self) -> set[str]:
        if self._params is None:
            return set()
        return set(self._params.ratings.keys())

    @property
    def params(self) -> EloParams | None:
        return self._params


# ── Private helpers ───────────────────────────────────────────────────────────


def _k_factor(tournament: str) -> float:
    """
    Match importance → K-factor.
    Higher K = result has more impact on ratings.
    Values calibrated to World Football Elo ratings conventions.
    """
    t = tournament.lower()
    if "world cup" in t and "qualif" not in t:
        return 60.0
    if any(x in t for x in ["euro", "copa am", "african cup", "afcon", "asia cup", "gold cup", "nations cup"]):
        return 50.0
    if "qualif" in t or "nations league" in t:
        return 40.0
    if "friendly" in t:
        return 20.0
    return 35.0


def _elo_to_outcome_probs(
    home_rating: float,
    away_rating: float,
    home_adv: float,
    is_neutral: bool,
) -> dict[str, float]:
    """
    Convert an Elo rating difference to 1X2 probabilities.

    Draw probability model:
      Peaks at ~26% when teams are perfectly matched, falls to ~20% for
      mismatches. Average ~23%, consistent with international football data.
      Remaining probability is split between the two win outcomes proportionally
      to the standard Elo win expectancy.
    """
    adv = 0.0 if is_neutral else home_adv
    dr = home_rating - away_rating + adv

    # Standard Elo win expectancy
    p_home_win = 1.0 / (1.0 + 10.0 ** (-dr / 400.0))
    p_away_win = 1.0 - p_home_win

    # Draw probability: highest when evenly matched, lowest for big mismatches
    closeness = 1.0 - abs(p_home_win - 0.5) * 2.0  # 1.0 at 50/50, 0.0 at 100/0
    p_draw = 0.20 + 0.06 * closeness  # range [0.20, 0.26], avg ~0.23

    # Redistribute remaining probability proportionally to win expectancies
    remaining = 1.0 - p_draw
    p_home = p_home_win * remaining
    p_away = p_away_win * remaining

    total = p_home + p_draw + p_away
    return {
        "home": p_home / total,
        "draw": p_draw / total,
        "away": p_away / total,
    }
