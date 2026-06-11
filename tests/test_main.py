"""Tests for the dataportaltools.main Click CLI."""

import pytest
from click.testing import CliRunner

from dataportaltools.local_utils import config
from dataportaltools.main import main


@pytest.fixture(autouse=True)
def _reset_config():
    attr = "_config__CONFIG" if hasattr(config, "_config__CONFIG") else "__CONFIG"
    setattr(config, attr, None)
    yield
    setattr(config, attr, None)


@pytest.fixture
def runner():
    return CliRunner()


def _patch_conn(mocker):
    """Patch the WCIBConnection class used in main; return (class_mock, instance)."""
    up_mock = mocker.patch("dataportaltools.main.up.WCIBConnection")
    instance = up_mock.return_value
    instance.connect.return_value = None
    return up_mock, instance


def test_help(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "PORTAL_TOKEN" in result.output


def test_connect_failure(runner, mocker):
    _, instance = _patch_conn(mocker)
    instance.connect.side_effect = Exception("nope")
    result = runner.invoke(main, ["-L", "-t", "something"])
    assert result.exit_code == 1
    assert "Failed to connect" in result.output


def test_list_datasets(runner, mocker):
    _, instance = _patch_conn(mocker)
    instance.list_datasets.return_value = 0
    result = runner.invoke(main, ["-L"])
    assert result.exit_code == 0
    instance.list_datasets.assert_called_once()


def test_create_dataset(runner, mocker, tmp_path):
    _, instance = _patch_conn(mocker)
    instance.create_dataset.return_value = 0
    infofile = tmp_path / "info.md"
    infofile.write_text("info")
    result = runner.invoke(main, ["-c", str(infofile), "-u", "user"])
    assert result.exit_code == 0
    instance.create_dataset.assert_called_once()


def test_create_dataset_failure(runner, mocker, tmp_path):
    _, instance = _patch_conn(mocker)
    instance.create_dataset.side_effect = Exception("x")
    infofile = tmp_path / "info.md"
    infofile.write_text("info")
    result = runner.invoke(main, ["-c", str(infofile), "-u", "user"])
    assert result.exit_code == 1
    assert "Failed to execute" in result.output


def test_upload(runner, mocker):
    _, instance = _patch_conn(mocker)
    instance.upload.return_value = 0
    result = runner.invoke(main, ["-U", "17", "-s", "somefile"])
    assert result.exit_code == 0
    instance.upload.assert_called_once()
    assert instance.upload.call_args.args[0] == 17


def test_upload_failure(runner, mocker):
    _, instance = _patch_conn(mocker)
    instance.upload.side_effect = Exception("x")
    result = runner.invoke(main, ["-U", "17", "-s", "somefile"])
    assert result.exit_code == 1
    assert "Failed to execute" in result.output


def test_delete(runner, mocker):
    _, instance = _patch_conn(mocker)
    instance.delete.return_value = 0
    result = runner.invoke(main, ["-d", "17"])
    assert result.exit_code == 0
    instance.delete.assert_called_once()


def test_delete_failure(runner, mocker):
    _, instance = _patch_conn(mocker)
    instance.delete.side_effect = Exception("x")
    result = runner.invoke(main, ["-d", "17"])
    assert result.exit_code == 1
    assert "Failed to execute" in result.output


def test_list_datasets_failure(runner, mocker):
    _, instance = _patch_conn(mocker)
    instance.list_datasets.side_effect = Exception("x")
    result = runner.invoke(main, ["-L"])
    assert result.exit_code == 1
    assert "Failed to execute" in result.output


def test_list_files(runner, mocker):
    _, instance = _patch_conn(mocker)
    instance.list_files.return_value = 0
    result = runner.invoke(main, ["-l", "17"])
    assert result.exit_code == 0
    instance.list_files.assert_called_once()


def test_list_files_failure(runner, mocker):
    _, instance = _patch_conn(mocker)
    instance.list_files.side_effect = Exception("x")
    result = runner.invoke(main, ["-l", "17"])
    assert result.exit_code == 1
    assert "Failed to execute" in result.output


def test_no_action_exits_zero(runner, mocker):
    _patch_conn(mocker)
    result = runner.invoke(main, [])
    assert result.exit_code == 0


def test_portal_token_env(runner, mocker, monkeypatch):
    up_mock, instance = _patch_conn(mocker)
    instance.list_datasets.return_value = 0
    monkeypatch.setenv("PORTAL_TOKEN", "tok")
    result = runner.invoke(main, ["-L"])
    assert result.exit_code == 0
    assert up_mock.call_args.kwargs.get("token") == "tok"


def test_token_file_precedence(runner, mocker, monkeypatch):
    up_mock, instance = _patch_conn(mocker)
    instance.list_datasets.return_value = 0
    monkeypatch.setenv("PORTAL_TOKEN", "envtok")
    result = runner.invoke(main, ["-L", "-t", "myfile"])
    assert result.exit_code == 0
    assert up_mock.call_args.kwargs.get("tokenfile") == "myfile"
    assert up_mock.call_args.kwargs.get("token") == ""


# --------------------------------------------------------------------------- #
# --setmeta annotation of existing files
# --------------------------------------------------------------------------- #
def test_setmeta_without_upload_or_listfiles(runner, mocker):
    _patch_conn(mocker)
    result = runner.invoke(main, ["--setmeta", "5"])
    assert result.exit_code == 2
    assert "requires --upload" in result.output


def test_setmeta_nothing_to_do(runner, mocker):
    _, instance = _patch_conn(mocker)
    result = runner.invoke(main, ["--setmeta", "5", "--upload", "1"])
    assert result.exit_code == 0
    assert "Nothing to do" in result.output
    instance.set_file_metadata.assert_not_called()


def test_setmeta_with_tag(runner, mocker):
    _, instance = _patch_conn(mocker)
    instance.set_file_metadata.return_value = {}
    result = runner.invoke(main, ["--setmeta", "5", "--upload", "1", "--tag", "foo"])
    assert result.exit_code == 0
    instance.set_file_metadata.assert_called_once_with(1, 5, ["foo"], None, False)


def test_setmeta_with_listfiles_dataset_id(runner, mocker):
    _, instance = _patch_conn(mocker)
    instance.set_file_metadata.return_value = {}
    result = runner.invoke(main, ["--setmeta", "5", "--listfiles", "3", "--tag", "foo"])
    assert result.exit_code == 0
    args = instance.set_file_metadata.call_args.args
    assert args[0] == 3


def test_setmeta_failure(runner, mocker):
    _, instance = _patch_conn(mocker)
    instance.set_file_metadata.side_effect = Exception("boom")
    result = runner.invoke(main, ["--setmeta", "5", "--upload", "1", "--tag", "foo"])
    assert result.exit_code == 1
    assert "Failed to execute" in result.output


# --------------------------------------------------------------------------- #
# --poi parsing / validation / normalization
# --------------------------------------------------------------------------- #
def test_poi_malformed_too_few_parts(runner, mocker):
    _patch_conn(mocker)
    result = runner.invoke(main, ["-U", "1", "-s", "somefile", "--poi", "bad"])
    assert result.exit_code == 2
    assert "Invalid --poi" in result.output


def test_poi_invalid_timestamps(runner, mocker):
    _patch_conn(mocker)
    result = runner.invoke(
        main, ["-U", "1", "-s", "somefile", "--poi", "notatime,alsobad,txt"]
    )
    assert result.exit_code == 2
    assert "valid timestamps" in result.output


def test_poi_normalization(runner, mocker):
    _, instance = _patch_conn(mocker)
    instance.set_file_metadata.return_value = {}
    result = runner.invoke(
        main,
        [
            "--setmeta",
            "5",
            "--upload",
            "1",
            "--poi",
            "2022-12-26T00:00:00,2022-12-26T01:00:00,my note",
        ],
    )
    assert result.exit_code == 0
    pois = instance.set_file_metadata.call_args.args[3]
    assert isinstance(pois, list)
    assert len(pois) == 1
    assert pois[0]["text"] == "my note"
    assert pois[0]["start"].endswith("Z")
    assert pois[0]["stop"].endswith("Z")


def test_poi_text_with_commas(runner, mocker):
    _, instance = _patch_conn(mocker)
    instance.set_file_metadata.return_value = {}
    result = runner.invoke(
        main,
        [
            "--setmeta",
            "5",
            "--upload",
            "1",
            "--poi",
            "2022-12-26T00:00:00,2022-12-26T01:00:00,note, with, commas",
        ],
    )
    assert result.exit_code == 0
    pois = instance.set_file_metadata.call_args.args[3]
    assert pois[0]["text"] == "note, with, commas"


def test_poi_multi_file_rejected(runner, mocker, tmp_path):
    _patch_conn(mocker)
    f1 = tmp_path / "file1.csv"
    f2 = tmp_path / "file2.csv"
    f1.write_text("a")
    f2.write_text("b")
    result = runner.invoke(
        main,
        [
            "-U",
            "1",
            "-s",
            str(f1),
            "-s",
            str(f2),
            "--poi",
            "2022-12-26T00:00:00,2022-12-26T01:00:00,t",
        ],
    )
    assert result.exit_code == 2
    assert "multi-file" in result.output


# --------------------------------------------------------------------------- #
# upload threads annotations through to wc.upload
# --------------------------------------------------------------------------- #
def test_upload_threads_tags(runner, mocker, tmp_path):
    _, instance = _patch_conn(mocker)
    instance.upload.return_value = 0
    f = tmp_path / "file.csv"
    f.write_text("data")
    result = runner.invoke(main, ["-U", "1", "-s", str(f), "--tag", "x"])
    assert result.exit_code == 0
    kwargs = instance.upload.call_args.kwargs
    assert kwargs["tags"] == ["x"]
    assert kwargs["points_of_interest"] is None


def test_verbose_flag_configures_logging(runner, mocker):
    _patch_conn(mocker)
    cfg = mocker.patch("dataportaltools.main.utils.configure_logging")
    runner.invoke(main, ["-vv", "-L"])
    cfg.assert_called_once_with(2)


def test_default_quiet_configures_logging_zero(runner, mocker):
    _patch_conn(mocker)
    cfg = mocker.patch("dataportaltools.main.utils.configure_logging")
    runner.invoke(main, ["-L"])
    cfg.assert_called_once_with(0)
