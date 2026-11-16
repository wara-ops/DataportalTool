"""Filename parsing, validation and construction helpers for the CLI."""

import glob
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

from .sniff import (
    MAGIC_HEX,
    PANDAS_CODEC,
    Sniff,
    check_not_wrapped_parquet,
    sniff_file,
    wrapped_parquet_message,
)

_logger = logging.getLogger("toolslib.utils")

# Default to quiet; configure_logging() raises this when asked.
_LOG_ENV_VAR = "PORTAL_LOG_LEVEL"
_DEFAULT_LEVEL = logging.WARNING


def configure_logging(verbose: int = 0) -> None:
    """Configure the ``toolslib`` loggers' verbosity.

    Precedence (highest first):
      * ``verbose`` count from the CLI (-v -> INFO, -vv or more -> DEBUG);
      * the ``PORTAL_LOG_LEVEL`` environment variable (e.g. DEBUG/INFO/WARNING);
      * the default (WARNING) -- only warnings and errors are shown.

    Installs a basic stderr handler once so the chosen level actually prints.
    Messages are shown as ``ERROR: <text>`` rather than with the internal
    logger name, since most of them are meant for the person running the tool.
    """
    if verbose >= 2:
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    else:
        env = os.environ.get(_LOG_ENV_VAR, "").strip().upper()
        level = getattr(logging, env, None) if env else None
        if not isinstance(level, int):
            level = _DEFAULT_LEVEL

    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
    logging.getLogger("toolslib").setLevel(level)


def parse_info(filename: str) -> dict:
    # The Markdown section parser is a small state machine; the extra branches
    # keep the parsing readable in one place rather than split across helpers.
    # pylint: disable=too-many-branches
    """
    Extracts information fields from named file needed when creating a new dataset

    Parameters
    ----------
    filename : str
        Name of information (Markdown) file

    Returns
    -------
    dict
        Containing key/values entry/data

    Raises
    ------
    """
    with open(filename, encoding="utf-8") as f:
        info = f.read()

    data = {}
    section = None
    txt = ""
    for line in info.split("\n"):
        m = re.fullmatch(r"#\s*(.*)", line)
        if m is not None:
            if (section is not None) and (txt != ""):
                data[section] = txt.strip()

            section = m.group(1).lower().strip()

            if "access" in section:
                section = "access"
            elif "category" in section:
                section = "category"
            else:
                pass

            txt = ""
            continue

        if (line == "") and (txt == ""):
            continue

        if txt == "":
            txt = line
        else:
            txt = f"{txt}\n{line}"

    if (section not in data) and (txt != ""):
        data[section] = txt.strip()

    _tags = []
    tags = data.get("tags", "")
    for line in tags.split("\n"):
        _line = None

        _s = re.split(r"[*+-.0-9]+\s+", line)
        if (len(_s) > 1) and (_s[0] == ""):
            _line = _s[1]

        _line = _line or line

        _s = re.split(r",\s+", _line)
        if (len(_s) > 0) and (_s[0] != ""):
            _tags.extend(_s)

    data["tags"] = _tags
    return data


def validate_info(data: dict) -> bool:
    """
    Inspects if all relevant fields are provided

    Parameters
    ----------
    data : dict
        Dictionary describing the new dataset

    Returns
    -------
    Boolean
        True if all keys are provided, else False

    Raises
    ------
    """
    for k in ["dataset", "category", "tenant", "short info", "long info", "tags"]:
        if k not in data:
            return False

    if data["category"].lower() not in ["metric", "log", "logs"]:
        return False

    return True


def get_all_src_files(src_list: list[str]) -> list[str]:
    """
    Uses file globbing to find all files that can be uploaded

    Parameters
    ----------
    src_list : list[str]
        Filename pattern matching

    Returns
    -------
    list
        List of files fulfilling the pattern matching

    Raises
    ------
    """
    ret = []

    if not isinstance(src_list, list):
        return ret

    for s in src_list:
        if isinstance(s, str):
            _ret = glob.glob(s, recursive=False)
            ret.extend(_ret)

    return ret


def valid_date(s: str) -> bool:
    """
    Inspects if provided date string in filename is on correct format


    Parameters
    ----------
    s : str
        Datestring

    Returns
    -------
    Boolean
        True, if date is valid, False if not

    Raises
    ------
    """
    date_pattern = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z?"
    m = re.search(date_pattern, s)

    return m is not None


def parse_filename(fname: str) -> tuple[str, dict]:
    """
    Inspect that ``fname`` follows the dataset naming convention.

    See ``wcib/docs/namingconvention.md`` for the full metric and log formats.
    A metric name has six underscore-separated fields plus a ``type`` field;
    a log name has six fields including an uncompressed ``size``.

    Parameters
    ----------
    fname : str
        File name

    Returns
    -------
    str, dict
        String is either "metric" or "log" depending on the filename
        Dict is parsed filename
            {"name": str,
             "type": str,
             "start": str,
             "stop": str,
             "count": str,
             "flag": str,
             "ext": str,
             "compression": str,
             "prefix": str
            }

    "extra", {}
         Default. Used for files that fail the naming convention and are
         therefore assumed to be extra files.

    Raises
    ------
    """
    regex_pattern = r"([^_]+)_([^_]+)_([^_]+)_([^_]+)_([^_]+)_([^_]+)"
    m = re.search(regex_pattern, fname)
    if m is not None:
        if valid_date(m.group(3)) and valid_date(m.group(4)):
            tail = m.group(6)
            tail_pattern = r"([^.]+)\.([^.]+)\.([^.]+)"
            t = re.search(tail_pattern, tail)
            if t is not None:
                return "metric", {
                    "name": m.group(1),
                    "type": m.group(2),
                    "start": m.group(3),
                    "stop": m.group(4),
                    "count": m.group(5),
                    "flag": t.group(1),
                    "ext": t.group(2),
                    "compression": t.group(3),
                    "prefix": m.group(3)[0:4],
                }

            tail_pattern = r"([^.]+)\.([^.]+)"
            t = re.search(tail_pattern, tail)
            if t is not None:
                return "metric", {
                    "name": m.group(1),
                    "type": m.group(2),
                    "start": m.group(3),
                    "stop": m.group(4),
                    "count": m.group(5),
                    "flag": t.group(1),
                    "ext": t.group(2),
                    "prefix": m.group(3)[0:4],
                }
        else:
            # invalid date(s)
            pass

    # try log
    regex_pattern = r"([^_]+)_([^_]+)_([^_]+)_([^_]+)_([^_]+)_([^.]+)\.(.*)"
    m = re.search(regex_pattern, fname)
    if m is not None:
        if valid_date(m.group(2)) and valid_date(m.group(3)):
            tail = m.group(7)
            tail_pattern = r"([^.]+)\.([^.]+)"
            t = re.search(tail_pattern, tail)
            if t is not None:
                return "log", {
                    "name": m.group(1),
                    "start": m.group(2),
                    "stop": m.group(3),
                    "count": m.group(4),
                    "size": m.group(5),
                    "flag": m.group(6),
                    "type": t.group(1),
                    "compression": t.group(2),
                    "prefix": m.group(3)[0:4],
                }

            return "log", {
                "name": m.group(1),
                "start": m.group(2),
                "stop": m.group(3),
                "count": m.group(4),
                "size": m.group(5),
                "flag": m.group(6),
                "compression": m.group(7),
                "prefix": m.group(3)[0:4],
            }
        # invalid date(s)

    return "extra", {}


def normalize_timestamp(s: str) -> tuple[bool, str]:
    """Normalize an ISO-8601 or epoch timestamp string.

    Returns ``(True, normalized)`` on success, or ``(False, "")`` if the input
    is empty or cannot be parsed. The normalized form is the
    ``YYYY-MM-DDThh:mm:ss[.uuu]Z`` representation the API expects.
    """
    obj, norm = _parse_time(s)
    return obj is not None, norm


def _parse_time(s: str) -> tuple[object, str]:
    """Parse an ISO-8601 or epoch timestamp into a (datetime, normalized) pair.

    Returns ``(None, "")`` for empty or unparseable input. The normalized
    string uses the ``YYYY-MM-DDThh:mm:ss[.uuu]Z`` form expected by the API.
    """
    if s == "":
        return None, ""

    try:
        time_f = float(s)
    except ValueError as e:
        _logger.debug("Not epoch, it seems, %s", str(e))
        time_f = -1.0

    time_o = None
    if time_f > 1e9:
        time_s = time_f / 1e10

        if time_s > 1.0:
            # invalid format
            return None, ""

        try:
            time_o = datetime.fromtimestamp(time_f, timezone.utc)
        except (
            ValueError,
            OverflowError,
            OSError,
        ) as e:  # pragma: no cover - bounded epoch rarely overflows
            _logger.debug("Not epoch, it seems, %s", str(e))
            return None, ""
    else:
        # last chance for parsing the date string
        try:
            time_o = datetime.fromisoformat(s)
        except ValueError as e:
            _logger.debug("Invalid date format '%s', %s", s, str(e))
            return None, ""

    if time_o is None:  # pragma: no cover - defensive, should not happen
        # this shall NOT happen
        return None, ""

    time_ts = time_o.strftime("%Y-%m-%dT%H:%M:%S.%f")
    time_ts = re.sub(r"\.000000", "", time_ts)
    if "." in time_ts:
        time_ts = time_ts[:-3]
    time_ts = f"{time_ts}Z"

    _logger.debug("time_ts %s", time_ts)

    return time_o, time_ts


_COMPRESSION_TOKENS = frozenset({"gz", "bz2", "zst", "zstd"})

# The portal rejects any file larger than this (a signed 32-bit size column);
# the limit is inclusive, so exactly this many bytes is accepted.
MAX_FILE_BYTES = 2147483647


def _normalize_compression(token: str) -> str:
    """Lowercase a compression token and spell zstandard ``zst``, never ``zstd``."""
    token = token.lower()
    return "zst" if token == "zstd" else token


def split_name_tail(fname: str) -> tuple[str, str, str]:
    """Split a file name into ``(base, extension, compression)``.

    The name is reduced to its basename and parsed from the END, so dots inside
    the base are harmless. The last dot-token is a compression method only when
    it is one of gz/bz2/zst/zstd (any case, ``zstd`` normalised to ``zst``);
    otherwise it is the format. A codec before ``parquet`` (``.zst.parquet``) is
    reported as the compression of a ``parquet`` extension. Extension and
    compression are lowercased; the base keeps its case. Missing parts are
    returned as empty strings.
    """
    tokens = os.path.basename(fname).split(".")
    if len(tokens) < 2:
        return "", "", ""

    last = tokens[-1].lower()
    if len(tokens) >= 3 and last in _COMPRESSION_TOKENS:
        return ".".join(tokens[:-2]), tokens[-2].lower(), _normalize_compression(last)
    if len(tokens) >= 3 and last == "parquet":
        codec = tokens[-2].lower()
        if codec in _COMPRESSION_TOKENS:
            return ".".join(tokens[:-2]), "parquet", _normalize_compression(codec)
    if last in _COMPRESSION_TOKENS:
        last = _normalize_compression(last)
    return ".".join(tokens[:-1]), last, ""


def format_suffix(extension: str, compression: str) -> str:
    """Return the canonical dot-suffix for an extension/compression pair.

    Plain parquet whose columns use the zstd codec is ``.zst.parquet`` (the
    codec is inside the file, so the compression token comes first). The legacy
    ``.parquet.zst`` is therefore rewritten; every other pair is
    ``.<extension>.<compression>``.
    """
    if compression == "":
        return f".{extension}"
    if extension == "parquet" and compression == "zst":
        return f".{compression}.{extension}"
    return f".{extension}.{compression}"


def _data_tail(filedata: dict) -> tuple[str, str]:
    """Return the ``(extension, compression)`` implied by a parsed file name."""
    if "ext" in filedata:  # metric: <flag>.<extension>[.<compression>]
        parts = [filedata.get("ext", ""), filedata.get("compression", "")]
    else:  # log: <flag>[.<type>].<compression>
        parts = [filedata.get("type", ""), filedata.get("compression", "")]
    _, extension, compression = split_name_tail("x." + ".".join(p for p in parts if p))
    return extension, compression


def is_plain_pickle(filedata: dict) -> bool:
    """True when a parsed file name is a bare, uncompressed ``.pkl``."""
    extension, compression = _data_tail(filedata)
    return extension == "pkl" and compression == ""


def upload_filename(filedata: dict) -> str:
    """Build the short filename sent to the portal for a parsed data file.

    The server derives the stored name from the metadata and from the upload
    filename split on dots, using only the first ``_`` token and the dot-tail.
    A full convention name (fractional timestamps contain dots) would corrupt
    that split, so send ``<name>.<canonical-suffix>`` instead, e.g.
    ``history.zst.parquet``. Returns ``""`` when ``filedata`` has no name or
    tail to build it from.
    """
    name = filedata.get("name", "")
    extension, compression = _data_tail(filedata)
    if not name or not extension:
        return ""
    return f"{name.replace('.', '-')}{format_suffix(extension, compression)}"


def drop_oversized(files: list[str]) -> tuple[list[str], list[str]]:
    """Split ``files`` into ``(uploadable, oversized)`` by the portal size limit.

    The portal answers 413 for anything above ``MAX_FILE_BYTES`` only after the
    whole file has been read, hashed and sent, so refuse it up front. Each
    oversized file is logged as an error.
    """
    keep, dropped = [], []
    for f in files:
        nbytes = os.path.getsize(f)
        if nbytes > MAX_FILE_BYTES:
            _logger.error(
                "Skipped %s: it is %.2f GiB (%d bytes), over the portal limit of "
                "%d bytes (one byte under 2 GiB). Split the file by time window "
                "into smaller files and upload those.",
                f,
                nbytes / 2**30,
                nbytes,
                MAX_FILE_BYTES,
            )
            dropped.append(f)
        else:
            keep.append(f)
    return keep, dropped


def accept_datafile(fname: str, kind: str, filedata: dict) -> bool:
    """Decide whether ``fname`` may be uploaded as a datafile, logging why not.

    Rejects names that do not follow the naming convention (``kind`` is
    ``"extra"``) and bare, uncompressed ``.pkl`` files, which are retired for
    new uploads.
    """
    if kind == "extra":
        _logger.error(
            "Rejected %s: the name does not follow the naming convention "
            "(see 'Naming convention' in the README). Either rename it "
            "(--rename suggests a name), or, for a single file, describe it "
            "with --kind, --start, --stop, --count, --flag and --dtype (metric) "
            "or --size (log) so the name is built for you, or pass "
            "-e/--extra-file to upload it unchanged as an extra file.",
            fname,
        )
        return False

    if is_plain_pickle(filedata):
        _logger.error(
            "Rejected %s: plain .pkl is retired for new uploads (uncompressed "
            "pickles are no longer accepted). Compress it to .pkl.zst (for "
            "example 'zstd <file>') and upload that, or convert it to parquet "
            "with --rename --apply.",
            fname,
        )
        return False

    # The name may lie about the bytes (see ``sniff.py``).
    return check_not_wrapped_parquet(fname)


def create_filename(
    data: dict, fname: str, kind: str, path: Optional[str] = None
) -> tuple[bool, str]:
    # This builds a name from many independent fields and validates each one
    # with an early return, which is clearer than nesting; the resulting
    # statement/branch/return counts are inherent to that validation.
    # pylint: disable=too-many-branches,too-many-return-statements
    # pylint: disable=too-many-statements,too-many-locals
    """
    Creates a filename that follows the naming convention using data

    Parameters
    ----------
    data : dict
        Dict contains field data
           data = {
                    "datatype": str,
                    "dataflag": str,
                    "start": str,
                    "stop": str,
                    "count": int,
                    "size": str,
                }
    fname : str
        File name
    kind : str
        Kind of filename, "metric", or "log"
    path : str | None
        The real file ``fname`` is taken from, when it exists. Its first bytes
        are checked so a parquet file that is wrapped in zstd/gzip/bz2 is not
        given a ``.zst.parquet`` name (a false claim). ``None`` skips the check.

    Returns
    -------
    tuple[bool, str]
        Constructed filename, or "" fname if name cannot be determined

    Raises
    ------
    """
    if kind not in ["metric", "log"]:
        # No --kind at all is the normal case for a file whose name already
        # follows the convention, so only a wrong value is worth an error.
        report = _logger.debug if kind == "" else _logger.error
        report(
            "Cannot build a file name: --kind must be 'metric' or 'log', got '%s'",
            kind,
        )
        return False, ""

    if path is not None and not check_not_wrapped_parquet(path):
        return False, ""

    # required fields are start, stop and count
    _logger.debug("create_filename, data %s", json.dumps(data))

    count = int(data.get("count", "0"))
    if count <= 0:
        _logger.debug("create_filename, count %d", count)
        return False, ""

    start_o, start = _parse_time(data.get("start", ""))
    if start_o is None:
        _logger.debug("create_filename, start_o %s", str(start_o))
        return False, ""

    stop_o, stop = _parse_time(data.get("stop", ""))
    if stop_o is None:
        _logger.debug("create_filename, stop_o %s", str(stop_o))
        return False, ""

    # Sanity check
    if stop_o < start_o:
        _logger.error(
            "The stop time (%s) is earlier than the start time (%s); "
            "check --start and --stop",
            stop,
            start,
        )
        return False, ""

    # See wcib/docs/namingconvention.md for the metric and log field layouts.

    # dataflag is also needed
    dataflag = data.get("dataflag", "")
    if dataflag == "":
        _logger.debug("create_filename, empty dataflag")
        return False, ""

    # inspect the tail: <base>.<extension>[.<compression>] or <base>.<codec>.parquet
    base, extension, compression = split_name_tail(fname)

    if (base.strip(".") == "") or (extension == ""):
        _logger.debug("create_filename, base or extension empty")
        return False, ""

    def _pretty(abc: str) -> str:
        abc = re.sub("[^a-zA-Z0-9-]", "-", abc)
        ret = re.sub("[-]+", "-", abc)
        return ret

    def _suffix() -> str:
        return format_suffix(extension, compression)

    base = _pretty(base)
    extension = _pretty(extension)
    dataflag = _pretty(dataflag)

    # Uncompressed size is mandatory for logs
    size = data.get("size", "")  # needed in log name
    datatype = data.get("datatype", "")  # needed in metric name
    new_name = ""

    if kind == "log":
        if size == "":
            _logger.error("A log file name needs the uncompressed size: pass --size")
            return False, ""

        if compression == "":
            _logger.error(
                "Log files must be compressed (.gz, .bz2 or .zst); "
                "compress the file and try again"
            )
            return False, ""

        # Without a datatype only the compression method is part of a log name,
        # except for parquet, whose canonical ``.zst.parquet`` spelling must be
        # kept whole (the codec sits inside the file).
        if datatype or extension == "parquet":
            suffix = _suffix()
        else:
            suffix = f".{compression}"
        new_name = f"{base}_{start}_{stop}_{count}_{size}_{dataflag}{suffix}"

    if kind == "metric":
        if datatype == "":
            _logger.error(
                "A metric file name needs a value type: pass --dtype "
                "(for example --dtype float)"
            )
            return False, ""

        datatype = _pretty(datatype)

        new_name = f"{base}_{datatype}_{start}_{stop}_{count}_{dataflag}{_suffix()}"

    return True, new_name


def _check_name_matches_content(
    path: str, extension: str, name_compression: str, sniffed: Sniff
) -> None:
    """Raise ``ValueError`` when the file's name contradicts what its bytes say.

    Whatever the name claims, the file is never read as something its bytes
    deny, and a name is never trusted over conclusive content. (A wrapped
    parquet file is rejected earlier, with its own message.)
    """
    if extension == "parquet":
        if sniffed.format != "parquet" or sniffed.compression:
            found = (
                f"a {sniffed.compression} stream (it starts with "
                f"{MAGIC_HEX[sniffed.compression]})"
                if sniffed.compression
                else "not parquet (it does not start with PAR1)"
            )
            raise ValueError(
                f"{path} is named .parquet but is {found}. Check what the file "
                "really is; a plain parquet file starts with PAR1."
            )
    elif sniffed.format == "parquet":
        raise ValueError(
            f"{path} is a plain parquet file (it starts with PAR1) but its name "
            f"says .{extension}. Rename it to end in .parquet (or .zst.parquet if "
            "its columns use the zstd codec) and try again."
        )
    elif sniffed.compression != name_compression:
        raise ValueError(
            f"{path} is named as {name_compression or 'uncompressed'} but its "
            f"bytes say {sniffed.compression or 'not compressed'}. Rename it to "
            "match its content, or (de)compress the file, and try again."
        )


def _read_dataframe(path: str) -> object:
    """Load ``path`` into a pandas DataFrame, preferring content over the name.

    Supports csv, parquet and pandas pickle, each optionally compressed
    (gzip/bz2/zstd). The portal's rule is to dispatch on the bytes, because a
    name can lie: the first bytes decide parquet (``PAR1``) and the outer
    compression (see :func:`sniff_file`), and a name that contradicts them is a
    clear error instead of a failure deep in pandas/pyarrow. Pickle and csv have
    no reliable magic, so which of the two it is comes from the extension.
    Content that cannot be read (empty or unreadable file) also falls back to
    the name.
    """
    # Imported lazily so the heavy pandas import is only paid when a rename is
    # actually requested, not on every CLI invocation.
    import pandas as pd  # pylint: disable=import-outside-toplevel

    _, extension, name_compression = split_name_tail(path)
    compression = "infer"  # pandas guesses from the name when content is silent
    sniffed = sniff_file(path)
    if sniffed is not None:
        if sniffed.compression and sniffed.format == "parquet":
            raise ValueError(wrapped_parquet_message(path, sniffed.compression))
        _check_name_matches_content(path, extension, name_compression, sniffed)
        compression = PANDAS_CODEC[sniffed.compression]

    if extension == "parquet":
        return pd.read_parquet(path)
    if extension == "pkl":
        return pd.read_pickle(path, compression=compression)
    if extension == "csv":
        return pd.read_csv(path, compression=compression)
    raise ValueError(f"Unsupported file format for '{path}' (use csv/parquet/pkl)")


_BAD_NAME_MSG = (
    "--name must not contain '_' or '.' (got '%s'): those characters separate "
    "the parts of a convention name. Use '-' instead."
)
_NO_ROWS_MSG = "%s has no data rows, so there is nothing to name"
_NO_TIMES_MSG = (
    "No valid timestamps in column '%s'; pick the timestamp column with --tscol"
)


def _detect_timestamp_column(frame: object, timestamp_col: Optional[str]) -> str:
    """Return the timestamp column name, validating or auto-detecting it."""
    columns = list(frame.columns)
    if timestamp_col is not None:
        if timestamp_col not in columns:
            raise ValueError(
                f"Timestamp column '{timestamp_col}' not found; the file has "
                f"columns {columns}. Pass one of them with --tscol."
            )
        return timestamp_col

    # Auto-detect: first column whose name hints at time, else the first column.
    for col in columns:
        if re.search(r"time|date|ts|timestamp", str(col), re.IGNORECASE):
            return col
    if not columns:
        raise ValueError("File has no columns to derive timestamps from")
    return columns[0]


def rename_from_data(
    path: str,
    name: str,
    kind: str,
    dtype: str = "",
    flag: str = "raw",
    size: str = "",
    timestamp_col: Optional[str] = None,
) -> tuple[bool, str]:
    # The parameters mirror the naming-convention fields that pandas cannot
    # infer (name/kind/dtype/flag/size) plus the timestamp column.
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    # pylint: disable=too-many-locals
    """Build a naming-convention filename for ``path`` from its data.

    Reads the file with pandas, derives ``count`` (number of rows) and
    ``start``/``stop`` (min/max of the timestamp column, auto-detected when
    ``timestamp_col`` is not given), then delegates to :func:`create_filename`.
    The fields pandas cannot infer must be supplied by the caller.

    Parameters
    ----------
    path : str
        Source data file (``.csv``/``.parquet``/``.pkl``, optionally compressed).
    name : str
        Series/source name for the ``<name>`` part (must not contain ``_`` or ``.``).
    kind : str
        ``"metric"`` or ``"log"``.
    dtype : str
        Value type for a metric (e.g. ``float``); required for metric names.
    flag : str
        Data flag (default ``"raw"``).
    size : str
        Uncompressed size; required for log names.
    timestamp_col : str | None
        Column holding the timestamps; auto-detected when ``None``.

    Returns
    -------
    tuple[bool, str]
        ``(True, new_name)`` on success, otherwise ``(False, "")``.
    """
    # Lazy import: only pay the pandas import cost when renaming.
    import pandas as pd  # pylint: disable=import-outside-toplevel

    if "_" in name or "." in name:
        _logger.error(_BAD_NAME_MSG, name)
        return False, ""

    frame = _read_dataframe(path)
    count = len(frame)
    if count <= 0:
        _logger.error(_NO_ROWS_MSG, path)
        return False, ""

    col = _detect_timestamp_column(frame, timestamp_col)
    times = pd.to_datetime(frame[col], errors="coerce", utc=True).dropna()
    if times.empty:
        _logger.error(_NO_TIMES_MSG, col)
        return False, ""

    data = {
        "datatype": dtype,
        "dataflag": flag,
        "start": times.min().isoformat(),
        "stop": times.max().isoformat(),
        "count": count,
        "size": size,
    }

    # create_filename derives base/ext/comp from the file name, so pass the
    # source basename but with the desired <name> as the base.
    _, extension, compression = split_name_tail(path)
    synthetic = f"{name}{format_suffix(extension, compression)}"  # ".csv.zst" etc.
    return create_filename(data, synthetic, kind, path=path)


def normalize_dataframe(frame: object, skip_cols: Optional[list] = None) -> list:
    """Coerce non-numeric columns to a tighter dtype, in place.

    For each column not in ``skip_cols`` that is not already numeric, try to
    convert it to integer, then to float, otherwise leave it as text. Columns
    that could not be made numeric are returned so the caller can ask the user
    to review them (the type could not be determined automatically).

    Works across pandas versions where string columns may report ``object`` or
    the newer ``str``/``string`` dtype.

    Returns
    -------
    list[str]
        Names of the columns left as (non-numeric) text after coercion.
    """
    import pandas as pd  # pylint: disable=import-outside-toplevel

    skip = set(skip_cols or [])
    text_cols = []
    for col in frame.columns:
        if col in skip:
            continue
        # Leave already-numeric columns as they are (int/float/etc.).
        if pd.api.types.is_numeric_dtype(frame[col]):
            continue

        numeric = pd.to_numeric(frame[col], errors="coerce")
        if numeric.notna().all():
            # All values parsed as numbers: prefer int when they are integral.
            if (numeric == numeric.astype("int64")).all():
                frame[col] = numeric.astype("int64")
            else:
                frame[col] = numeric.astype("float64")
        else:
            # Could not be made numeric; leave as text and flag for review.
            text_cols.append(str(col))

    return text_cols


def convert_and_rename(
    path: str,
    name: str,
    kind: str,
    dtype: str = "",
    flag: str = "raw",
    size: str = "",
    timestamp_col: Optional[str] = None,
    out_dir: Optional[str] = None,
) -> tuple[bool, str, list]:
    # Mirrors rename_from_data plus an output directory.
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    # pylint: disable=too-many-locals
    """Normalize a data file and write it as parquet + zstd with a convention name.

    Reads ``path``, coerces non-timestamp ``object`` columns (int -> float ->
    object) via :func:`normalize_dataframe`, derives the convention name with
    the preferred ``.zst.parquet`` form, and writes the normalized DataFrame
    there. The name is ``.zst.parquet`` (not ``.parquet.zst``) because the zstd
    codec is applied inside the parquet columns; the file is plain parquet and
    there is no outer zstd wrapper, so the compression token comes first.
    Returns ``(ok, out_path, object_columns)`` where ``object_columns``
    lists columns the user should review.
    """
    import pandas as pd  # pylint: disable=import-outside-toplevel

    if "_" in name or "." in name:
        _logger.error(_BAD_NAME_MSG, name)
        return False, "", []

    frame = _read_dataframe(path)
    if len(frame) <= 0:
        _logger.error(_NO_ROWS_MSG, path)
        return False, "", []

    col = _detect_timestamp_column(frame, timestamp_col)
    times = pd.to_datetime(frame[col], errors="coerce", utc=True).dropna()
    if times.empty:
        _logger.error(_NO_TIMES_MSG, col)
        return False, "", []

    object_cols = normalize_dataframe(frame, skip_cols=[col])

    data = {
        "datatype": dtype,
        "dataflag": flag,
        "start": times.min().isoformat(),
        "stop": times.max().isoformat(),
        "count": len(frame),
        "size": size,
    }
    # Preferred storage format per the naming convention: parquet whose columns
    # use the zstd codec, spelled ``.zst.parquet``.
    ok, new_name = create_filename(data, f"{name}.zst.parquet", kind)
    if not ok:
        return False, "", object_cols

    target_dir = out_dir if out_dir is not None else os.path.dirname(path)
    out_path = os.path.join(target_dir, new_name)
    frame.to_parquet(out_path, compression="zstd")

    written = os.path.getsize(out_path)
    if written > MAX_FILE_BYTES:
        _logger.error(
            "The converted file %s is %d bytes, over the portal limit of %d "
            "bytes, so it was removed. Split the source by time window and "
            "convert the parts separately.",
            out_path,
            written,
            MAX_FILE_BYTES,
        )
        os.remove(out_path)
        return False, "", object_cols
    return True, out_path, object_cols
