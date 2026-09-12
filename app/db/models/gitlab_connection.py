import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import relationship

from app.db.base import Base


class GitLabConnection(Base):
    __tablename__ = "gitlab_connections"

    connection_id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", name="fk_gitlab_connections_user"),
        unique=True,
        nullable=False,
    )
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="gitlab_connection")