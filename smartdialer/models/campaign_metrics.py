import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class CampaignMetrics(Base):
    __tablename__ = "campaign_metrics"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        primary_key=True,
    )

    answer_rate_ewma: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.05,
    )

    avg_setup_time_sec: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )

    avg_talk_time_sec: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=120.0,
    )

    provider_health: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )

    total_calls: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )

    answered_calls: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )

    failed_calls: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    campaign = relationship(
        "Campaign",
        back_populates="metrics",
    )