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
except ImportError:
    # Fallback: running this file directly (``python main.py``).
    from local_utils import config
    from local_utils import upload as up
    from local_utils import utils


_log = logging.getLogger("base")


@click.command()
@click.option(
    "--createdataset",
    "-c",
    default=None,
    type=click.Path(exists=True),
    metavar="<path to description file>",
    help="Create a new dataset using provided information Markdown file",
)
@click.option("--user", "-u", default=None, metavar="<user>", help="User name")
@click.option("--upload", "-U", default=None, metavar="<id>", help="Dataset id")
@click.option(
    "--src",
    "-s",
    default=None,
    multiple=True,
    metavar="<path1> <path2> .. <pathN>",
    help="Source files",
)
@click.option(
    "--prefix",
    "-p",
    default="",
    metavar="<top dir>",
    help="Dest folder in contains, only used in case of extrafile",
)
@click.option(
    "--delete",
    "-d",
    default=None,
    metavar="<id>",
    help="Delete dataset with provided id",
)
@click.option(
    "--listdataset/--no-listdataset",
    "-L",
    default=False,
    help="List users all datasets",
)
@click.option(
    "--listfiles",
    "-l",
    default=None,
    metavar="<id>",
    help="List objects in specified dataset",
)
@click.option("--dryrun/--no-dryrun", default=False, help="Dry run")
@click.option(
    "--token",
    "-t",
    default="",
    metavar="<token file>",
    help="Name of file containing token. If omitted, the token value is read "
    "from the PORTAL_TOKEN environment variable.",
)
@click.option(
    "--api",
    "-a",
    default=lambda: os.environ.get("PORTAL_URL", "https://portal.wara-ops.org/api/v1"),
    metavar="<url>",
    help="WARA-Ops API",
)
@click.option(
    "--start",
    default="",
    help="Timestamp of first event in file, YYYY-MM-ddThh:mm:ss[.uuu], "
    "e.g. 2022-12-26T00:00:00",
)
@click.option("--stop", default="", help="Timestamp of last event in file")
@click.option("--count", default=0, help="Number of events in the file")
@click.option(
    "--flag",
    default="",
    help="Data file description, e.g., 'preprocessed-and-anonymized', 'raw', 'filtered', ...",
)
@click.option(
    "--dtype", default="", help="Data type description, e.g., 'float', 'int', 'json'"
)
@click.option("--size", default="", help="Uncompressed file size (only log files)")
@click.option("--kind", default="", help='Kind of data, either "log" or "metric"')
@click.option(
    "--force/--no-force", default=False, help="Force action (whan action is 'delete')"
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
@click.pass_context
def main(
    ctx,
    createdataset,
    user,
    upload,
    src,
    prefix,
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
) -> None:
    # This is a Click command exposing the full CLI surface, so the large
    # number of options/branches maps directly onto the documented commands.
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """Dispatch a single dataportal operation based on the given options."""

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
        print(f"Failed to connect: {e}")
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
            print("Nothing to do: --setmeta needs --tag and/or --poi")
            ctx.exit(0)
        try:
            datasetid = int(upload) if upload is not None else int(listfiles)
            wc.set_file_metadata(datasetid, setmeta, tags, pois, dryrun)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # CLI boundary: surface any operation failure as a non-zero exit.
            print(f"Failed to execute: {e}")
            ret = 1

        ctx.exit(ret)

    if createdataset is not None:
        try:
            ret = wc.create_dataset(createdataset, user, dryrun)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # CLI boundary: surface any operation failure as a non-zero exit.
            print(f"Failed to execute: {e}")
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
                )
            else:
                ret = 1
        except Exception as e:  # pylint: disable=broad-exception-caught
            # CLI boundary: surface any operation failure as a non-zero exit.
            print(f"Failed to execute: {e}")
            ret = 1

        ctx.exit(ret)

    if delete is not None:
        try:
            datasetid = int(delete)
            ret = wc.delete(datasetid, force, dryrun)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # CLI boundary: surface any operation failure as a non-zero exit.
            print(f"Failed to execute: {e}")
            ret = 1

        ctx.exit(ret)

    if listdataset:
        try:
            ret = wc.list_datasets(dryrun)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # CLI boundary: surface any operation failure as a non-zero exit.
            print(f"Failed to execute: {e}")
            ret = 1

        ctx.exit(ret)

    if listfiles is not None:
        try:
            datasetid = int(listfiles)
            ret = wc.list_files(datasetid, dryrun)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # CLI boundary: surface any operation failure as a non-zero exit.
            print(f"Failed to execute: {e}")
            ret = 1

        ctx.exit(ret)

    ctx.exit()


if __name__ == "__main__":
    sys.exit(main())
