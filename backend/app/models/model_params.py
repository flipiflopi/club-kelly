from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base


class ModelParams(Base):
    """
    Stores the latest fitted Dixon-Coles parameters per team per competition.
    A new row is inserted every time the model is re-fitted (after each new result).
    Query the latest row per (competition_id, team_id) to get current parameters.
    """

    __tablename__ = "model_params"

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    attack_strength: Mapped[float] = mapped_column(Float, nullable=False)
    defense_strength: Mapped[float] = mapped_column(Float, nullable=False)
    home_advantage: Mapped[float] = mapped_column(Float, nullable=False)
    rho: Mapped[float] = mapped_column(Float, nullable=False)
    matches_used: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    competition: Mapped["Competition"] = relationship(back_populates="model_params")  # type: ignore[name-defined]
    team: Mapped["Team"] = relationship(back_populates="model_params")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<ModelParams team={self.team_id} competition={self.competition_id} at={self.computed_at}>"
