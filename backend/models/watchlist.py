from sqlalchemy import Column, String
from database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    stock_id = Column(String, primary_key=True)
    note = Column(String, nullable=False, default="")   # 研究筆記／買進理由
    added_at = Column(String, nullable=False)           # ISO8601 +08:00
