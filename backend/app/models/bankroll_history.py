import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base


class BankrollEventType(str, enum.Enum):
    INITIAL = "initial"
    BET_PLACED = "bet_placed"
    BET_RESOLVED = "bet_resolved"
    ADJUSTMENT = "adjustment"


class BankrollHistory(Base):
    """
    Append-only ledger of every event that changes the paper bankroll.
    Never updated — only new rows are inserted. Source of truth for ROI tracking.
    """

    __tablename__ = "bankroll_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[BankrollEventType] = mapped_column(
        Enum(BankrollEventType, native_enum=False), nullable=False
    )
    amount_change: Mapped[float] = mapped_column(Float, nullable=False)  # negative = loss
    balance_after: Mapped[float] = mapped_column(Float, nullable=False)
    reference_bet_id: Mapped[int | None] = mapped_column(
        ForeignKey("simulated_bets.id"), nullable=True, index=True
    )
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    bet: Mapped["SimulatedBet | None"] = relationship(back_populates="bankroll_events")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<BankrollHistory {self.event_type} {self.amount_change:+.2f}€ → {self.balance_after:.2f}€>"
