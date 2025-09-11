from sqlalchemy import BigInteger, String, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB, ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.models.enums import InstanceStatus

class UserBotInstance(Base):
    __tablename__ = "user_bot_instances"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("bots.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status: Mapped[InstanceStatus] = mapped_column(
        ENUM(InstanceStatus, name="instance_status", create_type=False),
        nullable=False,
        server_default="active",
    )
    last_charge_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_charge_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    user = relationship("User")
    bot = relationship("Bot")
