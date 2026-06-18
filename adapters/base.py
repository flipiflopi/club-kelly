"""
Abstract interfaces for all data sources.
Any concrete adapter must implement the relevant ABC.
The rest of the system imports from here — never from a concrete adapter directly.
Swapping data providers = writing a new class + changing one line of wiring code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


# ── Shared data types ─────────────────────────────────────────────────────────


@dataclass
class FixtureDTO:
    external_id: str
    home_team_name: str
    away_team_name: str
    match_date: datetime           # UTC
    status: str                    # "scheduled" | "live" | "finished" | "postponed"
    home_score: int | None
    away_score: int | None
    round: str | None
    venue: str | None
    is_neutral: bool = False


@dataclass
class OddsDTO:
    external_match_id: str
    market_slug: str               # e.g. "match_result", "over_under_2_5"
    outcomes: dict[str, float]     # e.g. {"home": 2.10, "draw": 3.40, "away": 3.20}
    bookmaker: str
    retrieved_at: datetime


@dataclass
class HistoricalMatchDTO:
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    match_date: datetime
    competition: str               # raw competition name from source
    is_neutral: bool = False


# ── Abstract sources ──────────────────────────────────────────────────────────


class AbstractFixtureSource(ABC):
    """Provides upcoming fixtures and live/recent results for one competition."""

    @abstractmethod
    def get_upcoming_fixtures(self) -> list[FixtureDTO]:
        """Return fixtures not yet finished, ordered by date ascending."""
        ...

    @abstractmethod
    def get_recent_results(self, days_back: int = 3) -> list[FixtureDTO]:
        """Return finished matches from the last N days."""
        ...


class AbstractOddsSource(ABC):
    """Provides bookmaker odds for a list of fixtures."""

    @abstractmethod
    def get_odds(
        self,
        external_match_ids: list[str],
        market_slugs: list[str],
    ) -> list[OddsDTO]:
        """Return odds for the requested matches and markets."""
        ...


class AbstractHistoricalSource(ABC):
    """Provides historical match results for initial model training."""

    @abstractmethod
    def get_matches(
        self,
        team_filter: list[str] | None = None,
        min_date: datetime | None = None,
        max_date: datetime | None = None,
    ) -> list[HistoricalMatchDTO]:
        """Return historical matches, optionally filtered."""
        ...
