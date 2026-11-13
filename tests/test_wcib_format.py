"""Tests for dataportaltools.local_utils.wcib_format."""

from dataportaltools.local_utils import wcib_format


def _entry(fid, size, name):
    return {
        "FileID": fid,
        "StartDate": "2009-10-10T00:10:18.000Z",
        "StopDate": "2009-10-10T00:10:19.000Z",
        "MetricEntries": 9,
        "FileSize": size,
        "MFileName": name,
    }


def test_print_files_skips_non_list_group(capsys):
    # A listing that failed upstream yields None (or another non-list) in place
    # of a group; it must be skipped without hiding the valid group.
    wcib_format.print_files([None, [_entry(1, 100, "kept.csv")], "oops"])
    out = capsys.readouterr().out
    assert "kept.csv" in out
    # Only the valid group counts towards the total row.
    last_line = out.rstrip("\n").splitlines()[-1]
    assert last_line.split("|")[0].strip() == "1"
    assert last_line.split("|")[4].strip() == "100"
