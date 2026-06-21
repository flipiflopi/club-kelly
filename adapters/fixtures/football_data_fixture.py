"""
Fixture adapter backed by football-data.org (free tier).

Free tier covers FIFA World Cup (competition code: WC).
Rate limit: 10 requests / minute.
Auth: X-Auth-Token header.

Used as a fallback for get_recent_results when The Odds API scores
endpoint returns 401 (requires paid plan).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from adapters.base import AbstractFixtureSource, FixtureDTO

logger = logging.getLogger(__name__)

_BASE = "https://api.football-data.org/v4"

# Status strings returned by football-data.org
_STATUS_MAP = {
    "SCHEDULED": "scheduled",
    "TIMED": "scheduled",
    "IN_PLAY": "live",
    "PAUSED": "live",
    "FINISHED": "finished",
    "POSTPONED": "postponed",
    "CANCELLED": "postponed",
}


class FootballDataFixtureSource(AbstractFixtureSource):
    """
    Uses football-data.org as a fixture/results source.
    competition_code: e.g. "WC" for FIFA World Cup.
    team_aliases: mapping from football-data.org names to DB names
                  (The Odds API names), defined in the competition YAML.
    """

    def __init__(
        self,
        api_key: str,
        competition_code: str = "WC",
        team_aliases: dict[str, str] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("FOOTBALL_DATA_API_KEY is required for FootballDataFixtureSource")
        self._api_key = api_key
        self._competition_code = competition_code
        self._aliases = team_aliases or {}
        self._client = httpx.Client(
            timeout=15.0,
            headers={"X-Auth-Token": api_key},
        )

    def _normalize(self, name: str) -> str:
        return self._aliases.get(name, name)

    def get_upcoming_fixtures(self) -> list[FixtureDTO]:
        url = f"{_BASE}/competitions/{self._competition_code}/matches"
        try:
            resp = self._client.get(url, params={"status": "SCHEDULED,TIMED,IN_PLAY"})
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("FootballData upcoming fetch failed: %s", exc)
            return []
        return self._parse_response(resp.json())

    def get_recent_results(self, days_back: int = 3) -> list[FixtureDTO]:
        now = datetime.now(timezone.utc)
        date_from = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")
        date_to = now.strftime("%Y-%m-%d")
        url = f"{_BASE}/competitions/{self._competition_code}/matches"
        try:
            resp = self._client.get(
                url,
                params={"status": "FINISHED", "dateFrom": date_from, "dateTo": date_to},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("FootballData results fetch failed: %s", exc)
            return []
        fixtures = self._parse_response(resp.json())
        logger.info("FootballData results: %d finished matches (%s → %s)", len(fixtures), date_from, date_to)
        return fixtures

    def _parse_response(self, data: dict) -> list[FixtureDTO]:
        fixtures = []
        for m in data.get("matches", []):
            try:
                dto = self._parse_match(m)
                if dto:
                    fixtures.append(dto)
            except Exception as exc:
                logger.warning("FootballData: could not parse match %s: %s", m.get("id"), exc)
        return fixtures

    def _parse_match(self, m: dict) -> FixtureDTO | None:
        raw_status = m.get("status", "")
        status = _STATUS_MAP.get(raw_status, "scheduled")

        match_date = datetime.fromisoformat(
            m["utcDate"].replace("Z", "+00:00")
        )

        home_name = self._normalize(m["homeTeam"]["name"])
        away_name = self._normalize(m["awayTeam"]["name"])

        home_score: int | None = None
        away_score: int | None = None
        if status == "finished":
            ft = m.get("score", {}).get("fullTime", {})
            home_score = ft.get("home")
            away_score = ft.get("away")

        stage = m.get("stage", "")
        group = m.get("group", "")
        if group:
            round_name = f"{group.replace('_', ' ').title()}"
        elif stage:
            round_name = stage.replace("_", " ").title()
        else:
            round_name = None

        return FixtureDTO(
            external_id=f"fd_{m['id']}",
            home_team_name=home_name,
            away_team_name=away_name,
            match_date=match_date,
            status=status,
            home_score=home_score,
            away_score=away_score,
            round=round_name,
            venue=None,
            is_neutral=True,
        )
