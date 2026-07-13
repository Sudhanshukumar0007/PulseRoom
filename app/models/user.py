from sqlalchemy.orm import Mapped,mapped_column
from uuid import UUID,uuid4
from sqlalchemy import String
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id:Mapped[UUID] = mapped_column(
        primary_key = True,
        index = True,
        default  = uuid4
    )

    name:Mapped[str] = mapped_column(
        String(100),
        nullable = False
    )

    email:Mapped[str] = mapped_column(
        String(256),
        nullable = False,
        unique = True
    )

    hashed_password:Mapped[str] = mapped_column(
        String(256),
        nullable = False
    )


