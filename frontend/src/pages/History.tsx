import { api } from "../api/client";
import { usePolling } from "../api/usePolling";

export default function History() {
  const { data: snapshot, loading: snapLoading } = usePolling(
    api.getBankrollSnapshot,
    60_000
  );

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">History & Performance</h1>

      {/* Bankroll summary */}
      {!snapLoading && snapshot && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Stat label="Bankroll" value={`€${snapshot.current_balance.toFixed(2)}`} />
          <Stat
            label="ROI"
            value={`${snapshot.roi_pct >= 0 ? "+" : ""}${snapshot.roi_pct.toFixed(1)}%`}
            positive={snapshot.roi_pct >= 0}
          />
          <Stat label="Bets" value={String(snapshot.total_bets)} />
          <Stat
            label="Win rate"
            value={
              snapshot.total_bets > 0
                ? `${((snapshot.won / snapshot.total_bets) * 100).toFixed(0)}%`
                : "—"
            }
          />
        </div>
      )}

      <p className="text-gray-500 text-sm">
        Historical bet table and bankroll chart coming in the next sprint.
      </p>
    </div>
  );
}

function Stat({
  label,
  value,
  positive,
}: {
  label: string;
  value: string;
  positive?: boolean;
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p
        className={`text-lg font-bold ${
          positive === true
            ? "text-green-400"
            : positive === false
            ? "text-red-400"
            : "text-white"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
