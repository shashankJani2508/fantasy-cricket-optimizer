"""Active rubric weights per format group, with borrowing for unreliable groups (spec 6.5, 9.2)."""
from dataclasses import dataclass

from engine.factors import FACTORS
from engine.groups import from_any, other_gender


class RubricError(Exception):
    pass


@dataclass
class RubricChoice:
    weights: dict
    version_id: str
    provisional: bool
    borrowed_from: str | None


def validate(weights):
    if set(weights) != set(FACTORS):
        raise RubricError(f"Rubric weights must have exactly these keys: {', '.join(FACTORS)}; got {sorted(weights)}")
    if any(float(w) < 0 for w in weights.values()):
        raise RubricError("Rubric weights must be >= 0")
    s = sum(float(w) for w in weights.values())
    if abs(s - 1.0) > 0.001:
        raise RubricError(f"Rubric weights must sum to 1 (within 0.001); they sum to {s:.4f}")


def _active(store, group):
    rows = [r for r in store.rubric_rows() if r["is_active"] and from_any(r["format_group"]) == group]
    if len(rows) > 1:
        raise RubricError(f"More than one active rubric row for {group}")
    return rows[0] if rows else None


def active_weights(store, format_group):
    group = from_any(format_group)
    row = _active(store, group)
    borrowed = None
    if row is None or not row.get("reliable"):
        other = other_gender(group)
        alt = _active(store, other)
        if alt is None or not alt.get("reliable"):
            raise RubricError(f"No rubric weights for {group}. Run the backtest.")
        row, borrowed = alt, other
    weights = {k: float(v) for k, v in row["weights"].items()}
    validate(weights)
    return RubricChoice(weights=weights, version_id=str(row["id"]),
                        provisional=not row.get("points_values_final"), borrowed_from=borrowed)
