import type { Bet, BankrollEvent, BankrollSnapshot, Match } from "../types/api";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  getUpcomingMatches: (competitionSlug?: string) =>
    get<Match[]>(
      `/v1/matches/upcoming${competitionSlug ? `?competition_slug=${competitionSlug}` : ""}`
    ),

  getPastMatches: (offset = 0, limit = 50) =>
    get<Match[]>(`/v1/matches/past?offset=${offset}&limit=${limit}`),

  getOpenBets: () => get<Bet[]>("/v1/bets/open"),

  getBankrollSnapshot: () => get<BankrollSnapshot>("/v1/bankroll/snapshot"),

  getBankrollHistory: (limit = 100) =>
    get<BankrollEvent[]>(`/v1/bankroll/history?limit=${limit}`),
};
