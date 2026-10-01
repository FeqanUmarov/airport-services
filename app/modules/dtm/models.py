from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Identity, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DtmSource(Base):
    __tablename__ = "TBL_DTM_SOURCES"

    DTM_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    AIR_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_AIRPORTS.AIR_ID", ondelete="CASCADE"), nullable=False, index=True
    )
    NAME: Mapped[str] = mapped_column(String(255), nullable=False)
    SOURCE_PATH: Mapped[str | None] = mapped_column(String(500), nullable=True)
    SOURCE_TYPE: Mapped[str] = mapped_column(String(30), nullable=False, server_default="GEOTIFF")
    CRS: Mapped[str | None] = mapped_column(String(50), nullable=True)
    RESOLUTION_M: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    NODATA_VALUE: Mapped[Decimal | None] = mapped_column(Numeric(15, 5), nullable=True)
    COVERAGE_GEOM: Mapped[object | None] = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True), nullable=True)
    IS_PRIMARY: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )
    CREATED_DATE: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    LAST_EDITED_DATE: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
