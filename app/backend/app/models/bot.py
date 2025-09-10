from sqlalchemy import BigInteger, String, Text, DateTime, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

class Bot(Base):
    __tablename__ = "bots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    activation_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    rate: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
