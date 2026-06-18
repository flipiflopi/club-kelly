"""
Fixture adapter for the open-source World Cup 2026 API.
Repository: https://github.com/rezarahimian/worldcup2026

No authentication required. Optionally provide a GitHub token in the
GITHUB_TOKEN env var to avoid GitHub API rate limits (60 req/h anon vs 5000 auth).

API base: https://raw.githubusercontent.com/rezarahimian/worldcup2026/main/data/
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from adapters.base import AbstractFixtureSource, FixtureDTO

logger = logging.getLogger(__name__)

_BASE_URL = "https://raw.githubusercontent.com/rezarahimian/worldcup2026/main/data"

_STATUS_MAP = {
    "scheduled": "scheduled",
    "upcoming": "scheduled",
    "live": "live",
    "in_progress": "live",
    "finished": "finished",
    "completed": "finished",
    "ft": "finished",
    "postponed": "postponed",
    "cancelled": "cancelled",
}


class WorldCup2026FixtureSource(AbstractFixtureSource):
    """
    Reads fixture/result data from the rezarahimian/worldcup2026 GitHub repo.
    Data is a set of JSON files updated by the repo maintainer.
    """

    def __init__(self, github_token: str = "") -> None:
        headers = {"Accept": "application/vnd.github.v3.raw"}
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
        self._client = httpx.Client(headers=headers, timeout=15.0)

    def _fetch_all_matches(self) -> list[dict]:
        url = f"{_BASE_URL}/matches.json"
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch World Cup 2026 fixtures: %s", exc)
            return []

    @staticmethod
    def _parse(raw: dict) -> FixtureDTO | None:
        try:
            date_str = raw.get("date") or raw.get("datetime") or raw.get("match_date")
            if not date_str:
                return None
            match_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

            raw_status = (raw.get("status") or "scheduled").lower()
            status = _STATUS_MAP.get(raw_status, "scheduled")

            home = raw.get("home_team") or {}
            away = raw.get("away_team") or {}

            return FixtureDTO(
                external_id=str(raw.get("id") or raw.get("match_id") or ""),
                home_team_name=home.get("name") or home if isinstance(home, str) else "TBD",
                away_team_name=away.get("name") or away if isinstance(away, str) else "TBD",
                match_date=match_date,
                status=status,
                home_score=raw.get("home_score"),
                away_score=raw.get("away_score"),
                round=raw.get("stage") or raw.get("round"),
                venue=raw.get("venue") or raw.get("stadium"),
                is_neutral=True,  # World Cup matches are at neutral venues
            )
        except Exception as exc:
            logger.warning("Could not parse fixture record %s: %s", raw, exc)
            return None

    def get_upcoming_fixtures(self) -> list[FixtureDTO]:
        all_matches = self._fetch_all_matches()
        now = datetime.now(timezone.utc)
        result = []
        for raw in all_matches:
            fixture = self._parse(raw)
            if fixture and fixture.status in ("scheduled", "live"):
                result.append(fixture)
        result.sort(key=lambda f: f.match_date)
        return result

    def get_recent_results(self, days_back: int = 3) -> list[FixtureDTO]:
        all_matches = self._fetch_all_matches()
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        result = []
        for raw in all_matches:
            fixture = self._parse(raw)
            if fixture and fixture.status == "finished" and fixture.match_date >= cutoff:
                result.append(fixture)
        result.sort(key=lambda f: f.match_date, reverse=True)
        return result
