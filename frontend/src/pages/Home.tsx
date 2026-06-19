import { Link } from "react-router-dom";
import { api } from "../api/client";
import { usePolling } from "../api/usePolling";
import { XIcon, TelegramIcon } from "../App";

function Logo() {
  return (
    <div className="w-20 h-20 rounded-full bg-gray-900 flex items-center justify-center mx-auto">
      <span className="text-white text-2xl font-black tracking-tighter select-none">CK</span>
    </div>
  );
}

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
      className="group block border border-gray-200 rounded-xl p-6 hover:border-gray-900 hover:shadow-md transition-all duration-200"
    >
      <span className="text-xs text-gray-300 font-mono">{number}</span>
      <h3 className="text-lg font-bold mt-2 mb-2 group-hover:text-green-600 transition-colors duration-200">
        {title}
      </h3>
      <p className="text-sm text-gray-500 leading-relaxed mb-5">{description}</p>
      {stat && (
        <p className="text-xs text-gray-400 font-mono mb-5">{stat}</p>
      )}
      <span className="text-sm text-gray-300 group-hover:text-gray-900 transition-colors duration-200 flex items-center gap-1">
        View{" "}
        <span className="inline-block group-hover:translate-x-1 transition-transform duration-200">
          →
        </span>
      </span>
    </Link>
  );
}

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
      {/* Hero */}
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

      <div className="border-t border-gray-100" />

      {/* About */}
      <section className="max-w-2xl mx-auto px-6 py-16">
        <p className="text-xs text-gray-300 uppercase tracking-widest font-mono mb-5">
          About
        </p>
        <div className="space-y-4 text-gray-600 leading-relaxed">
          <p>
            Kelly is a football intelligence system that has studied more than{" "}
            <span className="text-gray-900 font-medium">60,000 international matches</span>.
            Before each game, it analyses both teams in depth and forms a view on
            what the real chances of each outcome are.
          </p>
          <p>
            When those chances are better than what the bookmakers are offering,
            Kelly bets. When they are not, Kelly waits. No chasing losses. No gut
            feelings. No distractions.
          </p>
          <p className="text-sm text-gray-400">
            Paper trading since June 2026 &middot; Starting bankroll:{" "}
            {snapshot
              ? `${snapshot.initial_balance.toLocaleString("en-GB")}€`
              : "10,000€"}
          </p>
        </div>
      </section>

      <div className="border-t border-gray-100" />

      {/* Nav cards */}
      <section className="max-w-2xl mx-auto px-6 py-16">
        <p className="text-xs text-gray-300 uppercase tracking-widest font-mono mb-8">
          Explore
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <NavCard
            to="/apuestas"
            number="01"
            title="Active bets"
            description="Open positions right now. How much is at stake and why."
            stat={
              openBetCount !== null
                ? `${openBetCount} open${openBetStake ? ` · ${openBetStake.toFixed(0)}€ at stake` : ""}`
                : null
            }
          />
          <NavCard
            to="/historial"
            number="02"
            title="History"
            description="Resolved bets, bankroll chart and overall performance."
            stat={
              roi !== null && totalBets !== null
                ? `ROI ${roi >= 0 ? "+" : ""}${roi.toFixed(1)}% · ${totalBets} settled`
                : null
            }
          />
          <NavCard
            to="/partidos"
            number="03"
            title="Upcoming matches"
            description="Every analysed fixture with Kelly's probability breakdown."
            stat={
              upcomingCount !== null
                ? `${upcomingCount} upcoming match${upcomingCount !== 1 ? "es" : ""}`
                : null
            }
          />
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 max-w-2xl mx-auto px-6 py-8 mt-4">
        <p className="text-xs text-gray-300 text-center">
          Club Kelly &middot; Paper trading &middot; For research purposes only
        </p>
      </footer>
    </div>
  );
}
