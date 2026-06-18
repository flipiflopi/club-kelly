from engine.markets.base import AbstractMarket


class MarketRegistry:
    """
    Central registry for market modules.
    Lookup by slug; adding a new market requires no changes to existing code.
    """

    def __init__(self) -> None:
        self._markets: dict[str, AbstractMarket] = {}

    def register(self, market: AbstractMarket) -> None:
        if market.slug in self._markets:
            raise ValueError(f"Market already registered: {market.slug}")
        self._markets[market.slug] = market

    def get(self, slug: str) -> AbstractMarket:
        if slug not in self._markets:
            raise KeyError(f"Unknown market: {slug}. Registered: {list(self._markets)}")
        return self._markets[slug]

    def all_slugs(self) -> list[str]:
        return list(self._markets)

    def __contains__(self, slug: str) -> bool:
        return slug in self._markets


market_registry = MarketRegistry()
