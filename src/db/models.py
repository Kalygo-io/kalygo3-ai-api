from sqlalchemy import Column, Integer, String, ForeignKey, UUID, JSON, DateTime, func, Double
from sqlalchemy.orm import relationship
from .database import Base
import datetime

class Account(Base):
    __tablename__ = 'accounts'
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    reset_token = Column(String)
    stripe_id = Column(String, nullable=True)

    logins = relationship('Logins', back_populates='account')
    chat_app_sessions = relationship('ChatAppSession', back_populates='account')

    def __repr__(self):
        return f'<Account {self.email}>'
    
class Logins(Base):
    __tablename__ = 'logins'
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id'))
    created_at = Column(DateTime(timezone=True), default=func.now())
    ip_address = Column(String, nullable=False)
    similarity_score = Column(Double, default=False)
    
    account = relationship('Account', back_populates='logins')
    
    def __repr__(self):
        return f'<Login {self.login_time}>'
    
class ChatHistory(Base):
    __tablename__ = 'chat_history'
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(UUID, nullable=False)
    message = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now())

class ChatAppSession(Base):
    __tablename__ = 'chat_app_sessions'
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(UUID, unique=True, index=True)
    chat_app_id = Column(String, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    title = Column(String)
    
    account = relationship('Account', back_populates='chat_app_sessions')
    messages = relationship('ChatMessage', back_populates='session', cascade='all, delete-orphan')
    app_messages = relationship('ChatAppMessage', back_populates='session', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ChatAppSession {self.session_id}>'

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id = Column(Integer, primary_key=True, index=True)
    message = Column(JSON)
    session_id = Column(Integer, ForeignKey('chat_app_sessions.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    session = relationship('ChatAppSession', back_populates='messages')
    
    def __repr__(self):
        return f'<ChatMessage {self.id}>'

class ChatAppMessage(Base):
    __tablename__ = 'chat_app_messages'
    id = Column(Integer, primary_key=True, index=True)
    chat_app_session_id = Column(Integer, ForeignKey('chat_app_sessions.id'), nullable=False, index=True)
    message = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    session = relationship('ChatAppSession', back_populates='app_messages')
    
    def __repr__(self):
        return f'<ChatAppMessage {self.id}>'
