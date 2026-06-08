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
