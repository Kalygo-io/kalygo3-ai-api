from sqlalchemy import Column, Integer, String, Text, DateTime, func, Index
from .database import Base


class Feedback(Base):
    """User-submitted feedback from a branded UI (e.g. bolay.kalygo.io).

    Public, account-less submissions. `client` records which branded UI the
    feedback came from so a single table can serve multiple branded front-ends.
    """
    __tablename__ = 'feedback'

    id = Column(Integer, primary_key=True, index=True)
    # Which branded UI this came from, e.g. "bolay". Indexed for per-client triage.
    client = Column(String(64), nullable=False, index=True)
    # Topic slug from the form: "bug" | "feature" | "question" | "other".
    category = Column(String(32), nullable=False)
    # Optional contact email so an admin can follow up.
    email = Column(String(320), nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    __table_args__ = (
        Index('ix_feedback_client_created_at', 'client', 'created_at'),
    )

    def __repr__(self):
        return f'<Feedback {self.id} client={self.client} category={self.category}>'
