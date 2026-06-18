import numpy as np

from engine.markets.base import AbstractMarket


class BTTSMarket(AbstractMarket):
    """Both Teams To Score (BTTS) market."""

    @property
    def slug(self) -> str:
        return "btts"

    @property
    def name(self) -> str:
        return "Both Teams To Score"

    def calculate(self, score_matrix: np.ndarray) -> dict[str, float]:
        """
        BTTS Yes: home >= 1 AND away >= 1  → all cells except row 0 and column 0.
        BTTS No:  home == 0 OR away == 0.
        """
        # Slice out cells where both teams scored at least 1
        btts_yes = float(np.sum(score_matrix[1:, 1:]))
        btts_no = 1.0 - btts_yes
        return {"yes": btts_yes, "no": btts_no}
