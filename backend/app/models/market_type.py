from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin


class MarketType(Base, TimestampMixin):
    """
    Registry of available betting markets.
    Each row corresponds to a market module in engine/markets/.
    Populated via a seed script; new markets are added here when the module is registered.
    """

    __tablename__ = "market_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="market_type")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<MarketType {self.slug}>"
