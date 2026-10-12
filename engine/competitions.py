"""Upcoming-tab filter (config/competitions.yaml): international and IPL matches only. Never used for history."""
from pathlib import Path

import yaml

CFG = Path(__file__).resolve().parents[1] / "config" / "competitions.yaml"


def load(path=CFG):
    return yaml.safe_load(Path(path).read_text(encoding="utf8"))


def classify(team_a, team_b, series, gender, cfg):
    """-> "international" | "ipl" | "domestic" | None (unclassifiable: hidden and reported)."""
    if not team_a or not team_b:
        return None
    if any(k.lower() in (series or "").lower() for k in cfg.get("ipl_series_contains", [])):
        return "ipl"
    nat = set(cfg.get("national_teams", []))
    if team_a in nat and team_b in nat:
        return "international"
    return "domestic"


def visible(kind, gender, cfg):
    if kind == "international":
        return cfg.get("show_international", True) and (gender != "female" or cfg.get("show_womens_international", True))
    if kind == "ipl":
        return cfg.get("show_ipl", True)
    if kind == "domestic":
        return cfg.get("show_domestic", False)
    return False
