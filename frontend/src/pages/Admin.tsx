import { useState } from "react";
import { api } from "../api/client";
import { usePolling } from "../api/usePolling";
import type { AdminBet, ActivityEvent } from "../api/client";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number) {
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}€`;
}

const EVENT_LABELS: Record<string, string> = {
  initial: "Inicial",
  bet_placed: "Apuesta",
  bet_resolved: "Resultado",
  adjustment: "Ajuste",
};

const EVENT_COLORS: Record<string, string> = {
  initial: "text-blue-300",
  bet_placed: "text-gray-300",
  bet_resolved: "text-white",
  adjustment: "text-yellow-300",
};

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
    if (!confirm(`¿Anular apuesta #${bet.id} (${bet.home_team} vs ${bet.away_team})?`)) return;
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
      <h2 className="text-xs font-medium text-blue-400 uppercase tracking-wider mb-3">
        Apuestas abiertas ({bets.length})
      </h2>

      {message && (
        <div className="mb-3 text-sm px-3 py-2 rounded bg-gray-800 border border-gray-700">
          {message}
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-12 bg-gray-900 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : bets.length === 0 ? (
        <p className="text-gray-500 text-sm py-4">Sin apuestas abiertas</p>
      ) : (
        <div className="space-y-2">
          {bets.map((b) => (
            <div
              key={b.id}
              className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4"
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold truncate">
                  {b.home_team} vs {b.away_team}
                </div>
                <div className="text-xs text-gray-400 mt-0.5">
                  #{b.id} · {b.market} · {b.outcome} · @{b.decimal_odds.toFixed(2)}
                </div>
              </div>
              <div className="shrink-0 text-right text-sm font-mono">
                {b.stake_amount.toFixed(2)}€
                <span className="text-gray-500 text-xs ml-1">
                  ({(b.stake_pct * 100).toFixed(1)}%)
                </span>
              </div>
              <button
                onClick={() => handleVoid(b)}
                disabled={voiding === b.id}
                className="shrink-0 text-xs px-3 py-1.5 rounded border border-red-800 text-red-400 hover:bg-red-900/30 disabled:opacity-40 transition"
              >
                {voiding === b.id ? "Anulando…" : "Anular"}
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
      setMessage("❌ Introduce un importe válido (positivo o negativo)");
      return;
    }
    if (!confirm(`¿Ajustar bankroll ${parsed >= 0 ? "+" : ""}${parsed.toFixed(2)}€?`)) return;

    setLoading(true);
    setMessage(null);
    try {
      const r = await api.adminAdjustBankroll(parsed, note.trim());
      setMessage(
        `✅ Ajuste aplicado. ${r.balance_before.toFixed(2)}€ → ${r.balance_after.toFixed(2)}€`
      );
      setAmount("");
      setNote("");
      onRefresh();
    } catch (e: unknown) {
      setMessage(`❌ Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <h2 className="text-xs font-medium text-yellow-400 uppercase tracking-wider mb-3">
        Ajuste manual de bankroll
      </h2>

      <form
        onSubmit={handleSubmit}
        className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3 max-w-md"
      >
        <div>
          <label className="text-xs text-gray-400 block mb-1">
            Importe (€) — positivo para añadir, negativo para restar
          </label>
          <input
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="+500.00 ó -200.00"
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-yellow-600"
          />
        </div>
        <div>
          <label className="text-xs text-gray-400 block mb-1">Nota (opcional)</label>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Motivo del ajuste"
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-yellow-600"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="text-sm px-4 py-2 rounded bg-yellow-700 hover:bg-yellow-600 text-white font-medium disabled:opacity-40 transition"
        >
          {loading ? "Aplicando…" : "Aplicar ajuste"}
        </button>
        {message && (
          <p className="text-sm text-gray-300 pt-1">{message}</p>
        )}
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
      <h2 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
        Log de actividad ({events.length} eventos recientes)
      </h2>

      {loading ? (
        <div className="space-y-1">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-8 bg-gray-900 rounded animate-pulse" />
          ))}
        </div>
      ) : events.length === 0 ? (
        <p className="text-gray-500 text-sm py-4">Sin actividad registrada</p>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 uppercase border-b border-gray-800">
                <th className="text-left px-4 py-2">Tipo</th>
                <th className="text-right px-4 py-2">Cambio</th>
                <th className="text-right px-4 py-2">Saldo</th>
                <th className="text-left px-4 py-2 hidden sm:table-cell">Nota</th>
                <th className="text-right px-4 py-2 hidden md:table-cell">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e, idx) => (
                <tr
                  key={e.id}
                  className={`border-b border-gray-800/50 ${idx % 2 === 0 ? "" : "bg-gray-900/40"}`}
                >
                  <td className={`px-4 py-2 font-medium ${EVENT_COLORS[e.event_type] ?? "text-gray-300"}`}>
                    {EVENT_LABELS[e.event_type] ?? e.event_type}
                  </td>
                  <td
                    className={`px-4 py-2 text-right font-mono text-xs ${
                      e.amount_change >= 0 ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {fmt(e.amount_change)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-xs text-gray-200">
                    {e.balance_after.toFixed(2)}€
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-500 hidden sm:table-cell max-w-xs truncate">
                    {e.note ?? "—"}
                  </td>
                  <td className="px-4 py-2 text-right text-xs text-gray-600 hidden md:table-cell whitespace-nowrap">
                    {e.created_at ? new Date(e.created_at).toLocaleString("es-ES") : "—"}
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

export default function Admin() {
  const {
    data: openBets,
    loading: betsLoading,
    refresh: refreshBets,
  } = usePolling(api.adminGetOpenBets, 30_000);

  const {
    data: activity,
    loading: actLoading,
    refresh: refreshActivity,
  } = usePolling(api.adminGetActivity, 30_000);

  function refreshAll() {
    refreshBets();
    refreshActivity();
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Panel de administración</h1>
        <button
          onClick={refreshAll}
          className="text-xs text-gray-400 hover:text-white transition px-3 py-1.5 border border-gray-700 rounded"
        >
          Actualizar
        </button>
      </div>

      <OpenBetsPanel
        bets={openBets ?? []}
        loading={betsLoading}
        onRefresh={refreshAll}
      />

      <AdjustPanel onRefresh={refreshAll} />

      <ActivityPanel events={activity ?? []} loading={actLoading} />
    </div>
  );
}
