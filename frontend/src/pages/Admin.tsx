import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api, clearAdminKey, getAdminKey, setAdminKey } from "../api/client";
import { usePolling } from "../api/usePolling";
import type { AdminBet, ActivityEvent, MatchWithOpenBets } from "../api/client";

function fmt(n: number) {
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}€`;
}

const EVENT_LABELS: Record<string, string> = {
  initial: "Initial",
  bet_placed: "Bet",
  bet_resolved: "Result",
  adjustment: "Adjustment",
};

// ── Resolve match ──────────────────────────────────────────────────────────────

function ResolveMatchPanel({
  matches,
  loading,
  onRefresh,
}: {
  matches: MatchWithOpenBets[];
  loading: boolean;
  onRefresh: () => void;
}) {
  const [scores, setScores] = useState<Record<number, { home: string; away: string }>>({});
  const [resolving, setResolving] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  function setScore(id: number, side: "home" | "away", val: string) {
    setScores((prev) => ({ ...prev, [id]: { ...prev[id], [side]: val } }));
  }

  async function handleResolve(m: MatchWithOpenBets) {
    const s = scores[m.id];
    const home = parseInt(s?.home ?? "");
    const away = parseInt(s?.away ?? "");
    if (isNaN(home) || isNaN(away)) {
      setMessage("Enter both scores before resolving.");
      return;
    }
    if (!confirm(`Set ${m.home_team} ${home}-${away} ${m.away_team} and resolve bets?`)) return;
    setResolving(m.id);
    setMessage(null);
    try {
      const r = await api.adminResolveMatch(m.id, home, away);
      setMessage(`✅ Match resolved ${r.score} — ${r.bets_resolved} bet(s) settled`);
      onRefresh();
    } catch (e: unknown) {
      setMessage(`❌ ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setResolving(null);
    }
  }

  if (!loading && matches.length === 0) return null;

  return (
    <section>
      <h2 className="text-xs font-semibold text-orange-500 uppercase tracking-widest font-mono mb-1">
        Resolve matches manually
      </h2>
      <p className="text-xs text-gray-400 mb-4">
        The Odds API free tier does not include results. Enter scores to settle open bets.
      </p>

      {message && (
        <div className="mb-4 text-sm px-3 py-2 rounded border border-gray-200 text-gray-700 bg-gray-50">
          {message}
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="h-12 bg-gray-50 rounded-lg animate-pulse border border-gray-100" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {matches.map((m) => {
            const d = new Date(m.match_date).toLocaleDateString("en-GB", {
              day: "numeric", month: "short",
            });
            return (
              <div
                key={m.id}
                className="border border-orange-100 rounded-lg px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-3"
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-gray-900 truncate">
                    {m.home_team} vs {m.away_team}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">{d} · {m.status}</div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <input
                    type="number"
                    min="0"
                    placeholder="H"
                    value={scores[m.id]?.home ?? ""}
                    onChange={(e) => setScore(m.id, "home", e.target.value)}
                    className="w-14 border border-gray-200 rounded px-2 py-1.5 text-center text-sm font-mono focus:outline-none focus:border-gray-900"
                  />
                  <span className="text-gray-300 font-bold">–</span>
                  <input
                    type="number"
                    min="0"
                    placeholder="A"
                    value={scores[m.id]?.away ?? ""}
                    onChange={(e) => setScore(m.id, "away", e.target.value)}
                    className="w-14 border border-gray-200 rounded px-2 py-1.5 text-center text-sm font-mono focus:outline-none focus:border-gray-900"
                  />
                  <button
                    onClick={() => handleResolve(m)}
                    disabled={resolving === m.id}
                    className="text-xs px-3 py-1.5 rounded bg-orange-500 text-white hover:bg-orange-600 disabled:opacity-40 transition font-medium"
                  >
                    {resolving === m.id ? "Resolving…" : "Resolve"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

// ── Open-bet table ─────────────────────────────────────────────────────────────

function OpenBetsPanel({
  bets,
  loading,
  onRefresh,
}: {
  bets: AdminBet[];
  loading: boolean;
  onRefresh: () => void;
}) {
  const [voiding, setVoiding] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function handleVoid(bet: AdminBet) {
    if (!confirm(`Void bet #${bet.id} (${bet.home_team} vs ${bet.away_team})?`)) return;
    setVoiding(bet.id);
    setMessage(null);
    try {
      const r = await api.adminVoidBet(bet.id);
      setMessage(`✅ ${r.note}`);
      onRefresh();
    } catch (e: unknown) {
      setMessage(`❌ Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setVoiding(null);
    }
  }

  return (
    <section>
      <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest font-mono mb-4">
        Open bets ({bets.length})
      </h2>

      {message && (
        <div className="mb-4 text-sm px-3 py-2 rounded border border-gray-200 text-gray-700 bg-gray-50">
          {message}
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-12 bg-gray-50 rounded-lg animate-pulse border border-gray-100"
            />
          ))}
        </div>
      ) : bets.length === 0 ? (
        <p className="text-gray-400 text-sm py-4">No open bets.</p>
      ) : (
        <div className="space-y-2">
          {bets.map((b) => (
            <div
              key={b.id}
              className="border border-gray-100 rounded-lg px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4"
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-gray-900 truncate">
                  {b.home_team} vs {b.away_team}
                </div>
                <div className="text-xs text-gray-400 mt-0.5">
                  #{b.id} · {b.market} · {b.outcome} · @{b.decimal_odds.toFixed(2)}
                </div>
              </div>
              <div className="shrink-0 text-right text-sm font-mono text-gray-900">
                {b.stake_amount.toFixed(2)}€
                <span className="text-gray-400 text-xs ml-1">
                  ({(b.stake_pct * 100).toFixed(1)}%)
                </span>
              </div>
              <button
                onClick={() => handleVoid(b)}
                disabled={voiding === b.id}
                className="shrink-0 text-xs px-3 py-1.5 rounded border border-red-200 text-red-500 hover:bg-red-50 disabled:opacity-40 transition"
              >
                {voiding === b.id ? "Voiding…" : "Void"}
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

// ── Bankroll adjust ────────────────────────────────────────────────────────────

function AdjustPanel({ onRefresh }: { onRefresh: () => void }) {
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = parseFloat(amount);
    if (isNaN(parsed) || parsed === 0) {
      setMessage("Enter a valid amount (positive or negative).");
      return;
    }
    if (!confirm(`Adjust bankroll ${parsed >= 0 ? "+" : ""}${parsed.toFixed(2)}€?`)) return;

    setLoading(true);
    setMessage(null);
    try {
      const r = await api.adminAdjustBankroll(parsed, note.trim());
      setMessage(
        `Adjustment applied. ${r.balance_before.toFixed(2)}€ → ${r.balance_after.toFixed(2)}€`
      );
      setAmount("");
      setNote("");
      onRefresh();
    } catch (e: unknown) {
      setMessage(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest font-mono mb-4">
        Manual bankroll adjustment
      </h2>

      <form
        onSubmit={handleSubmit}
        className="border border-gray-100 rounded-xl p-5 space-y-3 max-w-md"
      >
        <div>
          <label className="text-xs text-gray-400 block mb-1">
            Amount (€) — positive to add, negative to subtract
          </label>
          <input
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="+500.00 or -200.00"
            className="w-full border border-gray-200 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-gray-900 transition-colors"
          />
        </div>
        <div>
          <label className="text-xs text-gray-400 block mb-1">Note (optional)</label>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Reason for adjustment"
            className="w-full border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:border-gray-900 transition-colors"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="text-sm px-4 py-2 rounded bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-40 transition font-medium"
        >
          {loading ? "Applying…" : "Apply adjustment"}
        </button>
        {message && <p className="text-sm text-gray-600 pt-1">{message}</p>}
      </form>
    </section>
  );
}

// ── Activity log ───────────────────────────────────────────────────────────────

function ActivityPanel({
  events,
  loading,
}: {
  events: ActivityEvent[];
  loading: boolean;
}) {
  return (
    <section>
      <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest font-mono mb-4">
        Activity log ({events.length} events)
      </h2>

      {loading ? (
        <div className="space-y-1">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-8 bg-gray-50 rounded animate-pulse" />
          ))}
        </div>
      ) : events.length === 0 ? (
        <p className="text-gray-400 text-sm py-4">No activity recorded.</p>
      ) : (
        <div className="border border-gray-100 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-400 uppercase border-b border-gray-100 font-mono">
                <th className="text-left px-4 py-2">Type</th>
                <th className="text-right px-4 py-2">Change</th>
                <th className="text-right px-4 py-2">Balance</th>
                <th className="text-left px-4 py-2 hidden sm:table-cell">Note</th>
                <th className="text-right px-4 py-2 hidden md:table-cell">Date</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e, idx) => (
                <tr
                  key={e.id}
                  className={`border-b border-gray-50 ${idx % 2 === 0 ? "" : "bg-gray-50/50"}`}
                >
                  <td className="px-4 py-2 text-gray-700 font-medium">
                    {EVENT_LABELS[e.event_type] ?? e.event_type}
                  </td>
                  <td
                    className={`px-4 py-2 text-right font-mono text-xs font-semibold ${
                      e.amount_change >= 0 ? "text-green-600" : "text-red-500"
                    }`}
                  >
                    {fmt(e.amount_change)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-xs text-gray-900">
                    {e.balance_after.toFixed(2)}€
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-400 hidden sm:table-cell max-w-xs truncate">
                    {e.note ?? "—"}
                  </td>
                  <td className="px-4 py-2 text-right text-xs text-gray-400 hidden md:table-cell whitespace-nowrap">
                    {e.created_at
                      ? new Date(e.created_at).toLocaleString("en-GB")
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

// ── Key gate ───────────────────────────────────────────────────────────────────

function AdminLogin({ onLogin, error }: { onLogin: () => void; error: string | null }) {
  const [key, setKey] = useState("");
  const [checking, setChecking] = useState(false);
  const [message, setMessage] = useState<string | null>(error);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!key.trim()) return;
    setChecking(true);
    setMessage(null);
    setAdminKey(key.trim());
    try {
      await api.adminGetActivity(1);
      onLogin();
    } catch (err: unknown) {
      clearAdminKey();
      if (err instanceof ApiError && err.status === 401) setMessage("Invalid key.");
      else if (err instanceof ApiError && err.status === 503) setMessage("Admin API is disabled on the server (ADMIN_API_KEY not set).");
      else setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="max-w-sm mx-auto px-6 py-24">
      <Link
        to="/"
        className="text-xs text-gray-400 hover:text-gray-900 transition-colors flex items-center gap-1 mb-8"
      >
        ← Club Kelly
      </Link>
      <h1 className="text-3xl font-black tracking-tight mb-6">Admin</h1>
      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          type="password"
          autoComplete="current-password"
          placeholder="Admin API key"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          className="w-full border border-gray-200 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-gray-900"
        />
        <button
          type="submit"
          disabled={checking || !key.trim()}
          className="w-full text-sm px-3 py-2 rounded bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-40 transition font-medium"
        >
          {checking ? "Checking…" : "Unlock"}
        </button>
        {message && <p className="text-xs text-red-500">{message}</p>}
      </form>
    </div>
  );
}

export default function Admin() {
  const [authed, setAuthed] = useState(() => getAdminKey() !== null);
  const [error, setError] = useState<string | null>(null);

  if (!authed) return <AdminLogin onLogin={() => setAuthed(true)} error={error} />;

  return (
    <AdminDashboard
      onLogout={(reason) => {
        clearAdminKey();
        setError(reason);
        setAuthed(false);
      }}
    />
  );
}

function AdminDashboard({ onLogout }: { onLogout: (reason: string | null) => void }) {
  const {
    data: openBets,
    loading: betsLoading,
    error: betsError,
    refresh: refreshBets,
  } = usePolling(api.adminGetOpenBets, 30_000);

  useEffect(() => {
    if (betsError instanceof ApiError && (betsError.status === 401 || betsError.status === 503)) {
      onLogout("Your saved key is no longer valid.");
    }
  }, [betsError, onLogout]);

  const {
    data: pendingMatches,
    loading: pendingLoading,
    refresh: refreshPending,
  } = usePolling(api.adminGetMatchesWithOpenBets, 30_000);

  const {
    data: activity,
    loading: actLoading,
    refresh: refreshActivity,
  } = usePolling(api.adminGetActivity, 30_000);

  function refreshAll() {
    refreshBets();
    refreshPending();
    refreshActivity();
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <Link
        to="/"
        className="text-xs text-gray-400 hover:text-gray-900 transition-colors flex items-center gap-1 mb-8"
      >
        ← Club Kelly
      </Link>

      <div className="flex items-center justify-between mb-10">
        <h1 className="text-3xl font-black tracking-tight">Admin</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={refreshAll}
            className="text-xs text-gray-400 hover:text-gray-900 transition-colors px-3 py-1.5 border border-gray-200 rounded hover:border-gray-400"
          >
            Refresh
          </button>
          <button
            onClick={() => onLogout(null)}
            className="text-xs text-gray-400 hover:text-gray-900 transition-colors px-3 py-1.5 border border-gray-200 rounded hover:border-gray-400"
          >
            Lock
          </button>
        </div>
      </div>

      <div className="space-y-10">
        <ResolveMatchPanel
          matches={pendingMatches ?? []}
          loading={pendingLoading}
          onRefresh={refreshAll}
        />
        <OpenBetsPanel
          bets={openBets ?? []}
          loading={betsLoading}
          onRefresh={refreshAll}
        />
        <AdjustPanel onRefresh={refreshAll} />
        <ActivityPanel events={activity ?? []} loading={actLoading} />
      </div>
    </div>
  );
}
