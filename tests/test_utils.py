"""Tests for dataportaltools.local_utils.utils."""

import logging
import os

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


# --------------------------------------------------------------------------- #
# normalize_dataframe / convert_and_rename
# --------------------------------------------------------------------------- #
def test_normalize_dataframe_coerces_int_float_object():
    import pandas as pd

    frame = pd.DataFrame(
        {
            "ts": ["2022-01-01T00:00:00Z", "2022-01-01T01:00:00Z"],
            "counter": ["1", "2"],
            "value": ["1.5", "2.0"],
            "label": ["a", "b"],
        }
    )
    review = utils.normalize_dataframe(frame, skip_cols=["ts"])
    assert pd.api.types.is_integer_dtype(frame["counter"])
    assert pd.api.types.is_float_dtype(frame["value"])
    assert not pd.api.types.is_numeric_dtype(frame["label"])
    assert review == ["label"]


def test_normalize_dataframe_skips_listed_columns():
    import pandas as pd

    frame = pd.DataFrame({"ts": ["1", "2"], "v": ["1", "2"]})
    review = utils.normalize_dataframe(frame, skip_cols=["ts"])
    assert not pd.api.types.is_numeric_dtype(frame["ts"])  # skipped, untouched
    assert pd.api.types.is_integer_dtype(frame["v"])
    assert review == []


def _write_csv_cols(path, **cols):
    import pandas as pd

    pd.DataFrame(cols).to_csv(path, index=False)


def test_convert_and_rename_writes_parquet_zstd(tmp_path):
    import pandas as pd

    p = tmp_path / "dump.csv"
    _write_csv_cols(
        p,
        timestamp=["2022-12-26T00:00:00Z", "2022-12-27T00:00:00Z"],
        counter=["1", "2"],
        label=["a", "b"],
    )
    ok, out_path, review = utils.convert_and_rename(
        str(p), name="history", kind="metric", dtype="float"
    )
    assert ok
    assert out_path.endswith(".zst.parquet")
    assert os.path.basename(out_path) == (
        "history_float_2022-12-26T00:00:00Z_2022-12-27T00:00:00Z_2_raw.zst.parquet"
    )
    assert review == ["label"]
    # The written file is valid parquet with coerced dtypes.
    df = pd.read_parquet(out_path)
    assert pd.api.types.is_integer_dtype(df["counter"])
    assert not pd.api.types.is_numeric_dtype(df["label"])


def test_convert_and_rename_rejects_underscore_name(tmp_path):
    p = tmp_path / "dump.csv"
    _write_csv_cols(p, timestamp=["2022-12-26T00:00:00Z"], v=["1"])
    ok, out_path, review = utils.convert_and_rename(
        str(p), name="bad_name", kind="metric", dtype="float"
    )
    assert not ok
    assert out_path == ""
    assert review == []


def test_convert_and_rename_out_dir(tmp_path):
    p = tmp_path / "dump.csv"
    _write_csv_cols(
        p, timestamp=["2022-12-26T00:00:00Z", "2022-12-27T00:00:00Z"], v=["1", "2"]
    )
    out = tmp_path / "out"
    out.mkdir()
    ok, out_path, _ = utils.convert_and_rename(
        str(p), name="h", kind="metric", dtype="float", out_dir=str(out)
    )
    assert ok
    assert os.path.dirname(out_path) == str(out)


# --------------------------------------------------------------------------- #
# coverage: parse_info blank lines, create_filename log branch, dataframe I/O
# --------------------------------------------------------------------------- #
def test_parse_info_handles_consecutive_blank_lines(tmp_path):
    md = "# Dataset\n\n\nDummy\n\n\n# Tags\n\na, b\n\n\n"
    p = tmp_path / "info.md"
    p.write_text(md, encoding="utf-8")
    data = utils.parse_info(str(p))
    assert data["dataset"] == "Dummy"
    assert data["tags"] == ["a", "b"]


def test_parse_info_trailing_empty_section_is_ignored(tmp_path):
    p = tmp_path / "info.md"
    p.write_text("# Dataset\nDummy\n\n# Tags\n", encoding="utf-8")
    data = utils.parse_info(str(p))
    assert data["dataset"] == "Dummy"
    assert data["tags"] == []


def test_parse_info_blank_line_inside_tags_is_skipped(tmp_path):
    p = tmp_path / "info.md"
    p.write_text("# Tags\na, b\n\nc\n", encoding="utf-8")
    assert utils.parse_info(str(p))["tags"] == ["a", "b", "c"]


def test_create_filename_invalid_stop_rejected():
    data = {
        "datatype": "float",
        "dataflag": "raw",
        "start": "2022-01-01T00:00:00",
        "stop": "not-a-date",
        "count": 5,
        "size": "",
    }
    ok, name = utils.create_filename(data, "x.csv", "metric")
    assert not ok and name == ""


_LOG_BASE = {
    "dataflag": "raw",
    "start": "1737645608",
    "stop": "1737645609",
    "count": 5,
}


def test_create_filename_log_missing_size():
    ok, _ = utils.create_filename(dict(_LOG_BASE), "x.csv.zst", "log")
    assert not ok


def test_create_filename_log_missing_compression():
    ok, _ = utils.create_filename({**_LOG_BASE, "size": "8G"}, "x.csv", "log")
    assert not ok


def test_create_filename_log_ok_without_datatype():
    ok, name = utils.create_filename({**_LOG_BASE, "size": "8G"}, "x.csv.zst", "log")
    assert ok
    assert "_8G_" in name and name.endswith(".zst")


def test_create_filename_log_ok_with_datatype():
    ok, name = utils.create_filename(
        {**_LOG_BASE, "size": "8G", "type": "json"}, "x.csv.zst", "log"
    )
    assert ok
    assert "_8G_" in name


_METRIC_BASE = {
    "datatype": "float",
    "dataflag": "raw",
    "start": "1737645608",
    "stop": "1737645609",
    "count": 5,
}


def test_create_filename_metric_legacy_parquet_zst_becomes_zst_parquet():
    ok, name = utils.create_filename(dict(_METRIC_BASE), "x.parquet.zst", "metric")
    assert ok
    assert name.endswith("_raw.zst.parquet")


def test_create_filename_metric_zst_parquet_kept():
    ok, name = utils.create_filename(dict(_METRIC_BASE), "x.zst.parquet", "metric")
    assert ok
    assert name.endswith("_raw.zst.parquet")


def test_create_filename_metric_parquet_zstd_becomes_zst_parquet():
    ok, name = utils.create_filename(dict(_METRIC_BASE), "x.parquet.zstd", "metric")
    assert ok
    assert name.endswith("_raw.zst.parquet")
    assert "zstd" not in name


def test_create_filename_log_zst_parquet_accepted():
    ok, name = utils.create_filename(
        {**_LOG_BASE, "size": "8G", "datatype": "float"}, "x.zst.parquet", "log"
    )
    assert ok
    assert "_8G_" in name and name.endswith("_raw.zst.parquet")


def test_create_filename_unrelated_extension_pairs_unchanged():
    ok, name = utils.create_filename(dict(_METRIC_BASE), "x.csv.gz", "metric")
    assert ok and name.endswith("_raw.csv.gz")
    ok, name = utils.create_filename(dict(_METRIC_BASE), "x.pkl.zst", "metric")
    assert ok and name.endswith("_raw.pkl.zst")


def test_read_dataframe_pickle(tmp_path):
    import pandas as pd

    p = tmp_path / "d.pkl"
    pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_pickle(p)
    frame = utils._read_dataframe(str(p))
    assert list(frame.columns) == ["a", "b"]
    assert len(frame) == 2


def test_read_dataframe_csv(tmp_path):
    import pandas as pd

    p = tmp_path / "d.csv"
    pd.DataFrame({"a": [1, 2]}).to_csv(p, index=False)
    frame = utils._read_dataframe(str(p))
    assert len(frame) == 2


def test_detect_timestamp_column_fallback_first_column():
    import pandas as pd

    frame = pd.DataFrame({"alpha": [1], "beta": [2]})
    assert utils._detect_timestamp_column(frame, None) == "alpha"


def test_detect_timestamp_column_empty_frame_raises():
    import pandas as pd

    with pytest.raises(ValueError):
        utils._detect_timestamp_column(pd.DataFrame(), None)


def test_rename_from_data_empty_frame(tmp_path):
    p = tmp_path / "e.csv"
    p.write_text("timestamp\n", encoding="utf-8")  # header only, 0 rows
    ok, name = utils.rename_from_data(str(p), name="h", kind="metric", dtype="float")
    assert not ok and name == ""


def test_rename_from_data_no_valid_timestamps(tmp_path):
    import pandas as pd

    p = tmp_path / "nd.csv"
    pd.DataFrame({"timestamp": ["x", "y"], "v": [1, 2]}).to_csv(p, index=False)
    ok, name = utils.rename_from_data(str(p), name="h", kind="metric", dtype="float")
    assert not ok and name == ""


def test_convert_and_rename_empty_frame(tmp_path):
    p = tmp_path / "e.csv"
    p.write_text("timestamp\n", encoding="utf-8")
    ok, out, review = utils.convert_and_rename(
        str(p), name="h", kind="metric", dtype="float"
    )
    assert not ok and out == "" and review == []


def test_convert_and_rename_no_valid_timestamps(tmp_path):
    import pandas as pd

    p = tmp_path / "nd.csv"
    pd.DataFrame({"timestamp": ["x", "y"]}).to_csv(p, index=False)
    ok, out, review = utils.convert_and_rename(
        str(p), name="h", kind="metric", dtype="float"
    )
    assert not ok and out == ""


def test_convert_and_rename_create_filename_fails(tmp_path):
    import pandas as pd

    # kind=metric with dtype="" makes create_filename fail; no parquet written.
    p = tmp_path / "d.csv"
    pd.DataFrame(
        {"timestamp": ["2022-12-26T00:00:00Z", "2022-12-27T00:00:00Z"], "v": [1, 2]}
    ).to_csv(p, index=False)
    ok, out, _ = utils.convert_and_rename(str(p), name="h", kind="metric", dtype="")
    assert not ok and out == ""
    assert not list(tmp_path.glob("*.zst.parquet"))


# --- create_filename: log parquet regression and tail parsing ---------------


def test_create_filename_log_parquet_without_datatype_keeps_zst_parquet():
    # Regression: a plain parquet log with no datatype once came out `.zst`.
    ok, name = utils.create_filename(
        {**_LOG_BASE, "size": "8G"}, "x.zst.parquet", "log"
    )
    assert ok
    assert name.endswith("_8G_raw.zst.parquet")


def test_create_filename_log_non_parquet_without_datatype_unchanged():
    ok, name = utils.create_filename({**_LOG_BASE, "size": "8G"}, "x.json.gz", "log")
    assert ok
    assert name.endswith("_8G_raw.gz")


@pytest.mark.parametrize(
    ("fname", "expected_base", "expected_tail"),
    [
        # dots in the base must not eat the real compression
        ("x.a.csv.gz", "x-a", "raw.csv.gz"),
        ("dump.2024.csv.gz", "dump-2024", "raw.csv.gz"),
        ("my.series.zst.parquet", "my-series", "raw.zst.parquet"),
        # directories are ignored
        ("/tmp/a.b/x.csv.gz", "x", "raw.csv.gz"),
        # zstd is always spelled zst
        ("x.pkl.zstd", "x", "raw.pkl.zst"),
        ("x.csv.zstd", "x", "raw.csv.zst"),
        ("x.zstd", "x", "raw.zst"),
        ("x.zstd.parquet", "x", "raw.zst.parquet"),
        # matching is case-insensitive and the output is lowercase
        ("x.PARQUET.ZST", "x", "raw.zst.parquet"),
        ("x.csv.ZSTD", "x", "raw.csv.zst"),
        ("X.CSV.GZ", "X", "raw.csv.gz"),
        ("x.csv.BZ2", "x", "raw.csv.bz2"),
    ],
)
def test_create_filename_tail_parsing(fname, expected_base, expected_tail):
    ok, name = utils.create_filename(dict(_METRIC_BASE), fname, "metric")
    assert ok
    assert name.startswith(f"{expected_base}_float_")
    assert name.endswith(f"_{expected_tail}")


@pytest.mark.parametrize("fname", ["x", ".csv", "x.", ""])
def test_create_filename_rejects_unparseable_tail(fname):
    ok, name = utils.create_filename(dict(_METRIC_BASE), fname, "metric")
    assert not ok and name == ""


def test_split_name_tail():
    assert utils.split_name_tail("a.b.csv.gz") == ("a.b", "csv", "gz")
    assert utils.split_name_tail("a.zst.parquet") == ("a", "parquet", "zst")
    assert utils.split_name_tail("a.parquet.zstd") == ("a", "parquet", "zst")
    assert utils.split_name_tail("a.parquet") == ("a", "parquet", "")
    assert utils.split_name_tail("a.ZSTD") == ("a", "zst", "")
    assert utils.split_name_tail("noext") == ("", "", "")


def test_split_name_tail_parquet_after_non_compression_token():
    # ".parquet" preceded by a token that is not a codec: parquet is simply the
    # extension and there is no compression.
    assert utils.split_name_tail("x.foo.parquet") == ("x.foo", "parquet", "")
    assert utils.split_name_tail("data.v2.parquet") == ("data.v2", "parquet", "")


def test_create_filename_parquet_after_non_compression_token():
    ok, name = utils.create_filename(dict(_METRIC_BASE), "data.v2.parquet", "metric")
    assert ok
    # No codec token is invented; the name ends in plain ".parquet".
    assert name.endswith("_raw.parquet")
    assert ".zst" not in name


def test_parse_filename_metric_name_without_extension_is_extra():
    # Shaped like a metric and with valid dates, but the tail has no dot, so
    # there is no extension; the log pattern needs one too.
    kind, d = utils.parse_filename(
        "history_float_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_raw"
    )
    assert (kind, d) == ("extra", {})


def test_parse_filename_log_shaped_with_invalid_dates_is_extra():
    kind, d = utils.parse_filename("history_notadate_alsobad_3000_76Mb_raw.json.bz2")
    assert (kind, d) == ("extra", {})


def test_rename_from_data_rejects_dot_name(tmp_path):
    import pandas as pd

    p = tmp_path / "d.csv"
    pd.DataFrame({"timestamp": ["2022-12-26T00:00:00Z"], "v": [1]}).to_csv(
        p, index=False
    )
    ok, name = utils.rename_from_data(str(p), name="a.b", kind="metric", dtype="float")
    assert not ok and name == ""


def test_convert_and_rename_rejects_dot_name(tmp_path):
    import pandas as pd

    p = tmp_path / "d.csv"
    pd.DataFrame({"timestamp": ["2022-12-26T00:00:00Z"], "v": [1]}).to_csv(
        p, index=False
    )
    ok, out, review = utils.convert_and_rename(
        str(p), name="a.b", kind="metric", dtype="float"
    )
    assert not ok and out == "" and review == []
    assert not list(tmp_path.glob("*.parquet"))


def test_rename_from_data_dotted_source_path(tmp_path):
    import pandas as pd

    # Dots in the source path must not leak into the generated name.
    p = tmp_path / "dump.2024.csv.gz"
    pd.DataFrame({"timestamp": ["2022-12-26T00:00:00Z"], "v": [1]}).to_csv(
        p, index=False, compression="gzip"
    )
    ok, name = utils.rename_from_data(str(p), name="h", kind="metric", dtype="float")
    assert ok
    assert name.startswith("h_float_") and name.endswith("_raw.csv.gz")


# --- size ceiling -----------------------------------------------------------


def test_max_file_bytes_value():
    assert utils.MAX_FILE_BYTES == 2147483647


def test_drop_oversized_boundary_is_inclusive(tmp_path, monkeypatch):
    a, b, c = (tmp_path / n for n in ("a", "b", "c"))
    for f in (a, b, c):
        f.write_bytes(b"x")
    sizes = {
        str(a): utils.MAX_FILE_BYTES - 1,
        str(b): utils.MAX_FILE_BYTES,
        str(c): utils.MAX_FILE_BYTES + 1,
    }
    monkeypatch.setattr(utils.os.path, "getsize", lambda p: sizes[p])
    keep, dropped = utils.drop_oversized([str(a), str(b), str(c)])
    assert keep == [str(a), str(b)]
    assert dropped == [str(c)]


def test_drop_oversized_message_names_limit(tmp_path, monkeypatch, caplog):
    f = tmp_path / "big"
    f.write_bytes(b"x")
    monkeypatch.setattr(utils.os.path, "getsize", lambda p: utils.MAX_FILE_BYTES + 1)
    with caplog.at_level(logging.ERROR, logger="toolslib.utils"):
        utils.drop_oversized([str(f)])
    assert "2147483647" in caplog.text
    assert "time window" in caplog.text


def test_convert_and_rename_fails_when_parquet_too_big(tmp_path, monkeypatch):
    import pandas as pd

    p = tmp_path / "d.csv"
    pd.DataFrame(
        {"timestamp": ["2022-12-26T00:00:00Z", "2022-12-27T00:00:00Z"], "v": [1, 2]}
    ).to_csv(p, index=False)
    real_getsize = os.path.getsize
    monkeypatch.setattr(
        utils.os.path,
        "getsize",
        lambda q: (
            utils.MAX_FILE_BYTES + 1 if str(q).endswith(".parquet") else real_getsize(q)
        ),
    )
    ok, out, _ = utils.convert_and_rename(
        str(p), name="h", kind="metric", dtype="float"
    )
    assert not ok and out == ""
    # the unusable file is not left behind
    assert not list(tmp_path.glob("*.parquet"))


def test_convert_and_rename_accepts_parquet_at_limit(tmp_path, monkeypatch):
    import pandas as pd

    p = tmp_path / "d.csv"
    pd.DataFrame(
        {"timestamp": ["2022-12-26T00:00:00Z", "2022-12-27T00:00:00Z"], "v": [1, 2]}
    ).to_csv(p, index=False)
    real_getsize = os.path.getsize
    monkeypatch.setattr(
        utils.os.path,
        "getsize",
        lambda q: (
            utils.MAX_FILE_BYTES if str(q).endswith(".parquet") else real_getsize(q)
        ),
    )
    ok, out, _ = utils.convert_and_rename(
        str(p), name="h", kind="metric", dtype="float"
    )
    assert ok and out.endswith(".zst.parquet")


# --- upload name and datafile acceptance ------------------------------------


@pytest.mark.parametrize(
    ("long_name", "expected"),
    [
        (
            "history_float_2022-12-26T00:00:00.000_2022-12-26T00:20:21.000_10547_raw.zst.parquet",
            "history.zst.parquet",
        ),
        (
            "history_float_2022-12-26T00:00:00_2022-12-27T00:00:00_5_raw.parquet.zst",
            "history.zst.parquet",
        ),
        ("h_float_2022-12-26T00:00:00_2022-12-27T00:00:00_5_raw.pkl.zst", "h.pkl.zst"),
        ("h_float_2022-12-26T00:00:00_2022-12-27T00:00:00_5_raw.csv.ZSTD", "h.csv.zst"),
        ("h_float_2022-12-26T00:00:00_2022-12-27T00:00:00_5_raw.csv", "h.csv"),
        (
            "my.series_float_2022-12-26T00:00:00_2022-12-27T00:00:00_5_raw.csv",
            "my-series.csv",
        ),
        ("l_2022-12-26T00:00:00_2022-12-27T00:00:00_5_8G_raw.json.gz", "l.json.gz"),
        ("l_2022-12-26T00:00:00_2022-12-27T00:00:00_5_8G_raw.gz", "l.gz"),
        (
            "l_2022-12-26T00:00:00_2022-12-27T00:00:00_5_8G_raw.zst.parquet",
            "l.zst.parquet",
        ),
    ],
)
def test_upload_filename_is_short_and_canonical(long_name, expected):
    kind, filedata = utils.parse_filename(long_name)
    assert kind in ("metric", "log")
    assert utils.upload_filename(filedata) == expected


def test_upload_filename_without_name_is_empty():
    assert utils.upload_filename({"ext": "csv"}) == ""
    assert utils.upload_filename({"name": "x"}) == ""


def test_is_plain_pickle():
    _, plain = utils.parse_filename(
        "h_float_2022-12-26T00:00:00_2022-12-27T00:00:00_5_raw.pkl"
    )
    _, packed = utils.parse_filename(
        "h_float_2022-12-26T00:00:00_2022-12-27T00:00:00_5_raw.pkl.zst"
    )
    assert utils.is_plain_pickle(plain)
    assert not utils.is_plain_pickle(packed)


def test_accept_datafile_logs_reasons(caplog):
    _, plain = utils.parse_filename(
        "h_float_2022-12-26T00:00:00_2022-12-27T00:00:00_5_raw.pkl"
    )
    with caplog.at_level(logging.ERROR, logger="toolslib.utils"):
        assert not utils.accept_datafile("a.pkl", "metric", plain)
        assert not utils.accept_datafile("bad.csv", "extra", {})
        assert utils.accept_datafile("ok.csv", "metric", {"ext": "csv"})
    assert "plain .pkl is retired" in caplog.text
    assert "--rename --apply" in caplog.text
    assert "-e/--extra-file" in caplog.text
