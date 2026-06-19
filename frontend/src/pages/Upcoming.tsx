import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { usePolling } from "../api/usePolling";
import type { Bet, Match, Prediction } from "../types/api";

const MARKET_NAMES: Record<string, string> = {
  match_result: "Match Result 1X2",
  over_under: "Over / Under",
  btts: "Both Teams to Score",
};

const OUTCOME_ORDER: Record<string, number> = { home: 0, draw: 1, away: 2 };

function outcomeLabel(outcome: string, match: Match): string {
  if (outcome === "home") return match.home_team.name;
  if (outcome === "away") return match.away_team.name;
  if (outcome === "draw") return "Draw";
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

  if (isSameDay(d, today)) return "Today";
  if (isSameDay(d, tomorrow)) return "Tomorrow";
  return d.toLocaleDateString("en-GB", {
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

// ── Probability bar ───────────────────────────────────────────────────────────

function ProbBar({ value, highlight }: { value: number; highlight: boolean }) {
  return (
    <div className="h-1 bg-gray-100 rounded-full overflow-hidden w-full">
      <div
        className={`h-full rounded-full ${highlight ? "bg-green-500" : "bg-gray-300"}`}
        style={{ width: `${Math.min(value * 100, 100)}%` }}
      />
    </div>
  );
}

// ── Prediction section ────────────────────────────────────────────────────────

function PredictionSection({ match }: { match: Match }) {
  const byMarket = new Map<string, Prediction[]>();
  for (const p of match.predictions ?? []) {
    const list = byMarket.get(p.market_slug) ?? [];
    list.push(p);
    byMarket.set(p.market_slug, list);
  }
  for (const list of byMarket.values()) {
    list.sort(
      (a, b) => (OUTCOME_ORDER[a.outcome] ?? 99) - (OUTCOME_ORDER[b.outcome] ?? 99)
    );
  }

  const betByPredKey = new Map<string, Bet>();
  for (const bet of match.bets ?? []) {
    betByPredKey.set(`${bet.market_slug}|${bet.outcome}`, bet);
  }

  if (byMarket.size === 0) {
    return (
      <p className="text-xs text-gray-400 py-3 text-center">
        No predictions available yet
      </p>
    );
  }

  return (
    <div className="space-y-5">
      {Array.from(byMarket.entries()).map(([marketSlug, preds]) => (
        <div key={marketSlug}>
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2 font-mono">
            {MARKET_NAMES[marketSlug] ?? marketSlug}
          </p>
          <div className="space-y-2">
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
                  className={`rounded-lg px-3 py-2.5 border ${
                    bet
                      ? "bg-green-50 border-green-200"
                      : hasEdge
                      ? "bg-green-50/50 border-green-100"
                      : "bg-gray-50 border-gray-100"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className="w-24 shrink-0 text-sm font-medium text-gray-900 truncate">
                      {outcomeLabel(pred.outcome, match)}
                    </span>
                    <div className="flex-1 min-w-0">
                      <ProbBar value={pred.model_probability} highlight={hasEdge} />
                    </div>
                    <span className="text-sm font-mono font-bold text-gray-900 shrink-0">
                      {(pred.model_probability * 100).toFixed(0)}%
                    </span>
                    <span className="text-xs text-gray-400 shrink-0">model</span>
                    {marketPct && (
                      <>
                        <span className="text-gray-300 text-xs shrink-0">·</span>
                        <span className="text-sm font-mono text-gray-500 shrink-0">
                          {marketPct}%
                        </span>
                        <span className="text-xs text-gray-400 shrink-0">market</span>
                      </>
                    )}
                    {pred.market_odds != null ? (
                      <span className="text-xs text-gray-400 font-mono shrink-0 w-11 text-right">
                        @{pred.market_odds.toFixed(2)}
                      </span>
                    ) : (
                      <span className="w-11 shrink-0" />
                    )}
                    <div className="w-14 shrink-0 text-right">
                      {hasEdge && (
                        <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-mono font-semibold">
                          +{((pred.edge ?? 0) * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>
                  {bet && (
                    <div className="mt-2 flex items-center gap-2 text-xs text-green-700 pl-1">
                      <span className="font-semibold font-mono">
                        {bet.stake_amount.toFixed(2)}€
                      </span>
                      <span className="text-green-500">
                        ({(bet.stake_pct * 100).toFixed(1)}% bankroll)
                      </span>
                      <span className="text-green-300">·</span>
                      <span className="text-green-600">
                        potential:{" "}
                        <span className="font-mono font-semibold">
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

// ── Match row ─────────────────────────────────────────────────────────────────

function MatchRow({
  match,
  expanded,
  onToggle,
}: {
  match: Match;
  expanded: boolean;
  onToggle: () => void;
}) {
  const time = new Date(match.match_date).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });

  const hasBet = (match.bets ?? []).length > 0;
  const hasEdge = (match.predictions ?? []).some((p) => (p.edge ?? 0) >= 0.03);
  const isLive = match.status === "live";

  return (
    <div
      className={`rounded-lg border transition-colors ${
        expanded
          ? "border-gray-300 bg-white shadow-sm"
          : hasBet
          ? "border-green-200 bg-green-50/30 hover:bg-white hover:shadow-sm"
          : "border-gray-100 bg-white hover:border-gray-200 hover:shadow-sm"
      }`}
    >
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 text-left"
      >
        <span
          className={`text-gray-400 text-lg leading-none transition-transform duration-150 ${
            expanded ? "rotate-90" : ""
          }`}
        >
          ›
        </span>

        <span className="w-5 shrink-0 text-center">
          {hasBet ? (
            <span
              title="Active bet"
              className="inline-block w-2 h-2 rounded-full bg-green-500"
            />
          ) : hasEdge ? (
            <span
              title="Edge detected"
              className="inline-block w-2 h-2 rounded-full bg-gray-300"
            />
          ) : null}
        </span>

        <span className="flex-1 font-medium truncate text-sm text-gray-900">
          {match.home_team.name}
        </span>
        <span className="shrink-0 text-xs text-gray-300 w-6 text-center">vs</span>
        <span className="flex-1 font-medium truncate text-sm text-right text-gray-900">
          {match.away_team.name}
        </span>

        <span className="shrink-0 w-20 text-right">
          {isLive ? (
            <span className="text-xs bg-red-500 text-white px-2 py-0.5 rounded-full font-medium animate-pulse">
              LIVE
            </span>
          ) : (
            <span className="text-sm text-gray-400 font-mono">{time}</span>
          )}
        </span>
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-gray-100">
          {match.round && (
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-3 font-mono">
              {match.round}
            </p>
          )}
          <PredictionSection match={match} />
        </div>
      )}
    </div>
  );
}

// ── Day header ────────────────────────────────────────────────────────────────

function DayHeader({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 py-1">
      <span className="text-xs font-semibold text-gray-400 uppercase tracking-widest font-mono">
        {label}
      </span>
      <div className="flex-1 h-px bg-gray-100" />
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

  const matches = data ?? [];
  const betCount = matches.filter((m) => (m.bets ?? []).length > 0).length;
  const groups = groupByDay(matches);

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <Link
        to="/"
        className="text-xs text-gray-400 hover:text-gray-900 transition-colors flex items-center gap-1 mb-8"
      >
        ← Club Kelly
      </Link>

      <h1 className="text-3xl font-black tracking-tight mb-2">Upcoming matches</h1>
      <div className="flex items-center gap-3 text-sm text-gray-400 mb-10 font-mono">
        <span>{matches.length} matches</span>
        {betCount > 0 && (
          <>
            <span className="text-gray-200">·</span>
            <span className="text-green-600">{betCount} with active bet</span>
          </>
        )}
      </div>

      {loading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div
              key={i}
              className="h-12 bg-gray-50 rounded-lg animate-pulse border border-gray-100"
            />
          ))}
        </div>
      ) : error ? (
        <p className="text-red-500 text-sm">{error.message}</p>
      ) : matches.length === 0 ? (
        <p className="text-gray-400 text-sm text-center py-12">
          No upcoming matches available.
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
