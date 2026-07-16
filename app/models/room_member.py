from sqlalchemy.orm import Mapped,mapped_column,relationship
from app.db.base import Base
from sqlalchemy import String,ForeignKey,UniqueConstraint,DateTime
from uuid import UUID,uuid4
from datetime import datetime,timezone
from app.models.user import User

class RoomMember(Base):
    __tablename__ = "room_members"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_room_user"),)

    id:Mapped[UUID] = mapped_column(
        primary_key = True,
        index = True,
        default = uuid4
    )

    room_id:Mapped[UUID] = mapped_column(
        ForeignKey("rooms.id"),
        nullable = False
    )
    user_id:Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable = False,
    )

    joined_at: Mapped[datetime] = mapped_column(
       DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
   )
    
    room: Mapped["Room"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()   # no back_populates needed unless User needs .room_memberships too