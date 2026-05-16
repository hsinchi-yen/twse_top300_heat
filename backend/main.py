from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers import stocks, sectors

Base.metadata.create_all(bind=engine)

app = FastAPI(title="TWSE Top 100 Heatmap API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router, prefix="/api")
app.include_router(sectors.router, prefix="/api")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
