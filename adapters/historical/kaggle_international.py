"""
Historical match adapter for the Kaggle 'international-football-results' dataset.
Dataset: https://www.kaggle.com/datasets/martj42/international-football-results

CSV columns (standard for this dataset):
  date, home_team, away_team, home_score, away_score, tournament, city, country, neutral

Download and place the CSV at: training/data/results.csv
(File is ~2.5MB for ~47k matches since 1872)
"""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from adapters.base import AbstractHistoricalSource, HistoricalMatchDTO

logger = logging.getLogger(__name__)

DEFAULT_CSV_PATH = Path(__file__).parents[2] / "training" / "data" / "results.csv"


class KaggleInternationalSource(AbstractHistoricalSource):
    """
    Reads the Kaggle international football results CSV.
    Lazily loaded on first call to get_matches().
    """

    def __init__(self, csv_path: Path | str = DEFAULT_CSV_PATH) -> None:
        self._csv_path = Path(csv_path)
        self._df: pd.DataFrame | None = None

    def _load(self) -> pd.DataFrame:
        if not self._csv_path.exists():
            raise FileNotFoundError(
                f"Historical data not found at {self._csv_path}. "
                "Download from Kaggle and place it there: "
                "https://www.kaggle.com/datasets/martj42/international-football-results"
            )
        df = pd.read_csv(self._csv_path, parse_dates=["date"])
        df = df.dropna(subset=["home_score", "away_score"])
        df["home_score"] = df["home_score"].astype(int)
        df["away_score"] = df["away_score"].astype(int)
        df["neutral"] = df["neutral"].fillna(False).astype(bool)
        logger.info("Loaded %d historical international matches from %s", len(df), self._csv_path)
        return df

    def get_matches(
        self,
        team_filter: list[str] | None = None,
        min_date: datetime | None = None,
        max_date: datetime | None = None,
    ) -> list[HistoricalMatchDTO]:
        if self._df is None:
            self._df = self._load()

        df = self._df.copy()

        if min_date:
            df = df[df["date"] >= pd.Timestamp(min_date)]
        if max_date:
            df = df[df["date"] <= pd.Timestamp(max_date)]
        if team_filter:
            team_set = set(team_filter)
            df = df[df["home_team"].isin(team_set) | df["away_team"].isin(team_set)]

        records = []
        for _, row in df.iterrows():
            records.append(HistoricalMatchDTO(
                home_team=row["home_team"],
                away_team=row["away_team"],
                home_goals=int(row["home_score"]),
                away_goals=int(row["away_score"]),
                match_date=row["date"].to_pydatetime(),
                competition=row.get("tournament", ""),
                is_neutral=bool(row["neutral"]),
            ))

        return records
