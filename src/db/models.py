from sqlalchemy import Column, Integer, String, ForeignKey, UUID, JSON, DateTime, func, Double, Float, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from .database import Base
from .service_name import ServiceName
import datetime
import uuid

class Account(Base):
    __tablename__ = 'accounts'
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    reset_token = Column(String)
    stripe_customer_id = Column(String, nullable=True)

    logins = relationship('Logins', back_populates='account')
    chat_app_sessions = relationship('ChatAppSession', back_populates='account')
    usage_credits = relationship('UsageCredits', back_populates='account')
    credentials = relationship('Credential', back_populates='account', cascade='all, delete-orphan')
    vector_db_logs = relationship('VectorDbIngestionLog', back_populates='account')

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

class UsageCredits(Base):
    __tablename__ = 'usage_credits'
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    account = relationship('Account', back_populates='usage_credits')
    
    def __repr__(self):
        return f'<UsageCredits {self.account_id}: ${self.amount}>'

class Credential(Base):
    __tablename__ = 'credentials'
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False, index=True)
    service_name = Column(Enum(ServiceName, name='service_name_enum'), nullable=False, index=True)
    encrypted_api_key = Column(String, nullable=False)  # Encrypted API key
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    account = relationship('Account', back_populates='credentials')
    
    def __repr__(self):
        return f'<Credential {self.service_name} for account {self.account_id}>'


class OperationType(str, Enum):
    """Enumeration of vector database operation types."""
    INGEST = "INGEST"
    DELETE = "DELETE"
    UPDATE = "UPDATE"


class OperationStatus(str, Enum):
    """Enumeration of vector database operation statuses."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    PENDING = "PENDING"


class VectorDbIngestionLog(Base):
    __tablename__ = 'vector_db_ingestion_log'
    
    # Primary Key (UUID)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), index=True)
    
    # Operation Details
    # Note: Enum types are created in migration, using create_type=False here
    operation_type = Column(
        PG_ENUM('INGEST', 'DELETE', 'UPDATE', name='operation_type_enum', create_type=False),
        nullable=False,
        index=True
    )
    status = Column(
        PG_ENUM('SUCCESS', 'FAILED', 'PARTIAL', 'PENDING', name='operation_status_enum', create_type=False),
        nullable=False,
        index=True
    )
    
    # User/Account
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False, index=True)
    
    # Vector Database Info
    provider = Column(String, nullable=False)  # 'pinecone', 'chroma', etc.
    index_name = Column(String, nullable=False, index=True)
    namespace = Column(String, nullable=True, index=True)
    
    # File Information
    filenames = Column(JSON, nullable=True)  # Array of filenames
    comment = Column(Text, nullable=True)
    
    # Vector Counts
    vectors_added = Column(Integer, default=0)
    vectors_deleted = Column(Integer, default=0)
    vectors_failed = Column(Integer, default=0)
    
    # Error Handling
    error_message = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    
    # Batch Grouping
    batch_number = Column(String, nullable=True, index=True)  # UUID for grouping related operations
    
    # Relationships
    account = relationship('Account', back_populates='vector_db_logs')
    
    def __repr__(self):
        return f'<VectorDbIngestionLog {self.id} - {self.operation_type.value} - {self.status.value}>'


class Agent(Base):
    __tablename__ = 'agents'
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    config = Column(JSON, nullable=True)  # JSONB in PostgreSQL, JSON in SQLAlchemy
    
    def __repr__(self):
        return f'<Agent {self.id}: {self.name}>'


class JsonSchema(Base):
    """
    Stores JSON schemas and their versions for validation across the Kalygo ecosystem.
    
    Example usage:
    - schema_name: "agent_config"
    - version: 1
    - schema_definition: { JSON schema definition }
    
    JSON blobs can reference schemas using:
    {
      "schema": "agent_config",
      "version": 1,
      "data": { ... }
    }
    """
    __tablename__ = 'json_schemas'
    
    id = Column(Integer, primary_key=True, index=True)
    schema_name = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    schema_definition = Column(JSON, nullable=False)  # JSONB in PostgreSQL
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    
    # Unique constraint on (schema_name, version) is handled in migration
    __table_args__ = (
        {'comment': 'Stores JSON schemas and their versions for validation across the Kalygo ecosystem'}
    )
    
    def __repr__(self):
        return f'<JsonSchema {self.schema_name} v{self.version}>'
