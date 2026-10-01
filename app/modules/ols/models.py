from datetime import date
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin
from app.core.database import Base


class StandardType(Base):
    __tablename__ = "DIC_STANDARD_TYPES"

    STANDARD_TYPE_ID: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    CODE: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    AZE_NAME: Mapped[str] = mapped_column(String(150), nullable=False)
    ENG_NAME: Mapped[str] = mapped_column(String(150), nullable=False)
    DESCRIPTION: Mapped[str] = mapped_column(String(255), nullable=False)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class Standard(TimestampMixin, Base):
    __tablename__ = "TBL_STANDARDS"
    __table_args__ = (
        UniqueConstraint("CODE", "EDITION", "AMENDMENT", name="uq_standard_version"),
    )

    STANDARD_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    STANDARD_TYPE_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STANDARD_TYPES.STANDARD_TYPE_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    CODE: Mapped[str] = mapped_column(String(50), nullable=False)
    AZE_NAME: Mapped[str] = mapped_column(String(255), nullable=False)
    ENG_NAME: Mapped[str] = mapped_column(String(255), nullable=False)
    EDITION: Mapped[str | None] = mapped_column(String(50), nullable=True)
    AMENDMENT: Mapped[str | None] = mapped_column(String(50), nullable=True)
    EFFECTIVE_DATE: Mapped[date] = mapped_column(Date, nullable=False)
    DESCRIPTION: Mapped[str | None] = mapped_column(Text, nullable=True)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class OlsSurfaceType(Base):
    __tablename__ = "DIC_OLS_SURFACE_TYPES"

    SURFACE_TYPE_ID: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    CODE: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    AZE_NAME: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ENG_NAME: Mapped[str | None] = mapped_column(String(150), nullable=True)
    DESCRIPTION: Mapped[str | None] = mapped_column(String(500), nullable=True)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class OlsGenerationMethod(Base):
    __tablename__ = "DIC_OLS_GENERATION_METHODS"

    GENERATION_METHOD_ID: Mapped[int] = mapped_column(
        Integer, Identity(), primary_key=True
    )
    CODE: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    AZE_NAME: Mapped[str] = mapped_column(String(150), nullable=False)
    ENG_NAME: Mapped[str] = mapped_column(String(150), nullable=False)
    DESCRIPTION: Mapped[str | None] = mapped_column(String(500), nullable=True)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class StandardOlsSurface(TimestampMixin, Base):
    __tablename__ = "TBL_STANDARD_OLS_SURFACES"
    __table_args__ = (
        UniqueConstraint("STANDARD_ID", "SURFACE_TYPE_ID", name="uq_standard_ols_surface"),
    )

    STANDARD_OLS_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    STANDARD_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_STANDARDS.STANDARD_ID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    SURFACE_TYPE_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_OLS_SURFACE_TYPES.SURFACE_TYPE_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    DESCRIPTION: Mapped[str | None] = mapped_column(String(500), nullable=True)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class Unit(Base):
    __tablename__ = "DIC_UNITS"

    UNIT_ID: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    CODE: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    SYMBOL: Mapped[str | None] = mapped_column(String(20), nullable=True)
    AZE_NAME: Mapped[str] = mapped_column(String(100), nullable=False)
    ENG_NAME: Mapped[str | None] = mapped_column(String(100), nullable=True)
    DESCRIPTION: Mapped[str | None] = mapped_column(String(255), nullable=True)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class OlsParameter(Base):
    __tablename__ = "DIC_OLS_PARAMETERS"

    PARAMETER_ID: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    CODE: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    AZE_NAME: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ENG_NAME: Mapped[str | None] = mapped_column(String(150), nullable=True)
    UNIT_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_UNITS.UNIT_ID", ondelete="RESTRICT"), nullable=False, index=True
    )
    DESCRIPTION: Mapped[str | None] = mapped_column(String(500), nullable=True)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class StandardOlsParameterValue(TimestampMixin, Base):
    __tablename__ = "TBL_STANDARD_OLS_PARAMETER_VALUES"
    __table_args__ = (
        UniqueConstraint(
            "STANDARD_OLS_ID",
            "PARAMETER_ID",
            "SECTION_NO",
            name="uq_standard_ols_parameter_section",
        ),
        CheckConstraint('"SECTION_NO" >= 0', name="section_no_non_negative"),
        CheckConstraint(
            '("NUMERIC_VALUE" IS NOT NULL AND "BOOLEAN_VALUE" IS NULL) OR '
            '("NUMERIC_VALUE" IS NULL AND "BOOLEAN_VALUE" IS NOT NULL)',
            name="exactly_one_parameter_value",
        ),
    )

    PARAM_VALUE_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    STANDARD_OLS_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_STANDARD_OLS_SURFACES.STANDARD_OLS_ID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    PARAMETER_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_OLS_PARAMETERS.PARAMETER_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    SECTION_NO: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    NUMERIC_VALUE: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    BOOLEAN_VALUE: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    DESCRIPTION: Mapped[str | None] = mapped_column(String(500), nullable=True)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class OlsSurface(TimestampMixin, Base):
    __tablename__ = "TBL_OLS_SURFACES"

    OLS_SURFACE_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    STANDARD_OLS_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_STANDARD_OLS_SURFACES.STANDARD_OLS_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    GENERATION_METHOD_ID: Mapped[int] = mapped_column(
        ForeignKey(
            "DIC_OLS_GENERATION_METHODS.GENERATION_METHOD_ID",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    AIR_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_AIRPORTS.AIR_ID", ondelete="CASCADE"), nullable=False, index=True
    )
    RUN_ID: Mapped[int | None] = mapped_column(
        ForeignKey("TBL_RUNWAYS.RUN_ID", ondelete="CASCADE"), nullable=True, index=True
    )
    RUN_DIR_ID: Mapped[int | None] = mapped_column(
        ForeignKey("TBL_RUNWAY_DIRECTIONS.RUN_DIR_ID", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    AZE_NAME: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ENG_NAME: Mapped[str | None] = mapped_column(String(255), nullable=True)
    GEOM: Mapped[object] = mapped_column(
        Geometry(
            geometry_type="GEOMETRYZ",
            srid=4326,
            dimension=3,
            spatial_index=True,
        ),
        nullable=False,
    )
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )
