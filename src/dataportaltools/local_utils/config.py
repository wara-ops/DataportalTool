"""
Implements a singleton config that is populated by environment and arguments.

It can be used everywhere so there is no need to pass parameters around.
"""


class ConfigError(Exception):
    """Raised when the config singleton is used incorrectly."""


__CONFIG = None


def get() -> dict:
    """Return the config dict, raising ``ConfigError`` if it is unset."""
    if __CONFIG is None:
        raise ConfigError("Config not initialized (please set config on startup)")
    return __CONFIG


def get_value(key: str, default: object = None) -> object:
    """Return ``key`` from the config, or ``default`` when it is absent."""
    if key not in get():
        return default
    return get()[key]


def set_conf(config: dict) -> None:
    """Populate the singleton once; raise ``ConfigError`` on a second call."""
    # The single module-level binding is the whole point of this singleton, so
    # the global statement is intentional here.
    global __CONFIG  # pylint: disable=global-statement
    if __CONFIG is not None:
        raise ConfigError("Config already set; do not set it multiple times")
    __CONFIG = config
