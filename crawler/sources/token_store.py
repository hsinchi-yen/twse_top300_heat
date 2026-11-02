"""token_store.py — resolve the FinMind token at call time.

Precedence: UI-set file (written by the backend) > FINMIND_TOKEN env.
Read on every call so a token saved in the UI applies to the next job
without restarting the crawler. Never logs the token.
"""

import os
from pathlib import Path

TOKEN_FILE = Path(os.getenv("FINMIND_TOKEN_FILE", "/app/data/.finmind_token"))


def get_token() -> str:
    try:
        tok = TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        tok = ""
    return tok or os.getenv("FINMIND_TOKEN", "").strip()
