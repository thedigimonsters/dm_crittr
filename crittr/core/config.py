# crittr/core/settings.py
from __future__ import annotations
from typing import Any
from PySide6.QtCore import QSettings
from app_config import apply_qsettings_org, DEFAULTS, SETTINGS_FILE

class Settings:
    """
    Thin wrapper over QSettings with defaults and simple dict-like get/set.
    Uses Native format (registry/plist) but we keep a reference file path for diagnostics.
    """
    def __init__(self):
        apply_qsettings_org()
        self._qs = QSettings()

        # Prime defaults if key not present
        for group, values in DEFAULTS.items():
            for k, v in values.items() if isinstance(values, dict) else []:
                self.get(f"{group}/{k}", v)

    def get(self, key: str, default: Any = None) -> Any:
        val = self._qs.value(key, default)
        return val if val is not None else default

    def set(self, key: str, value: Any) -> None:
        self._qs.setValue(key, value)
        self._qs.sync()

    def begin_group(self, group: str): self._qs.beginGroup(group)
    def end_group(self): self._qs.endGroup()

def get_settings() -> Settings:
    return Settings()
