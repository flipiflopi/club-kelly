import { Link } from "react-router-dom";
import { api } from "../api/client";
import { usePolling } from "../api/usePolling";
import type { Bet, BankrollEvent, BankrollSnapshot } from "../types/api";

const MARKET_NAMES: Record<string, string> = {
  match_result: "1X2",
  over_under: "Over/Under",
  btts: "BTTS",
};

const OUTCOME_LABELS: Record<string, string> = {
  draw: "Draw",
  over: "Over",
  under: "Under",
  yes: "Yes",
  no: "No",
};

function outcomeLabel(outcome: string, home: string, away: string): string {
  if (outcome === "home") return home;
  if (outcome === "away") return away;
  return OUTCOME_LABELS[outcome] ?? outcome;
}

// ── Bankroll chart ────────────────────────────────────────────────────────────

function BankrollChart({
  events,
  initial,
}: {
  events: BankrollEvent[];
  initial: number;
}) {
  if (events.length === 0) {
    return (
      <div className="h-32 flex items-center justify-center text-gray-300 text-sm">
        No movements recorded yet
      </div>
    );
  }

  const W = 600;
  const H = 140;
  const PX = 12;
  const PY = 20;

  const values = [initial, ...events.map((e) => e.balance_after)];
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const padding = (maxV - minV) * 0.1 || 10;
  const lo = minV - padding;
  const hi = maxV + padding;

  const sx = (i: number) => PX + (i / (values.length - 1)) * (W - 2 * PX);
  const sy = (v: number) => PY + (1 - (v - lo) / (hi - lo)) * (H - 2 * PY);

  const pts = values.map((v, i) => `${sx(i).toFixed(1)},${sy(v).toFixed(1)}`);
  const polyline = pts.join(" ");

  const lastX = sx(values.length - 1);
  const lastY = sy(values[values.length - 1]);
  const baseY = sy(initial);
  const isUp = values[values.length - 1] >= initial;
  const color = isUp ? "#16a34a" : "#ef4444";

  const areaPoints = [
    `${sx(0).toFixed(1)},${(H - PY).toFixed(1)}`,
    ...pts,
    `${lastX.toFixed(1)},${(H - PY).toFixed(1)}`,
  ].join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-36">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.12" />
          <stop offset="100%" stopColor={color} stopOpacity="0.01" />
        </linearGradient>
      </defs>
      <polygon points={areaPoints} fill="url(#bg)" />
      <line
        x1={PX}
        y1={baseY}
        x2={W - PX}
        y2={baseY}
        stroke="#e5e7eb"
        strokeWidth="1"
        strokeDasharray="5 3"
      />
      <polyline
        points={polyline}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={lastX} cy={lastY} r="4" fill={color} />
      <text x={W - PX - 2} y={PY + 4} textAnchor="end" fill="#9ca3af" fontSize="10">
        {maxV.toFixed(0)}€
      </text>
      <text x={PX + 2} y={baseY - 4} textAnchor="start" fill="#9ca3af" fontSize="9">
        Initial {initial.toFixed(0)}€
      </text>
      <text x={W - PX - 2} y={H - PY - 2} textAnchor="end" fill="#9ca3af" fontSize="10">
        {minV.toFixed(0)}€
      </text>
    </svg>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  positive,
}: {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
}) {
  return (
    <div className="border-t-2 border-gray-100 pt-4">
      <p className="text-xs text-gray-400 uppercase tracking-widest font-mono mb-2">{label}</p>
      <p
        className={`text-2xl font-black font-mono ${
          positive === true
            ? "text-green-600"
            : positive === false
            ? "text-red-500"
            : "text-gray-900"
        }`}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-gray-400 mt-1 font-mono">{sub}</p>}
    </div>
  );
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    open: "bg-blue-50 text-blue-600 border border-blue-200",
    won: "bg-green-50 text-green-700 border border-green-200",
    lost: "bg-red-50 text-red-600 border border-red-200",
    void: "bg-gray-50 text-gray-400 border border-gray-200",
  };
  const labels: Record<string, string> = {
    open: "Open",
    won: "Won",
    lost: "Lost",
    void: "Void",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${styles[status] ?? styles.void}`}>
      {labels[status] ?? status}
    </span>
  );
}

// ── Bet row ───────────────────────────────────────────────────────────────────

function BetRow({ bet }: { bet: Bet }) {
  const label = outcomeLabel(bet.outcome, bet.home_team_name, bet.away_team_name);
  const market = MARKET_NAMES[bet.market_slug] ?? bet.market_slug;
  const potential = bet.stake_amount * (bet.decimal_odds - 1);

  const pl = bet.profit_loss;
  const plStr =
    pl != null
      ? `${pl >= 0 ? "+" : ""}${pl.toFixed(2)}€`
      : `+${potential.toFixed(2)}€ potential`;
  const plPositive = pl != null ? pl >= 0 : undefined;

  return (
    <div className="border border-gray-100 rounded-lg px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 hover:border-gray-200 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-gray-900 truncate">
          {bet.home_team_name} vs {bet.away_team_name}
        </div>
        <div className="text-xs text-gray-400 mt-0.5">
          {market} · <span className="text-gray-900 font-medium">{label}</span>
        </div>
      </div>

      <div className="shrink-0 text-right">
        <div className="text-sm font-mono text-gray-600">@{bet.decimal_odds.toFixed(2)}</div>
        <div className="text-xs text-gray-400">odds</div>
      </div>

      <div className="shrink-0 text-right">
        <div className="text-sm font-mono font-semibold text-gray-900">
          {bet.stake_amount.toFixed(2)}€
        </div>
        <div className="text-xs text-gray-400">{(bet.stake_pct * 100).toFixed(1)}% bankroll</div>
      </div>

      <div className="shrink-0 text-right w-28">
        <div
          className={`text-sm font-mono font-bold ${
            plPositive === true
              ? "text-green-600"
              : plPositive === false
              ? "text-red-500"
              : "text-gray-400"
          }`}
        >
          {plStr}
        </div>
        <div className="text-xs text-gray-400">result</div>
      </div>

      <div className="shrink-0">
        <StatusBadge status={bet.status} />
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function History() {
  const { data: snapshot, loading: snapLoading } = usePolling(
    api.getBankrollSnapshot,
    60_000
  );
  const { data: chartData, loading: chartLoading } = usePolling(
    () => api.getBankrollHistory(200),
    60_000
  );
  const { data: bets, loading: betsLoading } = usePolling(
    () => api.getAllBets(undefined, 100),
    60_000
  );

  const loading = snapLoading || chartLoading || betsLoading;
  const openBets = bets?.filter((b) => b.status === "open") ?? [];
  const resolvedBets = bets?.filter((b) => b.status !== "open") ?? [];

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <Link
        to="/"
        className="text-xs text-gray-400 hover:text-gray-900 transition-colors flex items-center gap-1 mb-8"
      >
        ← Club Kelly
      </Link>

      <h1 className="text-3xl font-black tracking-tight mb-2">History</h1>
      <p className="text-sm text-gray-400 mb-10">Cumulative performance and all bets.</p>

      {/* Stats */}
      {!snapLoading && snapshot ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 mb-10">
          <StatCard
            label="Bankroll"
            value={`${snapshot.current_balance.toFixed(0)}€`}
            sub={`Initial: ${snapshot.initial_balance.toFixed(0)}€`}
          />
          <StatCard
            label="ROI"
            value={`${snapshot.roi_pct >= 0 ? "+" : ""}${snapshot.roi_pct.toFixed(1)}%`}
            sub={`${snapshot.total_profit_loss >= 0 ? "+" : ""}${snapshot.total_profit_loss.toFixed(2)}€`}
            positive={snapshot.roi_pct >= 0}
          />
          <StatCard
            label="Hit rate"
            value={
              snapshot.total_bets > 0
                ? `${((snapshot.won / snapshot.total_bets) * 100).toFixed(0)}%`
                : "—"
            }
            sub={`${snapshot.won}W / ${snapshot.lost}L of ${snapshot.total_bets}`}
            positive={snapshot.won > snapshot.lost}
          />
          <StatCard
            label="Open"
            value={String(openBets.length)}
            sub={
              openBets.length > 0
                ? `${openBets.reduce((s, b) => s + b.stake_amount, 0).toFixed(0)}€ at stake`
                : "No exposure"
            }
          />
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 mb-10">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="border-t-2 border-gray-100 pt-4 h-20 animate-pulse" />
          ))}
        </div>
      )}

      {/* Chart */}
      <div className="border border-gray-100 rounded-xl p-5 mb-10">
        <p className="text-xs text-gray-400 uppercase tracking-widest font-mono mb-4">
          Bankroll evolution
        </p>
        {chartLoading ? (
          <div className="h-36 animate-pulse bg-gray-50 rounded" />
        ) : (
          <BankrollChart
            events={chartData ?? []}
            initial={snapshot?.initial_balance ?? 0}
          />
        )}
      </div>

      {/* Bets */}
      {loading ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-gray-50 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : !bets || bets.length === 0 ? (
        <p className="text-gray-400 text-sm text-center py-8">
          No bets recorded yet.
        </p>
      ) : (
        <div className="space-y-5">
          {openBets.length > 0 && (
            <section>
              <h2 className="text-xs font-semibold text-blue-600 uppercase tracking-widest font-mono mb-3">
                Open ({openBets.length})
              </h2>
              <div className="space-y-2">
                {openBets.map((b) => (
                  <BetRow key={b.id} bet={b} />
                ))}
              </div>
            </section>
          )}

          {resolvedBets.length > 0 && (
            <section>
              <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest font-mono mb-3">
                Resolved ({resolvedBets.length})
              </h2>
              <div className="space-y-2">
                {resolvedBets.map((b) => (
                  <BetRow key={b.id} bet={b} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
