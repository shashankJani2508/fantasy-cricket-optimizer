"""Player name matching across sources (spec 9.3). Never guesses between two candidates."""
import re
import unicodedata


def normalise(name):
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s.lower())
    return " ".join(s.split())


def _initials_form(name):
    """'V Kohli' -> ('v', 'kohli'); 'MS Dhoni' -> ('ms', 'dhoni'); None if it isn't initials + surname."""
    parts = normalise(name).split()
    if len(parts) < 2:
        return None
    given, surname = parts[:-1], parts[-1]
    if all(len(p) <= 3 and p.isalpha() for p in given) and any(len(p) <= 2 for p in given):
        return "".join(given), surname
    return None


def _full_initials(name):
    parts = normalise(name).split()
    return ("".join(p[0] for p in parts[:-1]), parts[-1]) if len(parts) >= 2 else None


def initials_match(a, b):
    """True for 'V Kohli' <-> 'Virat Kohli' (either order)."""
    for short, full in ((a, b), (b, a)):
        s = _initials_form(short)
        f = _full_initials(full)
        if s and f and s == f:
            return True
    return False


class Matcher:
    """resolve(source, source_name, team_hint) -> player_id | None. team_hint: [(player_id, full_name)]."""

    def __init__(self, store):
        self.store = store
        self.unmatched = []

    def resolve(self, source, source_name, team_hint=None):
        candidates = team_hint or []
        cand_ids = {pid for pid, _ in candidates}
        linked = self.store.links(source, source_name)
        if team_hint is not None:
            linked = [p for p in linked if p in cand_ids] or (linked if len(linked) == 1 else [])
        if len(linked) == 1:
            return linked[0]
        n = normalise(source_name)
        exact = [pid for pid, full in candidates if normalise(full) == n]
        if len(exact) == 1:
            self.store.add_link(exact[0], source, source_name)
            return exact[0]
        if not exact:
            ini = [pid for pid, full in candidates if initials_match(source_name, full)]
            if len(ini) == 1:
                self.store.add_link(ini[0], source, source_name)
                return ini[0]
        self.unmatched.append(source_name)
        return None
