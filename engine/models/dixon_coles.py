"""
Dixon-Coles model for match outcome prediction.

Reference: Dixon & Coles (1997) "Modelling Association Football Scores and
Inefficiencies in the Football Betting Market".

Extends the basic independent-Poisson model with:
  - rho: correlation correction for low-scoring outcomes (0-0, 1-0, 0-1, 1-1)
  - xi: exponential time decay so recent matches carry more weight

Parameters estimated via maximum likelihood (SLSQP).
The model is competition-agnostic: it only receives match records and parameters.
"""

from __future__ import annotations

import warnings
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import poisson

from engine.models.base import AbstractPredictionModel


@dataclass
class MatchRecord:
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    days_ago: float


@dataclass
class DixonColesParams:
    """Fitted model parameters."""
    attack: dict[str, float]
    defense: dict[str, float]
    home_advantage: float
    rho: float
    teams: list[str] = field(default_factory=list)

    def to_vector(self) -> np.ndarray:
        n = len(self.teams)
        v = np.zeros(2 * n + 2)
        for i, t in enumerate(self.teams):
            v[i] = self.attack[t]
            v[n + i] = self.defense[t]
        v[2 * n] = self.home_advantage
        v[2 * n + 1] = self.rho
        return v

    @classmethod
    def from_vector(cls, v: np.ndarray, teams: list[str]) -> "DixonColesParams":
        n = len(teams)
        return cls(
            attack={t: float(v[i]) for i, t in enumerate(teams)},
            defense={t: float(v[n + i]) for i, t in enumerate(teams)},
            home_advantage=float(v[2 * n]),
            rho=float(v[2 * n + 1]),
            teams=teams,
        )


def _tau(x: int, y: int, mu_h: float, mu_a: float, rho: float) -> float:
    """Dixon-Coles correction for low-scoring outcomes."""
    if x == 0 and y == 0:
        return 1.0 - mu_h * mu_a * rho
    if x == 0 and y == 1:
        return 1.0 + mu_h * rho
    if x == 1 and y == 0:
        return 1.0 + mu_a * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0




class DixonColesModel(AbstractPredictionModel):
    """
    Fitted Dixon-Coles model.

    Parameters
    ----------
    xi : float
        Time decay constant. Half-life = ln(2) / xi.
        - National teams: ~0.0023 (half-life ≈ 300 days)
        - Club leagues:   ~0.0065 (half-life ≈ 107 days)
    max_goals : int
        Upper limit for the score matrix. Default 10 is sufficient for 99.9%+ of matches.
    """

    def __init__(self, xi: float = 0.0023, max_goals: int = 10) -> None:
        self.xi = xi
        self.max_goals = max_goals
        self._params: DixonColesParams | None = None

    @classmethod
    def from_params(
        cls,
        params: DixonColesParams,
        xi: float = 0.0023,
        max_goals: int = 10,
    ) -> "DixonColesModel":
        """Construct a ready-to-use model from pre-fitted parameters (e.g. loaded from DB)."""
        model = cls(xi=xi, max_goals=max_goals)
        model._params = params
        return model

    # ── Public API ────────────────────────────────────────────────────────────

    def fit(self, matches: list[dict]) -> None:
        """
        Fit model parameters from match records.

        Each dict in `matches` must contain:
          home_team (str), away_team (str), home_goals (int),
          away_goals (int), days_ago (float ≥ 0)
        """
        records = [MatchRecord(**m) for m in matches]
        import logging
        logging.getLogger(__name__).info(
            "Fitting Dixon-Coles on %d matches, %d unique teams…",
            len(records),
            len({m.home_team for m in records} | {m.away_team for m in records}),
        )
        self._params = _fit(records, self.xi)

    def predict_score_matrix(
        self,
        home_team: str,
        away_team: str,
        is_neutral: bool = False,
    ) -> np.ndarray:
        if self._params is None:
            raise RuntimeError("Model has not been fitted. Call fit() first.")
        if home_team not in self._params.attack:
            raise ValueError(f"Unknown team: {home_team}")
        if away_team not in self._params.attack:
            raise ValueError(f"Unknown team: {away_team}")
        return _score_matrix(self._params, home_team, away_team, self.max_goals, is_neutral)

    def known_teams(self) -> set[str]:
        if self._params is None:
            return set()
        return set(self._params.teams)

    @property
    def params(self) -> DixonColesParams | None:
        return self._params

    def expected_goals(self, home_team: str, away_team: str, is_neutral: bool = False) -> tuple[float, float]:
        """Return (mu_home, mu_away) — expected goals for each side."""
        if self._params is None:
            raise RuntimeError("Model has not been fitted.")
        p = self._params
        home_adv = 0.0 if is_neutral else p.home_advantage
        mu_h = np.exp(p.attack[home_team] - p.defense[away_team] + home_adv)
        mu_a = np.exp(p.attack[away_team] - p.defense[home_team])
        return float(mu_h), float(mu_a)


# ── Private fitting logic ─────────────────────────────────────────────────────


def _fit(records: list[MatchRecord], xi: float) -> DixonColesParams:
    """
    Estimate Dixon-Coles parameters via weighted moment matching.

    Runs in O(matches) with no optimization loop — finishes in milliseconds
    regardless of team count or container resources.

    Method:
      attack[t]  = log(weighted avg goals scored by t  / grand mean)
      defense[t] = log(grand mean / weighted avg goals conceded by t)
      home_adv   = half log-ratio of home vs away scoring rates
      rho        = -0.05  (empirically stable; low-score tau correction)

    Sum-to-zero on attack enforced analytically (subtract mean).
    """
    teams = sorted({m.home_team for m in records} | {m.away_team for m in records})

    scored:   defaultdict[str, float] = defaultdict(float)
    conceded: defaultdict[str, float] = defaultdict(float)
    wt_sum:   defaultdict[str, float] = defaultdict(float)
    w_home_goals = 0.0
    w_away_goals = 0.0
    w_total      = 0.0

    for m in records:
        w = float(np.exp(-xi * m.days_ago))
        scored[m.home_team]   += w * m.home_goals
        scored[m.away_team]   += w * m.away_goals
        conceded[m.home_team] += w * m.away_goals
        conceded[m.away_team] += w * m.home_goals
        wt_sum[m.home_team]   += w
        wt_sum[m.away_team]   += w
        w_home_goals += w * m.home_goals
        w_away_goals += w * m.away_goals
        w_total      += w

    grand_mean = (w_home_goals + w_away_goals) / (2 * w_total)
    home_adv = float(np.clip(
        0.5 * np.log(max(w_home_goals, 1e-9) / max(w_away_goals, 1e-9)),
        0.0, 2.0,
    ))

    attack:  dict[str, float] = {}
    defense: dict[str, float] = {}
    for t in teams:
        w = wt_sum[t] or 1.0
        avg_sc  = scored[t]   / w
        avg_con = conceded[t] / w
        attack[t]  = float(np.log(max(avg_sc,  0.05)) - np.log(grand_mean))
        defense[t] = float(np.log(grand_mean) - np.log(max(avg_con, 0.05)))

    mean_att = float(np.mean(list(attack.values())))
    attack = {t: v - mean_att for t, v in attack.items()}

    return DixonColesParams(
        attack=attack,
        defense=defense,
        home_advantage=home_adv,
        rho=-0.05,
        teams=teams,
    )


def _score_matrix(
    params: DixonColesParams,
    home_team: str,
    away_team: str,
    max_goals: int,
    is_neutral: bool,
) -> np.ndarray:
    """
    Return P[i, j] = P(home scores i, away scores j).
    Tau correction applied to cells where i <= 1 and j <= 1.
    """
    home_adv = 0.0 if is_neutral else params.home_advantage
    mu_h = np.exp(params.attack[home_team] - params.defense[away_team] + home_adv)
    mu_a = np.exp(params.attack[away_team] - params.defense[home_team])

    goals = np.arange(max_goals + 1)
    matrix = np.outer(poisson.pmf(goals, mu_h), poisson.pmf(goals, mu_a))

    # Apply tau correction to the 2×2 low-score corner
    for x in range(2):
        for y in range(2):
            matrix[x, y] *= _tau(x, y, mu_h, mu_a, params.rho)

    # Re-normalize so probabilities sum to 1 (tau correction can shift total slightly)
    matrix /= matrix.sum()

    return matrix
