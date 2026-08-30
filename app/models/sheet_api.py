import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.db.session import Base


class SheetApi(Base):
    """One published endpoint: a single tab of a single spreadsheet.

    `id` is the public handle - it appears in the URL, so it is a random UUID
    rather than a sequential integer. Knowing one endpoint's URL should not let
    you guess anybody else's.
    """

    __tablename__ = "sheet_apis"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    spreadsheet_id = Column(String, nullable=False)
    sheet_name = Column(String, nullable=False, default="Sheet1")
    title = Column(String, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Publishing the same tab twice would create two endpoints and two cache
    # entries that silently drift apart, so the pair is unique per user.
    __table_args__ = (
        UniqueConstraint("user_id", "spreadsheet_id", "sheet_name", name="uq_sheet_api_target"),
    )
