"""
Backtesting command: walk-forward evaluation of the DC + Elo ensemble on historical WCs.

Usage:
  uv run python -m backend.app.commands.backtest
  uv run python -m backend.app.commands.backtest --wc-years 2014,2018,2022
  uv run python -m backend.app.commands.backtest --csv training/data/results.csv --margin 0.08

Output: accuracy, calibration, Brier score, and simulated P&L per tournament.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest the DC + Elo ensemble on historical World Cups")
    parser.add_argument("--csv", default="training/data/results.csv", help="Path to Kaggle CSV")
    parser.add_argument("--wc-years", default="2010,2014,2018,2022", help="Comma-separated WC years to test")
    parser.add_argument("--dc-weight", type=float, default=0.5)
    parser.add_argument("--elo-weight", type=float, default=0.5)
    parser.add_argument("--max-disagreement", type=float, default=0.12, help="Consensus filter threshold (pp)")
    parser.add_argument("--initial-bankroll", type=float, default=1000.0)
    parser.add_argument("--kelly-multiplier", type=float, default=0.25)
    parser.add_argument("--max-bet-pct", type=float, default=0.03)
    parser.add_argument("--min-edge", type=float, default=0.03)
    parser.add_argument("--margin", type=float, default=0.05, help="Simulated bookmaker margin (0.05 = 5%%)")
    parser.add_argument("--verbose", action="store_true", help="Show all predictions")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: CSV not found at '{csv_path}'")
        print("Download from https://www.kaggle.com/datasets/martj42/international-football-results")
        return 1

    years = [int(y.strip()) for y in args.wc_years.split(",")]

    print(f"\nBacktest: DC+Elo ensemble | WC years: {', '.join(str(y) for y in years)}")
    print(f"CSV: {csv_path} | Margin: {args.margin*100:.0f}% | Kelly: {args.kelly_multiplier}x | Min edge: {args.min_edge*100:.0f}pp\n")

    from engine.backtest.runner import run_backtest

    result = run_backtest(
        csv_path=csv_path,
        wc_years=years,
        dc_weight=args.dc_weight,
        elo_weight=args.elo_weight,
        max_disagreement=args.max_disagreement,
        initial_bankroll=args.initial_bankroll,
        kelly_multiplier=args.kelly_multiplier,
        max_bet_pct=args.max_bet_pct,
        min_edge=args.min_edge,
        bookmaker_margin=args.margin,
    )

    if not result.wc_results:
        print("No results — check --wc-years and that the CSV contains FIFA World Cup matches.")
        return 1

    _print_results(result, args)
    return 0


def _print_results(result, args) -> None:
    from engine.backtest.runner import BacktestResult

    NAIVE_BRIER = 1/3 * ((1 - 1/3)**2 + 2 * (0 - 1/3)**2)  # ≈ 0.222

    # ── Per-tournament table ──────────────────────────────────────────────────
    W = 88
    print("=" * W)
    print("PER-TOURNAMENT SUMMARY")
    print("=" * W)
    print(f"{'Year':<6} {'Matches':>7} {'Training':>9} {'Acc':>6} {'Brier':>7} {'Bets':>5} {'P&L':>9} {'ROI':>7}")
    print("-" * W)

    for wc in result.wc_results:
        n_pred = len([p for p in wc.predictions if not p.consensus_skipped])
        skipped = len([p for p in wc.predictions if p.consensus_skipped])
        skip_note = f" ({skipped} skipped)" if skipped else ""
        print(
            f"{wc.year:<6} {wc.test_matches:>7}{skip_note:<12} "
            f"{wc.train_size:>9,} "
            f"{wc.accuracy*100:>5.0f}% "
            f"{wc.brier_score:>7.4f} "
            f"{len(wc.bets):>5} "
            f"{wc.pnl:>+9.2f}€ "
            f"{wc.roi*100:>+6.1f}%"
        )

    print("-" * W)
    n_total = sum(wc.test_matches for wc in result.wc_results)
    all_preds = [p for p in result.all_predictions if not p.consensus_skipped]
    n_skip_total = len([p for p in result.all_predictions if p.consensus_skipped])
    print(
        f"{'TOTAL':<6} {n_total:>7} ({n_skip_total} skipped)     "
        f"{'':>9} "
        f"{result.overall_accuracy*100:>5.0f}% "
        f"{result.overall_brier:>7.4f} "
        f"{len(result.all_bets):>5} "
        f"{result.overall_pnl:>+9.2f}€ "
        f"{result.overall_roi*100:>+6.1f}%"
    )
    print("=" * W)

    # ── Calibration ───────────────────────────────────────────────────────────
    print("\nCALIBRATION  (predicted probability vs actual win rate)")
    print(f"{'Bucket':<12} {'Predicted':>10} {'Actual':>8} {'Count':>7}  {'Quality':>10}")
    print("-" * 55)
    buckets = result.calibration_buckets(n=5)
    for center, actual_rate, count in buckets:
        lo = (center - 0.1) * 100
        hi = (center + 0.1) * 100
        diff = actual_rate - center
        quality = "✓ good" if abs(diff) < 0.04 else ("▲ over" if diff > 0 else "▼ under")
        bar_pred = "█" * int(center * 20)
        bar_act  = "█" * int(actual_rate * 20)
        print(
            f"{lo:.0f}–{hi:.0f}%{'':<5} "
            f"{center*100:>8.0f}%   "
            f"{actual_rate*100:>6.0f}%   "
            f"{count:>6}   "
            f"{quality}"
        )

    # ── Summary stats ─────────────────────────────────────────────────────────
    print("\nMODEL QUALITY")
    print(f"  Accuracy:    {result.overall_accuracy*100:.1f}%  (baseline: 33% random, ~46% for home team)")
    print(f"  Brier score: {result.overall_brier:.4f}  (naive uniform baseline: {NAIVE_BRIER:.4f}, lower is better)")
    brier_vs_naive = (NAIVE_BRIER - result.overall_brier) / NAIVE_BRIER * 100
    print(f"  Brier gain:  {brier_vs_naive:+.1f}% vs uniform baseline")

    # ── P&L breakdown ─────────────────────────────────────────────────────────
    bets = result.all_bets
    if bets:
        won_bets = [b for b in bets if b.won]
        print(f"\nSIMULATED P&L  (market = empirical frequency + {args.margin*100:.0f}% margin)")
        print(f"  Total bets:  {len(bets)}")
        print(f"  Win rate:    {len(won_bets)/len(bets)*100:.1f}%  ({len(won_bets)}W / {len(bets)-len(won_bets)}L)")
        print(f"  Avg stake:   {sum(b.stake for b in bets)/len(bets):.2f}€")
        print(f"  Avg odds:    {sum(b.market_odds for b in bets)/len(bets):.2f}")
        print(f"  Total P&L:   {result.overall_pnl:+.2f}€ over {len(result.wc_results)} tournaments")
        by_outcome = {"home": [], "draw": [], "away": []}
        for b in bets:
            by_outcome[b.outcome].append(b.pnl)
        for outcome, pnls in by_outcome.items():
            if pnls:
                print(f"    {outcome:<5}:  {len(pnls)} bets  P&L {sum(pnls):+.2f}€  win%={sum(1 for p in pnls if p > 0)/len(pnls)*100:.0f}%")
    else:
        print("\nNo bets placed (edge threshold not met against frequency baseline)")
        print("Try --min-edge 0.01 or --margin 0.10 to see more simulated bets")

    if args.verbose:
        _print_predictions(result)

    print("\n⚠  P&L is simulated against a naive frequency baseline, NOT real bookmaker odds.")
    print("   Real markets are sharper. Use calibration and Brier score as primary quality signals.\n")


def _print_predictions(result) -> None:
    print("\nALL PREDICTIONS")
    print(f"{'Match':<35} {'Date':<12} {'DC':>8} {'Elo':>8} {'Ens':>8} {'Pred':>6} {'Act':>6} {'OK':>4}")
    print("-" * 100)
    for wc in result.wc_results:
        print(f"  --- WC {wc.year} ---")
        for p in wc.predictions:
            match_name = f"{p.home_team} vs {p.away_team}"[:34]
            ens_str = f"{p.ens_home*100:.0f}/{p.ens_draw*100:.0f}/{p.ens_away*100:.0f}"
            dc_str  = f"{p.dc_home*100:.0f}/{p.dc_draw*100:.0f}/{p.dc_away*100:.0f}"
            elo_str = f"{p.elo_home*100:.0f}/{p.elo_draw*100:.0f}/{p.elo_away*100:.0f}"
            skip = "SKIP" if p.consensus_skipped else ""
            ok = "✓" if p.correct else ("✗" if not p.consensus_skipped else "-")
            print(
                f"{match_name:<35} {p.match_date.strftime('%Y-%m-%d'):<12} "
                f"{dc_str:>8} {elo_str:>8} {ens_str:>8} "
                f"{p.predicted_outcome:>6} {p.actual_outcome:>6} {ok:>4} {skip}"
            )


if __name__ == "__main__":
    sys.exit(main())
