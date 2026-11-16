"""Content sniffing: decide a file's format from its bytes, not its name."""

import bz2
import gzip
import logging
from typing import NamedTuple, Optional

import zstandard

_logger = logging.getLogger("toolslib.sniff")


# The portal's rule (wcib/docs/namingconvention.md) is to dispatch on what a
# file CONTAINS, because its name can lie. Two magics matter for parquet:
#   PAR1         -> a plain parquet file. Any codec (zstd, snappy, ...) is applied
#                   per column INSIDE it, so the canonical ``*.zst.parquet`` files
#                   (33,179 in production) start with PAR1 and are plain.
#   28 b5 2f fd  -> a zstd stream wrapped around the WHOLE file (``zstd x.parquet``).
#                   ``pd.read_parquet`` cannot open that, and calling it
#                   ``*.zst.parquet`` would be a false claim.
# gzip (1f 8b) and bz2 (42 5a 68) are recognised so the compressed csv/pickle
# paths stay correct. Pickle and csv have no reliable magic, so "none of the
# above" is reported as an unknown format and the caller falls back to the name.
_PARQUET_MAGIC = b"PAR1"
_COMPRESSION_MAGIC = (
    ("zst", b"\x28\xb5\x2f\xfd"),
    ("gz", b"\x1f\x8b"),
    ("bz2", b"BZh"),
)
MAGIC_HEX = {"zst": "28 b5 2f fd", "gz": "1f 8b", "bz2": "42 5a 68"}
_UNWRAP_COMMAND = {"zst": "zstd -d", "gz": "gzip -d", "bz2": "bzip2 -d"}
# Names for pandas' ``compression=`` argument; ``None`` means "not compressed".
PANDAS_CODEC = {"": None, "gz": "gzip", "bz2": "bz2", "zst": "zstd"}


class Sniff(NamedTuple):
    """What a file's bytes say it is.

    ``compression`` is the OUTER compression: ``""`` (none of the known magics),
    ``"gz"``, ``"bz2"`` or ``"zst"``. ``format`` is ``"parquet"`` when the file
    (after undoing the outer compression) starts with ``PAR1``, else ``""``
    meaning "unknown" (pickle and csv cannot be told apart reliably).
    """

    compression: str
    format: str


def _decompressing_reader(raw: object, compression: str) -> object:
    """Return a streaming reader over ``raw`` that undoes ``compression``."""
    if compression == "gz":
        return gzip.GzipFile(fileobj=raw)
    if compression == "bz2":
        return bz2.BZ2File(raw)
    return zstandard.ZstdDecompressor().stream_reader(raw)


def sniff_file(path: str) -> Optional[Sniff]:
    """Classify ``path`` from its first bytes, or ``None`` if there is nothing to read.

    Only the first 4 bytes are examined. For a wrapped file the front of the
    stream is decompressed through a streaming reader, asking for just 4 bytes,
    so a multi-GB file is never loaded. ``None`` (missing, unreadable or empty
    file) means "inconclusive": the caller should fall back to the name.
    """
    try:
        with open(path, "rb") as raw:
            head = raw.read(4)
            if not head:
                return None
            compression = next(
                (name for name, magic in _COMPRESSION_MAGIC if head.startswith(magic)),
                "",
            )
            if not compression:
                return Sniff("", "parquet" if head == _PARQUET_MAGIC else "")
            raw.seek(0)
            try:
                inner = _decompressing_reader(raw, compression).read(4)
            except (OSError, EOFError, ValueError, zstandard.ZstdError):
                # Truncated or corrupt stream: the outer compression is known,
                # the inner format is not.
                inner = b""
    except OSError:
        return None
    return Sniff(compression, "parquet" if inner == _PARQUET_MAGIC else "")


def wrapped_parquet_message(path: str, compression: str) -> str:
    """Say what a compression-wrapped parquet file is and what to do about it."""
    return (
        f"{path} is a parquet file wrapped in {compression} compression (it starts "
        f"with {MAGIC_HEX[compression]}, not PAR1), not a plain parquet file. "
        "pandas cannot read it, and a name ending in .zst.parquet would claim the "
        "opposite: that is a plain parquet file whose columns use the zstd codec. "
        f"Decompress it first ('{_UNWRAP_COMMAND[compression]} <file>') and use the "
        "plain .parquet file that results."
    )


def check_not_wrapped_parquet(path: str) -> bool:
    """True unless ``path`` is a compression-wrapped parquet file (logged as an error).

    A file that cannot be read, or whose content is inconclusive, passes: the
    name is then all there is to go on.
    """
    sniffed = sniff_file(path)
    if sniffed is not None and sniffed.compression and sniffed.format == "parquet":
        _logger.error("Rejected %s", wrapped_parquet_message(path, sniffed.compression))
        return False
    return True
