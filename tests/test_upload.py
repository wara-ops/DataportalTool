"""Tests for dataportaltools.local_utils.upload.WCIBConnection."""

from unittest.mock import MagicMock

import pytest
import requests
import xxhash

from dataportaltools.local_utils import upload
from dataportaltools.local_utils.upload import WCIBConnection, WCIBError


def _connected():
    """Return a connected WCIBConnection plus its MagicMock session."""
    wc = WCIBConnection("http://x/v1", token="tok")
    sess = MagicMock()
    sess.get.return_value.status_code = 200
    wc.connect(session=sess)
    return wc, sess


# --------------------------------------------------------------------------- #
# connect
# --------------------------------------------------------------------------- #
def test_connect_success():
    wc, sess = _connected()
    assert wc._s is sess
    sess.get.assert_called_once()


def test_connect_no_token_raises():
    wc = WCIBConnection("http://x/v1")
    with pytest.raises(WCIBError, match="No token provided"):
        wc.connect()


def test_connect_failed_test_api_raises():
    wc = WCIBConnection("http://x/v1", token="tok")
    sess = MagicMock()
    sess.get.return_value.status_code = 500
    with pytest.raises(WCIBError, match="Failed to test api"):
        wc.connect(session=sess)


def test_connect_reads_token_file(tmp_path):
    tokfile = tmp_path / "tok.txt"
    tokfile.write_text("  filetoken  \n")
    wc = WCIBConnection("http://x/v1", tokenfile=str(tokfile))
    sess = MagicMock()
    sess.get.return_value.status_code = 200
    wc.connect(session=sess)
    assert wc.token_data == "filetoken"


def test_connect_default_session(mocker):
    sess = MagicMock()
    sess.get.return_value.status_code = 200
    mocker.patch.object(requests, "Session", return_value=sess)
    wc = WCIBConnection("http://x/v1", token="tok")
    wc.connect()
    assert wc._s is sess


# --------------------------------------------------------------------------- #
# create_dataset
# --------------------------------------------------------------------------- #
_VALID_INFO = {
    "category": "metric",
    "tenant": "tester",
    "dataset": "ds1",
    "short info": "short",
    "long info": "long",
    "access": "closed",
    "tags": ["t1"],
}


def test_create_dataset_ok(mocker):
    wc, sess = _connected()
    mocker.patch.object(upload.utils, "parse_info", return_value=_VALID_INFO)
    mocker.patch.object(upload.utils, "validate_info", return_value=True)
    resp = MagicMock()
    resp.json.return_value = {"DatasetID": 1, "ContainerName": "c"}
    resp.raise_for_status.return_value = None
    sess.post.return_value = resp
    assert wc.create_dataset("info.md", "user", False) == 0
    sess.post.assert_called_once()


def test_create_dataset_dryrun(mocker):
    wc, sess = _connected()
    mocker.patch.object(upload.utils, "parse_info", return_value=_VALID_INFO)
    mocker.patch.object(upload.utils, "validate_info", return_value=True)
    assert wc.create_dataset("info.md", "user", True) == 0
    sess.post.assert_not_called()


def test_create_dataset_invalid_raises(mocker):
    wc, _ = _connected()
    mocker.patch.object(upload.utils, "parse_info", return_value={})
    mocker.patch.object(upload.utils, "validate_info", return_value=False)
    with pytest.raises(WCIBError, match="Invalid info file"):
        wc.create_dataset("info.md", "user", False)


def test_create_dataset_http_error(mocker):
    wc, sess = _connected()
    mocker.patch.object(upload.utils, "parse_info", return_value=_VALID_INFO)
    mocker.patch.object(upload.utils, "validate_info", return_value=True)
    resp = MagicMock()
    resp.raise_for_status.side_effect = requests.exceptions.HTTPError("boom")
    sess.post.return_value = resp
    assert wc.create_dataset("info.md", "user", False) == 1


# --------------------------------------------------------------------------- #
# _upload_data
# --------------------------------------------------------------------------- #
def _filedata():
    return {
        "count": 3,
        "start": "s",
        "stop": "e",
        "size": "10",
        "flag": "raw",
        "type": "float",
    }


def test_upload_data_ok(tmp_path):
    wc, sess = _connected()
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")

    post_resp = MagicMock()
    post_resp.json.return_value = {"fileId": 5, "status": "READY"}
    post_resp.raise_for_status.return_value = None
    sess.post.return_value = post_resp

    result = wc._upload_data(1, str(f), _filedata(), False)
    assert result == {"fileId": 5, "status": "READY"}

    # Single atomic POST, no second PUT.
    sess.post.assert_called_once()
    sess.put.assert_not_called()

    _, kwargs = sess.post.call_args
    form = kwargs["data"]
    assert form["size"] == f.stat().st_size
    assert form["filename"] == "file.bin"
    assert form["start"] == "s"
    assert form["stop"] == "e"
    assert form["count"] == 3

    headers = kwargs["headers"]
    expected_key = xxhash.xxh128(f.read_bytes()).hexdigest()
    assert headers["Idempotency-Key"] == expected_key


def test_upload_data_dryrun(tmp_path):
    wc, sess = _connected()
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")
    assert wc._upload_data(1, str(f), _filedata(), True) == {}
    sess.post.assert_not_called()


def test_upload_data_http_error_propagates(tmp_path):
    wc, sess = _connected()
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")
    post_resp = MagicMock()
    post_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("boom")
    sess.post.return_value = post_resp
    with pytest.raises(requests.exceptions.HTTPError):
        wc._upload_data(1, str(f), {"count": 1, "start": "s", "stop": "e"}, False)


# --------------------------------------------------------------------------- #
# _upload_extra
# --------------------------------------------------------------------------- #
def test_upload_extra_ok(tmp_path):
    wc, sess = _connected()
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")
    post_resp = MagicMock()
    post_resp.json.return_value = {"path": "somepath"}
    post_resp.raise_for_status.return_value = None
    sess.post.return_value = post_resp
    result = wc._upload_extra(1, str(f), "dir", False)
    assert result == {"path": "somepath"}


def test_upload_extra_empty_prefix(tmp_path):
    wc, sess = _connected()
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")
    post_resp = MagicMock()
    post_resp.json.return_value = {"path": "p"}
    post_resp.raise_for_status.return_value = None
    sess.post.return_value = post_resp
    result = wc._upload_extra(1, str(f), "", False)
    assert result == {"path": "p"}
    # Empty prefix -> sent as "" (server applies the metadata/ default).
    _, kwargs = sess.post.call_args
    assert kwargs["data"]["prefix"] == ""
    assert kwargs["data"]["filename"] == "file.bin"


def test_upload_extra_two_level_prefix(tmp_path):
    wc, sess = _connected()
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")
    post_resp = MagicMock()
    post_resp.json.return_value = {"path": "p"}
    post_resp.raise_for_status.return_value = None
    sess.post.return_value = post_resp
    # Two path segments are kept as nested folders (no longer a rename).
    result = wc._upload_extra(1, str(f), "dir1/dir2", False)
    assert result == {"path": "p"}
    _, kwargs = sess.post.call_args
    assert kwargs["data"]["prefix"] == "dir1/dir2"
    assert kwargs["data"]["filename"] == "file.bin"


def test_upload_extra_trailing_slash_ignored(tmp_path):
    wc, sess = _connected()
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")
    post_resp = MagicMock()
    post_resp.json.return_value = {"path": "p"}
    post_resp.raise_for_status.return_value = None
    sess.post.return_value = post_resp
    wc._upload_extra(1, str(f), "dir1/dir2/", False)
    _, kwargs = sess.post.call_args
    assert kwargs["data"]["prefix"] == "dir1/dir2"


def test_upload_extra_dryrun(tmp_path):
    wc, sess = _connected()
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")
    assert wc._upload_extra(1, str(f), "dir", True) == {}
    sess.put.assert_not_called()
    sess.post.assert_not_called()


def test_upload_extra_too_many_levels_raises(tmp_path):
    wc, sess = _connected()
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")
    with pytest.raises(WCIBError):
        wc._upload_extra(1, str(f), "dir1/dir2/dir3", False)
    sess.post.assert_not_called()


def test_upload_extra_unsafe_segment_raises(tmp_path):
    wc, sess = _connected()
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")
    with pytest.raises(WCIBError):
        wc._upload_extra(1, str(f), "../escape", False)
    sess.post.assert_not_called()


# --------------------------------------------------------------------------- #
# upload
# --------------------------------------------------------------------------- #
def test_upload_data_branch(tmp_path, mocker):
    wc, sess = _connected()
    f = tmp_path / "data.csv"
    f.write_bytes(b"data")
    mocker.patch.object(upload.utils, "get_all_src_files", return_value=[str(f)])
    mocker.patch.object(wc, "_upload_data_files", return_value=(0, {str(f): "dst"}))
    ret = wc.upload(1, [str(f)], _filedata(), "", "metric", False)
    assert ret == 0
    wc._upload_data_files.assert_called_once()


def test_upload_extra_branch(tmp_path, mocker):
    wc, sess = _connected()
    f = tmp_path / "extra.bin"
    f.write_bytes(b"data")
    mocker.patch.object(upload.utils, "get_all_src_files", return_value=[str(f)])
    mocker.patch.object(wc, "_upload_extra_files", return_value=(0, {str(f): "dst"}))
    ret = wc.upload(1, [str(f)], {}, "prefixdir", "", False, extra=True)
    assert ret == 0
    wc._upload_extra_files.assert_called_once()


def test_upload_no_files(mocker):
    wc, _ = _connected()
    mocker.patch.object(upload.utils, "get_all_src_files", return_value=[])
    assert wc.upload(1, ["nomatch*"], {}, "", "metric", False) == 1


# --------------------------------------------------------------------------- #
# _upload_extra_files / _upload_data_files (integration via real helpers)
# --------------------------------------------------------------------------- #
def test_upload_extra_files_collects_paths(tmp_path, mocker):
    wc, _ = _connected()
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")
    mocker.patch.object(wc, "_upload_extra", return_value={"path": "P"})
    ret, resp = wc._upload_extra_files(1, [str(f)], "dir", False)
    assert ret == 0
    assert resp == {str(f): "P"}


def test_upload_extra_files_handles_error(tmp_path, mocker):
    wc, _ = _connected()
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")
    mocker.patch.object(wc, "_upload_extra", side_effect=Exception("boom"))
    ret, resp = wc._upload_extra_files(1, [str(f)], "dir", False)
    assert ret == 1
    assert resp == {}


def test_upload_data_files_single(tmp_path, mocker):
    wc, _ = _connected()
    f = tmp_path / "file.csv"
    f.write_bytes(b"data")
    mocker.patch.object(
        upload.utils, "create_filename", return_value=(True, "long_name")
    )
    mocker.patch.object(
        upload.utils, "parse_filename", return_value=("metric", _filedata())
    )
    mocker.patch.object(wc, "_upload_data", return_value={"path": "P"})
    ret, resp = wc._upload_data_files(1, [str(f)], _filedata(), "metric", False)
    assert ret == 0
    assert resp == {str(f): "P"}


def test_upload_data_files_single_bad_name(tmp_path, mocker):
    wc, _ = _connected()
    f = tmp_path / "file.csv"
    f.write_bytes(b"data")
    mocker.patch.object(upload.utils, "create_filename", return_value=(False, ""))
    mocker.patch.object(upload.utils, "parse_filename", return_value=("extra", {}))
    ret, resp = wc._upload_data_files(1, [str(f)], {}, "metric", False)
    assert ret == 1
    assert resp == {}


def test_upload_data_files_multi(tmp_path, mocker):
    wc, _ = _connected()
    f1 = tmp_path / "a.csv"
    f2 = tmp_path / "b.csv"
    f1.write_bytes(b"a")
    f2.write_bytes(b"b")
    mocker.patch.object(
        upload.utils, "parse_filename", return_value=("metric", _filedata())
    )
    mocker.patch.object(wc, "_upload_data", return_value={"path": "P"})
    ret, resp = wc._upload_data_files(
        1, [str(f1), str(f2)], _filedata(), "metric", False
    )
    assert ret == 0
    assert len(resp) == 2


def test_upload_data_files_upload_error(tmp_path, mocker):
    wc, _ = _connected()
    f = tmp_path / "a.csv"
    f.write_bytes(b"a")
    mocker.patch.object(upload.utils, "create_filename", return_value=(True, "long"))
    mocker.patch.object(
        upload.utils, "parse_filename", return_value=("metric", _filedata())
    )
    mocker.patch.object(wc, "_upload_data", side_effect=Exception("boom"))
    ret, _resp = wc._upload_data_files(1, [str(f)], _filedata(), "metric", False)
    assert ret == 1


# --------------------------------------------------------------------------- #
# delete
# --------------------------------------------------------------------------- #
def test_delete_force_ok():
    wc, sess = _connected()
    resp = MagicMock()
    resp.json.return_value = {}
    resp.raise_for_status.return_value = None
    sess.delete.return_value = resp
    assert wc.delete(1, True, False) == 0
    sess.delete.assert_called_once()


def test_delete_dryrun():
    wc, sess = _connected()
    assert wc.delete(1, True, True) == 0
    sess.delete.assert_not_called()


def test_delete_non_empty_data_rejected():
    wc, sess = _connected()
    resp = MagicMock()
    resp.json.return_value = {"data": [{"FileID": 1}]}
    resp.raise_for_status.return_value = None
    sess.get.return_value = resp
    assert wc.delete(1, False, False) == 1


def test_delete_list_files_none(mocker):
    wc, _ = _connected()
    mocker.patch.object(wc, "_list_files", return_value=None)
    assert wc.delete(1, False, False) == 1


def test_delete_empty_then_delete(mocker):
    wc, sess = _connected()
    mocker.patch.object(wc, "_list_files", return_value=[])
    resp = MagicMock()
    resp.json.return_value = {}
    resp.raise_for_status.return_value = None
    sess.delete.return_value = resp
    assert wc.delete(1, False, False) == 0


def test_delete_extra_non_empty(mocker):
    wc, _ = _connected()
    mocker.patch.object(wc, "_list_files", side_effect=[[], [{"FileID": 2}]])
    assert wc.delete(1, False, False) == 1


def test_delete_extra_none(mocker):
    wc, _ = _connected()
    mocker.patch.object(wc, "_list_files", side_effect=[[], None])
    assert wc.delete(1, False, False) == 1


def test_delete_http_error():
    wc, sess = _connected()
    resp = MagicMock()
    resp.raise_for_status.side_effect = requests.exceptions.HTTPError("boom")
    sess.delete.return_value = resp
    assert wc.delete(1, True, False) == 1


# --------------------------------------------------------------------------- #
# list_datasets
# --------------------------------------------------------------------------- #
def test_list_datasets_ok():
    wc, sess = _connected()
    resp = MagicMock()
    resp.json.return_value = {
        "Datasets": [
            {
                "DatasetID": 1,
                "DatasetName": "n",
                "CreateDate": "d",
                "Category": "metric",
                "Organization": "Ericsson",
            }
        ]
    }
    resp.raise_for_status.return_value = None
    sess.get.return_value = resp
    assert wc.list_datasets(False) == 0


def test_list_datasets_dryrun():
    wc, sess = _connected()
    assert wc.list_datasets(True) == 0


def test_list_datasets_http_error():
    wc, sess = _connected()
    resp = MagicMock()
    resp.raise_for_status.side_effect = requests.exceptions.HTTPError("boom")
    sess.get.return_value = resp
    assert wc.list_datasets(False) == 1


# --------------------------------------------------------------------------- #
# list_files / _list_files
# --------------------------------------------------------------------------- #
def _file_entry(fid=1):
    return {
        "FileID": fid,
        "StartDate": "2009-10-10T00:10:18.000Z",
        "StopDate": "2009-10-10T00:10:19.000Z",
        "MetricEntries": 9,
        "FileSize": 100,
        "MFileName": "name.csv",
    }


def test_list_files_ok():
    wc, sess = _connected()
    resp = MagicMock()
    resp.json.return_value = {"data": [_file_entry(1)]}
    resp.raise_for_status.return_value = None
    sess.get.return_value = resp
    assert wc.list_files(1, False) == 0


def test_list_files_data_none(mocker):
    wc, _ = _connected()
    mocker.patch.object(wc, "_list_files", return_value=None)
    assert wc.list_files(1, False) == 1


def test_list_files_extra_none(mocker):
    wc, _ = _connected()
    mocker.patch.object(wc, "_list_files", side_effect=[[_file_entry()], None])
    assert wc.list_files(1, False) == 1


def test_list_files_dryrun():
    wc, sess = _connected()
    assert wc.list_files(1, True) == 0
    sess.get.assert_called_once()  # only the connect() test call


def test_internal_list_files_http_error():
    wc, sess = _connected()
    resp = MagicMock()
    resp.raise_for_status.side_effect = requests.exceptions.HTTPError("boom")
    sess.get.return_value = resp
    assert wc._list_files(1, False, False) is None


# --------------------------------------------------------------------------- #
# set_file_metadata
# --------------------------------------------------------------------------- #
def _put_ok(sess, payload=None):
    """Configure sess.put to return a successful response with given json."""
    put_resp = MagicMock()
    put_resp.json.return_value = {} if payload is None else payload
    put_resp.raise_for_status.return_value = None
    sess.put.return_value = put_resp
    return put_resp


def test_set_file_metadata_tags_only():
    wc, sess = _connected()
    _put_ok(sess, {"ok": True})
    result = wc.set_file_metadata(1, 5, tags=["a", "b"])
    assert result == {"ok": True}
    sess.put.assert_called_once()
    args, kwargs = sess.put.call_args
    assert args[0] == "http://x/v1/dataset/1/files/5"
    body = kwargs["json"]
    assert body["tags"] == ["a", "b"]
    assert "pointsOfInterest" not in body
    assert kwargs["headers"]["Authorization"] == "Bearer tok"


def test_set_file_metadata_poi_only():
    wc, sess = _connected()
    _put_ok(sess)
    poi = [{"start": "s", "stop": "e", "text": "note"}]
    wc.set_file_metadata(1, 5, points_of_interest=poi)
    sess.put.assert_called_once()
    _, kwargs = sess.put.call_args
    body = kwargs["json"]
    assert body["pointsOfInterest"] == poi
    assert "tags" not in body


def test_set_file_metadata_both():
    wc, sess = _connected()
    _put_ok(sess)
    poi = [{"start": "s", "stop": "e", "text": "note"}]
    wc.set_file_metadata(1, 5, tags=["t"], points_of_interest=poi)
    _, kwargs = sess.put.call_args
    body = kwargs["json"]
    assert body["tags"] == ["t"]
    assert body["pointsOfInterest"] == poi


def test_set_file_metadata_empty_tags_clears():
    wc, sess = _connected()
    _put_ok(sess)
    # Empty list must still be sent (clear semantics), not skipped.
    wc.set_file_metadata(1, 5, tags=[])
    sess.put.assert_called_once()
    _, kwargs = sess.put.call_args
    assert "tags" in kwargs["json"]
    assert kwargs["json"]["tags"] == []


def test_set_file_metadata_neither_noop():
    wc, sess = _connected()
    assert wc.set_file_metadata(1, 5) == {}
    sess.put.assert_not_called()


def test_set_file_metadata_dryrun():
    wc, sess = _connected()
    assert wc.set_file_metadata(1, 5, tags=["t"], dryrun=True) == {}
    sess.put.assert_not_called()


def test_set_file_metadata_http_error_propagates():
    wc, sess = _connected()
    put_resp = MagicMock()
    put_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("boom")
    sess.put.return_value = put_resp
    with pytest.raises(requests.exceptions.HTTPError):
        wc.set_file_metadata(1, 5, tags=["t"])


# --------------------------------------------------------------------------- #
# upload threads annotations (datafile + extrafile)
# --------------------------------------------------------------------------- #
def test_upload_datafile_threads_annotations(tmp_path, mocker):
    wc, sess = _connected()
    f = tmp_path / "file.csv"
    f.write_bytes(b"data")

    mocker.patch.object(upload.utils, "get_all_src_files", return_value=[str(f)])
    mocker.patch.object(
        upload.utils, "create_filename", return_value=(True, "long_name")
    )
    mocker.patch.object(
        upload.utils, "parse_filename", return_value=("metric", _filedata())
    )
    # data upload POST -> READY datafile with fileId 5
    mocker.patch.object(
        wc, "_upload_data", return_value={"fileId": 5, "status": "READY", "path": "p"}
    )
    # annotation PUT returns {}
    _put_ok(sess, {})

    poi = [{"start": "s", "stop": "e", "text": "n"}]
    ret = wc.upload(
        1,
        [str(f)],
        _filedata(),
        "",
        "metric",
        False,
        tags=["x"],
        points_of_interest=poi,
    )
    assert ret == 0

    # The annotation PUT must hit /files/5 with the tags + poi.
    sess.put.assert_called_once()
    args, kwargs = sess.put.call_args
    assert args[0] == "http://x/v1/dataset/1/files/5"
    assert kwargs["json"]["tags"] == ["x"]
    assert kwargs["json"]["pointsOfInterest"] == poi


def test_upload_extrafile_threads_annotations(tmp_path, mocker):
    wc, sess = _connected()
    f = tmp_path / "extra.bin"
    f.write_bytes(b"data")

    mocker.patch.object(upload.utils, "get_all_src_files", return_value=[str(f)])
    # extra upload PUT -> READY extrafile with fileId 7
    mocker.patch.object(
        wc,
        "_upload_extra",
        return_value={
            "fileId": 7,
            "status": "READY",
            "path": "p",
            "extraFile": True,
        },
    )
    # annotation PUT returns {}
    _put_ok(sess, {})

    ret = wc.upload(1, [str(f)], {}, "metadata", "", False, tags=["x"], extra=True)
    assert ret == 0

    # THIS IS THE EXTRAFILE-WORKS VERIFICATION: annotation PUT to /files/7.
    sess.put.assert_called_once()
    args, kwargs = sess.put.call_args
    assert args[0] == "http://x/v1/dataset/1/files/7"
    assert kwargs["json"]["tags"] == ["x"]
    assert "pointsOfInterest" not in kwargs["json"]


def test_upload_without_annotations_no_setmeta(tmp_path, mocker):
    wc, _ = _connected()
    f = tmp_path / "file.csv"
    f.write_bytes(b"data")

    mocker.patch.object(upload.utils, "get_all_src_files", return_value=[str(f)])
    mocker.patch.object(
        upload.utils, "create_filename", return_value=(True, "long_name")
    )
    mocker.patch.object(
        upload.utils, "parse_filename", return_value=("metric", _filedata())
    )
    mocker.patch.object(
        wc, "_upload_data", return_value={"fileId": 5, "status": "READY", "path": "p"}
    )
    spy = mocker.patch.object(wc, "set_file_metadata")

    ret = wc.upload(1, [str(f)], _filedata(), "", "metric", False)
    assert ret == 0
    # Existing behaviour preserved: no annotation when no flags given.
    spy.assert_not_called()


# --------------------------------------------------------------------------- #
# extrafile end-to-end smoke: upload() entrypoint drives the real
# _upload_extra (multipart + Idempotency-Key) AND the annotation PUT
# --------------------------------------------------------------------------- #
def test_upload_extrafile_end_to_end_with_annotation(tmp_path, mocker):
    wc, sess = _connected()
    f = tmp_path / "extra.bin"
    f.write_bytes(b"payload")

    mocker.patch.object(upload.utils, "get_all_src_files", return_value=[str(f)])

    post_calls = []
    put_calls = []

    def _post(pth, **kwargs):
        post_calls.append((pth, kwargs))
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "fileId": 9,
            "status": "READY",
            "path": "metadata/extra.bin",
            "extraFile": True,
        }
        return resp

    def _put(pth, **kwargs):
        put_calls.append((pth, kwargs))
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {}
        return resp

    sess.post.side_effect = _post
    sess.put.side_effect = _put

    ret = wc.upload(1, [str(f)], {}, "metadata", "", False, tags=["x"], extra=True)
    assert ret == 0

    # Extrafiles upload is a POST (multipart data + Idempotency-Key).
    upload_pth, upload_kwargs = post_calls[0]
    assert upload_pth == "http://x/v1/dataset/1/extrafiles"
    body = upload_kwargs["data"]
    assert body["filename"] == "extra.bin"
    assert body["prefix"] == "metadata"
    assert body["size"] == f.stat().st_size
    assert "files" in upload_kwargs
    expected_key = xxhash.xxh128(f.read_bytes()).hexdigest()
    assert upload_kwargs["headers"]["Idempotency-Key"] == expected_key

    # Annotation is a PUT to /files/9 with tags.
    anno_pth, anno_kwargs = put_calls[0]
    assert anno_pth == "http://x/v1/dataset/1/files/9"
    assert anno_kwargs["json"]["tags"] == ["x"]


# --------------------------------------------------------------------------- #
# _annotate_uploaded
# --------------------------------------------------------------------------- #
def test_annotate_uploaded_noop_no_annotations():
    wc, sess = _connected()
    wc._annotate_uploaded(1, {"fileId": 7, "status": "READY"}, None, None, False)
    sess.put.assert_not_called()


def test_annotate_uploaded_noop_dryrun():
    wc, sess = _connected()
    wc._annotate_uploaded(1, {"fileId": 7, "status": "READY"}, ["a"], None, True)
    sess.put.assert_not_called()


def test_annotate_uploaded_noop_no_fileid():
    wc, sess = _connected()
    wc._annotate_uploaded(1, {"status": "READY"}, ["a"], None, False)
    sess.put.assert_not_called()


def test_annotate_uploaded_noop_not_ready():
    wc, sess = _connected()
    wc._annotate_uploaded(1, {"fileId": 7, "status": "PENDING"}, ["a"], None, False)
    sess.put.assert_not_called()


def test_annotate_uploaded_happy_ready():
    wc, sess = _connected()
    _put_ok(sess, {})
    wc._annotate_uploaded(1, {"fileId": 7, "status": "READY"}, ["a"], None, False)
    sess.put.assert_called_once()
    args, kwargs = sess.put.call_args
    assert args[0] == "http://x/v1/dataset/1/files/7"
    assert kwargs["json"]["tags"] == ["a"]


def test_annotate_uploaded_status_missing_still_annotates():
    wc, sess = _connected()
    _put_ok(sess, {})
    wc._annotate_uploaded(1, {"fileId": 7}, ["a"], None, False)
    sess.put.assert_called_once()
    args, _ = sess.put.call_args
    assert args[0] == "http://x/v1/dataset/1/files/7"


def test_annotate_uploaded_http_error_propagates():
    wc, sess = _connected()
    put_resp = MagicMock()
    put_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("boom")
    sess.put.return_value = put_resp
    with pytest.raises(requests.exceptions.HTTPError):
        wc._annotate_uploaded(1, {"fileId": 7, "status": "READY"}, ["a"], None, False)


# --------------------------------------------------------------------------- #
# annotation-failure path: upload succeeds but annotation fails -> ret==1 but
# the upload is still recorded in resp.
# --------------------------------------------------------------------------- #
def test_upload_data_files_annotation_failure_records_upload(tmp_path, mocker):
    wc, sess = _connected()
    f = tmp_path / "file.csv"
    f.write_bytes(b"data")

    mocker.patch.object(
        upload.utils, "create_filename", return_value=(True, "long_name")
    )
    mocker.patch.object(
        upload.utils, "parse_filename", return_value=("metric", _filedata())
    )
    # Upload succeeds and returns a READY datafile with a path.
    mocker.patch.object(
        wc,
        "_upload_data",
        return_value={"fileId": 5, "status": "READY", "path": "p"},
    )
    # Annotation PUT fails.
    put_resp = MagicMock()
    put_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("boom")
    sess.put.return_value = put_resp

    ret, resp = wc._upload_data_files(
        1, [str(f)], _filedata(), "metric", False, tags=["x"]
    )
    # Annotation failed -> ret 1, but the upload itself is still recorded.
    assert ret == 1
    assert resp == {str(f): "p"}
    # The annotation PUT was attempted.
    sess.put.assert_called_once()


def test_upload_extra_files_annotation_failure_records_upload(tmp_path, mocker):
    wc, sess = _connected()
    f = tmp_path / "extra.bin"
    f.write_bytes(b"data")

    # Upload succeeds and returns a READY extrafile with a path.
    mocker.patch.object(
        wc,
        "_upload_extra",
        return_value={"fileId": 9, "status": "READY", "path": "p"},
    )
    # Annotation PUT fails.
    put_resp = MagicMock()
    put_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("boom")
    sess.put.return_value = put_resp

    ret, resp = wc._upload_extra_files(1, [str(f)], "dir", False, tags=["x"])
    # Annotation failed -> ret 1, but the upload itself is still recorded.
    assert ret == 1
    assert resp == {str(f): "p"}
    sess.put.assert_called_once()


# --------------------------------------------------------------------------- #
# _error_detail and timestamp normalization
# --------------------------------------------------------------------------- #
def test_error_detail_includes_server_body():
    resp = MagicMock()
    resp.text = '{"message":"start must match format date-time"}'
    err = requests.exceptions.HTTPError("400 Client Error: Bad Request")
    err.response = resp
    detail = WCIBConnection._error_detail(err)
    assert "400 Client Error" in detail
    assert "start must match format date-time" in detail


def test_error_detail_plain_exception():
    assert WCIBConnection._error_detail(ValueError("boom")) == "boom"


def test_error_detail_no_response_body():
    err = requests.exceptions.HTTPError("500 Server Error")
    err.response = None
    assert WCIBConnection._error_detail(err) == "500 Server Error"


def test_upload_data_normalizes_timestamps(tmp_path):
    wc, sess = _connected()
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")

    post_resp = MagicMock()
    post_resp.json.return_value = {"fileId": 5, "status": "READY"}
    post_resp.raise_for_status.return_value = None
    sess.post.return_value = post_resp

    data = {
        "count": 3,
        # filename-style timestamps with no timezone
        "start": "2024-01-31T21:00:00",
        "stop": "2024-01-31T21:59:59",
        "flag": "raw",
        "type": "float",
    }
    wc._upload_data(1, str(f), data, False)

    _, kwargs = sess.post.call_args
    form = kwargs["data"]
    # API requires RFC3339 date-time -> normalized with trailing Z
    assert form["start"] == "2024-01-31T21:00:00Z"
    assert form["stop"] == "2024-01-31T21:59:59Z"
