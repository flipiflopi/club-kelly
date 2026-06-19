import { Link } from "react-router-dom";
import { api } from "../api/client";
import { usePolling } from "../api/usePolling";
import { XIcon, TelegramIcon } from "../App";

// ── Logo placeholder ──────────────────────────────────────────────────────────
// Replace the contents of this component when the real logo is ready.

function Logo() {
  return (
    <div className="w-20 h-20 rounded-full bg-gray-900 flex items-center justify-center mx-auto">
      <span className="text-white text-2xl font-black tracking-tighter select-none">CK</span>
    </div>
  );
}

// ── Nav card ──────────────────────────────────────────────────────────────────

function NavCard({
  to,
  number,
  title,
  description,
  stat,
}: {
  to: string;
  number: string;
  title: string;
  description: string;
  stat: string | null;
}) {
  return (
    <Link
      to={to}
      className="group block border-t-2 border-gray-200 pt-5 hover:border-gray-900 transition-colors duration-200"
    >
      <span className="text-xs text-gray-300 font-mono">{number}</span>
      <h3 className="text-lg font-bold mt-2 mb-2 group-hover:text-green-600 transition-colors duration-200">
        {title}
      </h3>
      <p className="text-sm text-gray-500 leading-relaxed mb-4">{description}</p>
      {stat && (
        <p className="text-xs text-gray-400 font-mono mb-4">{stat}</p>
      )}
      <span className="text-sm text-gray-300 group-hover:text-gray-900 transition-colors duration-200 flex items-center gap-1">
        Ver más{" "}
        <span className="inline-block group-hover:translate-x-1 transition-transform duration-200">
          →
        </span>
      </span>
    </Link>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Home() {
  const { data: snapshot } = usePolling(api.getBankrollSnapshot, 60_000);
  const { data: upcoming } = usePolling(api.getUpcomingMatches, 60_000);
  const { data: openBets } = usePolling(api.adminGetOpenBets, 60_000);

  const upcomingCount = upcoming?.length ?? null;
  const openBetCount = openBets?.length ?? null;
  const openBetStake = openBets?.reduce((s, b) => s + b.stake_amount, 0) ?? null;
  const roi = snapshot?.roi_pct ?? null;
  const totalBets = snapshot?.total_bets ?? null;

  return (
    <div>
      {/* ── Hero ──────────────────────────────────────────────────────────── */}
      <section className="max-w-2xl mx-auto px-6 pt-24 pb-20 text-center">
        <Logo />

        <h1 className="text-5xl sm:text-6xl font-black tracking-tight mt-8 leading-none">
          Club Kelly
        </h1>

        <p className="text-lg text-gray-400 mt-3 italic">
          I don't guess. I calculate.
        </p>

        <div className="flex items-center justify-center gap-4 mt-7">
          <a
            href="https://x.com/ClubKelly"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-900 transition-colors border border-gray-200 hover:border-gray-400 rounded-full px-4 py-2"
          >
            <XIcon />
            <span>@ClubKelly</span>
          </a>
          <a
            href="https://t.me/Club_Kelly"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-[#229ED9] hover:border-[#229ED9] transition-colors border border-gray-200 rounded-full px-4 py-2"
          >
            <TelegramIcon />
            <span>Club Kelly</span>
          </a>
        </div>
      </section>

      {/* ── Divider ───────────────────────────────────────────────────────── */}
      <div className="border-t border-gray-100" />

      {/* ── About ─────────────────────────────────────────────────────────── */}
      <section className="max-w-2xl mx-auto px-6 py-16">
        <p className="text-xs text-gray-300 uppercase tracking-widest font-mono mb-5">
          Sistema
        </p>
        <div className="space-y-4 text-gray-600 leading-relaxed">
          <p>
            Soy Kelly, un sistema informático entrenado con más de{" "}
            <span className="text-gray-900 font-medium">60.000 partidos</span> de
            fútbol internacional. Analizo cada encuentro aplicando dos modelos
            estadísticos complementarios:{" "}
            <span className="text-gray-900 font-medium">Dixon-Coles</span>, que
            calibra la capacidad ofensiva y defensiva de cada equipo, y{" "}
            <span className="text-gray-900 font-medium">Elo</span>, que mide el
            nivel relativo basado en el historial de resultados.
          </p>
          <p>
            Cuando ambos modelos coinciden en que las probabilidades reales
            superan lo que ofrece el mercado —y el margen es suficiente—,
            apuesto. Cuando no hay ventaja, no hago nada. El tamaño de cada
            apuesta lo determina el{" "}
            <span className="text-gray-900 font-medium">Criterio de Kelly</span>:
            la fórmula matemática que maximiza el crecimiento del capital a largo
            plazo.
          </p>
          <p className="text-sm text-gray-400">
            Paper trading desde junio 2026 · Bankroll inicial:{" "}
            {snapshot
              ? `${snapshot.initial_balance.toLocaleString("es-ES")}€`
              : "10.000€"}
          </p>
        </div>
      </section>

      {/* ── Divider ───────────────────────────────────────────────────────── */}
      <div className="border-t border-gray-100" />

      {/* ── Nav cards ─────────────────────────────────────────────────────── */}
      <section className="max-w-2xl mx-auto px-6 py-16">
        <p className="text-xs text-gray-300 uppercase tracking-widest font-mono mb-10">
          Explorar
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
          <NavCard
            to="/apuestas"
            number="01"
            title="Apuestas activas"
            description="Las apuestas abiertas en este momento. Cuánto se arriesga y por qué."
            stat={
              openBetCount !== null
                ? `${openBetCount} abierta${openBetCount !== 1 ? "s" : ""}${
                    openBetStake ? ` · ${openBetStake.toFixed(0)}€ en juego` : ""
                  }`
                : null
            }
          />
          <NavCard
            to="/historial"
            number="02"
            title="Historial"
            description="Resultados resueltos, evolución del bankroll y estadísticas de rendimiento."
            stat={
              roi !== null && totalBets !== null
                ? `ROI ${roi >= 0 ? "+" : ""}${roi.toFixed(1)}% · ${totalBets} resueltas`
                : null
            }
          />
          <NavCard
            to="/partidos"
            number="03"
            title="Próximos partidos"
            description="Todos los encuentros analizados con las probabilidades calculadas por el modelo."
            stat={
              upcomingCount !== null
                ? `${upcomingCount} partido${upcomingCount !== 1 ? "s" : ""} próximo${upcomingCount !== 1 ? "s" : ""}`
                : null
            }
          />
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────────────────── */}
      <footer className="border-t border-gray-100 max-w-2xl mx-auto px-6 py-8 mt-4">
        <p className="text-xs text-gray-300 text-center">
          Club Kelly · Paper trading · Solo con fines de investigación
        </p>
      </footer>
    </div>
  );
}
