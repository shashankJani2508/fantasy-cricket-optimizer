"""Every test runs offline and can never reach the network (SCORING_ENGINE.md fix-up 5)."""
import urllib.request

import pytest


class NetworkBlocked(AssertionError):
    pass


@pytest.fixture(autouse=True)
def no_live_calls(monkeypatch):
    monkeypatch.setenv("CRICKETDATA_MODE", "offline")

    def blocked(*a, **k):
        raise NetworkBlocked("tests must never call a live API")

    monkeypatch.setattr(urllib.request, "urlopen", blocked)
    monkeypatch.setattr("engine.sources.cricketdata._http_get", blocked)
