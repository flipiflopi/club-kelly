import { api } from "../api/client";
import { usePolling } from "../api/usePolling";
import type { Bet, BankrollEvent, BankrollSnapshot } from "../types/api";

const MARKET_NAMES: Record<string, string> = {
  match_result: "Resultado 1X2",
  over_under: "Más/Menos",
  btts: "Ambos marcan",
};

const OUTCOME_LABELS: Record<string, string> = {
  draw: "Empate",
  over: "Más",
  under: "Menos",
  yes: "Sí",
  no: "No",
};

function outcomeLabel(outcome: string, home: string, away: string): string {
  if (outcome === "home") return home;
  if (outcome === "away") return away;
  return OUTCOME_LABELS[outcome] ?? outcome;
}

// ── Bankroll chart (pure SVG, no dependencies) ────────────────────────────────

function BankrollChart({
  events,
  initial,
}: {
  events: BankrollEvent[];
  initial: number;
}) {
  if (events.length === 0) {
    return (
      <div className="h-32 flex items-center justify-center text-gray-600 text-sm">
        Sin movimientos registrados todavía
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
  const color = isUp ? "#22c55e" : "#ef4444";

  // Filled area under line
  const areaPoints = [
    `${sx(0).toFixed(1)},${(H - PY).toFixed(1)}`,
    ...pts,
    `${lastX.toFixed(1)},${(H - PY).toFixed(1)}`,
  ].join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-36">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {/* Filled area */}
      <polygon points={areaPoints} fill="url(#bg)" />

      {/* Baseline at initial bankroll */}
      <line
        x1={PX}
        y1={baseY}
        x2={W - PX}
        y2={baseY}
        stroke="#4b5563"
        strokeWidth="1"
        strokeDasharray="5 3"
      />

      {/* Line chart */}
      <polyline
        points={polyline}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* End dot */}
      <circle cx={lastX} cy={lastY} r="4" fill={color} />

      {/* Y labels */}
      <text x={W - PX - 2} y={PY + 4} textAnchor="end" fill="#6b7280" fontSize="10">
        {maxV.toFixed(0)}€
      </text>
      <text
        x={PX + 2}
        y={baseY - 4}
        textAnchor="start"
        fill="#6b7280"
        fontSize="9"
      >
        Inicial {initial.toFixed(0)}€
      </text>
      <text x={W - PX - 2} y={H - PY - 2} textAnchor="end" fill="#6b7280" fontSize="10">
        {minV.toFixed(0)}€
      </text>
    </svg>
  );
}

// ── Stats cards ───────────────────────────────────────────────────────────────

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
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">{label}</p>
      <p
        className={`text-2xl font-bold ${
          positive === true
            ? "text-green-400"
            : positive === false
            ? "text-red-400"
            : "text-white"
        }`}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-gray-600 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    open: "bg-blue-900/60 text-blue-300 border border-blue-800",
    won: "bg-green-900/60 text-green-300 border border-green-800",
    lost: "bg-red-900/60 text-red-300 border border-red-800",
    void: "bg-gray-800 text-gray-400 border border-gray-700",
  };
  const labels: Record<string, string> = {
    open: "Abierta",
    won: "Ganada",
    lost: "Perdida",
    void: "Nula",
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
      : `+${potential.toFixed(2)}€ potencial`;
  const plPositive = pl != null ? pl >= 0 : undefined;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
      {/* Match + outcome */}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold truncate">
          {bet.home_team_name} vs {bet.away_team_name}
        </div>
        <div className="text-xs text-gray-400 mt-0.5">
          {market} · <span className="text-white">{label}</span>
        </div>
      </div>

      {/* Odds */}
      <div className="shrink-0 text-right">
        <div className="text-sm font-mono text-gray-300">@{bet.decimal_odds.toFixed(2)}</div>
        <div className="text-xs text-gray-600">cuota</div>
      </div>

      {/* Stake */}
      <div className="shrink-0 text-right">
        <div className="text-sm font-mono text-white">{bet.stake_amount.toFixed(2)}€</div>
        <div className="text-xs text-gray-600">{(bet.stake_pct * 100).toFixed(1)}% bankroll</div>
      </div>

      {/* P&L */}
      <div className="shrink-0 text-right w-28">
        <div
          className={`text-sm font-mono font-semibold ${
            plPositive === true
              ? "text-green-400"
              : plPositive === false
              ? "text-red-400"
              : "text-gray-500"
          }`}
        >
          {plStr}
        </div>
        <div className="text-xs text-gray-600">resultado</div>
      </div>

      {/* Status */}
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
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Historial y rendimiento</h1>

      {/* Stats row */}
      {!snapLoading && snapshot ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard
            label="Bankroll actual"
            value={`${snapshot.current_balance.toFixed(2)}€`}
            sub={`Inicial: ${snapshot.initial_balance.toFixed(2)}€`}
          />
          <StatCard
            label="ROI"
            value={`${snapshot.roi_pct >= 0 ? "+" : ""}${snapshot.roi_pct.toFixed(1)}%`}
            sub={`${snapshot.total_profit_loss >= 0 ? "+" : ""}${snapshot.total_profit_loss.toFixed(2)}€`}
            positive={snapshot.roi_pct >= 0}
          />
          <StatCard
            label="Acierto"
            value={
              snapshot.total_bets > 0
                ? `${((snapshot.won / snapshot.total_bets) * 100).toFixed(0)}%`
                : "—"
            }
            sub={`${snapshot.won}G / ${snapshot.lost}P de ${snapshot.total_bets} resueltas`}
            positive={snapshot.won > snapshot.lost}
          />
          <StatCard
            label="Apuestas abiertas"
            value={String(openBets.length)}
            sub={
              openBets.length > 0
                ? `${openBets.reduce((s, b) => s + b.stake_amount, 0).toFixed(2)}€ en juego`
                : "Sin exposición"
            }
          />
        </div>
      ) : (
        <div className="h-24 bg-gray-900 rounded-xl animate-pulse" />
      )}

      {/* Bankroll chart */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <p className="text-sm text-gray-500 mb-3 uppercase tracking-wider text-xs">
          Evolución del bankroll
        </p>
        {chartLoading ? (
          <div className="h-36 animate-pulse bg-gray-800 rounded" />
        ) : (
          <BankrollChart
            events={chartData ?? []}
            initial={snapshot?.initial_balance ?? 1000}
          />
        )}
      </div>

      {/* Bets table */}
      {loading ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-gray-900 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : !bets || bets.length === 0 ? (
        <p className="text-gray-500 text-sm text-center py-8">
          Sin apuestas registradas todavía
        </p>
      ) : (
        <div className="space-y-5">
          {openBets.length > 0 && (
            <section>
              <h2 className="text-xs font-medium text-blue-400 uppercase tracking-wider mb-2">
                Apuestas abiertas ({openBets.length})
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
              <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                Historial resuelto ({resolvedBets.length})
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
