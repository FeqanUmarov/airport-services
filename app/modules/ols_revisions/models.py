from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OlsSurfaceRevision(Base):
    __tablename__ = "TBL_OLS_SURFACE_REVISIONS"
    __table_args__ = (
        UniqueConstraint("OLS_SURFACE_ID", "REVISION_NO", name="uq_ols_surface_revision_no"),
    )

    REVISION_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    OLS_SURFACE_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_OLS_SURFACES.OLS_SURFACE_ID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    REVISION_NO: Mapped[int] = mapped_column(Integer, nullable=False)
    STANDARD_OLS_ID: Mapped[int] = mapped_column(BigInteger, nullable=False)
    GENERATION_METHOD_ID: Mapped[int] = mapped_column(Integer, nullable=False)
    AIR_ID: Mapped[int] = mapped_column(BigInteger, nullable=False)
    RUN_ID: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    RUN_DIR_ID: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    AZE_NAME: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ENG_NAME: Mapped[str | None] = mapped_column(String(255), nullable=True)
    GEOM: Mapped[object] = mapped_column(
        Geometry(geometry_type="GEOMETRYZ", srid=4326, dimension=3, spatial_index=True),
        nullable=False,
    )
    STATUS_ID: Mapped[int] = mapped_column(Integer, nullable=False)
    CHANGE_TYPE: Mapped[str] = mapped_column(String(30), nullable=False)
    CHANGE_NOTE: Mapped[str | None] = mapped_column(String(500), nullable=True)
    CREATED_BY: Mapped[int | None] = mapped_column(
        ForeignKey("TBL_USERS.USER_ID", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    CREATED_DATE: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
