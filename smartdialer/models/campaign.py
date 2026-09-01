import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    max_overdial_cap: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    agents = relationship(
        "Agent",
        back_populates="campaign",
    )

    borrowers = relationship(
        "Borrower",
        back_populates="campaign",
    )

    calls = relationship(
        "Call",
        back_populates="campaign",
    )

    metrics = relationship(
        "CampaignMetrics",
        back_populates="campaign",
        uselist=False,
    )

    __table_args__ = (
        CheckConstraint(
            "mode IN ('PROGRESSIVE', 'PREDICTIVE')",
            name="ck_campaign_mode",
        ),
        CheckConstraint(
            "max_overdial_cap >= 0",
            name="ck_campaign_overdial_cap",
        ),
    )