from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base


class EloRating(Base):
    """
    Stores the latest Elo rating for each team.
    Updated whenever the Elo model is retrained (seed or after each result).
    Global across competitions: a team's Elo reflects all international history.
    """

    __tablename__ = "elo_ratings"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"), nullable=False, index=True, unique=True
    )
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    matches_played: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    team: Mapped["Team"] = relationship()  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<EloRating team_id={self.team_id} rating={self.rating:.1f}>"
