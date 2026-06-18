import numpy as np

from engine.markets.base import AbstractMarket


class MatchResultMarket(AbstractMarket):
    """1X2 market: home win / draw / away win."""

    @property
    def slug(self) -> str:
        return "match_result"

    @property
    def name(self) -> str:
        return "Match Result (1X2)"

    def calculate(self, score_matrix: np.ndarray) -> dict[str, float]:
        """
        score_matrix[i, j] = P(home=i goals, away=j goals).
        Home wins when i > j  → below-diagonal elements.
        Draw when i == j      → diagonal.
        Away wins when j > i  → above-diagonal elements.
        """
        home_win = float(np.sum(np.tril(score_matrix, -1)))
        draw = float(np.trace(score_matrix))
        away_win = float(np.sum(np.triu(score_matrix, 1)))
        return {"home": home_win, "draw": draw, "away": away_win}
