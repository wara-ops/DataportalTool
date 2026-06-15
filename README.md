# dataportaltools
 WARA-Ops DataportalTools

A thin client for

- creating datasets,
- uploading files to datasets,
- list datasets and datafiles, and
- deleting datasets.

See the [Usage](#usage) section below for details.

## Setup

This project uses pdm (https://pdm-project.org/latest/) as its package manager. See the webpage for installation instructions.

Tests and lints can be run with `pdm run test` and `pdm run lint`. These are also run in the CI pipe on pushes to the repository.

## Run with uvx (no install)

The CLI ships a console script (`dataportaltools`) and can be run directly with
[`uvx`](https://docs.astral.sh/uv/) without a manual install:

``` bash
# From a git checkout / clone
uvx --from . dataportaltools --help

# Straight from the git repository
uvx --from git+https://gitlab.internal.ericsson.com/autodc/dataportaltools dataportaltools -L

# From a locally built wheel
pdm build
uvx --from ./dist/dataportaltools-0.0.1-py3-none-any.whl dataportaltools --help
```

`uvx` runs the tool in a throwaway environment, so nothing is added to your
system or active virtualenv. The first run resolves and caches the dependencies
(`requests`, `click`); later runs reuse the cache and start quickly.

> **Note — picking up local changes.** `uvx --from .` caches the built package
> keyed by its version (`0.0.1`). If you edit the source without bumping the
> version, `uvx` keeps serving the old build (e.g. a new flag like `-v` shows
> `No such option`). Force a rebuild with `--refresh` (or `--no-cache`):
>
> ``` bash
> uvx --refresh --from . dataportaltools --help
> ```
>
> For active development prefer the editable venv (`.venv/bin/dataportaltools …`
> or `pdm run dataportaltools …`), which always reflects the current source.

Because `--from <source> dataportaltools` is verbose, set the source once and
alias it for a session:

``` bash
export DPT_SRC="git+https://gitlab.internal.ericsson.com/autodc/dataportaltools"
alias dpt="uvx --from $DPT_SRC dataportaltools"
```

### Examples (uvx + PORTAL_TOKEN)

Provide the token once via the environment so it does not need to be repeated on
every command (see [Environment variables](#environment-variables) below):

``` bash
export PORTAL_TOKEN="$(cat user.token)"
# Optional: point at a non-default API server (e.g. a dev portal)
# export PORTAL_URL="http://127.0.0.1:3001/v1"

# List all datasets you can see
uvx --from . dataportaltools -L

# Create a dataset from a description file, owned by user123
uvx --from . dataportaltools -c info.md -u user123

# List files in dataset 17
uvx --from . dataportaltools -l 17

# Upload a data file (the name must follow the naming convention); dry-run first
uvx --from . dataportaltools -U 17 -s "./dataset/history_float_2022-12-26T00:00:00Z_2022-12-27T00:00:00Z_140190_raw.csv.zst" --dryrun
uvx --from . dataportaltools -U 17 -s "./dataset/history_float_2022-12-26T00:00:00Z_2022-12-27T00:00:00Z_140190_raw.csv.zst"

# Upload an extra (non-convention) file into a subfolder
uvx --from . dataportaltools -U 17 -s ./dataset/README.md -e -p metadata

# Delete dataset 17
uvx --from . dataportaltools -d 17
```

Data-file names must follow the convention
`<name>_<type>_<start>_<stop>_<count>_<flag>.<ext>[.<comp>]` (e.g.
`history_float_2022-12-26T00:00:00Z_2022-12-27T00:00:00Z_140190_raw.csv.zst`,
where `start`/`stop` are UTC timestamps with a trailing `Z`); a file whose name
does not match is uploaded as an *extra* file instead. See the
[Naming convention](#naming-convention) section for the full part-by-part
breakdown, and use `--rename` to derive a convention name from the data:
``` bash
uvx --from . dataportaltools --rename ./dump.csv --name history --kind metric --dtype float
```

A `-t <token file>` still works and takes precedence over `PORTAL_TOKEN`:

``` bash
uvx --from . dataportaltools -L -t user.token
```

See the [Usage](#usage) section for the full set of commands and options.

### Environment variables

The CLI reads a few `PORTAL_`-prefixed environment variables as fallbacks for
command-line options:

| Variable | Maps to | Description |
|---|---|---|
| `PORTAL_URL` | `-a` / `--api` | API server URL. Defaults to `https://portal.wara-ops.org/api/v1`. |
| `PORTAL_TOKEN` | `-t` / `--token` | The token **value** (not a file path). Used when `-t` is not given. A `-t <token file>` always takes precedence. |
| `PORTAL_LOG_LEVEL` | `-v` / `--verbose` | Log level (e.g. `DEBUG`, `INFO`, `WARNING`) used when no `-v` flag is given. |

Example:
``` bash
export PORTAL_TOKEN="$(cat user.token)"
dataportaltools -L          # lists datasets using the token from the env
```

### Logging / verbosity

Output is quiet by default (only warnings and errors). Increase verbosity with
`-v` (INFO) or `-vv` (DEBUG), or set `PORTAL_LOG_LEVEL` when no flag is passed.
A `-v` flag takes precedence over the env var.
``` bash
dataportaltools -L                 # quiet (warnings/errors only)
dataportaltools -vv -U 17 -s f.csv # full DEBUG (request/response details)
PORTAL_LOG_LEVEL=INFO dataportaltools -L
```

### Install
``` bash
uv python install 3.12 3.13
uv venv --python 3.12
source .venv/bin/activate
uv pip install -U --prerelease=allow -r requirements.txt
```

### Manual linting
prefer running `scripts/check.sh` or pre-commit (see [Development](#development))
``` bash
ruff check
```

### Update

#### update python libs

``` bash
mv requirements.txt requirements.txt.old
grep -o -E "^[^=]+" requirements.txt.old > requirements.txt
.venv/bin/python3 -m pip install -U -r requirements.txt
# Test that everything works and then
.venv/bin/python -m pip freeze | grep -E "$(tr '\n' '|' <requirements.txt | sed 's/|$//')"
# Update requirements.txt after output
```

## Usage

### Example of dataset description text

```markdown
# Dataset
Dummy dataset

# Tenant
Ericsson

# Category: metric/log
metric

# Short Info
Short and catchy slogan

# Long Info
Longer and informative text about the dataset.
- Interesting fact 1.
- Interesting fact 3.

# Tags
tag1, tag2

# Access: open/closed
closed
```

### Prerequisites
- User must exist in the Portal. In the examples below denoted ```user123```
- A token is created and downloaded. In the examples below denoted ```user.token```
  (pass it with `-t user.token`, or omit `-t` and set the token value in the
  `PORTAL_TOKEN` environment variable).

Uploads are sent as a single atomic POST with an `Idempotency-Key` (a hash of
the file contents), so re-running an upload de-duplicates server-side instead of
creating a duplicate.

### Naming convention
[See here.](./src/namingconvention.md)

### Create a dataset
```sh
dataportaltools -c info.md -u user123 -t user.token
```

### List datasets
```sh
dataportaltools -L -t user.token
```

### Upload a file that follows the data file naming convention
A metric file name has the form
`<name>_<type>_<start>_<stop>_<count>_<flag>.<ext>[.<comp>]`
(see [Naming convention](./src/namingconvention.md)); otherwise the file is
treated as an extra file. The `start`/`stop` timestamps are UTC and carry a
trailing `Z` (the canonical form the tool generates; the API validates them as
RFC3339 `date-time`). For example:
```sh
dataportaltools -U 17 -s "./dataset/history_float_2022-12-26T00:00:00Z_2022-12-27T00:00:00Z_140190_raw.csv.zst" -t user.token
```
where the parts of `history_float_2022-12-26T00:00:00Z_2022-12-27T00:00:00Z_140190_raw.csv.zst` are:

| Part | Value | Meaning |
|---|---|---|
| `name` | `history` | source/series name (no underscores) |
| `type` | `float` | value type (`uint`, `float`, `str`, `text`, `log`) |
| `start` | `2022-12-26T00:00:00Z` | timestamp of the first entry (UTC, trailing `Z`) |
| `stop` | `2022-12-27T00:00:00Z` | timestamp of the last entry (UTC, trailing `Z`) |
| `count` | `140190` | number of entries |
| `flag` | `raw` | data flag (`raw`, or a short descriptor) |
| `ext` | `csv` | file format (`csv`, `pkl`, `parquet`) |
| `comp` | `zst` | compression method (optional: `bz2`, `gz`, `zst`/`zstd`; `zstd` preferred) |

The timestamps may be written without the `Z` and the tool will still parse the
file, but the generated/canonical form includes it.

Not sure how to name a file? Let the tool derive `start`/`stop`/`count` from the
data and build the name for you (see
[Rename a file to the naming convention](#rename-a-file-to-the-naming-convention)).

### Upload an extra file
Use `-e`/`--extra-file` to upload a file as an *extra* file (stored verbatim,
not subject to the datafile naming convention):
```sh
dataportaltools -U 17 -s ./dataset/README.md -t user.token -e
```
Add `-p` to place it in a sub-folder of up to **two** levels (`-p` requires
`-e`):
```sh
# stored under docs/
dataportaltools -U 17 -s ./dataset/README.md -t user.token -e -p docs

# two nested levels -> docs/api/
dataportaltools -U 17 -s ./dataset/README.md -t user.token -e -p docs/api
```
A prefix deeper than two levels (e.g. `a/b/c`) or with unsafe segments (`..`)
is rejected with an error rather than silently dropped. A trailing slash is
ignored (`docs/` is the same as `docs`).

### Rename a file to the naming convention
`--rename <file>` reads the data file with pandas and derives the parts it can
(`count` = number of rows, `start`/`stop` = min/max of the timestamp column,
auto-detected or set with `--tscol`). You supply the parts that cannot be
inferred: `--name` and `--kind` are required, plus `--dtype`/`--flag`/`--size`
as needed. Supported input formats: `.csv`, `.parquet`, `.pkl`, each optionally
compressed (`.gz`, `.bz2`, `.zst`).

Without `--apply` it only prints the suggested convention name (keeping the
input's extension):
```sh
dataportaltools --rename ./dump.csv --name history --kind metric --dtype float
# -> history_float_2022-12-26T00:00:00Z_2022-12-27T00:00:00Z_140190_raw.csv
```

With `--apply` it **normalizes and rewrites** the file as the convention's
preferred **parquet + zstd** form (matching what the dataportal ingester uses):
- each non-timestamp column is coerced `int -> float -> text` (left as text when
  no numeric type fits), and any text columns are reported so you can review
  them;
- a new `<name>...raw.parquet.zst` file is written next to the source (the
  original is left untouched).
```sh
dataportaltools --rename ./dump.csv --name history --kind metric --dtype float --apply
# Review: could not infer a numeric type for column(s): label (left as text)
# -> history_float_2022-12-26T00:00:00Z_2022-12-27T00:00:00Z_140190_raw.parquet.zst
```
The resulting file already follows the naming convention and can be uploaded
directly with `-U`.

### List files in dataset
```sh
dataportaltools -l 17 -t user.token
```

### Annotate files (tags and points-of-interest)

Files can carry user annotations: free-form **tags** and **points-of-interest**
(POIs), which are time ranges with a text note.

Annotate while uploading. `--tag` may be repeated and is applied to every file
in the upload:
```sh
dataportaltools -U 17 -s "./dataset/history_float_2022-12-26T00:00:00Z_2022-12-27T00:00:00Z_140190_raw.csv.zst" -t user.token --tag radio --tag drive-test
```

Annotate an existing file without re-uploading, using `--setmeta <FileID>`
(the dataset id comes from `-U`/`--upload` or `-l`/`--listfiles`):
```sh
dataportaltools --setmeta 74 -U 17 -t user.token --tag reviewed
```

A POI is given as `--poi 'start,stop,text'`. `start`/`stop` are timestamps
(ISO-8601 or epoch, no commas) and are normalized to a trailing `Z`; the text
may contain commas. POIs only apply to a **single** file — either a single-file
upload or `--setmeta`:
```sh
dataportaltools --setmeta 74 -U 17 -t user.token \
  --poi '2024-01-31T21:00:00,2024-01-31T21:05:00,anomaly spike'
```
Trying to attach a POI to a multi-file upload is rejected; use `--setmeta` per
file instead. Running `--setmeta` without any `--tag`/`--poi` is a no-op.

### Delete dataset
```sh
dataportaltools -d 17 -t user.token
```

### Setting another API server URL
```sh
$ dataportaltools -a http://localhost:3001/v1 ...

$ PORTAL_URL=http://localhost:3001/v1 dataportaltools ...
```

## Example
In the examples below, we use the live portal where we access the API on ```https://portal.wara-ops.org/api/v1``` which is the default.
Other API servers, e.g., development servers, can be set either with the `-a`/`--api` flag or via the `PORTAL_URL` environment variable.

```sh
# List available datasets
$ dataportaltools -L -t /tmp/user01_token
DatasetID |                              DatasetName |                     CreateDate |   Category | Organization
----------+------------------------------------------+--------------------------------+------------+---------------
        1 |                              ERDCmetrics |       2023-12-13T09:21:35.000Z |     metric |   Ericsson
        2 |                                 ERDClogs |       2023-12-13T10:30:03.000Z |        log |   Ericsson
        3 |                                   5Gdata |       2023-12-13T10:41:59.000Z |     metric |   Ericsson
        4 |                                      srs |       2023-12-13T11:03:49.000Z |     metric |   Ericsson
        5 |                            ControlSystem |       2024-01-08T12:13:35.000Z |     metric |        ESS
        6 |                                CrashDump |       2024-01-08T12:21:20.000Z |        log | Schneider-Electric
        7 |                          ERDClogs-parsed |       2024-02-16T06:51:10.000Z |        log |   Ericsson
       14 |                          SRS-Positioning |       2024-09-23T06:38:23.000Z |     metric |   Ericsson
       15 |             ISAC-midband-drone-detection |       2024-10-11T12:40:53.000Z |     metric |   Ericsson
       16 |                      AdvenicaLogAnalysis |       2024-11-27T08:27:51.000Z |        log |   Advenica
       17 |                       Kockums-Kubernetes |       2024-12-12T12:37:03.000Z |        log | SAAB-Kockums



# List files in dataset
$ dataportaltools -l 1 -t /tmp/user01_token
FileID |                      StartDate |                       StopDate |    Entries |     FileSize | MFileName
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
     1 |       2022-11-16T00:00:00.000Z |       2022-11-17T00:00:00.000Z |     637438 |      5521085 | history_uint_2022-11-16T00:00:00Z_2022-11-17T00:00:00Z_637438_raw.pkl.bz2
     4 |       2022-11-17T00:00:00.000Z |       2022-11-18T00:00:00.000Z |     630806 |      5458175 | history_uint_2022-11-17T00:00:00Z_2022-11-18T00:00:00Z_630806_raw.pkl.bz2
...
 99004 |       2024-01-31T21:00:00.000Z |       2024-01-31T21:59:59.000Z |     869106 |      5964930 | history_uint_2024-01-31T21:00:00Z_2024-01-31T21:59:59Z_869106_raw.pkl.bz2
 99005 |       2024-01-31T22:00:00.000Z |       2024-01-31T22:59:59.000Z |     868935 |      5956555 | history_uint_2024-01-31T22:00:00Z_2024-01-31T22:59:59Z_868935_raw.pkl.bz2
 99006 |       2024-01-31T23:00:00.000Z |       2024-01-31T23:59:59.000Z |     868797 |      5956084 | history_uint_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_868797_raw.pkl.bz2
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
 15744 |                                |                                |            | 148268459480 |


# Create a dataset
$ dataportaltools -a http://127.0.0.1:3001/v1 -c dummy.md -u user01 -t /tmp/user01_token
DatasetID | ContainerName
----------+--------------------------------------------------------------------------------------------------
     20 | waraops_qtorgho_ade10eab-63a3-4946-8d5d-a298ddf0ad66_Ericsson_Example-dataset

# List files (Should not be any!)
$ dataportaltools -l 20 -u user01 -t /tmp/user01_token
FileID |                      StartDate |                       StopDate |    Entries |     FileSize | MFileName
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------


# Upload an extrafile. Note: use -e; -p sets the destination sub-folder
$ dataportaltools -U 20 -s README.md -t /tmp/user01_token -e -p testing
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------
README.md                                          | testing/README.md

# Upload datafiles.
# Note 1: it can be a good idea to make a dry run first
# Note 2: Globbing requires double quotes
$ ls -l hist*
-rw-r--r--  1 qtorgho  staff  1442 Jan 20 13:23 history_uint_2024-01-31T21:00:00Z_2024-01-31T21:59:59Z_1000_raw.csv
-rw-r--r--  1 qtorgho  staff  1442 Jan 20 13:23 history_uint_2024-01-31T22:00:00Z_2024-01-31T22:59:59Z_2000_raw.csv
-rw-r--r--  1 qtorgho  staff  1442 Jan 20 13:24 history_uint_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_raw.csv

$ dataportaltools -v -U 20 -s "history_uint_2024-01-31T2*" -t /tmp/user01_token --dryrun
INFO:toolslib.upload:_upload_data {
    "datatype": "uint",
    "dataflag": "raw",
    "start": "2024-01-31T23:00:00Z",
    "stop": "2024-01-31T23:59:59Z",
    "count": 3000
}
INFO:toolslib.upload:_upload_data {
    "datatype": "uint",
    "dataflag": "raw",
    "start": "2024-01-31T22:00:00Z",
    "stop": "2024-01-31T22:59:59Z",
    "count": 2000
}
INFO:toolslib.upload:_upload_data {
    "datatype": "uint",
    "dataflag": "raw",
    "start": "2024-01-31T21:00:00Z",
    "stop": "2024-01-31T21:59:59Z",
    "count": 1000
}
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------

$ dataportaltools -U 20 -s "history_uint_2024-01-31T2*" -t /tmp/user01_token
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------
history_uint_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_raw.csv | 2024/history_uint_2024-01-31T23:00:00.000Z_2024-01-31T23:59:59.000Z_3000_raw.csv
history_uint_2024-01-31T22:00:00Z_2024-01-31T22:59:59Z_2000_raw.csv | 2024/history_uint_2024-01-31T22:00:00.000Z_2024-01-31T22:59:59.000Z_2000_raw.csv
history_uint_2024-01-31T21:00:00Z_2024-01-31T21:59:59Z_1000_raw.csv | 2024/history_uint_2024-01-31T21:00:00.000Z_2024-01-31T21:59:59.000Z_1000_raw.csv

# Delete dataset
$ dataportaltools -d 20 -t /tmp/user01_token
```

## More examples
In the examples below, we use a dev portal where we access the API on ```http://127.0.0.1:3001/v1```.

### Create a dataset
Yes, same as above.
```sh
$ dataportaltools -a http://127.0.0.1:3001/v1 -L -t /tmp/user01_token
DatasetID |                              DatasetName |                     CreateDate |   Category | Organization
----------+------------------------------------------+--------------------------------+------------+---------------

$ dataportaltools -a http://127.0.0.1:3001/v1 -c dummy.md -u user01 -t /tmp/user01_token
DatasetID | ContainerName
----------+--------------------------------------------------------------------------------------------------
        7 | waraops_qtorgho_bb2019ca-0ec3-4b63-b0a8-9b931e52daeb_Ericsson_Dummy-dataset
```

### Upload an extra file.
Use `-e`/`--extra-file` to upload a file as an extra file. Add `-p` to set the
destination sub-folder (up to two levels).

```sh
$ dataportaltools -a http://127.0.0.1:3001/v1 -U 7 -s extrafile.csv.zst -e -p larry -t /tmp/user01_token
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------
extrafile.csv.zst                                  | larry/extrafile.csv.zst
```

Place it under a two-level sub-folder.
```sh
$ dataportaltools -a http://127.0.0.1:3001/v1 -U 7 -s extrafile.csv.zst -e -p larry/sub -t /tmp/user01_token
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------
extrafile.csv.zst                                  | larry/sub/extrafile.csv.zst
```

### List all files so far.
```sh
$ dataportaltools -a http://127.0.0.1:3001/v1 -l 7 -t /tmp/user01_token
FileID |                      StartDate |                       StopDate |    Entries |     FileSize | MFileName
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
    72 |                            n/a |                            n/a |        n/a |         1442 | extrafile.csv.zst
    73 |                            n/a |                            n/a |        n/a |         1442 | newname.csv.zst
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
     2 |                                |                                |            |         2884 |
```

### Upload data files
Globbing is allowed. Notice here that all files follow the naming convention.
```sh
$ ls -l metric
total 24
-rw-r--r--  1 qtorgho  staff  1442 Jan 20 13:23 history_uint_2024-01-31T21:00:00Z_2024-01-31T21:59:59Z_1000_raw.csv
-rw-r--r--  1 qtorgho  staff  1442 Jan 20 13:23 history_uint_2024-01-31T22:00:00Z_2024-01-31T22:59:59Z_2000_raw.csv
-rw-r--r--  1 qtorgho  staff  1442 Jan 20 13:24 history_uint_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_raw.csv

$ dataportaltools -a http://127.0.0.1:3001/v1 -U 7 -t /tmp/user01_token -s "metric/history*"
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------
metric/history_uint_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_raw.csv | 2024/history_uint_2024-01-31T23:00:00.000Z_2024-01-31T23:59:59.000Z_3000_raw.csv
metric/history_uint_2024-01-31T22:00:00Z_2024-01-31T22:59:59Z_2000_raw.csv | 2024/history_uint_2024-01-31T22:00:00.000Z_2024-01-31T22:59:59.000Z_2000_raw.csv
metric/history_uint_2024-01-31T21:00:00Z_2024-01-31T21:59:59Z_1000_raw.csv | 2024/history_uint_2024-01-31T21:00:00.000Z_2024-01-31T21:59:59.000Z_1000_raw.csv
```
Alternatively, the argument ```-s``` can be repeated, e.g.,
```sh
... -s file1 -s file2 -s file3 ...
```
List uploaded files so far
```sh
$ dataportaltools -a http://127.0.0.1:3001/v1 -l 7 -t /tmp/user01_token
FileID |                      StartDate |                       StopDate |    Entries |     FileSize | MFileName
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
    72 |                            n/a |                            n/a |        n/a |         1442 | extrafile.csv.zst
    73 |                            n/a |                            n/a |        n/a |         1442 | newname.csv.zst
    74 |       2024-01-31T23:00:00.000Z |       2024-01-31T23:59:59.000Z |       3000 |         1442 | history_uint_2024-01-31T23:00:00.000Z_2024-01-31T23:59:59.000Z_3000_raw.csv
    75 |       2024-01-31T22:00:00.000Z |       2024-01-31T22:59:59.000Z |       2000 |         1442 | history_uint_2024-01-31T22:00:00.000Z_2024-01-31T22:59:59.000Z_2000_raw.csv
    76 |       2024-01-31T21:00:00.000Z |       2024-01-31T21:59:59.000Z |       1000 |         1442 | history_uint_2024-01-31T21:00:00.000Z_2024-01-31T21:59:59.000Z_1000_raw.csv
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
     5 |                                |                                |            |         7210 |

```

### Upload a file using arguments to describe the data content
In this example, we have information (arguments) to construct both a ```metric``` file and a ```log``` file which the tool complains about.
```sh
$ dataportaltools -a http://127.0.0.1:3001/v1 -U 7 -s extrafile3.csv -t /tmp/user01_token \
--start "$(date +%s)" \
--stop "$(date +%s)" \
--count 1000 \
--flag raw \
--dtype float
ERROR:toolslib.utils:create_filename, cannot build a name without a valid 'kind', got ''
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------
```
We need to hint that the file is a ```metric``` file.
```sh
$ dataportaltools -a http://127.0.0.1:3001/v1 -U 7 -s extrafile3.csv -t /tmp/user01_token \
--start "$(date +%s)" \
--stop "$(date +%s)" \
--count 1000 \
--flag raw \
--dtype float \
--kind metric
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------
extrafile3.csv                                     | 2025/extrafile3_float_2025-01-25T10:19:05.000Z_2025-01-25T10:19:05.000Z_1000_raw.csv
```
Note: using parameters to describe a data file only applies when a single file shall be uploaded. Also, ```start``` and ```stop``` can be epoch, i.e., time in seconds since 1970-01-01.

List the uploaded files so far.
```sh
$ dataportaltools -a http://127.0.0.1:3001/v1 -l 7 -t /tmp/user01_token
FileID |                      StartDate |                       StopDate |    Entries |     FileSize | MFileName
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
    72 |                            n/a |                            n/a |        n/a |         1442 | extrafile.csv.zst
    73 |                            n/a |                            n/a |        n/a |         1442 | newname.csv.zst
    74 |       2024-01-31T23:00:00.000Z |       2024-01-31T23:59:59.000Z |       3000 |         1442 | history_uint_2024-01-31T23:00:00.000Z_2024-01-31T23:59:59.000Z_3000_raw.csv
    75 |       2024-01-31T22:00:00.000Z |       2024-01-31T22:59:59.000Z |       2000 |         1442 | history_uint_2024-01-31T22:00:00.000Z_2024-01-31T22:59:59.000Z_2000_raw.csv
    76 |       2024-01-31T21:00:00.000Z |       2024-01-31T21:59:59.000Z |       1000 |         1442 | history_uint_2024-01-31T21:00:00.000Z_2024-01-31T21:59:59.000Z_1000_raw.csv
    77 |       2025-01-25T10:19:05.000Z |       2025-01-25T10:19:05.000Z |       1000 |         1442 | extrafile3_float_2025-01-25T10:19:05.000Z_2025-01-25T10:19:05.000Z_1000_raw.csv
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
     6 |                                |                                |            |         8652 |

```

## Development

To run **all** checks and tests at once (ruff lint, ruff format check, pylint and
pytest with the coverage gate) using the project's `.venv`:

``` bash
scripts/check.sh          # run everything (same checks as CI)
scripts/check.sh --fix    # auto-fix ruff lint + formatting first
```

The script creates the `.venv` via `pdm install --dev` if it does not exist yet,
and can be run from any directory.

### pre-commit
https://pre-commit.com/#intro
``` bash
uv pip install -U pre-commit
```

Install commit hook
``` bash
pre-commit install
```

Run lint and checks
``` bash
pre-commit run -v --all-files
```

#### Update pre-commit
``` bash
pre-commit autoupdate
```

### Build

Create the development virtualenv(s):
``` bash
./scripts/create-venv.sh
```

Build the distribution (sdist + wheel) with the pdm backend:
``` bash
pdm build        # or: python3 -m build
```
