"""Settings from the Neon `settings` table, with typed accessors (spec 9.1)."""


class MissingSetting(Exception):
    def __init__(self, key):
        super().__init__(f"Missing setting {key}")
        self.key = key


class Settings:
    def __init__(self, store):
        self.store = store

    def get(self, key):
        v = self.store.setting(key)
        if v is None:
            raise MissingSetting(key)
        return v

    def int(self, key):
        return int(self.get(key))

    def float(self, key):
        return float(self.get(key))

    def factor_cfg(self):
        """The cfg dict engine/factors.py expects, built from settings (names differ from run 1)."""
        return {
            "thin_data_threshold": self.int("thin_data_full_trust"),
            "pitch_min_matches": self.int("pitch_type_min_matches"),
            "cold_start_min_matches": self.int("cold_start_min_matches"),
            "form_matches": self.int("form_window"),
            "form_recent_double": self.int("form_recent_double"),
            "current_touch_days": self.int("current_touch_days"),
            "current_touch_matches": self.int("current_touch_matches"),
        }
