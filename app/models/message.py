from uuid import UUID
from app.db.base import Base
from sqlalchemy import String,ForeignKey,DateTime
from sqlalchemy.orm import Mapped,mapped_column,relationship
from datetime import datetime,timezone
from uuid import UUID, uuid4

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4
    )

    room_id: Mapped[UUID] = mapped_column(
        ForeignKey("rooms.id"),
        nullable=False,
        index=True  
    )

    sender_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    content: Mapped[str] = mapped_column(
        String(1024),
        nullable=False
    )

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True   
    )

    sender: Mapped["User"] = relationship()