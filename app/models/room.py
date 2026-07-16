from sqlalchemy.orm import Mapped,mapped_column,relationship
from app.db.base import Base
from sqlalchemy import String
from uuid import UUID,uuid4
from datetime import timezone,datetime
from sqlalchemy import ForeignKey,DateTime

class Room(Base):
    __tablename__ = "rooms"

    id:Mapped[UUID] = mapped_column(
        primary_key = True,
        index = True,
        default = uuid4
    )

    name:Mapped[str] = mapped_column(
        String(100),
        nullable = False
    )

    created_by:Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable = False
    )

    created_at: Mapped[datetime] = mapped_column(
       DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
   )
    
    members: Mapped[list["RoomMember"]] = relationship(back_populates="room")