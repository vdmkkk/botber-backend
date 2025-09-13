from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base

class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    instance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user_bot_instances.id", ondelete="CASCADE"), unique=True, index=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    external_entry_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    __table_args__ = (UniqueConstraint("kb_id", "external_entry_id", name="uq_kb_external_entry"),)
