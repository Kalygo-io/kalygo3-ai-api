from sqlalchemy import Column, Integer, String, ForeignKey, UUID, JSON, DateTime, func, Double, Float, Enum, Text, Boolean, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
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
    newsletter_subscribed = Column(Boolean, default=False, nullable=False)
    login_otp = Column(String, nullable=True)
    login_otp_expires_at = Column(DateTime(timezone=True), nullable=True)

    logins = relationship('Logins', back_populates='account')
    chat_sessions = relationship('ChatSession', back_populates='account')
    usage_credits = relationship('UsageCredits', back_populates='account')
    credentials = relationship('Credential', back_populates='account', cascade='all, delete-orphan')
    vector_db_logs = relationship('VectorDbIngestionLog', back_populates='account')
    api_keys = relationship('ApiKey', back_populates='account', cascade='all, delete-orphan')
    leads = relationship('Lead', back_populates='account', cascade='all, delete-orphan')
    contacts = relationship('Contact', back_populates='account', cascade='all, delete-orphan')
    contact_lists = relationship('ContactList', back_populates='account', cascade='all, delete-orphan')
    prompts = relationship('Prompt', back_populates='account', cascade='all, delete-orphan')
    access_groups = relationship('AccessGroup', back_populates='owner', cascade='all, delete-orphan')
    group_memberships = relationship('AccessGroupMember', back_populates='account', cascade='all, delete-orphan')
    tool_approvals = relationship('PendingToolApproval', back_populates='account', cascade='all, delete-orphan')
    email_events = relationship('EmailEvent', back_populates='account', cascade='all, delete-orphan')

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

class ChatSession(Base):
    __tablename__ = 'chat_sessions'
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(UUID, unique=True, index=True)
    agent_id = Column(Integer, ForeignKey('agents.id', ondelete='CASCADE'), nullable=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    title = Column(String)
    
    account = relationship('Account', back_populates='chat_sessions')
    agent = relationship('Agent', back_populates='chat_sessions')
    messages = relationship('ChatMessage', back_populates='session', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ChatSession {self.session_id}>'

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(Integer, ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    message = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    session = relationship('ChatSession', back_populates='messages')
    
    def __repr__(self):
        return f'<ChatMessage {self.id}>'

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

class CredentialType(str, Enum):
    """
    Types of credentials that can be stored.
    This determines the expected structure of encrypted_data.
    """
    API_KEY = "api_key"
    DB_CONNECTION = "db_connection"
    OAUTH = "oauth"
    SSH_KEY = "ssh_key"
    CERTIFICATE = "certificate"
    AWS_ACCESS_KEY_PAIR = "aws_access_key_pair"


class Credential(Base):
    """
    Stores encrypted credentials for third-party services.
    
    The table supports multiple credential types:
    - API keys: Simple key-value (e.g., OpenAI API key)
    - Database connections: Host, port, username, password, database name
    - OAuth: Client ID, client secret, tokens
    - SSH keys: Private keys with optional passphrases
    - Certificates: Certificate data with optional private keys
    
    All credentials are stored in encrypted_data as encrypted JSON structures.
    """
    __tablename__ = 'credentials'
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False, index=True)
    service_name = Column(Enum(ServiceName, name='service_name_enum'), nullable=False, index=True)
    credential_type = Column(String(50), nullable=False, index=True, default='api_key')
    
    # Encrypted storage (JSON structure, encrypted with Fernet)
    encrypted_data = Column(Text, nullable=False)
    
    # Non-sensitive metadata (e.g., display name, description, last_validated)
    credential_metadata = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    account = relationship('Account', back_populates='credentials')
    
    def __repr__(self):
        return f'<Credential {self.service_name} ({self.credential_type}) for account {self.account_id}>'


class ApiKeyStatus(str, Enum):
    """Enumeration of API key statuses."""
    ACTIVE = "active"
    REVOKED = "revoked"


class ApiKey(Base):
    __tablename__ = 'api_keys'
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False, index=True)
    
    # Key storage: hash the full key, store prefix for display/lookup
    key_hash = Column(String, nullable=False, unique=True, index=True)
    key_prefix = Column(String, nullable=False, index=True)  # First 20 chars for display/lookup
    
    # Optional metadata
    name = Column(String, nullable=True)  # User-friendly name (e.g., "Website Chatbot")
    status = Column(PG_ENUM('active', 'revoked', name='api_key_status_enum', create_type=False), nullable=False, default=ApiKeyStatus.ACTIVE, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    account = relationship('Account', back_populates='api_keys')
    
    def __repr__(self):
        return f'<ApiKey {self.key_prefix}... for account {self.account_id}>'


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
    
    chat_sessions = relationship('ChatSession', back_populates='agent', cascade='all, delete-orphan')
    access_grants = relationship('AgentAccessGrant', back_populates='agent', cascade='all, delete-orphan')
    
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


class Lead(Base):
    """
    Stores lead/inquiry information.
    
    Leads are potential customers or inquiries captured through
    various channels (website forms, chat, etc.).
    """
    __tablename__ = 'leads'
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False, index=True)
    chat_session_id = Column(UUID, nullable=True, index=True)  # UUID of the chat session where lead was captured
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    
    account = relationship('Account', back_populates='leads')
    
    def __repr__(self):
        return f'<Lead {self.id}: {self.name}>'


class Prompt(Base):
    """
    Stores reusable prompt templates.
    
    Prompts are text templates that can be saved and reused
    across different agents or contexts.
    """
    __tablename__ = 'prompts'
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    
    account = relationship('Account', back_populates='prompts')
    
    def __repr__(self):
        return f'<Prompt {self.id}: {self.name}>'


class AccessGroup(Base):
    """
    Named group owned by an account. The owner can add/remove members
    and other account holders (agent owners) can grant the group access
    to their agents.
    """
    __tablename__ = 'access_groups'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    owner_account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    
    owner = relationship('Account', back_populates='access_groups')
    members = relationship('AccessGroupMember', back_populates='group', cascade='all, delete-orphan')
    agent_grants = relationship('AgentAccessGrant', back_populates='access_group', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<AccessGroup {self.id}: {self.name}>'


class AccessGroupMember(Base):
    """
    Junction table linking accounts to access groups they are members of.
    Only the group owner can add/remove members.
    """
    __tablename__ = 'access_group_members'
    
    id = Column(Integer, primary_key=True, index=True)
    access_group_id = Column(Integer, ForeignKey('access_groups.id', ondelete='CASCADE'), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('access_group_id', 'account_id', name='uq_access_group_members_group_account'),
    )
    
    group = relationship('AccessGroup', back_populates='members')
    account = relationship('Account', back_populates='group_memberships')
    
    def __repr__(self):
        return f'<AccessGroupMember group={self.access_group_id} account={self.account_id}>'


class AgentAccessGrant(Base):
    """
    Grants an access group permission to use a specific agent.
    Only the agent owner can create/revoke grants.
    """
    __tablename__ = 'agent_access_grants'
    
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey('agents.id', ondelete='CASCADE'), nullable=False, index=True)
    access_group_id = Column(Integer, ForeignKey('access_groups.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('agent_id', 'access_group_id', name='uq_agent_access_grants_agent_group'),
    )
    
    agent = relationship('Agent', back_populates='access_grants')
    access_group = relationship('AccessGroup', back_populates='agent_grants')
    
    def __repr__(self):
        return f'<AgentAccessGrant agent={self.agent_id} group={self.access_group_id}>'


class Contact(Base):
    """
    Stores CRM contact records.

    A Contact belongs to an Account and can have a chronological log of
    ContactEvents (calls, emails, meetings, notes, etc.).
    """
    __tablename__ = 'contacts'

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)

    # Required fields
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=False, unique=True, index=True)

    # Optional contact details
    phone = Column(String(50), nullable=True)
    company = Column(String(255), nullable=True, index=True)
    title = Column(String(255), nullable=True)

    @hybrid_property
    def name(self) -> str:
        """Full display name combining first and last name."""
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name

    # CRM metadata
    source = Column(String(100), nullable=True)   # e.g. "website", "referral", "chat_bot", "import"
    status = Column(String(50), nullable=True, index=True)  # e.g. "lead", "prospect", "customer", "churned"
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    account = relationship('Account', back_populates='contacts')
    events = relationship('ContactEvent', back_populates='contact', cascade='all, delete-orphan')
    list_memberships = relationship('ContactListMember', back_populates='contact', cascade='all, delete-orphan')
    email_events = relationship('EmailEvent', back_populates='contact')

    def __repr__(self):
        return f'<Contact {self.id}: {self.name}>'


class ContactList(Base):
    """
    A named subset of contacts for targeted outbound campaigns, sequences, etc.

    A ContactList belongs to an Account and holds references to a subset of that
    account's Contacts via the ContactListMember join table.
    """
    __tablename__ = 'contact_lists'

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    account = relationship('Account', back_populates='contact_lists')
    members = relationship('ContactListMember', back_populates='contact_list', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ContactList {self.id}: {self.name}>'


class ContactListMember(Base):
    """
    Join table linking a ContactList to its member Contacts.
    """
    __tablename__ = 'contact_list_members'

    id = Column(Integer, primary_key=True, index=True)
    contact_list_id = Column(Integer, ForeignKey('contact_lists.id', ondelete='CASCADE'), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)

    added_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    contact_list = relationship('ContactList', back_populates='members')
    contact = relationship('Contact', back_populates='list_memberships')

    __table_args__ = (
        UniqueConstraint('contact_list_id', 'contact_id', name='uq_contact_list_member'),
    )

    def __repr__(self):
        return f'<ContactListMember list={self.contact_list_id} contact={self.contact_id}>'


class ContactEvent(Base):
    """
    Chronological log of interactions with a Contact.

    Each event captures what happened (event_type), a short title, optional
    description, and when it occurred (occurred_at supports backdating).
    """
    __tablename__ = 'contact_events'

    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)

    # e.g. "note", "call", "email", "meeting", "demo", "proposal_sent", "contract_signed"
    event_type = Column(String(100), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    occurred_at = Column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    contact = relationship('Contact', back_populates='events')

    def __repr__(self):
        return f'<ContactEvent {self.id}: {self.event_type} for contact {self.contact_id}>'


class PendingToolApproval(Base):
    """
    Durable queue entry created when a HITL-gated tool (e.g. sendTxtEmailWithSes)
    wants to execute.  The record holds everything needed to act on an approval
    *without* persisting decrypted credentials — the credential_id in the
    payload is re-looked-up at execution time.

    Lifecycle: pending → approved (→ executed) | rejected | expired
    """
    __tablename__ = 'pending_tool_approvals'

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey('agents.id', ondelete='SET NULL'), nullable=True, index=True)
    chat_session_id = Column(Integer, ForeignKey('chat_sessions.id', ondelete='SET NULL'), nullable=True, index=True)

    tool_type = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False, default='pending', index=True)

    # Stores tool arguments.  MUST NOT contain decrypted secrets.
    # For sendTxtEmailWithSes: {credential_id, to_email, subject, body}
    payload = Column(JSON, nullable=False)

    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    account = relationship('Account', back_populates='tool_approvals')
    email_events = relationship('EmailEvent', back_populates='tool_approval', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<PendingToolApproval {self.id}: {self.tool_type} [{self.status}]>'


# PostgreSQL native enum type — mirrors the Alembic migration definition
_email_event_type_pg = PG_ENUM(
    'send', 'delivery', 'open', 'bounce', 'complaint', 'click', 'other',
    name='emaileventtype',
    create_type=False,  # managed by Alembic, not SQLAlchemy metadata
)


class EmailEvent(Base):
    """
    Records a single event in the lifecycle of an email sent through Kalygo.

    One email send typically produces multiple events:
      send → delivery → open (if tracking enabled)

    Or for failures:
      send → bounce / complaint

    provider_message_id is the key for correlating inbound webhook payloads
    (e.g. AWS SNS notifications from SES) back to a specific email record.
    """
    __tablename__ = 'email_events'

    id = Column(Integer, primary_key=True, index=True)

    # Multi-tenant scoping — always filter by this first
    account_id = Column(Integer, ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)

    # The HITL approval record that triggered the original send
    tool_approval_id = Column(Integer, ForeignKey('pending_tool_approvals.id', ondelete='SET NULL'), nullable=True, index=True)

    # Campaign grouping — nullable until a campaigns table is introduced
    campaign_id = Column(Integer, nullable=True, index=True)

    # Recipient — nullable to support group/campaign sends where there is no single primary recipient
    contact_id = Column(Integer, ForeignKey('contacts.id', ondelete='SET NULL'), nullable=True, index=True)
    primary_recipient = Column(String(320), nullable=True)

    # Event classification
    event_type = Column(_email_event_type_pg, nullable=False, index=True)

    # Sending provider (ses | google_oauth | google_smtp)
    provider = Column(String(50), nullable=True)
    # Provider-assigned message ID — used to match inbound webhook notifications
    provider_message_id = Column(String(255), nullable=True, index=True)

    # Arbitrary extra payload (bounce type/subtype, user-agent, IP, clicked URL, etc.)
    event_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    account = relationship('Account', back_populates='email_events')
    tool_approval = relationship('PendingToolApproval', back_populates='email_events')
    contact = relationship('Contact', back_populates='email_events')

    def __repr__(self):
        return f'<EmailEvent {self.id}: {self.event_type} → {self.primary_recipient}>'
