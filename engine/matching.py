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


# ---------------------------------------------------------------- fix-up 1: more coverage, still no guessing

class Register:
    """Cricsheet people register (https://cricsheet.org/register/): names.csv (identifier, name) holds
    alternative names such as "Dasun Shanaka" for identifier 3ff033bb ("MD Shanaka" in people.csv);
    people.csv (identifier, name, unique_name, ...) holds the primary names. Checked from the real files
    on 12 Oct 2026. people.csv's key_cricbuzz column is filled for only 50 of 18,623 people, so it is not used."""

    def __init__(self, by_name):
        self.by_name = by_name

    @classmethod
    def from_dir(cls, folder):
        import csv
        from pathlib import Path
        folder = Path(folder)
        names, people = folder / "names.csv", folder / "people.csv"
        if not names.exists() or not people.exists():
            return None
        by_name = {}
        for row in csv.DictReader(open(names, encoding="utf8")):
            by_name.setdefault(normalise(row["name"]), set()).add(row["identifier"])
        for row in csv.DictReader(open(people, encoding="utf8")):
            for col in ("name", "unique_name"):
                if row.get(col):
                    by_name.setdefault(normalise(row[col]), set()).add(row["identifier"])
        return cls(by_name)

    def lookup(self, name):
        return self.by_name.get(normalise(name), set())


def surname_initial_match(source_name, cricsheet_name):
    """'Dasun Shanaka' <-> 'MD Shanaka': same surname and the source's first initial appears in the
    Cricsheet initials. Only applies when the Cricsheet name is initials + surname."""
    src = normalise(source_name).split()
    raw = cricsheet_name.split()
    # Cricsheet initials are written in capitals before the surname: "MD", "BKG", "PHKD"
    if len(src) < 2 or len(raw) < 2 or not all(t.isalpha() and t.isupper() and len(t) <= 5 for t in raw[:-1]):
        return False
    initials = "".join(raw[:-1]).lower()
    return src[-1] == normalise(raw[-1]) and src[0][0] in initials


class CoverageMatcher(Matcher):
    """Matcher plus the fix-up 1 steps, each accepted only if exactly one candidate remains:
      a. Cricsheet register alternative names, within the team's players
      b. surname + given-name initial, within players who played for the team in the last 12 months
    Candidates already linked (same source) under a different name are known to be someone else and
    are left out. Anything still ambiguous stays unmatched for a person to confirm (`engine.cli link`)."""

    def __init__(self, store, register=None):
        super().__init__(store)
        self.register = register

    def _other_people(self, source, source_name, pids):
        return [p for p in pids if not any(n != source_name for n in self.store.links_for_player(p, source))]

    def resolve(self, source, source_name, team_hint=None, recent_hint=None):
        before = len(self.unmatched)
        pid = super().resolve(source, source_name, team_hint)
        if pid is not None:
            return pid
        del self.unmatched[before:]   # retry with the extra steps first
        cand_ids = {p for p, _ in (team_hint or [])}
        if self.register is not None:
            hits = self._other_people(source, source_name, sorted(self.register.lookup(source_name) & cand_ids))
            if len(hits) == 1:
                self.store.add_link(hits[0], source, source_name)
                return hits[0]
        pool = recent_hint if recent_hint is not None else (team_hint or [])
        hits = self._other_people(source, source_name,
                                  sorted({p for p, full in pool if surname_initial_match(source_name, full)}))
        if len(hits) == 1:
            self.store.add_link(hits[0], source, source_name)
            return hits[0]
        self.unmatched.append(source_name)
        return None

    def resolve_all(self, source, items):
        """items: [(key, source_name, team_hint, recent_hint)] -> {key: player_id}. Two passes, so a link
        made for one player can rule him out as a candidate for another (e.g. Kusal vs Kamindu Mendis)."""
        out, pending = {}, list(items)
        for _ in range(2):
            self.unmatched, retry = [], []
            for key, name, hint, recent in pending:
                pid = self.resolve(source, name, hint, recent)
                if pid is None:
                    retry.append((key, name, hint, recent))
                else:
                    out[key] = pid
            if len(retry) == len(pending):
                break
            pending = retry
        return out
