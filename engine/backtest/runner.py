"""
Walk-forward backtesting engine for the DC + Elo ensemble.

For each target World Cup year:
  1. Train DC and Elo on ALL data before the tournament starts
  2. Predict every WC match (1X2 outcome only)
  3. Evaluate calibration, accuracy, Brier score
  4. Simulate bets against a naive frequency baseline (empirical historical rates + margin)

P&L note: the simulated market uses empirical outcome frequencies from recent
training data as implied probabilities, then applies a bookmaker margin on top.
Real bookmaker markets are sharper — treat calibration as the primary quality signal.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class PredictionRecord:
    home_team: str
    away_team: str
    match_date: datetime
    home_goals: int
    away_goals: int
    actual_outcome: str        # "home" | "draw" | "away"
    dc_home: float
    dc_draw: float
    dc_away: float
    elo_home: float
    elo_draw: float
    elo_away: float
    ens_home: float
    ens_draw: float
    ens_away: float
    predicted_outcome: str     # outcome with highest ensemble prob
    consensus_skipped: bool = False

    @property
    def correct(self) -> bool:
        return (not self.consensus_skipped) and (self.predicted_outcome == self.actual_outcome)

    def brier_components(self) -> list[float]:
        if self.consensus_skipped:
            return []
        return [
            (float(self.actual_outcome == "home") - self.ens_home) ** 2,
            (float(self.actual_outcome == "draw") - self.ens_draw) ** 2,
            (float(self.actual_outcome == "away") - self.ens_away) ** 2,
        ]


@dataclass
class BetRecord:
    home_team: str
    away_team: str
    match_date: datetime
    outcome: str
    model_prob: float
    market_odds: float
    edge: float
    stake: float
    won: bool
    pnl: float
    bankroll_after: float


@dataclass
class WCResult:
    year: int
    train_size: int
    test_matches: int
    predictions: list[PredictionRecord] = field(default_factory=list)
    bets: list[BetRecord] = field(default_factory=list)
    bankroll_start: float = 0.0
    bankroll_end: float = 0.0

    @property
    def pnl(self) -> float:
        return self.bankroll_end - self.bankroll_start

    @property
    def roi(self) -> float:
        return self.pnl / self.bankroll_start if self.bankroll_start else 0.0

    @property
    def accuracy(self) -> float:
        preds = [p for p in self.predictions if not p.consensus_skipped]
        return sum(p.correct for p in preds) / len(preds) if preds else 0.0

    @property
    def brier_score(self) -> float:
        comps = [c for p in self.predictions for c in p.brier_components()]
        return sum(comps) / len(comps) if comps else 0.0


@dataclass
class BacktestResult:
    wc_results: list[WCResult]
    initial_bankroll: float

    @property
    def all_predictions(self) -> list[PredictionRecord]:
        return [p for wc in self.wc_results for p in wc.predictions]

    @property
    def all_bets(self) -> list[BetRecord]:
        return [b for wc in self.wc_results for b in wc.bets]

    @property
    def overall_accuracy(self) -> float:
        preds = [p for p in self.all_predictions if not p.consensus_skipped]
        return sum(p.correct for p in preds) / len(preds) if preds else 0.0

    @property
    def overall_brier(self) -> float:
        comps = [c for p in self.all_predictions for c in p.brier_components()]
        return sum(comps) / len(comps) if comps else 0.0

    @property
    def overall_pnl(self) -> float:
        return sum(wc.pnl for wc in self.wc_results)

    @property
    def overall_roi(self) -> float:
        return self.overall_pnl / (self.initial_bankroll * len(self.wc_results)) if self.wc_results else 0.0

    def calibration_buckets(self, n: int = 5) -> list[tuple[float, float, int]]:
        """
        Returns (bucket_center, actual_rate, count) for each probability bucket.
        Uses all (prediction, outcome) pairs (3 per match — one per outcome class).
        """
        bucket_size = 1.0 / n
        totals = [0] * n
        hits = [0] * n
        for p in self.all_predictions:
            if p.consensus_skipped:
                continue
            for outcome, prob in [("home", p.ens_home), ("draw", p.ens_draw), ("away", p.ens_away)]:
                idx = min(int(prob / bucket_size), n - 1)
                totals[idx] += 1
                if p.actual_outcome == outcome:
                    hits[idx] += 1
        return [
            ((i + 0.5) * bucket_size, hits[i] / totals[i] if totals[i] else 0.0, totals[i])
            for i in range(n)
        ]


# ── Main backtest runner ──────────────────────────────────────────────────────


def run_backtest(
    csv_path: Path,
    wc_years: list[int],
    dc_weight: float = 0.5,
    elo_weight: float = 0.5,
    max_disagreement: float = 0.12,
    dc_xi: float = 0.0023,
    initial_bankroll: float = 1000.0,
    kelly_multiplier: float = 0.25,
    max_bet_pct: float = 0.03,
    min_edge: float = 0.03,
    bookmaker_margin: float = 0.05,
    dc_min_years_back: int = 15,
    elo_min_years_back: int = 30,
) -> BacktestResult:
    from adapters.historical.kaggle_international import KaggleInternationalSource
    from engine.models.dixon_coles import DixonColesModel
    from engine.models.elo import EloModel

    source = KaggleInternationalSource(csv_path=csv_path)
    all_matches = source.get_matches(min_date=datetime(1950, 1, 1))
    all_matches.sort(key=lambda m: m.match_date)
    logger.info("Loaded %d total historical matches", len(all_matches))

    wc_results: list[WCResult] = []

    for year in wc_years:
        wc_matches = [
            m for m in all_matches
            if m.competition == "FIFA World Cup" and m.match_date.year == year
        ]
        if not wc_matches:
            logger.warning("No WC matches found for year %d — skipping", year)
            continue

        wc_matches.sort(key=lambda m: m.match_date)
        wc_start = wc_matches[0].match_date.replace(hour=0, minute=0, second=0, microsecond=0)
        logger.info("WC %d: %d matches, starts %s", year, len(wc_matches), wc_start.date())

        dc_cutoff = datetime(year - dc_min_years_back, 1, 1)
        elo_cutoff = datetime(year - elo_min_years_back, 1, 1)

        train_all = [m for m in all_matches if m.match_date < wc_start]
        dc_train = [m for m in train_all if m.match_date >= dc_cutoff]
        elo_train = [m for m in train_all if m.match_date >= elo_cutoff]

        # Train DC
        dc_records = [
            {
                "home_team": m.home_team,
                "away_team": m.away_team,
                "home_goals": m.home_goals,
                "away_goals": m.away_goals,
                "days_ago": max(0, (wc_start - m.match_date).days),
            }
            for m in dc_train
        ]
        dc_model = DixonColesModel(xi=dc_xi)
        dc_model.fit(dc_records)

        # Train Elo (sequential — oldest first, already sorted)
        elo_records = [
            {
                "home_team": m.home_team,
                "away_team": m.away_team,
                "home_goals": m.home_goals,
                "away_goals": m.away_goals,
                "tournament": m.competition,
                "is_neutral": m.is_neutral,
            }
            for m in elo_train
        ]
        elo_model = EloModel(home_advantage=65.0)
        elo_model.fit(elo_records)

        # Empirical baseline: outcome frequency from recent training data (last 8 years)
        recent_cutoff = datetime(year - 8, 1, 1)
        recent = [m for m in train_all if m.match_date >= recent_cutoff]
        if recent:
            n = len(recent)
            emp = {
                "home": sum(1 for m in recent if m.home_goals > m.away_goals) / n,
                "draw": sum(1 for m in recent if m.home_goals == m.away_goals) / n,
                "away": sum(1 for m in recent if m.home_goals < m.away_goals) / n,
            }
        else:
            emp = {"home": 0.40, "draw": 0.26, "away": 0.34}

        logger.info(
            "WC %d train: DC=%d matches, Elo=%d. Empirical base: H=%.0f%% D=%.0f%% A=%.0f%%",
            year, len(dc_train), len(elo_train),
            emp["home"] * 100, emp["draw"] * 100, emp["away"] * 100,
        )

        predictions: list[PredictionRecord] = []
        bets: list[BetRecord] = []
        bankroll = initial_bankroll

        for m in wc_matches:
            actual = (
                "home" if m.home_goals > m.away_goals
                else "draw" if m.home_goals == m.away_goals
                else "away"
            )

            # DC: 1X2 probs from score matrix
            dc_h, dc_d, dc_a = _dc_outcome_probs(dc_model, m.home_team, m.away_team, is_neutral=True)

            # Elo: 1X2 probs
            elo_h, elo_d, elo_a = _elo_outcome_probs(elo_model, m.home_team, m.away_team, is_neutral=True)

            # Ensemble (weighted average)
            total_w = dc_weight + elo_weight
            ens_h = (dc_weight * dc_h + elo_weight * elo_h) / total_w
            ens_d = (dc_weight * dc_d + elo_weight * elo_d) / total_w
            ens_a = (dc_weight * dc_a + elo_weight * elo_a) / total_w

            # Consensus filter
            skipped = (
                abs(dc_h - elo_h) > max_disagreement
                or abs(dc_d - elo_d) > max_disagreement
                or abs(dc_a - elo_a) > max_disagreement
            )

            ens = {"home": ens_h, "draw": ens_d, "away": ens_a}
            predicted = max(ens, key=ens.get)  # type: ignore[arg-type]

            pred = PredictionRecord(
                home_team=m.home_team,
                away_team=m.away_team,
                match_date=m.match_date,
                home_goals=m.home_goals,
                away_goals=m.away_goals,
                actual_outcome=actual,
                dc_home=dc_h, dc_draw=dc_d, dc_away=dc_a,
                elo_home=elo_h, elo_draw=elo_d, elo_away=elo_a,
                ens_home=ens_h, ens_draw=ens_d, ens_away=ens_a,
                predicted_outcome=predicted,
                consensus_skipped=skipped,
            )
            predictions.append(pred)

            if skipped:
                continue

            # Simulate bets against the empirical frequency market + margin
            for outcome, model_prob in ens.items():
                base_freq = emp[outcome]
                if base_freq <= 0:
                    continue
                # Market prices at empirical frequency with margin against bettor
                market_odds = (1.0 / base_freq) * (1.0 - bookmaker_margin)
                if market_odds <= 1.01:
                    continue
                edge = model_prob - (1.0 / market_odds)
                if edge < min_edge:
                    continue

                # Quarter-Kelly stake
                q = model_prob - (1.0 - model_prob) / (market_odds - 1.0)
                kelly_frac = max(0.0, q) * kelly_multiplier
                stake = min(bankroll * kelly_frac, bankroll * max_bet_pct)
                if stake < 0.01:
                    continue

                won = actual == outcome
                pnl = stake * (market_odds - 1.0) if won else -stake
                bankroll = max(0.0, bankroll + pnl)

                bets.append(BetRecord(
                    home_team=m.home_team,
                    away_team=m.away_team,
                    match_date=m.match_date,
                    outcome=outcome,
                    model_prob=model_prob,
                    market_odds=round(market_odds, 3),
                    edge=round(edge, 4),
                    stake=round(stake, 2),
                    won=won,
                    pnl=round(pnl, 2),
                    bankroll_after=round(bankroll, 2),
                ))

        wc_results.append(WCResult(
            year=year,
            train_size=len(dc_train),
            test_matches=len(wc_matches),
            predictions=predictions,
            bets=bets,
            bankroll_start=initial_bankroll,
            bankroll_end=bankroll,
        ))

    return BacktestResult(wc_results=wc_results, initial_bankroll=initial_bankroll)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _dc_outcome_probs(model, home: str, away: str, is_neutral: bool) -> tuple[float, float, float]:
    """Extract 1X2 probabilities from a DC score matrix."""
    try:
        matrix = model.predict_score_matrix(home, away, is_neutral=is_neutral)
        p_home = float(np.tril(matrix, -1).sum())
        p_draw = float(np.trace(matrix))
        p_away = float(np.triu(matrix, 1).sum())
        return p_home, p_draw, p_away
    except Exception:
        return 1 / 3, 1 / 3, 1 / 3


def _elo_outcome_probs(model, home: str, away: str, is_neutral: bool) -> tuple[float, float, float]:
    """Get 1X2 probabilities from the Elo model."""
    try:
        probs = model.predict_outcome_probs(home, away, is_neutral=is_neutral)
        return probs["home"], probs["draw"], probs["away"]
    except Exception:
        return 1 / 3, 1 / 3, 1 / 3
