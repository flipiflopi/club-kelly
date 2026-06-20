import { Route, Routes, Link } from "react-router-dom";
import Home from "./pages/Home";
import Bets from "./pages/Bets";
import Upcoming from "./pages/Upcoming";
import History from "./pages/History";
import Admin from "./pages/Admin";

function XIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.746l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

function TelegramIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  );
}

export { XIcon, TelegramIcon };

export default function App() {
  return (
    <div className="min-h-screen bg-white text-gray-900">
      <nav className="border-b border-gray-100 px-6 py-4 flex items-center justify-between">
        <Link
          to="/"
          className="font-bold text-base tracking-tight hover:text-green-600 transition-colors"
        >
          Club Kelly
        </Link>
        <div className="flex items-center gap-3">
          <a
            href="https://x.com/ClubKellyBet"
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-400 hover:text-gray-900 transition-colors p-1"
            aria-label="X / Twitter"
          >
            <XIcon />
          </a>
          <a
            href="https://t.me/Club_Kelly"
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-400 hover:text-[#229ED9] transition-colors p-1"
            aria-label="Telegram"
          >
            <TelegramIcon />
          </a>
        </div>
      </nav>

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/apuestas" element={<Bets />} />
        <Route path="/partidos" element={<Upcoming />} />
        <Route path="/historial" element={<History />} />
        <Route path="/admin" element={<Admin />} />
      </Routes>
    </div>
  );
}
