from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Identity, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin
from app.core.database import Base


class DeclaredDistance(TimestampMixin, Base):
    __tablename__ = "TBL_RUNWAY_DECLARED_DISTANCES"
    __table_args__ = (
        CheckConstraint('"TORA_M" > 0', name="declared_distance_tora_positive"),
        CheckConstraint('"TODA_M" > 0', name="declared_distance_toda_positive"),
        CheckConstraint('"ASDA_M" > 0', name="declared_distance_asda_positive"),
        CheckConstraint('"LDA_M" > 0', name="declared_distance_lda_positive"),
        CheckConstraint('"TODA_M" >= "TORA_M"', name="declared_distance_toda_gte_tora"),
        CheckConstraint('"ASDA_M" >= "TORA_M"', name="declared_distance_asda_gte_tora"),
    )

    DECLARED_DISTANCE_ID: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )
    RUN_DIR_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_RUNWAY_DIRECTIONS.RUN_DIR_ID", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    TORA_M: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    TODA_M: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    ASDA_M: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    LDA_M: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
