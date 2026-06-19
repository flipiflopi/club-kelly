import { Route, Routes, NavLink } from "react-router-dom";
import Upcoming from "./pages/Upcoming";
import History from "./pages/History";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <nav className="border-b border-gray-800 px-6 py-3 flex gap-6 items-center">
        <span className="font-bold text-lg text-green-400">Club Kelly</span>
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            isActive ? "text-white font-medium" : "text-gray-400 hover:text-white"
          }
        >
          Upcoming
        </NavLink>
        <NavLink
          to="/history"
          className={({ isActive }) =>
            isActive ? "text-white font-medium" : "text-gray-400 hover:text-white"
          }
        >
          History
        </NavLink>
      </nav>
      <main className="max-w-5xl mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<Upcoming />} />
          <Route path="/history" element={<History />} />
        </Routes>
      </main>
    </div>
  );
}
