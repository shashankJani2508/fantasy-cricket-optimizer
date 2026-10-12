"""Spec test 12: player_match_points (source cricsheet) row count equals bt_player_match_points.
Reads Neon (no CricketData.org calls); skipped when DATABASE_URL is not available."""
import pytest

from engine.env import env


@pytest.mark.skipif(not env("DATABASE_URL"), reason="DATABASE_URL not set")
def test_copied_row_count_matches():
    import psycopg
    with psycopg.connect(env("DATABASE_URL")) as c:
        bt = c.execute("SELECT count(*) FROM bt_player_match_points").fetchone()[0]
        pmp = c.execute("SELECT count(*) FROM player_match_points WHERE source = 'cricsheet'").fetchone()[0]
    assert bt == pmp
