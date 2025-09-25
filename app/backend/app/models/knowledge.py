from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from app.models.enums import KBDataType, KBLangHint, KBEntryStatus

class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    instance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user_bot_instances.id", ondelete="CASCADE"), unique=True, index=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    instance = relationship("UserBotInstance", back_populates="knowledge_base", uselist=False)
    entries = relationship(
        "KnowledgeEntry",
        back_populates="kb",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="KnowledgeEntry.id",
    )

class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    data_type: Mapped[KBDataType] = mapped_column(
        PGEnum(KBDataType, name="kb_data_type", create_type=False),
        nullable=False,
        server_default=KBDataType.document.value,
    )
    lang_hint: Mapped[KBLangHint] = mapped_column(
        PGEnum(KBLangHint, name="kb_lang_hint", create_type=False),
        nullable=False,
        server_default=KBLangHint.ru.value,
    )
    execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[KBEntryStatus] = mapped_column(
        PGEnum(KBEntryStatus, name="kb_entry_status", create_type=False),
        nullable=False,
        server_default=KBEntryStatus.in_progress.value,
    )

    external_entry_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    kb = relationship("KnowledgeBase", back_populates="entries")
