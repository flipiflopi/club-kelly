from engine.markets.registry import market_registry
from engine.markets.match_result import MatchResultMarket
from engine.markets.over_under import OverUnderMarket
from engine.markets.btts import BTTSMarket

# Auto-register all built-in markets on import
market_registry.register(MatchResultMarket())
market_registry.register(OverUnderMarket(threshold=2.5))
market_registry.register(OverUnderMarket(threshold=1.5))
market_registry.register(OverUnderMarket(threshold=3.5))
market_registry.register(BTTSMarket())

__all__ = ["market_registry"]
