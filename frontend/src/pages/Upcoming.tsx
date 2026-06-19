import { useState } from "react";
import { api } from "../api/client";
import { usePolling } from "../api/usePolling";
import type { Bet, Match, Prediction } from "../types/api";

// ── Constants ────────────────────────────────────────────────────────────────

const APP_NAME = "La Ventaja";
const APP_SLOGAN = "Predicciones cuantitativas del fútbol";

const MARKET_NAMES: Record<string, string> = {
  match_result: "Resultado 1X2",
  over_under: "Más/Menos goles",
  btts: "Ambos marcan",
};

const OUTCOME_ORDER: Record<string, number> = { home: 0, draw: 1, away: 2 };

function outcomeLabel(outcome: string, match: Match): string {
  if (outcome === "home") return match.home_team.name;
  if (outcome === "away") return match.away_team.name;
  if (outcome === "draw") return "Empate";
  return outcome;
}

// ── Date grouping ─────────────────────────────────────────────────────────────

function dayKey(dateStr: string): string {
  const d = new Date(dateStr);
  const today = new Date();
  const tomorrow = new Date();
  tomorrow.setDate(today.getDate() + 1);

  const isSameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();

  if (isSameDay(d, today)) return "Hoy";
  if (isSameDay(d, tomorrow)) return "Mañana";
  return d.toLocaleDateString("es-ES", {
    weekday: "long",
    day: "numeric",
    month: "short",
  });
}

function groupByDay(matches: Match[]): [string, Match[]][] {
  const map = new Map<string, Match[]>();
  for (const m of matches) {
    const key = dayKey(m.match_date);
    const list = map.get(key) ?? [];
    list.push(m);
    map.set(key, list);
  }
  return Array.from(map.entries());
}

// ── Prediction details (shown when expanded) ──────────────────────────────────

function ProbBar({ value, highlight }: { value: number; highlight: boolean }) {
  return (
    <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden w-full">
      <div
        className={`h-full rounded-full ${highlight ? "bg-green-500" : "bg-blue-500"}`}
        style={{ width: `${Math.min(value * 100, 100)}%` }}
      />
    </div>
  );
}

function PredictionSection({ match }: { match: Match }) {
  const byMarket = new Map<string, Prediction[]>();
  for (const p of match.predictions ?? []) {
    const list = byMarket.get(p.market_slug) ?? [];
    list.push(p);
    byMarket.set(p.market_slug, list);
  }
  for (const list of byMarket.values()) {
    list.sort(
      (a, b) =>
        (OUTCOME_ORDER[a.outcome] ?? 99) - (OUTCOME_ORDER[b.outcome] ?? 99)
    );
  }

  const betByPredKey = new Map<string, Bet>();
  for (const bet of match.bets ?? []) {
    betByPredKey.set(`${bet.market_slug}|${bet.outcome}`, bet);
  }

  if (byMarket.size === 0) {
    return (
      <p className="text-xs text-gray-600 py-2 text-center">
        Sin predicciones disponibles aún
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {Array.from(byMarket.entries()).map(([marketSlug, preds]) => (
        <div key={marketSlug}>
          <p className="text-xs text-gray-600 uppercase tracking-wider mb-2">
            {MARKET_NAMES[marketSlug] ?? marketSlug}
          </p>
          <div className="space-y-1.5">
            {preds.map((pred) => {
              const bet = betByPredKey.get(`${pred.market_slug}|${pred.outcome}`);
              const hasEdge = (pred.edge ?? 0) >= 0.03;
              const marketPct =
                pred.market_probability != null
                  ? (pred.market_probability * 100).toFixed(0)
                  : pred.market_odds != null
                  ? (100 / pred.market_odds).toFixed(0)
                  : null;

              return (
                <div
                  key={pred.id}
                  className={`rounded-lg px-3 py-2 ${
                    bet
                      ? "bg-green-950 border border-green-800/60"
                      : hasEdge
                      ? "bg-green-950/20 border border-green-900/30"
                      : "bg-gray-800/40"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className="w-24 shrink-0 text-sm font-medium truncate">
                      {outcomeLabel(pred.outcome, match)}
                    </span>
                    <div className="flex-1 min-w-0">
                      <ProbBar value={pred.model_probability} highlight={hasEdge} />
                    </div>
                    <span className="text-sm font-mono font-semibold text-white shrink-0">
                      {(pred.model_probability * 100).toFixed(0)}%
                    </span>
                    <span className="text-xs text-gray-500 shrink-0">modelo</span>
                    {marketPct && (
                      <>
                        <span className="text-gray-700 text-xs shrink-0">·</span>
                        <span className="text-sm font-mono text-gray-400 shrink-0">
                          {marketPct}%
                        </span>
                        <span className="text-xs text-gray-600 shrink-0">mercado</span>
                      </>
                    )}
                    {pred.market_odds != null ? (
                      <span className="text-xs text-gray-500 font-mono shrink-0 w-11 text-right">
                        @{pred.market_odds.toFixed(2)}
                      </span>
                    ) : (
                      <span className="w-11 shrink-0" />
                    )}
                    <div className="w-14 shrink-0 text-right">
                      {hasEdge && (
                        <span className="text-xs bg-green-800 text-green-300 px-1.5 py-0.5 rounded font-mono">
                          +{((pred.edge ?? 0) * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>
                  {bet && (
                    <div className="mt-1.5 flex items-center gap-2 text-xs text-green-400 pl-1">
                      <span>💰</span>
                      <span className="font-semibold font-mono">
                        {bet.stake_amount.toFixed(2)}€
                      </span>
                      <span className="text-green-600">
                        ({(bet.stake_pct * 100).toFixed(1)}% bankroll)
                      </span>
                      <span className="text-green-700">·</span>
                      <span className="text-green-600">
                        potencial:{" "}
                        <span className="font-mono text-green-400">
                          +{(bet.stake_amount * (bet.decimal_odds - 1)).toFixed(2)}€
                        </span>
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Match row (collapsed + expanded) ─────────────────────────────────────────

function MatchRow({
  match,
  expanded,
  onToggle,
}: {
  match: Match;
  expanded: boolean;
  onToggle: () => void;
}) {
  const time = new Date(match.match_date).toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
  });

  const hasBet = (match.bets ?? []).length > 0;
  const hasEdge = (match.predictions ?? []).some(
    (p) => (p.edge ?? 0) >= 0.03
  );
  const isLive = match.status === "live";

  return (
    <div
      className={`rounded-lg border transition-colors ${
        expanded
          ? "border-gray-700 bg-gray-900"
          : hasBet
          ? "border-green-900/50 bg-gray-900/60 hover:bg-gray-900"
          : "border-gray-800/50 bg-gray-900/40 hover:bg-gray-900/80"
      }`}
    >
      {/* Clickable header row */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 text-left"
      >
        {/* Chevron */}
        <span
          className={`text-gray-500 text-lg leading-none transition-transform duration-150 ${
            expanded ? "rotate-90" : ""
          }`}
        >
          ›
        </span>

        {/* Bet / edge dot */}
        <span className="w-5 shrink-0 text-center">
          {hasBet ? (
            <span title="Apuesta activa" className="text-sm">💰</span>
          ) : hasEdge ? (
            <span
              title="Ventaja detectada"
              className="inline-block w-2 h-2 rounded-full bg-green-500"
            />
          ) : null}
        </span>

        {/* Home team */}
        <span className="flex-1 font-medium truncate text-sm">
          {match.home_team.name}
        </span>

        {/* Score / vs */}
        <span className="shrink-0 text-xs text-gray-500 w-6 text-center">
          vs
        </span>

        {/* Away team */}
        <span className="flex-1 font-medium truncate text-sm text-right">
          {match.away_team.name}
        </span>

        {/* Live badge or time */}
        <span className="shrink-0 w-20 text-right">
          {isLive ? (
            <span className="text-xs bg-red-600 text-white px-2 py-0.5 rounded-full font-medium animate-pulse">
              EN DIRECTO
            </span>
          ) : (
            <span className="text-sm text-gray-400 font-mono">{time}</span>
          )}
        </span>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-gray-800">
          {match.round && (
            <p className="text-xs text-gray-600 uppercase tracking-wider mb-3">
              {match.round}
            </p>
          )}
          <PredictionSection match={match} />
        </div>
      )}
    </div>
  );
}

// ── Hero header ───────────────────────────────────────────────────────────────

function Hero({
  matchCount,
  betCount,
}: {
  matchCount: number;
  betCount: number;
}) {
  return (
    <div className="mb-8">
      <h1 className="text-3xl font-bold text-white tracking-tight">{APP_NAME}</h1>
      <p className="text-gray-500 mt-1 text-sm">{APP_SLOGAN}</p>
      <div className="flex items-center gap-4 mt-3 text-xs text-gray-600">
        <span>{matchCount} partidos próximos</span>
        {betCount > 0 && (
          <>
            <span>·</span>
            <span className="text-green-600">{betCount} con apuesta activa</span>
          </>
        )}
      </div>
    </div>
  );
}

// ── Day section header ────────────────────────────────────────────────────────

function DayHeader({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 py-1">
      <span className="text-xs font-semibold text-gray-500 uppercase tracking-widest capitalize">
        {label}
      </span>
      <div className="flex-1 h-px bg-gray-800" />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Upcoming() {
  const { data, loading, error } = usePolling(api.getUpcomingMatches, 30_000);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  function toggle(id: number) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (loading)
    return (
      <div className="space-y-2 mt-8">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-12 bg-gray-900 rounded-lg animate-pulse" />
        ))}
      </div>
    );

  if (error)
    return <p className="text-red-400 mt-8">Error: {error.message}</p>;

  const matches = data ?? [];
  const betCount = matches.filter((m) => (m.bets ?? []).length > 0).length;
  const groups = groupByDay(matches);

  return (
    <div>
      <Hero matchCount={matches.length} betCount={betCount} />

      {matches.length === 0 ? (
        <p className="text-gray-500 text-center py-12">
          No hay partidos próximos disponibles.
        </p>
      ) : (
        <div className="space-y-5">
          {groups.map(([day, dayMatches]) => (
            <section key={day}>
              <DayHeader label={day} />
              <div className="space-y-1.5 mt-2">
                {dayMatches.map((m) => (
                  <MatchRow
                    key={m.id}
                    match={m}
                    expanded={expandedIds.has(m.id)}
                    onToggle={() => toggle(m.id)}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
