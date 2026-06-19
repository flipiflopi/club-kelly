"""
Fixture adapter backed by The Odds API events + scores endpoints.

Upcoming fixtures:  GET /v4/sports/{sport}/events
Recent results:     GET /v4/sports/{sport}/scores?daysFrom=N

Both endpoints are available on the free tier.
External IDs from The Odds API match the IDs used by the odds adapter,
so odds lookups can be correlated with fixtures without any extra join.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from adapters.base import AbstractFixtureSource, FixtureDTO

logger = logging.getLogger(__name__)

_BASE = "https://api.the-odds-api.com/v4"


class OddsApiFixtureSource(AbstractFixtureSource):
    """
    Uses The Odds API as the fixture source. The same API key is already
    used for odds, so no new credential is needed.
    """

    def __init__(self, api_key: str, sport_key: str = "soccer_fifa_world_cup") -> None:
        if not api_key:
            raise ValueError("THE_ODDS_API_KEY is required for OddsApiFixtureSource")
        self._api_key = api_key
        self._sport_key = sport_key
        self._client = httpx.Client(timeout=15.0)

    # ── Public interface ──────────────────────────────────────────────────────

    def get_upcoming_fixtures(self) -> list[FixtureDTO]:
        """Return all scheduled/live events for this sport."""
        url = f"{_BASE}/sports/{self._sport_key}/events"
        try:
            resp = self._client.get(url, params={"apiKey": self._api_key, "dateFormat": "iso"})
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("OddsApi events fetch failed: %s", exc)
            return []

        events = resp.json()
        logger.info("OddsApi events: %d events returned for %s", len(events), self._sport_key)

        fixtures = []
        now = datetime.now(timezone.utc)
        for event in events:
            dto = self._parse_event(event)
            if dto:
                fixtures.append(dto)

        fixtures.sort(key=lambda f: f.match_date)
        return fixtures

    def get_recent_results(self, days_back: int = 3) -> list[FixtureDTO]:
        """Return finished matches from the last N days (max 3 on free tier)."""
        days_back = min(days_back, 3)  # free tier cap
        url = f"{_BASE}/sports/{self._sport_key}/scores"
        try:
            resp = self._client.get(
                url,
                params={
                    "apiKey": self._api_key,
                    "dateFormat": "iso",
                    "daysFrom": days_back,
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("OddsApi scores fetch failed: %s", exc)
            return []

        events = resp.json()
        logger.info("OddsApi scores: %d events returned", len(events))

        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        fixtures = []
        for event in events:
            if not event.get("completed"):
                continue
            dto = self._parse_event(event)
            if dto and dto.match_date >= cutoff:
                fixtures.append(dto)

        fixtures.sort(key=lambda f: f.match_date, reverse=True)
        return fixtures

    # ── Private helpers ───────────────────────────────────────────────────────

    def _parse_event(self, event: dict) -> FixtureDTO | None:
        try:
            match_date = datetime.fromisoformat(
                event["commence_time"].replace("Z", "+00:00")
            )
            completed = event.get("completed", False)

            home_score: int | None = None
            away_score: int | None = None
            if completed and event.get("scores"):
                scores_by_team: dict[str, int] = {}
                for s in event["scores"]:
                    try:
                        scores_by_team[s["name"]] = int(s["score"])
                    except (KeyError, ValueError):
                        pass
                home_team_name = event["home_team"]
                away_team_name = event["away_team"]
                home_score = scores_by_team.get(home_team_name)
                away_score = scores_by_team.get(away_team_name)

            now = datetime.now(timezone.utc)
            if completed:
                status = "finished"
            elif match_date <= now:
                status = "live"
            else:
                status = "scheduled"

            return FixtureDTO(
                external_id=event["id"],
                home_team_name=event["home_team"],
                away_team_name=event["away_team"],
                match_date=match_date,
                status=status,
                home_score=home_score,
                away_score=away_score,
                round=None,
                venue=None,
                is_neutral=True,
            )
        except Exception as exc:
            logger.warning("Could not parse OddsApi event %s: %s", event.get("id"), exc)
            return None
