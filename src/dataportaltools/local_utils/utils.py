"""Filename parsing, validation and construction helpers for the CLI."""

import glob
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

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

    logging.basicConfig(level=level)
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

    See ``src/namingconvention.md`` for the full metric and log formats.
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
        except (ValueError, OverflowError, OSError) as e:
            _logger.debug("Not epoch, it seems, %s", str(e))
            return None, ""
    else:
        # last chance for parsing the date string
        try:
            time_o = datetime.fromisoformat(s)
        except ValueError as e:
            _logger.debug("Invalid date format '%s', %s", s, str(e))
            return None, ""

    if time_o is None:
        # this shall NOT happen
        return None, ""

    time_ts = time_o.strftime("%Y-%m-%dT%H:%M:%S.%f")
    time_ts = re.sub(r"\.000000", "", time_ts)
    if "." in time_ts:
        time_ts = time_ts[:-3]
    time_ts = f"{time_ts}Z"

    _logger.debug("time_ts %s", time_ts)

    return time_o, time_ts


def create_filename(data: dict, fname: str, kind: str) -> tuple[bool, str]:
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

    Returns
    -------
    tuple[bool, str]
        Constructed filename, or "" fname if name cannot be determined

    Raises
    ------
    """
    if kind not in ["metric", "log"]:
        _logger.error(
            "create_filename, cannot build a name without a valid 'kind', got '%s'",
            kind,
        )
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
        _logger.error("Stop time is earlier than start time")
        return False, ""

    # See src/namingconvention.md for the metric and log field layouts.

    # dataflag is also needed
    dataflag = data.get("dataflag", "")
    if dataflag == "":
        _logger.debug("create_filename, empty dataflag")
        return False, ""

    # inspect the tails
    # fname = <base>.<extension>.<compression> ?
    base, extension, compression = "", "", ""

    tail_pattern = r"([^.]+)\.([^.]+)\.([^.]+)"
    m = re.search(tail_pattern, fname)
    if m is not None:
        base = m.group(1)
        extension = m.group(2)
        compression = m.group(3)
    else:
        # fname = <base>.<extension> ?

        tail_pattern = r"([^.]+)\.([^.]+)"
        m = re.search(tail_pattern, fname)
        if m is not None:
            base = m.group(1)
            extension = m.group(2)

    if (base == "") or (extension == ""):
        _logger.debug("create_filename, base or extension empty")
        return False, ""

    def _pretty(abc: str) -> str:
        abc = re.sub("[^a-zA-Z0-9-]", "-", abc)
        ret = re.sub("[-]+", "-", abc)
        return ret

    base = _pretty(base)
    extension = _pretty(extension)
    dataflag = _pretty(dataflag)

    # Uncompressed size is mandatory for logs
    size = data.get("size", "")  # needed in log name
    datatype = data.get("datatype", "")  # needed in metric name

    if kind == "log":
        if size == "":
            _logger.error("Log file missing size parameter")
            return False, ""

        if compression == "":
            _logger.error("Log file is not compressed")
            return False, ""

        if datatype:
            new_name = (
                f"{base}_{start}_{stop}_{count}_{size}_{dataflag}"
                f".{extension}.{compression}"
            )
        else:
            new_name = f"{base}_{start}_{stop}_{count}_{size}_{dataflag}.{compression}"

    if kind == "metric":
        if datatype == "":
            _logger.error("Metric file is missing datatype")
            return False, ""

        datatype = _pretty(datatype)

        new_name = f"{base}_{datatype}_{start}_{stop}_{count}_{dataflag}.{extension}"
        if compression != "":
            new_name = f"{new_name}.{compression}"

    return True, new_name


def _read_dataframe(path: str) -> object:
    """Load ``path`` into a pandas DataFrame, dispatching on the extension.

    Supports ``.csv``, ``.parquet`` and ``.pkl`` (pandas pickle), each optionally
    compressed (``.gz``/``.bz2``/``.zst``). pandas/pyarrow handle the formats and
    the compression libraries; ``.zst`` needs the ``zstandard`` package, which is
    a project dependency.
    """
    # Imported lazily so the heavy pandas import is only paid when a rename is
    # actually requested, not on every CLI invocation.
    import pandas as pd  # pylint: disable=import-outside-toplevel

    lower = path.lower()
    # Strip a trailing compression suffix to find the format extension.
    stem = re.sub(r"\.(gz|bz2|zst|zstd)$", "", lower)

    if stem.endswith(".parquet"):
        return pd.read_parquet(path)
    if stem.endswith(".pkl"):
        return pd.read_pickle(path)
    if stem.endswith(".csv"):
        return pd.read_csv(path)
    raise ValueError(f"Unsupported file format for '{path}' (use csv/parquet/pkl)")


def _detect_timestamp_column(frame: object, timestamp_col: Optional[str]) -> str:
    """Return the timestamp column name, validating or auto-detecting it."""
    columns = list(frame.columns)
    if timestamp_col is not None:
        if timestamp_col not in columns:
            raise ValueError(
                f"Timestamp column '{timestamp_col}' not found; columns: {columns}"
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
        Series/source name for the ``<name>`` part (must not contain ``_``).
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

    if "_" in name:
        _logger.error("rename_from_data, name must not contain '_': '%s'", name)
        return False, ""

    frame = _read_dataframe(path)
    count = len(frame)
    if count <= 0:
        _logger.error("rename_from_data, '%s' has no rows", path)
        return False, ""

    col = _detect_timestamp_column(frame, timestamp_col)
    times = pd.to_datetime(frame[col], errors="coerce", utc=True).dropna()
    if times.empty:
        _logger.error("rename_from_data, no valid timestamps in column '%s'", col)
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
    base = os.path.basename(path)
    suffix = base[len(base.split(".")[0]) :]  # ".csv.zst" etc.
    synthetic = f"{name}{suffix}"
    return create_filename(data, synthetic, kind)


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
    the preferred ``.parquet.zst`` form, and writes the normalized DataFrame
    there. Returns ``(ok, out_path, object_columns)`` where ``object_columns``
    lists columns the user should review.
    """
    import pandas as pd  # pylint: disable=import-outside-toplevel

    if "_" in name:
        _logger.error("convert_and_rename, name must not contain '_': '%s'", name)
        return False, "", []

    frame = _read_dataframe(path)
    if len(frame) <= 0:
        _logger.error("convert_and_rename, '%s' has no rows", path)
        return False, "", []

    col = _detect_timestamp_column(frame, timestamp_col)
    times = pd.to_datetime(frame[col], errors="coerce", utc=True).dropna()
    if times.empty:
        _logger.error("convert_and_rename, no valid timestamps in '%s'", col)
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
    # Preferred storage format per the naming convention: parquet + zstd.
    ok, new_name = create_filename(data, f"{name}.parquet.zst", kind)
    if not ok:
        return False, "", object_cols

    target_dir = out_dir if out_dir is not None else os.path.dirname(path)
    out_path = os.path.join(target_dir, new_name)
    frame.to_parquet(out_path, compression="zstd")
    return True, out_path, object_cols
