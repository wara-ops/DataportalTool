"""Tests for dataportaltools.local_utils.utils."""

import logging

import pytest

from dataportaltools.local_utils import utils


@pytest.fixture
def _restore_logging(monkeypatch):
    """Save/restore the toolslib logger level and the log-level env var."""
    monkeypatch.delenv("PORTAL_LOG_LEVEL", raising=False)
    log = logging.getLogger("toolslib")
    prev = log.level
    yield
    log.setLevel(prev)


def test_configure_logging_default_is_warning(_restore_logging):
    utils.configure_logging(0)
    assert logging.getLogger("toolslib").level == logging.WARNING


def test_configure_logging_verbose_info(_restore_logging):
    utils.configure_logging(1)
    assert logging.getLogger("toolslib").level == logging.INFO


def test_configure_logging_verbose_debug(_restore_logging):
    utils.configure_logging(2)
    assert logging.getLogger("toolslib").level == logging.DEBUG


def test_configure_logging_env_var(monkeypatch, _restore_logging):
    monkeypatch.setenv("PORTAL_LOG_LEVEL", "DEBUG")
    utils.configure_logging(0)
    assert logging.getLogger("toolslib").level == logging.DEBUG


def test_configure_logging_flag_overrides_env(monkeypatch, _restore_logging):
    monkeypatch.setenv("PORTAL_LOG_LEVEL", "DEBUG")
    utils.configure_logging(1)  # -v wins over env
    assert logging.getLogger("toolslib").level == logging.INFO


def test_configure_logging_invalid_env_falls_back(monkeypatch, _restore_logging):
    monkeypatch.setenv("PORTAL_LOG_LEVEL", "NOTALEVEL")
    utils.configure_logging(0)
    assert logging.getLogger("toolslib").level == logging.WARNING


def test_valid_date_accepts_iso_with_and_without_fraction_and_z():
    assert utils.valid_date("2024-01-31T23:00:00Z")
    assert utils.valid_date("2024-01-31T23:00:00")
    assert utils.valid_date("2024-01-31T23:00:00.123")


def test_valid_date_rejects_non_dates():
    assert not utils.valid_date("not-a-date")
    assert not utils.valid_date("2024-01-31")


def test_get_all_src_files_non_list_returns_empty():
    assert utils.get_all_src_files("notalist") == []


def test_get_all_src_files_globs(tmp_path):
    (tmp_path / "a.csv").write_text("x", encoding="utf-8")
    (tmp_path / "b.csv").write_text("y", encoding="utf-8")
    pattern = str(tmp_path / "*.csv")
    found = utils.get_all_src_files([pattern, 123])  # 123 is ignored (not str)
    assert sorted(found) == sorted([str(tmp_path / "a.csv"), str(tmp_path / "b.csv")])


def test_validate_info_missing_keys():
    assert not utils.validate_info({})


def test_validate_info_bad_category():
    data = {
        "dataset": "d",
        "category": "bogus",
        "tenant": "t",
        "short info": "s",
        "long info": "l",
        "tags": [],
    }
    assert not utils.validate_info(data)


@pytest.mark.parametrize("category", ["metric", "log", "logs", "Metric", "LOG"])
def test_validate_info_accepts_known_categories(category):
    data = {
        "dataset": "d",
        "category": category,
        "tenant": "t",
        "short info": "s",
        "long info": "l",
        "tags": [],
    }
    assert utils.validate_info(data)


def test_parse_info_extracts_all_sections(tmp_path):
    md = (
        "# Dataset\nDummy dataset\n\n"
        "# Tenant\nEricsson\n\n"
        "# Category: metric/log\nmetric\n\n"
        "# Short Info\nShort slogan\n\n"
        "# Long Info\nLonger text.\n- fact 1.\n\n"
        "# Tags\ntag1, tag2\n\n"
        "# Access: open/closed\nclosed\n"
    )
    p = tmp_path / "info.md"
    p.write_text(md, encoding="utf-8")

    data = utils.parse_info(str(p))

    assert data["dataset"] == "Dummy dataset"
    assert data["tenant"] == "Ericsson"
    assert data["category"] == "metric"
    assert data["short info"] == "Short slogan"
    assert data["long info"] == "Longer text.\n- fact 1."
    assert data["access"] == "closed"
    assert data["tags"] == ["tag1", "tag2"]


def test_parse_info_bulleted_tags(tmp_path):
    md = "# Dataset\nd\n\n# Tags\n- tag1\n- tag2\n"
    p = tmp_path / "info.md"
    p.write_text(md, encoding="utf-8")
    data = utils.parse_info(str(p))
    assert "tag1" in data["tags"]
    assert "tag2" in data["tags"]


# --- parse_filename: ported from the original module __main__ assertions ---


def test_parse_filename_extra_when_unparseable():
    kind, _ = utils.parse_filename(
        "history_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_76Mb.json.zip"
    )
    assert kind == "extra"


def test_parse_filename_plain_name_is_extra():
    assert utils.parse_filename("readme.md") == ("extra", {})


def test_parse_filename_log_with_datatype():
    kind, d = utils.parse_filename(
        "history_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_76Mb_raw.json.bz2"
    )
    assert kind == "log"
    assert d["compression"] == "bz2"
    assert d["type"] == "json"
    assert d["flag"] == "raw"


def test_parse_filename_log_without_datatype():
    kind, d = utils.parse_filename(
        "history_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_76Mb_raw.bz2"
    )
    assert kind == "log"
    assert d["compression"] == "bz2"
    assert d["flag"] == "raw"


def test_parse_filename_metric_with_compression():
    kind, d = utils.parse_filename(
        "history_float_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_raw.csv.zip"
    )
    assert kind == "metric"
    assert d["compression"] == "zip"
    assert d["ext"] == "csv"


def test_parse_filename_metric_without_compression():
    kind, d = utils.parse_filename(
        "history_float_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_raw.csv"
    )
    assert kind == "metric"
    assert d["ext"] == "csv"


# --- _parse_time ---


def test_parse_time_empty_returns_none_pair():
    assert utils._parse_time("") == (None, "")


def test_parse_time_iso():
    obj, norm = utils._parse_time("2022-12-26T00:00:00")
    assert obj is not None
    assert norm == "2022-12-26T00:00:00Z"


def test_parse_time_epoch_seconds():
    obj, norm = utils._parse_time("1737645608")
    assert obj is not None
    assert norm.endswith("Z")


def test_parse_time_invalid_string():
    assert utils._parse_time("totally-not-a-time") == (None, "")


def test_parse_time_too_large_epoch_invalid():
    # value/1e10 > 1.0 is treated as invalid format
    assert utils._parse_time("99999999999999") == (None, "")


# --- create_filename: ported from the original module __main__ assertions ---


def test_create_filename_rejects_unknown_kind():
    ok, name = utils.create_filename({}, "x.csv", "bogus")
    assert not ok
    assert name == ""


def test_create_filename_log_requires_compression():
    data = {
        "datatype": "float",
        "dataflag": "raw",
        "start": "2022-12-26T00:00:00",
        "stop": "2022-12-26T01:00:00",
        "count": 700,
        "size": "8.1G",
    }
    ok, _ = utils.create_filename(data, "kenny.csv", "log")
    assert not ok  # no compression


def test_create_filename_log_ok():
    data = {
        "datatype": "float",
        "dataflag": "raw",
        "start": "2022-12-26T00:00:00",
        "stop": "2022-12-26T01:00:00",
        "count": 700,
        "size": "8.1G",
    }
    ok, name = utils.create_filename(data, "kenny.pkl.zst", "log")
    assert ok
    assert (
        name == "kenny_2022-12-26T00:00:00Z_2022-12-26T01:00:00Z_700_8.1G_raw.pkl.zst"
    )


def test_create_filename_metric_from_epoch_and_pretty_flag():
    data = {
        "datatype": "float",
        "dataflag": "raw and juicy",
        "start": "1737645608",
        "stop": "1737645608.6",
        "count": 700,
        "size": "",
    }
    ok, name = utils.create_filename(data, "kenny.csv", "metric")
    assert ok
    # spaces in the flag are normalized to dashes
    assert "raw-and-juicy" in name
    assert name.startswith("kenny_float_")
    assert name.endswith("_raw-and-juicy.csv")


def test_create_filename_metric_with_compression():
    data = {
        "datatype": "float",
        "dataflag": "raw and juicy",
        "start": "1737645608",
        "stop": "1737645608.6",
        "count": 700,
        "size": "",
    }
    ok, name = utils.create_filename(data, "kenny.pkl.zst", "metric")
    assert ok
    assert name.endswith(".pkl.zst")


def test_create_filename_missing_datatype_for_metric():
    data = {
        "dataflag": "raw",
        "start": "1737645608",
        "stop": "1737645608.6",
        "count": 700,
    }
    ok, _ = utils.create_filename(data, "kenny", "metric")
    assert not ok


def test_create_filename_zero_count_rejected():
    data = {
        "datatype": "float",
        "dataflag": "raw",
        "start": "1737645608",
        "stop": "1737645608.6",
        "count": 0,
        "size": "1",
    }
    ok, _ = utils.create_filename(data, "kenny.csv.zst", "log")
    assert not ok


def test_create_filename_invalid_start_rejected():
    data = {
        "datatype": "float",
        "dataflag": "raw",
        "start": "nope",
        "stop": "1737645608.6",
        "count": 700,
        "size": "1",
    }
    ok, _ = utils.create_filename(data, "kenny.csv.zst", "log")
    assert not ok


def test_create_filename_stop_before_start_rejected():
    data = {
        "datatype": "float",
        "dataflag": "raw",
        "start": "1737645608",
        "stop": "1737645607",
        "count": 700,
        "size": "12343243",
    }
    ok, _ = utils.create_filename(data, "kenny.csv.zst", "log")
    assert not ok


def test_create_filename_empty_dataflag_rejected():
    data = {
        "datatype": "float",
        "dataflag": "",
        "start": "1737645608",
        "stop": "1737645608.6",
        "count": 700,
        "size": "1",
    }
    ok, _ = utils.create_filename(data, "kenny.csv.zst", "log")
    assert not ok


def test_create_filename_no_extension_rejected():
    data = {
        "datatype": "float",
        "dataflag": "raw",
        "start": "1737645608",
        "stop": "1737645608.6",
        "count": 700,
        "size": "1",
    }
    ok, _ = utils.create_filename(data, "kenny", "log")
    assert not ok


# --------------------------------------------------------------------------- #
# rename_from_data
# --------------------------------------------------------------------------- #
def _write_csv(path, timestamps, col="timestamp"):
    import pandas as pd

    pd.DataFrame({col: timestamps, "value": range(len(timestamps))}).to_csv(
        path, index=False
    )


def test_rename_from_data_csv_metric(tmp_path):
    p = tmp_path / "raw.csv"
    _write_csv(p, ["2022-12-26T00:00:00Z", "2022-12-27T00:00:00Z"])
    ok, name = utils.rename_from_data(
        str(p), name="history", kind="metric", dtype="float", flag="raw"
    )
    assert ok
    assert name == ("history_float_2022-12-26T00:00:00Z_2022-12-27T00:00:00Z_2_raw.csv")


def test_rename_from_data_autodetect_time_column(tmp_path):
    p = tmp_path / "d.csv"
    _write_csv(p, ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"], col="time")
    ok, name = utils.rename_from_data(str(p), name="srs", kind="metric", dtype="uint")
    assert ok
    assert name.startswith("srs_uint_2024-01-01T00:00:00Z_2024-01-01T01:00:00Z_2_")


def test_rename_from_data_parquet(tmp_path):
    import pandas as pd

    p = tmp_path / "d.parquet"
    pd.DataFrame(
        {"timestamp": pd.to_datetime(["2024-02-01T00:00:00Z", "2024-02-01T06:00:00Z"])}
    ).to_parquet(p)
    ok, name = utils.rename_from_data(str(p), name="srs", kind="metric", dtype="float")
    assert ok
    assert name.endswith(".parquet")
    assert "_2_" in name


def test_rename_from_data_preserves_compression_suffix(tmp_path):
    p = tmp_path / "d.csv.zst"
    _write_csv(p, ["2024-02-01T00:00:00Z", "2024-02-01T12:00:00Z"])
    ok, name = utils.rename_from_data(str(p), name="logz", kind="metric", dtype="float")
    assert ok
    assert name.endswith(".csv.zst")


def test_rename_from_data_rejects_underscore_name(tmp_path):
    p = tmp_path / "raw.csv"
    _write_csv(p, ["2022-12-26T00:00:00Z", "2022-12-27T00:00:00Z"])
    ok, name = utils.rename_from_data(
        str(p), name="bad_name", kind="metric", dtype="float"
    )
    assert not ok
    assert name == ""


def test_rename_from_data_explicit_tscol(tmp_path):
    p = tmp_path / "d.csv"
    _write_csv(p, ["2024-03-01T00:00:00Z", "2024-03-02T00:00:00Z"], col="when")
    ok, name = utils.rename_from_data(
        str(p), name="x", kind="metric", dtype="float", timestamp_col="when"
    )
    assert ok
    assert "2024-03-01T00:00:00Z" in name


def test_rename_from_data_bad_tscol_raises(tmp_path):
    p = tmp_path / "d.csv"
    _write_csv(p, ["2024-03-01T00:00:00Z"])
    with pytest.raises(ValueError):
        utils.rename_from_data(
            str(p), name="x", kind="metric", dtype="float", timestamp_col="nope"
        )


def test_rename_from_data_unsupported_format(tmp_path):
    p = tmp_path / "d.txt"
    p.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        utils.rename_from_data(str(p), name="x", kind="metric", dtype="float")
