"""
implements singleton config thats populated by environment and arguments.
It can be used everywhere so no need to send around parameters.
"""

__CONFIG = None


def get() -> dict:
    if __CONFIG is None:
        raise Exception("Not initialized config(Please set config on startup)")
    return __CONFIG


def get_value(key: str, default: object = None) -> str:
    if key not in get():
        return default
    return get()[key]


def set_conf(config: dict) -> None:
    global __CONFIG  # pylint: disable=W0603
    if __CONFIG is not None:
        raise Exception("Dont do multiple set")
    __CONFIG = config
