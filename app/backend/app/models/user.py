from sqlalchemy import BigInteger, String, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    surname: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram: Mapped[str | None] = mapped_column(String(64), nullable=True)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
