import numpy as np

from engine.markets.base import AbstractMarket


class OverUnderMarket(AbstractMarket):
    """
    Over/Under N.5 goals market.
    Threshold must be a half-integer (1.5, 2.5, 3.5, …) so there is no push.
    """

    def __init__(self, threshold: float = 2.5) -> None:
        if threshold % 1 != 0.5:
            raise ValueError("threshold must be a half-integer (e.g. 2.5)")
        self._threshold = threshold

    @property
    def slug(self) -> str:
        return f"over_under_{self._threshold:.1f}".replace(".", "_")

    @property
    def name(self) -> str:
        return f"Over/Under {self._threshold} Goals"

    @property
    def threshold(self) -> float:
        return self._threshold

    def calculate(self, score_matrix: np.ndarray) -> dict[str, float]:
        """
        Sum all cells where total goals (i + j) > threshold → over.
        Remainder → under.
        """
        n = score_matrix.shape[0]
        total_goals = np.add.outer(np.arange(n), np.arange(n))
        over = float(np.sum(score_matrix[total_goals > self._threshold]))
        under = float(np.sum(score_matrix[total_goals <= self._threshold]))
        return {"over": over, "under": under}
