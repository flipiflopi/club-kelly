export type MatchStatus = "scheduled" | "live" | "finished" | "postponed" | "cancelled";
export type BetStatus = "open" | "won" | "lost" | "void";
export type BankrollEventType = "initial" | "bet_placed" | "bet_resolved" | "adjustment";

export interface Team {
  id: number;
  name: string;
  short_name: string;
  country_code: string | null;
}

export interface Prediction {
  id: number;
  market_slug: string;
  outcome: string;
  model_probability: number;
  market_probability: number | null;
  market_odds: number | null;
  edge: number | null;
}

export interface Bet {
  id: number;
  status: BetStatus;
  stake_amount: number;
  stake_pct: number;
  bankroll_before: number;
  decimal_odds: number;
  profit_loss: number | null;
  outcome: string;
  market_slug: string;
  bankroll_after: number | null;
  kelly_fraction: number;
  reasoning_text: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface Match {
  id: number;
  competition_id: number;
  home_team: Team;
  away_team: Team;
  match_date: string;
  status: MatchStatus;
  home_score: number | null;
  away_score: number | null;
  round: string | null;
  venue: string | null;
  is_neutral: boolean;
  predictions?: Prediction[];
  bets?: Bet[];  // open bets on this match (populated for upcoming matches)
}

export interface BankrollSnapshot {
  current_balance: number;
  initial_balance: number;
  total_profit_loss: number;
  roi_pct: number;
  total_bets: number;
  won: number;
  lost: number;
}

export interface BankrollEvent {
  id: number;
  event_type: BankrollEventType;
  amount_change: number;
  balance_after: number;
  note: string | null;
  created_at: string;
}
