from abc import ABC, abstractmethod

import numpy as np


class AbstractMarket(ABC):
    """
    Each market module knows how to extract outcome probabilities from
    a score matrix. Markets are stateless and receive the matrix from outside.

    To add a new market type: subclass this, implement the two abstract methods,
    then register an instance via market_registry.register().
    """

    @property
    @abstractmethod
    def slug(self) -> str:
        """Unique identifier used in the database and API (e.g. 'over_under_2_5')."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name (e.g. 'Over/Under 2.5 Goals')."""
        ...

    @abstractmethod
    def calculate(self, score_matrix: np.ndarray) -> dict[str, float]:
        """
        Extract probabilities for each outcome.

        Parameters
        ----------
        score_matrix : np.ndarray
            Shape (max_goals+1, max_goals+1). Element [i, j] =
            P(home scores i goals, away scores j goals).

        Returns
        -------
        dict mapping outcome label -> probability.
        Probabilities must sum to 1.0 (within floating-point tolerance).
        """
        ...
