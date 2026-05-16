from sqlalchemy import Column, Integer, String, Float, UniqueConstraint
from database import Base


class ETFRank(Base):
    __tablename__ = "etf_ranks"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    etf_id            = Column(String, nullable=False)          # e.g. "0050", "00878"
    name              = Column(String, nullable=False)
    date              = Column(String, nullable=False)          # 'YYYY-MM-DD'
    etf_type          = Column(String, default="股票型")        # 股票型/債券型/商品型/槓桿反向/貨幣市場
    tracking_index    = Column(String, default="")
    management_fee    = Column(Float, default=None)             # % per year
    asset_scale       = Column(Float, default=None)             # NT億
    outstanding_units = Column(Float, default=None)             # 在外流通單位數
    volume            = Column(Integer, default=None)           # 成交量 (shares)
    turnover_rate     = Column(Float, default=None)             # volume/outstanding_units*100
    close_price       = Column(Float, default=None)
    price_change_pct  = Column(Float, default=None)
    nav               = Column(Float, default=None)             # 淨值 per unit
    premium_discount  = Column(Float, default=None)             # (price-nav)/nav*100
    portfolio_turnover = Column(Float, default=None)            # annual % from prospectus / type estimate
    color_tier        = Column(String, default="neutral")
    turnover_rank     = Column(Integer, default=None)
    asset_scale_rank  = Column(Integer, default=None)

    __table_args__ = (UniqueConstraint("etf_id", "date", name="uq_etf_date"),)
