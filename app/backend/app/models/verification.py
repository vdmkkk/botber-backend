from sqlalchemy import BigInteger, String, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

class EmailVerification(Base):
    __tablename__ = "email_verifications"
    __table_args__ = (UniqueConstraint("email", name="uq_verification_email_single_pending"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    surname: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(64), nullable=False)
    telegram: Mapped[str | None] = mapped_column(String(64), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    expires_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True))
