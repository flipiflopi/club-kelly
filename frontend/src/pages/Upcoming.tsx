import { api } from "../api/client";
import { usePolling } from "../api/usePolling";
import type { Bet, Match, Prediction } from "../types/api";

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

function ProbBar({ value, color = "bg-blue-500" }: { value: number; color?: string }) {
  return (
    <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden w-full">
      <div
        className={`h-full rounded-full transition-all ${color}`}
        style={{ width: `${Math.min(value * 100, 100)}%` }}
      />
    </div>
  );
}

function PredictionRow({
  pred,
  match,
  bet,
}: {
  pred: Prediction;
  match: Match;
  bet?: Bet;
}) {
  const label = outcomeLabel(pred.outcome, match);
  const hasEdge = pred.edge != null && pred.edge >= 0.03;
  const modelPct = (pred.model_probability * 100).toFixed(0);
  const marketPct = pred.market_probability != null
    ? (pred.market_probability * 100).toFixed(0)
    : pred.market_odds != null
    ? (100 / pred.market_odds).toFixed(0)
    : null;

  return (
    <div
      className={`rounded-lg px-3 py-2 ${
        bet
          ? "bg-green-950 border border-green-800/60"
          : hasEdge
          ? "bg-green-950/30 border border-green-900/40"
          : "bg-gray-800/40"
      }`}
    >
      <div className="flex items-center gap-3">
        {/* Outcome label */}
        <span className="w-28 shrink-0 text-sm font-medium truncate">{label}</span>

        {/* Probability bar */}
        <div className="flex-1 min-w-0">
          <ProbBar
            value={pred.model_probability}
            color={hasEdge ? "bg-green-500" : "bg-blue-500"}
          />
        </div>

        {/* Modelo % */}
        <div className="shrink-0 text-right">
          <span className="text-sm font-mono font-semibold text-white">
            {modelPct}%
          </span>
          <span className="text-xs text-gray-500 ml-0.5">modelo</span>
        </div>

        {/* Separador */}
        {marketPct && (
          <>
            <span className="text-gray-600 text-xs shrink-0">vs</span>
            <div className="shrink-0 text-right">
              <span className="text-sm font-mono text-gray-400">
                {marketPct}%
              </span>
              <span className="text-xs text-gray-600 ml-0.5">mercado</span>
            </div>
          </>
        )}

        {/* Cuota */}
        {pred.market_odds != null ? (
          <span className="shrink-0 text-xs text-gray-500 w-12 text-right font-mono">
            @{pred.market_odds.toFixed(2)}
          </span>
        ) : (
          <span className="w-12 shrink-0" />
        )}

        {/* Edge badge */}
        <div className="shrink-0 w-16 text-right">
          {hasEdge ? (
            <span className="text-xs bg-green-800 text-green-300 px-1.5 py-0.5 rounded font-mono">
              +{((pred.edge ?? 0) * 100).toFixed(1)}%
            </span>
          ) : null}
        </div>
      </div>

      {/* Bet info inline */}
      {bet && (
        <div className="mt-1.5 flex items-center gap-2 text-xs text-green-400 pl-1">
          <span>💰</span>
          <span className="font-semibold font-mono">
            {bet.stake_amount.toFixed(2)}€
          </span>
          <span className="text-green-600">
            ({(bet.stake_pct * 100).toFixed(1)}% del bankroll)
          </span>
          <span className="text-green-700">·</span>
          <span className="text-green-600">
            ganancia potencial:{" "}
            <span className="text-green-400 font-mono">
              +{(bet.stake_amount * (bet.decimal_odds - 1)).toFixed(2)}€
            </span>
          </span>
        </div>
      )}
    </div>
  );
}

function MatchCard({ match }: { match: Match }) {
  const date = new Date(match.match_date).toLocaleString("es-ES", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

  // Group predictions by market, sorted by market and then by outcome order
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

  // Map predictionId → bet (for highlighting)
  const betByPredId = new Map<number, Bet>();
  for (const bet of match.bets ?? []) {
    // Match bets to predictions by outcome + market_slug
    const pred = (match.predictions ?? []).find(
      (p) => p.outcome === bet.outcome && p.market_slug === bet.market_slug
    );
    if (pred) betByPredId.set(pred.id, bet);
  }

  const hasAnyBet = (match.bets ?? []).length > 0;

  return (
    <div
      className={`bg-gray-900 rounded-xl p-4 border ${
        hasAnyBet ? "border-green-900" : "border-gray-800"
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-gray-500 uppercase tracking-wider">
          {match.round ?? "—"}
        </span>
        <div className="flex items-center gap-2">
          {match.status === "live" && (
            <span className="text-xs bg-red-600 text-white px-2 py-0.5 rounded-full font-medium animate-pulse">
              EN DIRECTO
            </span>
          )}
          <span className="text-xs text-gray-500">{date}</span>
        </div>
      </div>

      {/* Teams */}
      <div className="flex items-center justify-center gap-3 mb-4">
        <span className="text-base font-bold text-right flex-1 truncate">
          {match.home_team.name}
        </span>
        <span className="text-gray-600 text-sm shrink-0">vs</span>
        <span className="text-base font-bold text-left flex-1 truncate">
          {match.away_team.name}
        </span>
      </div>

      {/* Predictions grouped by market */}
      {byMarket.size > 0 ? (
        <div className="space-y-3">
          {Array.from(byMarket.entries()).map(([marketSlug, preds]) => (
            <div key={marketSlug}>
              <div className="text-xs text-gray-600 uppercase tracking-wider mb-1.5 px-1">
                {MARKET_NAMES[marketSlug] ?? marketSlug}
              </div>
              <div className="space-y-1">
                {preds.map((pred) => (
                  <PredictionRow
                    key={pred.id}
                    pred={pred}
                    match={match}
                    bet={betByPredId.get(pred.id)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-gray-600 text-center py-2">
          Sin predicciones disponibles
        </p>
      )}
    </div>
  );
}

export default function Upcoming() {
  const { data, loading, error } = usePolling(api.getUpcomingMatches, 30_000);

  if (loading) return <p className="text-gray-400">Cargando partidos…</p>;
  if (error) return <p className="text-red-400">Error: {error.message}</p>;
  if (!data || data.length === 0)
    return (
      <p className="text-gray-500 text-center py-12">
        No hay partidos próximos disponibles.
      </p>
    );

  const withBets = data.filter((m) => (m.bets ?? []).length > 0);
  const withoutBets = data.filter((m) => (m.bets ?? []).length === 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Partidos próximos</h1>
        <span className="text-sm text-gray-500">
          {data.length} partidos · {withBets.length} con apuesta
        </span>
      </div>

      {withBets.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-green-400 uppercase tracking-wider mb-3">
            💰 Con apuesta activa
          </h2>
          <div className="space-y-3">
            {withBets.map((m) => (
              <MatchCard key={m.id} match={m} />
            ))}
          </div>
        </section>
      )}

      {withoutBets.length > 0 && (
        <section>
          {withBets.length > 0 && (
            <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">
              Resto de partidos
            </h2>
          )}
          <div className="space-y-3">
            {withoutBets.map((m) => (
              <MatchCard key={m.id} match={m} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
