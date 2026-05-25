from __future__ import annotations

__version__ = "0.1.0"

_HA_EXPORTS = {"async_setup_entry", "async_unload_entry", "PLATFORMS"}


def __getattr__(name: str):
    # Lazy import: pulls Home Assistant modules only when HA loads the
    # integration. Keeps the package importable from plain Python (CLI, tests)
    # on machines without homeassistant installed.
    if name in _HA_EXPORTS:
        from . import _ha_setup

        return getattr(_ha_setup, name)
    raise AttributeError(name)
