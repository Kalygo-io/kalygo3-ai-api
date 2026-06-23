from sqlalchemy import Column, Integer, String
from .database import Base

class Waitlist(Base):
    __tablename__ = 'waitlist'
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)

    def __repr__(self):
        return f'<Account {self.email}>'