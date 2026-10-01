from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TimestampMixin
from app.core.database import Base


class User(TimestampMixin, Base):
    __tablename__ = "TBL_USERS"

    USER_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    USERNAME: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    EMAIL: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    PASSWORD_HASH: Mapped[str] = mapped_column(String(255), nullable=False)
    FIRST_NAME: Mapped[str] = mapped_column(String(100), nullable=False)
    LAST_NAME: Mapped[str] = mapped_column(String(100), nullable=False)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class Role(Base):
    __tablename__ = "DIC_ROLES"

    ROLE_ID: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    CODE: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    AZE_NAME: Mapped[str] = mapped_column(String(100), nullable=False)
    ENG_NAME: Mapped[str] = mapped_column(String(100), nullable=False)
    STATUS_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_STATUS.STATUS_ID", ondelete="RESTRICT"), nullable=False, index=True
    )


class UserRole(Base):
    __tablename__ = "TBL_USER_ROLES"
    __table_args__ = (
        UniqueConstraint("USER_ID", "ROLE_ID", name="uq_user_role"),
    )

    USER_ROLE_ID: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    USER_ID: Mapped[int] = mapped_column(
        ForeignKey("TBL_USERS.USER_ID", ondelete="CASCADE"), nullable=False, index=True
    )
    ROLE_ID: Mapped[int] = mapped_column(
        ForeignKey("DIC_ROLES.ROLE_ID", ondelete="RESTRICT"), nullable=False, index=True
    )
    CREATED_DATE: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
