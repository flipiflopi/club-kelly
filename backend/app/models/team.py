from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin


class Team(Base, TimestampMixin):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    short_name: Mapped[str] = mapped_column(String(10), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(3), nullable=True)  # ISO 3166-1 alpha-3
    team_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "national" | "club"
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)

    players: Mapped[list["Player"]] = relationship(back_populates="team")  # type: ignore[name-defined]
    model_params: Mapped[list["ModelParams"]] = relationship(back_populates="team")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Team {self.short_name}>"
