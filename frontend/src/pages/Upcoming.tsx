import { api } from "../api/client";
import { usePolling } from "../api/usePolling";
import type { Match } from "../types/api";

function MatchCard({ match }: { match: Match }) {
  const date = new Date(match.match_date).toLocaleString("es-ES", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500">{match.round ?? "—"}</span>
        <span className="text-xs text-gray-500">{date}</span>
      </div>
      <div className="flex items-center justify-center gap-4 text-lg font-semibold">
        <span>{match.home_team.name}</span>
        <span className="text-gray-500 text-sm">vs</span>
        <span>{match.away_team.name}</span>
      </div>
      {match.predictions && match.predictions.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {match.predictions.map((p) => (
            <span
              key={p.id}
              className={`text-xs px-2 py-1 rounded ${
                p.edge && p.edge >= 0.03
                  ? "bg-green-900 text-green-300"
                  : "bg-gray-800 text-gray-400"
              }`}
            >
              {p.outcome} {(p.model_probability * 100).toFixed(0)}%
              {p.edge != null && p.edge >= 0.03 && (
                <span className="ml-1 text-green-400">
                  +{(p.edge * 100).toFixed(1)}%
                </span>
              )}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Upcoming() {
  const { data, loading, error } = usePolling(api.getUpcomingMatches, 30_000);

  if (loading) return <p className="text-gray-400">Loading matches…</p>;
  if (error) return <p className="text-red-400">Error: {error.message}</p>;
  if (!data || data.length === 0)
    return <p className="text-gray-500">No upcoming matches found.</p>;

  return (
    <div className="space-y-3">
      <h1 className="text-xl font-bold mb-4">Upcoming Matches</h1>
      {data.map((m) => (
        <MatchCard key={m.id} match={m} />
      ))}
    </div>
  );
}
