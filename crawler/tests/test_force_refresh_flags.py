"""
test_force_refresh_flags.py — unit tests for the crawler's stale-flag cleanup.

A crashed/restarted score run can leave an orphaned .scoring_in_progress flag.
_clear_stale_in_progress() removes it once it is older than SCORING_FLAG_STALE_S
so it cannot pin the backend's fetching=true forever.
"""

import os
import sys
import time

from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# main.py imports apscheduler at module load; it is only installed in the crawler
# container. Skip cleanly when running outside that environment.
pytest.importorskip("apscheduler")

import main


def _make_flag(path, age_seconds):
    path.write_text("x", encoding="utf-8")
    past = time.time() - age_seconds
    os.utime(path, (past, past))


def test_stale_in_progress_flag_removed(tmp_path):
    flag = tmp_path / ".scoring_in_progress"
    with patch.object(main, "SCORING_IN_PROGRESS_FLAG", flag), \
         patch.object(main, "SCORING_FLAG_STALE_S", 10800):
        _make_flag(flag, age_seconds=20000)
        main._clear_stale_in_progress()
        assert not flag.exists()


def test_fresh_in_progress_flag_kept(tmp_path):
    flag = tmp_path / ".scoring_in_progress"
    with patch.object(main, "SCORING_IN_PROGRESS_FLAG", flag), \
         patch.object(main, "SCORING_FLAG_STALE_S", 10800):
        _make_flag(flag, age_seconds=60)
        main._clear_stale_in_progress()
        assert flag.exists()


def test_missing_flag_is_noop(tmp_path):
    flag = tmp_path / ".scoring_in_progress"
    with patch.object(main, "SCORING_IN_PROGRESS_FLAG", flag), \
         patch.object(main, "SCORING_FLAG_STALE_S", 10800):
        main._clear_stale_in_progress()  # must not raise
        assert not flag.exists()
