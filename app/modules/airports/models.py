from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
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


class Status(Base):
    __tablename__ = "DIC_STATUS"

    STATUS_ID: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    AZE_NAME: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    ENG_NAME: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    DESCRIPTION: Mapped[str] = mapped_column(String(255), nullable=False)


class IcaoCode(Base):
    __tablename__ = "DIC_ICAO_CODES"

    ICAO_ID: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    ICAO_CODE: Mapped[str] = mapped_column(String(4), nullable=False, unique=True)
    DESCRIPTION: Mapped[str] = mapped_column(String(255), nullable=False)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


class Country(Base):
    __tablename__ = "DIC_COUNTRIES"

    COUNTRY_ID: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    AZE_NAME: Mapped[str] = mapped_column(String(150), nullable=False)
    ENG_NAME: Mapped[str] = mapped_column(String(150), nullable=False)
    ISO_CODE: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


class City(Base):
    __tablename__ = "DIC_CITIES"
    __table_args__ = (
        UniqueConstraint("COUNTRY_ID", "ENG_NAME", name="uq_city_country_eng_name"),
    )

    CITY_ID: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    COUNTRY_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_COUNTRIES.COUNTRY_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    AZE_NAME: Mapped[str] = mapped_column(String(150), nullable=False)
    ENG_NAME: Mapped[str] = mapped_column(String(150), nullable=False)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


class Airport(TimestampMixin, Base):
    __tablename__ = "TBL_AIRPORTS"

    AIR_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    ICAO_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_ICAO_CODES.ICAO_ID", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    IATA_CODE: Mapped[str | None] = mapped_column(String(3), nullable=True, unique=True)
    AZE_NAME: Mapped[str] = mapped_column(String(255), nullable=False)
    ENG_NAME: Mapped[str] = mapped_column(String(255), nullable=False)
    COUNTRY_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_COUNTRIES.COUNTRY_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    CITY_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_CITIES.CITY_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ELEVATION_M: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    ARP_GEOM: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    BOUNDARY_GEOM: Mapped[object] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True),
        nullable=False,
    )
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
