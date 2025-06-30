from sqlalchemy import Column, Integer, String
from app.database import Base

class PlushTable(Base):
    __tablename__ = "plushtable"

    #primary key will serve as its unique identity, index just increases performance for inquiries
    id = Column(Integer, primary_key=True, index=True)
    character = Column(String, index=True)
    variation = Column(String, index=True)
    set = Column(String, index=True)
    releaseyear = Column(Integer)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)