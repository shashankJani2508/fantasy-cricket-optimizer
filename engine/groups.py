"""Format-group names. The spec uses "T20_men"; backtest run 1 stored "T20-male" in rubric_versions."""

FORMATS = ("T20", "ODI", "Test")


def spec_group(fmt, gender):
    """('T20', 'male') -> 'T20_men'."""
    return f"{fmt}_{'men' if gender in ('male', 'men') else 'women'}"


def run1_group(group):
    """'T20_men' -> 'T20-male' (the name used in run 1 rows)."""
    fmt, g = group.split("_")
    return f"{fmt}-{'male' if g == 'men' else 'female'}"


def from_any(group):
    """Accept either naming and return the spec name."""
    if "-" in group:
        fmt, g = group.split("-")
        return spec_group(fmt, g)
    return group


def other_gender(group):
    fmt, g = group.split("_")
    return f"{fmt}_{'women' if g == 'men' else 'men'}"


def fmt_of(group):
    return group.split("_")[0]
