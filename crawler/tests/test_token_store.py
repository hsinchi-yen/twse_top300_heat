"""token_store: UI-set token file takes precedence over env, read fresh each call."""

from sources import token_store


def test_env_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(token_store, "TOKEN_FILE", tmp_path / "t")
    monkeypatch.setenv("FINMIND_TOKEN", "from-env")
    assert token_store.get_token() == "from-env"


def test_file_overrides_env_and_is_read_fresh(tmp_path, monkeypatch):
    f = tmp_path / "t"
    monkeypatch.setattr(token_store, "TOKEN_FILE", f)
    monkeypatch.setenv("FINMIND_TOKEN", "from-env")
    f.write_text("  from-ui\n")
    assert token_store.get_token() == "from-ui"
    f.write_text("changed")
    assert token_store.get_token() == "changed"
    f.unlink()
    assert token_store.get_token() == "from-env"


def test_empty_file_falls_back(tmp_path, monkeypatch):
    f = tmp_path / "t"
    f.write_text("  \n")
    monkeypatch.setattr(token_store, "TOKEN_FILE", f)
    monkeypatch.delenv("FINMIND_TOKEN", raising=False)
    assert token_store.get_token() == ""


def test_buy_score_uses_current_token(tmp_path, monkeypatch):
    from sources import buy_score
    seen = {}
    monkeypatch.setattr(buy_score, "compute_buy_score",
                        lambda sid, token: seen.setdefault("t", token) and {"max_score": 0})
    f = tmp_path / "t"
    f.write_text("ui-token")
    monkeypatch.setattr(token_store, "TOKEN_FILE", f)
    buy_score.fetch_buy_score("2330")
    assert seen["t"] == "ui-token"
