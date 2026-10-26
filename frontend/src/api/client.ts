import type { Bet, BankrollEvent, BankrollSnapshot, Match } from "../types/api";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

// ── Admin key (kept in this browser only) ─────────────────────────────────────

const ADMIN_KEY_STORAGE = "clubkelly_admin_key";

export function getAdminKey(): string | null {
  try {
    return localStorage.getItem(ADMIN_KEY_STORAGE);
  } catch {
    return null;
  }
}

export function setAdminKey(key: string): void {
  try {
    localStorage.setItem(ADMIN_KEY_STORAGE, key);
  } catch {
    /* storage unavailable — key lives only for this page load */
  }
}

export function clearAdminKey(): void {
  try {
    localStorage.removeItem(ADMIN_KEY_STORAGE);
  } catch {
    /* ignore */
  }
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function authHeaders(path: string): Record<string, string> {
  const key = path.startsWith("/v1/admin") ? getAdminKey() : null;
  return key ? { "X-API-Key": key } : {};
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders(path) });
  if (!res.ok) throw new ApiError(`API error ${res.status}: ${path}`, res.status);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: {
      ...authHeaders(path),
      ...(body != null ? { "Content-Type": "application/json" } : {}),
    },
    body: body != null ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().then((d) => d?.detail ?? res.statusText).catch(() => res.statusText);
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

export type MatchWithOpenBets = {
  id: number;
  home_team: string;
  away_team: string;
  match_date: string;
  status: string;
  home_score: number | null;
  away_score: number | null;
};

export type AdminBet = {
  id: number;
  match_id: number;
  home_team: string;
  away_team: string;
  match_date: string;
  outcome: string;
  market: string;
  stake_amount: number;
  stake_pct: number;
  decimal_odds: number;
  created_at: string;
};

export type ActivityEvent = {
  id: number;
  event_type: string;
  amount_change: number;
  balance_after: number;
  note: string | null;
  created_at: string;
};

export const api = {
  getUpcomingMatches: (competitionSlug?: string) =>
    get<Match[]>(
      `/v1/matches/upcoming${competitionSlug ? `?competition_slug=${competitionSlug}` : ""}`
    ),

  getPastMatches: (offset = 0, limit = 50) =>
    get<Match[]>(`/v1/matches/past?offset=${offset}&limit=${limit}`),

  getAllBets: (status?: string, limit = 100) =>
    get<Bet[]>(`/v1/bets/${status ? `?status=${status}&limit=${limit}` : `?limit=${limit}`}`),

  getOpenBets: () => get<Bet[]>("/v1/bets/open"),

  getBankrollSnapshot: () => get<BankrollSnapshot>("/v1/bankroll/snapshot"),

  getBankrollHistory: (limit = 100) =>
    get<BankrollEvent[]>(`/v1/bankroll/history?limit=${limit}`),

  // Admin
  adminGetOpenBets: () => get<AdminBet[]>("/v1/admin/open-bets"),
  adminVoidBet: (betId: number) =>
    post<{ ok: boolean; bet_id: number; note: string }>(`/v1/admin/bets/${betId}/void`),
  adminAdjustBankroll: (amount: number, note: string) =>
    post<{ ok: boolean; balance_before: number; balance_after: number }>(
      "/v1/admin/bankroll/adjust",
      { amount, note }
    ),
  adminGetActivity: (limit = 50) =>
    get<ActivityEvent[]>(`/v1/admin/activity?limit=${limit}`),
  adminGetMatchesWithOpenBets: () =>
    get<MatchWithOpenBets[]>("/v1/admin/matches-with-open-bets"),
  adminResolveMatch: (matchId: number, homeScore: number, awayScore: number) =>
    post<{ ok: boolean; match_id: number; score: string; bets_resolved: number }>(
      `/v1/admin/matches/${matchId}/resolve`,
      { home_score: homeScore, away_score: awayScore }
    ),
};
