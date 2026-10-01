from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin
from app.core.database import Base


class ObstacleType(Base):
    __tablename__ = "DIC_OBSTACLE_TYPES"

    OBSTACLE_TYPE_ID: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    CODE: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    AZE_NAME: Mapped[str] = mapped_column(String(150), nullable=False)
    ENG_NAME: Mapped[str | None] = mapped_column(String(150), nullable=True)
    DESCRIPTION: Mapped[str | None] = mapped_column(String(500), nullable=True)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class Obstacle(TimestampMixin, Base):
    __tablename__ = "TBL_OBSTACLES"
    __table_args__ = (
        CheckConstraint(
            '"GROUND_ELEVATION_M" IS NOT NULL OR "TOP_ELEVATION_M" IS NOT NULL',
            name="obstacle_has_absolute_elevation",
        ),
        CheckConstraint(
            '"OBJECT_HEIGHT_M" IS NULL OR "OBJECT_HEIGHT_M" >= 0',
            name="object_height_non_negative",
        ),
    )

    OBSTACLE_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    AIR_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_AIRPORTS.AIR_ID", ondelete="CASCADE"), nullable=False, index=True
    )
    DTM_ID: Mapped[int | None] = mapped_column(
        ForeignKey("TBL_DTM_SOURCES.DTM_ID", ondelete="SET NULL"), nullable=True, index=True
    )
    AZE_NAME: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ENG_NAME: Mapped[str | None] = mapped_column(String(255), nullable=True)
    OBSTACLE_TYPE_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_OBSTACLE_TYPES.OBSTACLE_TYPE_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    GROUND_ELEVATION_M: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    OBJECT_HEIGHT_M: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    TOP_ELEVATION_M: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    GEOM: Mapped[object] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True), nullable=False
    )
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class OlsViolation(Base):
    __tablename__ = "TBL_OLS_VIOLATIONS"
    __table_args__ = (
        UniqueConstraint("OBSTACLE_ID", "OLS_SURFACE_ID", name="uq_violation_obstacle_surface"),
        CheckConstraint(
            '"PENETRATION_M" IS NULL OR "PENETRATION_M" >= 0',
            name="penetration_non_negative",
        ),
    )

    VIOLATION_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    OBSTACLE_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_OBSTACLES.OBSTACLE_ID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    OLS_SURFACE_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_OLS_SURFACES.OLS_SURFACE_ID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    SURFACE_ELEVATION_M: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    OBSTACLE_TOP_ELEVATION_M: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    PENETRATION_M: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )
    CREATED_DATE: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    LAST_CHECKED_DATE: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
