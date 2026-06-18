from abc import ABC, abstractmethod

import numpy as np


class AbstractPredictionModel(ABC):
    """
    Base class for all prediction models.
    Models receive raw match data and return a score probability matrix.
    They are completely agnostic of competition type and market structure.
    """

    @abstractmethod
    def fit(self, matches: list[dict]) -> None:
        """Estimate model parameters from historical match data."""
        ...

    @abstractmethod
    def predict_score_matrix(
        self,
        home_team: str,
        away_team: str,
        is_neutral: bool = False,
    ) -> np.ndarray:
        """
        Return matrix M where M[i, j] = P(home scores i goals, away scores j goals).
        Shape: (max_goals+1, max_goals+1).
        """
        ...

    @abstractmethod
    def known_teams(self) -> set[str]:
        """Return the set of teams the model has parameters for."""
        ...
