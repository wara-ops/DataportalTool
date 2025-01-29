#!/usr/bin/env python3

import sys
import os

import click

from toolslib import upload as up


@click.command()
@click.option('--createdataset', '-c', default=None, type=click.Path(exists=True), metavar="<path to description file>", help="Create a new dataset using provided information Markdown file")
@click.option('--user', '-u', default=None, metavar="<user>", help="User name")
@click.option('--upload', '-U', default=None, metavar="<id>", help="Dataset id")
@click.option('--src', '-s', default=None, multiple=True, metavar="<path1> <path2> .. <pathN>", help="Source files")
@click.option('--prefix', '-p', default="",  metavar="<top dir>", help="Dest folder in contains, only used in case of extrafile")
@click.option('--delete', '-d', default=None, metavar="<id>", help="Delete dataset with provided id")
@click.option('--listdataset/--no-listdataset', '-L', default=False, help="List users all datasets")
@click.option('--listfiles', '-l', default=None, metavar="<id>", help="List objects in specified dataset")
@click.option('--dryrun/--no-dryrun', default=False, help="Dry run")
@click.option('--token', '-t', default="", metavar="<token file>", help="Name of file containing token")
@click.option('--api', '-a', default=lambda: os.environ.get('PORTAL_URL', 'https://portal.wara-ops.org/api/v1'), metavar="<url>", help="WARA-Ops API")
@click.option('--start', default="", help="Timestamp of first event in file, YYYY-MM-ddThh:mm:ss[.uuu], e.g. 2022-12-26T00:00:00_2022-12-27T00:00:00")
@click.option('--stop', default="", help="Timestamp of last event in file")
@click.option('--count', default=0, help="Number of events in the file")
@click.option('--flag', default="", help="Data file description, e.g., 'preprocessed-and-anonymized', 'raw', 'filtered', ...")
@click.option('--dtype', default="", help="Data type description, e.g., 'float', 'int', 'json'")
@click.option('--size', default="", help="Uncompressed file size (only log files)")
@click.option('--kind', default="", help="Kind of data, either \"log\" or \"metric\"")
def main(createdataset, user, upload, src , prefix, delete, listdataset, listfiles, dryrun, token, api, start, stop, count, flag, dtype, size, kind):  # pylint: disable=R0911, R0913
    wc = up.WCIBConnection(api, tokenfile=token)

    try:
        wc.connect()
    except Exception as e:
        print(f"Failed to connect: {e}")
        return 1

    if api != "http://127.0.0.1:3001/v1":
        return 1

    try:
        if createdataset is not None:
            return wc.create_dataset(createdataset, user, dryrun)

        if upload is not None:
            if not isinstance(src, tuple):
                return 1

            datasetid = int(upload)
            data = {"datatype": dtype,
                    "dataflag": flag,
                    "start": start,
                    "stop": stop,
                    "count": count,
                    "size": size,
                }
            return wc.upload(datasetid, list(src), data, prefix, kind, dryrun)

        if delete is not None:
            datasetid = int(delete)
            return wc.delete(datasetid, dryrun)

        if listdataset:
            return wc.list_datasets(dryrun)

        if listfiles is not None:
            datasetid = int(listfiles)
            return wc.list_files(datasetid, dryrun)
    except Exception as e:
        print(f"Failed to execute: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
