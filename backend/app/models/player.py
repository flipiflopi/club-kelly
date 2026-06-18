from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin


class Player(Base, TimestampMixin):
    """
    Player entity. Present in the schema from day 1 even though the MVP
    doesn't use individual player models. Allows adjusting lambda (expected
    goals) based on confirmed lineups once that feature is implemented.
    """

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    position: Mapped[str | None] = mapped_column(String(8), nullable=True)  # GK / DEF / MID / FWD
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    team: Mapped["Team"] = relationship(back_populates="players")  # type: ignore[name-defined]
    match_stats: Mapped[list["PlayerMatchStats"]] = relationship(back_populates="player")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Player {self.name}>"
