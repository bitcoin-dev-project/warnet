import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    createdAt = Column(DateTime, default=datetime.datetime.utcnow)
    updatedAt = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
    api_token = Column(String, unique=True, index=True)
    networks = relationship("Network", back_populates="owner")


class Network(Base):
    __tablename__ = "networks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    status = Column(Boolean, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    createdAt = Column(DateTime, default=datetime.datetime.utcnow)
    updatedAt = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    owner = relationship("User", back_populates="networks")
