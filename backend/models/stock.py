from sqlalchemy import Column, Integer, String, Float, UniqueConstraint
from database import Base


class StockRank(Base):
    __tablename__ = "stock_ranks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    date = Column(String, nullable=False)          # 'YYYY-MM-DD'
    volume = Column(Integer)
    close_price = Column(Float)
    turnover_rate = Column(Float)
    price_change_pct = Column(Float)
    color_tier = Column(String)
    volume_rank = Column(Integer)
    turnover_rank = Column(Integer)

    __table_args__ = (UniqueConstraint("stock_id", "date", name="uq_stock_date"),)


class SectorMap(Base):
    __tablename__ = "sector_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(String, nullable=False, unique=True)
    sector = Column(String, nullable=False, default="其他")
