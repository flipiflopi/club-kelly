from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin


class Prediction(Base, TimestampMixin):
    """
    Model output for a specific outcome in a specific market for a specific match.
    Created for every evaluated outcome, regardless of whether a bet is placed.
    This is the audit trail for all model decisions.
    """

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    market_type_id: Mapped[int] = mapped_column(ForeignKey("market_types.id"), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)  # "home" / "draw" / "over" / etc.
    model_probability: Mapped[float] = mapped_column(Float, nullable=False)
    market_odds: Mapped[float | None] = mapped_column(Float, nullable=True)      # decimal odds at prediction time
    market_probability: Mapped[float | None] = mapped_column(Float, nullable=True)  # implied prob after vig removal
    edge: Mapped[float | None] = mapped_column(Float, nullable=True)
    closing_odds: Mapped[float | None] = mapped_column(Float, nullable=True)     # for CLV tracking
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)

    match: Mapped["Match"] = relationship(back_populates="predictions")  # type: ignore[name-defined]
    market_type: Mapped["MarketType"] = relationship(back_populates="predictions")  # type: ignore[name-defined]
    simulated_bet: Mapped["SimulatedBet | None"] = relationship(back_populates="prediction")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Prediction match={self.match_id} {self.outcome} p={self.model_probability:.3f}>"
