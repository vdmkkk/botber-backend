from sqlalchemy import BigInteger, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

class InstanceStatusEvent(Base):
    __tablename__ = "instance_status_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    instance_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user_bot_instances.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
