import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin


class BetStatus(str, enum.Enum):
    OPEN = "open"
    WON = "won"
    LOST = "lost"
    VOID = "void"   # match cancelled / postponed


class SimulatedBet(Base, TimestampMixin):
    """
    Paper trade: a bet that would have been placed with a real bookmaker.
    No real money involved. Resolved automatically when the match finishes.
    """

    __tablename__ = "simulated_bets"

    id: Mapped[int] = mapped_column(primary_key=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.id"), nullable=False, unique=True, index=True
    )
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)

    stake_amount: Mapped[float] = mapped_column(Float, nullable=False)     # euros
    stake_pct: Mapped[float] = mapped_column(Float, nullable=False)        # % of bankroll
    bankroll_before: Mapped[float] = mapped_column(Float, nullable=False)  # snapshot at bet time
    kelly_fraction: Mapped[float] = mapped_column(Float, nullable=False)
    decimal_odds: Mapped[float] = mapped_column(Float, nullable=False)

    reasoning_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # from Claude API

    status: Mapped[BetStatus] = mapped_column(
        Enum(BetStatus), nullable=False, default=BetStatus.OPEN
    )
    profit_loss: Mapped[float | None] = mapped_column(Float, nullable=True)  # + win / - loss
    bankroll_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    prediction: Mapped["Prediction"] = relationship(back_populates="simulated_bet")  # type: ignore[name-defined]
    match: Mapped["Match"] = relationship()  # type: ignore[name-defined]
    bankroll_events: Mapped[list["BankrollHistory"]] = relationship(back_populates="bet")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<SimulatedBet id={self.id} {self.status} stake={self.stake_amount:.2f}€>"
