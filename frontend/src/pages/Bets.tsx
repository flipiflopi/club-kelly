import { Link } from "react-router-dom";
import { api } from "../api/client";
import { usePolling } from "../api/usePolling";
import type { AdminBet } from "../api/client";

function BetCard({ bet }: { bet: AdminBet }) {
  const date = new Date(bet.match_date).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
  const potential = bet.stake_amount * (bet.decimal_odds - 1);

  const outcomeLabel =
    bet.outcome === "home"
      ? bet.home_team
      : bet.outcome === "away"
      ? bet.away_team
      : bet.outcome === "draw"
      ? "Draw"
      : bet.outcome;

  return (
    <div className="border-t border-gray-100 pt-5 pb-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-xs text-gray-400 font-mono mb-1">{date}</p>
          <p className="font-semibold text-gray-900 truncate">
            {bet.home_team} <span className="text-gray-400 font-normal">vs</span>{" "}
            {bet.away_team}
          </p>
          <p className="text-sm text-gray-500 mt-0.5">
            Bet:{" "}
            <span className="text-gray-900 font-medium">{outcomeLabel}</span>
            <span className="text-gray-300 mx-2">·</span>
            odds{" "}
            <span className="font-mono text-gray-900">@{bet.decimal_odds.toFixed(2)}</span>
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-lg font-bold text-gray-900 font-mono">
            {bet.stake_amount.toFixed(2)}€
          </p>
          <p className="text-xs text-gray-400 mt-0.5">
            {(bet.stake_pct * 100).toFixed(1)}% bankroll
          </p>
          <p className="text-xs text-green-600 font-mono mt-1">
            +{potential.toFixed(2)}€ potential
          </p>
        </div>
      </div>
    </div>
  );
}

export default function Bets() {
  const { data: bets, loading, error } = usePolling(api.adminGetOpenBets, 30_000);

  const totalStake = bets?.reduce((s, b) => s + b.stake_amount, 0) ?? 0;
  const totalPotential =
    bets?.reduce((s, b) => s + b.stake_amount * (b.decimal_odds - 1), 0) ?? 0;

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <Link
        to="/"
        className="text-xs text-gray-400 hover:text-gray-900 transition-colors flex items-center gap-1 mb-8"
      >
        ← Club Kelly
      </Link>

      <h1 className="text-3xl font-black tracking-tight mb-2">Active bets</h1>
      <p className="text-gray-500 text-sm mb-10">
        Open positions right now. Pending resolution.
      </p>

      {loading ? (
        <div className="space-y-6">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="border-t border-gray-100 pt-5 h-20 animate-pulse bg-gray-50 rounded"
            />
          ))}
        </div>
      ) : error ? (
        <p className="text-red-500 text-sm">{error.message}</p>
      ) : !bets || bets.length === 0 ? (
        <div className="border-t border-gray-100 pt-12 text-center">
          <p className="text-gray-400 text-sm">No active bets at the moment.</p>
          <p className="text-gray-300 text-xs mt-2">
            Kelly will bet when it detects a genuine edge.
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-0">
            {bets.map((b) => (
              <BetCard key={b.id} bet={b} />
            ))}
          </div>

          <div className="border-t-2 border-gray-900 mt-2 pt-5 flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-widest font-mono">
                Total at stake
              </p>
              <p className="text-2xl font-black font-mono mt-1">
                {totalStake.toFixed(2)}€
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-gray-400 uppercase tracking-widest font-mono">
                Potential
              </p>
              <p className="text-2xl font-black font-mono text-green-600 mt-1">
                +{totalPotential.toFixed(2)}€
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
