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
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
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


def _prepare_arrays(records: list[MatchRecord], teams: list[str], xi: float) -> dict:
    """Pre-compute numpy arrays from match records. Called once before optimization."""
    idx = {t: i for i, t in enumerate(teams)}
    hg = np.array([m.home_goals for m in records], dtype=np.int32)
    ag = np.array([m.away_goals for m in records], dtype=np.int32)
    return {
        "hi": np.array([idx[m.home_team] for m in records], dtype=np.int32),
        "ai": np.array([idx[m.away_team] for m in records], dtype=np.int32),
        "hg": hg,
        "ag": ag,
        "w":  np.exp(-xi * np.array([m.days_ago for m in records])),
        "log_hg_fact": gammaln(hg + 1),
        "log_ag_fact": gammaln(ag + 1),
        # Boolean masks for the 4 tau-correction cases (computed once)
        "m00": (hg == 0) & (ag == 0),
        "m01": (hg == 0) & (ag == 1),
        "m10": (hg == 1) & (ag == 0),
        "m11": (hg == 1) & (ag == 1),
    }


def _neg_log_likelihood(v: np.ndarray, data: dict, n_teams: int) -> float:
    """Vectorized log-likelihood — no Python loops over matches."""
    attack   = v[:n_teams]
    defense  = v[n_teams : 2 * n_teams]
    home_adv = v[2 * n_teams]
    rho      = v[2 * n_teams + 1]

    mu_h = np.exp(attack[data["hi"]] - defense[data["ai"]] + home_adv)
    mu_a = np.exp(attack[data["ai"]] - defense[data["hi"]])

    hg, ag = data["hg"], data["ag"]

    # Poisson log-PMF: k*log(mu) - mu - log(k!)
    log_pmf_h = hg * np.log(mu_h) - mu_h - data["log_hg_fact"]
    log_pmf_a = ag * np.log(mu_a) - mu_a - data["log_ag_fact"]

    # Tau correction for 4 low-scoring outcomes
    tau = np.ones(len(hg))
    tau[data["m00"]] = 1.0 - mu_h[data["m00"]] * mu_a[data["m00"]] * rho
    tau[data["m01"]] = 1.0 + mu_h[data["m01"]] * rho
    tau[data["m10"]] = 1.0 + mu_a[data["m10"]] * rho
    tau[data["m11"]] = 1.0 - rho

    if np.any(tau <= 0):
        return 1e12

    return -float(np.sum(data["w"] * (np.log(tau) + log_pmf_h + log_pmf_a)))


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
    teams = sorted(
        {m.home_team for m in records} | {m.away_team for m in records}
    )
    n = len(teams)

    # Pre-compute arrays once — passed as args to every optimizer call
    data = _prepare_arrays(records, teams, xi)

    # Initial guess: all zeros (log-space), small home advantage, small rho
    v0 = np.zeros(2 * n + 2)
    v0[2 * n] = 0.25      # home advantage
    v0[2 * n + 1] = 0.05  # rho

    # Bounds: attack/defense in (-3, 3), home_adv in (0, 2), rho in (-0.5, 0.5)
    bounds = [(-3.0, 3.0)] * (2 * n) + [(0.0, 2.0)] + [(-0.5, 0.5)]

    # Sum-to-zero constraint on attack params for identifiability
    constraints = [{"type": "eq", "fun": lambda v, _n=n: np.sum(v[:_n])}]

    result = minimize(
        _neg_log_likelihood,
        v0,
        args=(data, n),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        # ftol=1e-5 is plenty for betting decisions; 1e-10 never terminates
        options={"maxiter": 500, "ftol": 1e-5, "disp": False},
    )

    if not result.success:
        warnings.warn(
            f"Dixon-Coles optimization did not fully converge: {result.message}"
        )

    return DixonColesParams.from_vector(result.x, teams)


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
