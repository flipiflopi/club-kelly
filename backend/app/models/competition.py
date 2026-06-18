from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin


class Competition(Base, TimestampMixin):
    """
    A football competition (World Cup, La Liga, Champions League, etc.).
    Adding a new competition = inserting a row here + creating a YAML config file.
    """

    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    competition_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # "national_team" | "club_league" | "club_cup"
    season: Mapped[str] = mapped_column(String(16), nullable=False)  # e.g. "2026"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # mirrors YAML config

    matches: Mapped[list["Match"]] = relationship(back_populates="competition")  # type: ignore[name-defined]
    model_params: Mapped[list["ModelParams"]] = relationship(back_populates="competition")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Competition {self.slug}>"
