"""test_settings_api.py — write-only FinMind token store contract."""

import os
import stat

import pytest
from fastapi.testclient import TestClient

from main import app
from routers import settings as settings_router

client = TestClient(app)
URL = "/api/settings/finmind-token"
TOKEN = "eyJhbGciOiJIUzI1NiJ9.secretvalue1234"


@pytest.fixture(autouse=True)
def token_file(tmp_path, monkeypatch):
    path = tmp_path / ".finmind_token"
    monkeypatch.setattr(settings_router, "TOKEN_FILE", path)
    return path


def test_initially_not_configured():
    r = client.get(URL)
    assert r.status_code == 200
    assert r.json() == {"configured": False, "hint": None}


def test_put_stores_and_never_echoes_token(token_file):
    r = client.put(URL, json={"token": f"  {TOKEN}  "})
    assert r.status_code == 200
    body = r.json()
    assert body == {"configured": True, "hint": "****1234"}
    assert TOKEN not in r.text
    assert token_file.read_text().strip() == TOKEN
    assert TOKEN not in client.get(URL).text


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_file_is_private(token_file):
    client.put(URL, json={"token": TOKEN})
    assert stat.S_IMODE(token_file.stat().st_mode) == 0o600


def test_short_token_has_no_hint():
    r = client.put(URL, json={"token": "short"})
    assert r.json() == {"configured": True, "hint": None}


@pytest.mark.parametrize("bad", ["", "   ", "has space", "tab\there", "x" * 513])
def test_invalid_token_rejected(bad, token_file):
    r = client.put(URL, json={"token": bad})
    assert r.status_code == 422
    assert not token_file.exists()


def test_delete_clears():
    client.put(URL, json={"token": TOKEN})
    r = client.delete(URL)
    assert r.status_code == 200
    assert r.json() == {"configured": False, "hint": None}
    assert client.delete(URL).json()["configured"] is False


def test_replace_is_atomic_no_tmp_left(token_file):
    client.put(URL, json={"token": TOKEN})
    client.put(URL, json={"token": TOKEN + "x"})
    assert [p.name for p in token_file.parent.iterdir()] == [".finmind_token"]


def test_token_not_logged(caplog):
    with caplog.at_level("DEBUG"):
        client.put(URL, json={"token": TOKEN})
    assert TOKEN not in caplog.text
