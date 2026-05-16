from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.stock import SectorMap

router = APIRouter()


class SectorUpdate(BaseModel):
    stock_id: str
    sector: str


@router.get("/sectors")
def list_sectors(db: Session = Depends(get_db)):
    rows = db.query(SectorMap).all()
    return [{"stock_id": r.stock_id, "sector": r.sector} for r in rows]


@router.put("/sectors/{stock_id}")
def update_sector(stock_id: str, body: SectorUpdate, db: Session = Depends(get_db)):
    row = db.query(SectorMap).filter(SectorMap.stock_id == stock_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="stock_id not found in sector_map")
    row.sector = body.sector
    db.commit()
    return {"stock_id": stock_id, "sector": row.sector}
