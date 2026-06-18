from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin


class PlayerMatchStats(Base, TimestampMixin):
    """
    Per-player statistics for a match.
    Present from day 1 in the schema even though the MVP prediction engine
    doesn't yet consume individual player features. When player-level models
    are implemented, the data will already be here.
    """

    __tablename__ = "player_match_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)

    minutes_played: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goals: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assists: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    yellow_cards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    red_cards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shots_on_target: Mapped[int | None] = mapped_column(Integer, nullable=True)

    match: Mapped["Match"] = relationship(back_populates="player_stats")  # type: ignore[name-defined]
    player: Mapped["Player"] = relationship(back_populates="match_stats")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<PlayerMatchStats player={self.player_id} match={self.match_id}>"
