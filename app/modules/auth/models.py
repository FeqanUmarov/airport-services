from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserToken(Base):
    __tablename__ = "TBL_USER_TOKEN"

    TOKEN_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    USER_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_USERS.USER_ID", ondelete="CASCADE"), nullable=False, index=True
    )
    REFRESH_TOKEN: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    EXPIRES_AT: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    REVOKED_AT: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    CREATED_DATE: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
