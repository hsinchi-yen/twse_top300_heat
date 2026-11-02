"""settings.py — write-only FinMind token store shared with the crawler.

The token lives in a file on the shared data volume. No response ever contains
it; GET exposes only whether one is set plus the last 4 characters.
"""

import os
import re
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

router = APIRouter()

TOKEN_FILE = Path(os.getenv("FINMIND_TOKEN_FILE", "/app/data/.finmind_token"))
MAX_TOKEN_LEN = 512
HINT_MIN_LEN = 12


class TokenBody(BaseModel):
    token: str

    @field_validator("token")
    @classmethod
    def _valid(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > MAX_TOKEN_LEN or re.search(r"\s", v):
            raise ValueError("invalid token")
        return v


def _read() -> str:
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _status() -> dict:
    tok = _read()
    hint = f"****{tok[-4:]}" if len(tok) >= HINT_MIN_LEN else None
    return {"configured": bool(tok), "hint": hint}


@router.get("/settings/finmind-token")
def get_token_status() -> dict:
    return _status()


@router.put("/settings/finmind-token")
def put_token(body: TokenBody) -> dict:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = TOKEN_FILE.with_name(TOKEN_FILE.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(body.token)
    os.replace(tmp, TOKEN_FILE)
    return _status()


@router.delete("/settings/finmind-token")
def delete_token() -> dict:
    try:
        TOKEN_FILE.unlink()
    except FileNotFoundError:
        pass
    return _status()
