"""Tests for the dataportaltools.local_utils.config singleton."""

import pytest

from dataportaltools.local_utils import config

# The singleton stores its state in a module-level name. Accessed from a plain
# (non-class) scope, the dunder name is not mangled, so we can reset it here.
_STATE_ATTR = "_config__CONFIG" if hasattr(config, "_config__CONFIG") else "__CONFIG"


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset the module-level singleton before and after each test."""
    setattr(config, _STATE_ATTR, None)
    yield
    setattr(config, _STATE_ATTR, None)


def test_get_before_set_raises():
    with pytest.raises(config.ConfigError):
        config.get()


def test_set_and_get():
    config.set_conf({"a": 1})
    assert config.get() == {"a": 1}


def test_get_value_present_and_default():
    config.set_conf({"a": 1})
    assert config.get_value("a") == 1
    assert config.get_value("missing") is None
    assert config.get_value("missing", "fallback") == "fallback"


def test_double_set_raises():
    config.set_conf({"a": 1})
    with pytest.raises(config.ConfigError):
        config.set_conf({"b": 2})
