import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin


class MatchStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class Match(Base, TimestampMixin):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False, index=True)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    match_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus), nullable=False, default=MatchStatus.SCHEDULED
    )
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    round: Mapped[str | None] = mapped_column(String(64), nullable=True)   # "Group Stage", "QF", etc.
    venue: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_neutral: Mapped[bool] = mapped_column(default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    competition: Mapped["Competition"] = relationship(back_populates="matches")  # type: ignore[name-defined]
    home_team: Mapped["Team"] = relationship(foreign_keys=[home_team_id])  # type: ignore[name-defined]
    away_team: Mapped["Team"] = relationship(foreign_keys=[away_team_id])  # type: ignore[name-defined]
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="match")  # type: ignore[name-defined]
    player_stats: Mapped[list["PlayerMatchStats"]] = relationship(back_populates="match")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Match {self.home_team_id} vs {self.away_team_id} @ {self.match_date}>"
