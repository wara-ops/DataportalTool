#!/usr/bin/env python3
# flake8: noqa: ANN001
"""Command-line entry point for the WARA-Ops dataportaltools client."""

import logging
import os
import sys

import click

try:
    # Normal case: installed/imported as part of the package.
    from .local_utils import config
    from .local_utils import upload as up
    from .local_utils import utils
except ImportError:  # pragma: no cover - direct-script bootstrap fallback
    # Fallback: running this file directly (``python main.py``).
    from local_utils import config
    from local_utils import upload as up
    from local_utils import utils


_log = logging.getLogger("base")

# Bound at import so it keeps working when tests replace WCIBConnection.
_error_detail = up.WCIBConnection._error_detail  # pylint: disable=protected-access


def _fail(action: str, err: Exception) -> None:
    """Tell the user on stderr that ``action`` failed, with the full reason."""
    click.echo(f"Failed to execute {action}: {_error_detail(err)}", err=True)


@click.command()
@click.option(
    "--createdataset",
    "-c",
    default=None,
    type=click.Path(exists=True),
    metavar="<path to description file>",
    help="Create a new dataset described by this Markdown file.",
)
@click.option("--user", "-u", default=None, metavar="<user>", help="Owner name for -c.")
@click.option(
    "--upload",
    "-U",
    default=None,
    metavar="<id>",
    help="Upload the --src file(s) to the dataset with this id.",
)
@click.option(
    "--src",
    "-s",
    default=None,
    multiple=True,
    metavar="<path or 'glob'>",
    help="File to upload. Repeat -s for each file, or quote a wildcard so this "
    "tool expands it (-s 'data/*.parquet').",
)
@click.option(
    "--prefix",
    "-p",
    default="",
    metavar="<top dir>",
    help="Destination sub-folder (up to two levels) for an extra file. "
    "Requires --extra-file.",
)
@click.option(
    "--extra-file",
    "-e",
    "extra_file",
    is_flag=True,
    default=False,
    help="Upload the file(s) as extra file(s), such as a README or notes, "
    "stored unchanged. Needed for any file whose name does not follow the "
    "data-file naming convention. Required to use --prefix.",
)
@click.option(
    "--delete",
    "-d",
    default=None,
    metavar="<id>",
    help="Delete the dataset with this id. Refused while it still has files, "
    "unless --force is given.",
)
@click.option(
    "--listdataset/--no-listdataset",
    "-L",
    default=False,
    help="List all your datasets.",
)
@click.option(
    "--listfiles",
    "-l",
    default=None,
    metavar="<id>",
    help="List the files in the dataset with this id.",
)
@click.option(
    "--dryrun/--no-dryrun",
    default=False,
    help="Show what would be done without changing anything on the portal. "
    "Add -v to see the details of each request.",
)
@click.option(
    "--token",
    "-t",
    default="",
    metavar="<token file>",
    show_envvar=True,
    help="Name of file containing token. If omitted, the token value is read "
    "from the PORTAL_TOKEN environment variable.",
)
@click.option(
    "--api",
    "-a",
    default="https://portal.wara-ops.org/api/v1",
    envvar="PORTAL_URL",
    show_envvar=True,
    metavar="<url>",
    help="WARA-Ops API base URL. Falls back to the PORTAL_URL environment "
    "variable, then the public portal.",
)
@click.option(
    "--start",
    default="",
    help="Time of the first event, YYYY-MM-ddThh:mm:ss[.uuu], e.g. "
    "2022-12-26T00:00:00. With --stop, --count, --flag, --kind and --dtype "
    "(metric) or --size (log), lets a single file whose name does not follow "
    "the convention be uploaded as a data file; also used by --rename.",
)
@click.option("--stop", default="", help="Time of the last event (see --start).")
@click.option("--count", default=0, help="Number of events in the file (see --start).")
@click.option(
    "--flag",
    default="",
    help="Data file description, e.g., 'preprocessed-and-anonymized', 'raw', 'filtered', ...",
)
@click.option(
    "--dtype", default="", help="Value type of a metric, e.g., 'float', 'int', 'json'"
)
@click.option(
    "--size", default="", help="Uncompressed file size (required for log files)"
)
@click.option(
    "--kind",
    default="",
    help='Kind of data, "log" or "metric". Needed when the name is built from '
    "--start/--stop/--count, and by --rename.",
)
@click.option(
    "--force/--no-force",
    default=False,
    help="With --delete, delete the dataset even if it still has files.",
)
@click.option(
    "--tag",
    "tag",
    multiple=True,
    metavar="<tag>",
    help="Tag to attach to uploaded/annotated file(s). May be repeated.",
)
@click.option(
    "--poi",
    "poi",
    multiple=True,
    metavar="<start,stop,text>",
    help="Point-of-interest time range as 'start,stop,text'. start/stop are "
    "timestamps (ISO-8601 or epoch, no commas); the text may contain commas. "
    "May be repeated. POIs are only allowed when uploading a single file or "
    "with --setmeta.",
)
@click.option(
    "--setmeta",
    default=None,
    type=int,
    metavar="<fileid>",
    help="Annotate an existing file (by FileID) with --tag/--poi without "
    "re-uploading. Requires --upload <datasetid> or --listfiles <datasetid> "
    "for the dataset id.",
)
@click.option(
    "--rename",
    default=None,
    type=click.Path(exists=True),
    metavar="<file>",
    help="Suggest a naming-convention filename for a local data file (.csv, "
    ".parquet or .pkl, optionally .gz/.bz2/.zst), using its row count and "
    "first/last timestamp. Offline; no token needed. Requires --name and "
    "--kind; give --dtype (metric) or --size (log). By default it only prints "
    "the name and does not touch the file; add --apply to write a converted "
    "copy.",
)
@click.option(
    "--name",
    default="",
    metavar="<name>",
    help="Series name for --rename (no '_' or '.').",
)
@click.option(
    "--tscol",
    default=None,
    metavar="<column>",
    help="Timestamp column for --rename (auto-detected when omitted).",
)
@click.option(
    "--apply/--no-apply",
    default=False,
    help="With --rename, write a new parquet+zstd file named per the "
    "convention next to the original (the original is kept), converting text "
    "columns to numbers where possible and listing those left as text.",
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase log verbosity: -v for INFO, -vv for DEBUG. Default shows "
    "only warnings/errors. The PORTAL_LOG_LEVEL env var sets a level when no "
    "-v is given.",
)
@click.pass_context
def main(
    ctx,
    createdataset,
    user,
    upload,
    src,
    prefix,
    extra_file,
    delete,
    listdataset,
    listfiles,
    dryrun,
    token,
    api,
    start,
    stop,
    count,
    flag,
    dtype,
    size,
    kind,
    force,
    tag,
    poi,
    setmeta,
    rename,
    name,
    tscol,
    apply,
    verbose,
) -> None:
    # This is a Click command exposing the full CLI surface, so the large
    # number of options/branches maps directly onto the documented commands.
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """Upload, annotate, list and delete datasets in the WARA-Ops data portal.

    Each call does one thing, chosen by the option you give. Portal commands
    need a token: pass -t <token file> or set PORTAL_TOKEN.

    \b
    Examples:
      dataportaltools -L                         list your datasets
      dataportaltools -l 17                      list the files in dataset 17
      dataportaltools -U 17 -s 'data/*.zst.parquet' --dryrun -v
                                                 preview an upload
      dataportaltools -U 17 -s README.md -e      upload an extra file
      dataportaltools --rename raw.csv --name cpu --kind metric --dtype float
                                                 suggest a convention name

    Data files must be named per the naming convention (see the README);
    anything else needs -e/--extra-file. Exit status is 0 on success and 1 if
    anything failed, including a batch where only some files were uploaded.
    """

    utils.configure_logging(verbose)

    # --prefix only makes sense for an extra-file upload.
    if prefix and not extra_file:
        raise click.UsageError("--prefix requires --extra-file/-e")

    # Offline operation: derive a naming-convention filename from a data file.
    # Handled before connecting since it does not touch the API.
    if rename is not None:
        if not name or not kind:
            raise click.UsageError("--rename requires --name and --kind")
        if apply:
            # Normalize column dtypes and write the preferred parquet+zstd form.
            try:
                ok, out_path, review = utils.convert_and_rename(
                    rename,
                    name=name,
                    kind=kind,
                    dtype=dtype,
                    flag=flag or "raw",
                    size=size,
                    timestamp_col=tscol,
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                # pandas/pyarrow raise many types for unreadable input; turn
                # any of them into a message instead of a traceback.
                click.echo(f"Failed to convert/rename {rename}: {e}", err=True)
                ctx.exit(1)
            if not ok:
                click.echo(
                    f"Failed to convert/rename {rename} (see the message above)",
                    err=True,
                )
                ctx.exit(1)
            if review:
                click.echo(
                    "Review: could not infer a numeric type for column(s): "
                    + ", ".join(review)
                    + " (left as text)",
                    err=True,
                )
            print(out_path)
        else:
            try:
                ok, new_name = utils.rename_from_data(
                    rename,
                    name=name,
                    kind=kind,
                    dtype=dtype,
                    flag=flag or "raw",
                    size=size,
                    timestamp_col=tscol,
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                # Same boundary as above, for the read-only path.
                click.echo(f"Failed to build a name from {rename}: {e}", err=True)
                ctx.exit(1)
            if not ok:
                click.echo(
                    f"Failed to build a name from {rename} (see the message above)",
                    err=True,
                )
                ctx.exit(1)
            print(new_name)
        ctx.exit(0)

    config.set_conf(locals())
    _log.debug("config %s", config.get())

    ok = True
    # A token file passed via -t takes precedence; otherwise fall back to the
    # token value in the PORTAL_TOKEN environment variable.
    env_token = os.environ.get("PORTAL_TOKEN", "")
    wc = up.WCIBConnection(api, tokenfile=token, token="" if token else env_token)
    try:
        wc.connect()
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Top-level CLI boundary: report any failure and exit non-zero.
        click.echo(f"Failed to connect: {e}", err=True)
        ok = False

    if not ok:
        ctx.exit(1)

    # if api != "http://127.0.0.1:3001/v1":
    #    return 1

    ret = 0

    # Parse annotation flags. ``None`` means "not provided" so existing
    # behaviour is unchanged when no annotation flags are passed; an empty
    # list (impossible via multiple=True) would mean "clear".
    tags = list(tag) if tag else None

    pois = None
    if poi:
        pois = []
        for s in poi:
            # text may contain commas, so split on the first two only
            parts = s.split(",", 2)
            if len(parts) != 3:
                raise click.UsageError(
                    f"Invalid --poi '{s}', expected 'start,stop,text'"
                )
            # Normalize start/stop the same way upload timestamps are handled.
            start_ok, start_norm = utils.normalize_timestamp(parts[0])
            stop_ok, stop_norm = utils.normalize_timestamp(parts[1])
            if not start_ok or not stop_ok:
                raise click.UsageError(
                    f"Invalid --poi '{s}': start/stop must be valid timestamps "
                    "(ISO-8601 or epoch)"
                )
            pois.append({"start": start_norm, "stop": stop_norm, "text": parts[2]})

    # POIs are time ranges for one file; applying the same range to a whole
    # glob/batch is almost never intended, so reject it for multi-file uploads.
    if pois is not None and upload is not None and setmeta is None:
        matched = [f for f in utils.get_all_src_files(list(src)) if os.path.isfile(f)]
        if len(matched) > 1:
            raise click.UsageError(
                "--poi cannot be applied to a multi-file upload "
                f"({len(matched)} files matched); upload a single file or use "
                "--setmeta <fileid> to annotate individual files"
            )

    # Annotate an existing file without re-uploading.
    if setmeta is not None:
        if upload is None and listfiles is None:
            raise click.UsageError(
                "--setmeta requires --upload <datasetid> or "
                "--listfiles <datasetid> for the dataset id"
            )
        if tags is None and pois is None:
            click.echo("Nothing to do: --setmeta needs --tag and/or --poi", err=True)
            ctx.exit(0)
        try:
            datasetid = int(upload) if upload is not None else int(listfiles)
            wc.set_file_metadata(datasetid, setmeta, tags, pois, dryrun)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # CLI boundary: surface any operation failure as a non-zero exit.
            _fail("the annotation", e)
            ret = 1

        ctx.exit(ret)

    if createdataset is not None:
        try:
            ret = wc.create_dataset(createdataset, user, dryrun)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # CLI boundary: surface any operation failure as a non-zero exit.
            _fail("the dataset creation", e)
            ret = 1

        ctx.exit(ret)

    if upload is not None:
        try:
            if isinstance(src, tuple):
                datasetid = int(upload)
                data = {
                    "datatype": dtype,
                    "dataflag": flag,
                    "start": start,
                    "stop": stop,
                    "count": count,
                    "size": size,
                }
                ret = wc.upload(
                    datasetid,
                    list(src),
                    data,
                    prefix,
                    kind,
                    dryrun,
                    tags=tags,
                    points_of_interest=pois,
                    extra=extra_file,
                )
            else:  # pragma: no cover - click always supplies a tuple for src
                ret = 1
        except Exception as e:  # pylint: disable=broad-exception-caught
            # CLI boundary: surface any operation failure as a non-zero exit.
            _fail("the upload", e)
            ret = 1

        ctx.exit(ret)

    if delete is not None:
        try:
            datasetid = int(delete)
            ret = wc.delete(datasetid, force, dryrun)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # CLI boundary: surface any operation failure as a non-zero exit.
            _fail("the delete", e)
            ret = 1

        ctx.exit(ret)

    if listdataset:
        try:
            ret = wc.list_datasets(dryrun)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # CLI boundary: surface any operation failure as a non-zero exit.
            _fail("the dataset listing", e)
            ret = 1

        ctx.exit(ret)

    if listfiles is not None:
        try:
            datasetid = int(listfiles)
            ret = wc.list_files(datasetid, dryrun)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # CLI boundary: surface any operation failure as a non-zero exit.
            _fail("the file listing", e)
            ret = 1

        ctx.exit(ret)

    click.echo(
        "Nothing to do: give an action such as -L, -l <id>, -U <id> -s <file>, "
        "-c <file>, -d <id> or --rename <file>. See --help.",
        err=True,
    )
    ctx.exit()


if __name__ == "__main__":
    sys.exit(main())
