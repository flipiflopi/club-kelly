"""
Odds adapter for The Odds API (https://the-odds-api.com).
Free tier: 500 requests/month.

Strategy to stay within the free limit for the World Cup:
  - Fetch ALL upcoming soccer/football odds in ONE API call per request
  - Cache response in memory for 2 hours before re-fetching
  - n8n should trigger sync-odds at most every 2 hours

Market slug mapping (The Odds API key → our slug):
  h2h         → match_result
  totals      → over_under_X_X  (The Odds API separates by line)
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from adapters.base import AbstractOddsSource, OddsDTO

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.the-odds-api.com/v4"
_SPORT_KEY = "soccer_fifa_world_cup"  # The Odds API key for World Cup 2026


class TheOddsApiSource(AbstractOddsSource):
    """
    Fetches odds from The Odds API with in-memory caching to preserve the
    monthly request budget.
    """

    def __init__(self, api_key: str, cache_ttl_seconds: int = 7200) -> None:
        if not api_key:
            raise ValueError("THE_ODDS_API_KEY is required")
        self._api_key = api_key
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache: list[OddsDTO] = []
        self._cache_at: datetime | None = None

    def _cache_is_fresh(self) -> bool:
        if self._cache_at is None:
            return False
        return datetime.now(timezone.utc) - self._cache_at < self._cache_ttl

    def _fetch_h2h(self) -> list[OddsDTO]:
        """Fetch 1X2 (head-to-head) odds for all upcoming matches."""
        resp = httpx.get(
            f"{_BASE_URL}/sports/{_SPORT_KEY}/odds",
            params={
                "apiKey": self._api_key,
                "regions": "eu",
                "markets": "h2h",
                "oddsFormat": "decimal",
            },
            timeout=15.0,
        )
        resp.raise_for_status()

        remaining = resp.headers.get("x-requests-remaining", "?")
        logger.info("The Odds API requests remaining this month: %s", remaining)

        result: list[OddsDTO] = []
        retrieved_at = datetime.now(timezone.utc)

        for event in resp.json():
            for bookmaker in event.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    if market["key"] != "h2h":
                        continue
                    outcomes = {o["name"]: o["price"] for o in market["outcomes"]}
                    # Map "Home" / "Draw" / "Away" to our slugs
                    mapped = {
                        "home": outcomes.get(event.get("home_team", ""), 0.0) or next(
                            (v for k, v in outcomes.items() if k not in ("Draw",)), 0.0
                        ),
                        "draw": outcomes.get("Draw", 0.0),
                        "away": outcomes.get(event.get("away_team", ""), 0.0),
                    }
                    result.append(OddsDTO(
                        external_match_id=event["id"],
                        market_slug="match_result",
                        outcomes=mapped,
                        bookmaker=bookmaker["key"],
                        retrieved_at=retrieved_at,
                    ))
                    break  # take first bookmaker only
                break

        return result

    def _refresh_cache(self) -> None:
        try:
            self._cache = self._fetch_h2h()
            self._cache_at = datetime.now(timezone.utc)
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch odds: %s", exc)
            # Keep stale cache rather than crashing

    def get_odds(
        self,
        external_match_ids: list[str],
        market_slugs: list[str],
    ) -> list[OddsDTO]:
        if not self._cache_is_fresh():
            self._refresh_cache()

        id_set = set(external_match_ids)
        slug_set = set(market_slugs)
        return [
            o for o in self._cache
            if (not id_set or o.external_match_id in id_set)
            and (not slug_set or o.market_slug in slug_set)
        ]
