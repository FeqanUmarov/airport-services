from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin
from app.core.database import Base


class Runway(TimestampMixin, Base):
    __tablename__ = "TBL_RUNWAYS"
    __table_args__ = (
        UniqueConstraint("AIR_ID", "DESIGNATOR_1", "DESIGNATOR_2", name="uq_runway_air_designators"),
        CheckConstraint('"LENGTH_M" > 0', name="runway_length_positive"),
        CheckConstraint('"WIDTH_M" > 0', name="runway_width_positive"),
    )

    RUN_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    AIR_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_AIRPORTS.AIR_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    AZE_NAME: Mapped[str] = mapped_column(String(150), nullable=False)
    ENG_NAME: Mapped[str] = mapped_column(String(150), nullable=False)
    DESIGNATOR_1: Mapped[str] = mapped_column(String(10), nullable=False)
    DESIGNATOR_2: Mapped[str] = mapped_column(String(10), nullable=False)
    LENGTH_M: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    WIDTH_M: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    GEOM: Mapped[object] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True),
        nullable=False,
    )
    CENTERLINE_GEOM: Mapped[object] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True),
        nullable=False,
    )
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class RunwayDirection(TimestampMixin, Base):
    __tablename__ = "TBL_RUNWAY_DIRECTIONS"
    __table_args__ = (
        UniqueConstraint("RUN_ID", "DESIGNATOR", name="uq_runway_direction_designator"),
        CheckConstraint(
            '"TRUE_BEARING_DEG" >= 0 AND "TRUE_BEARING_DEG" < 360',
            name="true_bearing_range",
        ),
    )

    RUN_DIR_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    RUN_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_RUNWAYS.RUN_ID", ondelete="CASCADE"), nullable=False, index=True
    )
    DESIGNATOR: Mapped[str] = mapped_column(String(10), nullable=False)
    TRUE_BEARING_DEG: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    THRESHOLD_ELEVATION_M: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    THRESHOLD_GEOM: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False
    )
    SLOPE_PCT: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class RunwayStrip(TimestampMixin, Base):
    __tablename__ = "TBL_RUNWAY_STRIP"
    __table_args__ = (
        CheckConstraint('"LENGTH_M" > 0', name="runway_strip_length_positive"),
        CheckConstraint('"WIDTH_M" > 0', name="runway_strip_width_positive"),
    )

    STRIP_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    RUN_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_RUNWAYS.RUN_ID", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    LENGTH_M: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    WIDTH_M: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    GEOM: Mapped[object] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True), nullable=False
    )
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class RunwayAreaType(Base):
    __tablename__ = "DIC_RUNWAY_AREA_TYPES"

    AREA_TYPE_ID: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    CODE: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    AZE_NAME: Mapped[str] = mapped_column(String(150), nullable=False)
    ENG_NAME: Mapped[str] = mapped_column(String(150), nullable=False)
    DESCRIPTION: Mapped[str | None] = mapped_column(String(500), nullable=True)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class RunwayArea(TimestampMixin, Base):
    __tablename__ = "TBL_RUNWAY_AREAS"
    __table_args__ = (
        UniqueConstraint("RUN_DIR_ID", "AREA_TYPE_ID", name="uq_runway_area_direction_type"),
        CheckConstraint('"LENGTH_M" > 0', name="runway_area_length_positive"),
        CheckConstraint('"WIDTH_M" > 0', name="runway_area_width_positive"),
    )

    RUNWAY_AREA_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    RUN_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_RUNWAYS.RUN_ID", ondelete="CASCADE"), nullable=False, index=True
    )
    RUN_DIR_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_RUNWAY_DIRECTIONS.RUN_DIR_ID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    AREA_TYPE_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_RUNWAY_AREA_TYPES.AREA_TYPE_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    LENGTH_M: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    WIDTH_M: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    GEOM: Mapped[object] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True), nullable=False
    )
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )
