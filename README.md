# dataportaltools
 WARA-Ops DataportalTools

<b>The compute portal repository can be found [here](https://gitlab.internal.ericsson.com/autodc/jupyterk8s)</b>

<b>The data portal repository can be found [here](https://gitlab.internal.ericsson.com/autodc/wcib)</b>

A thin client for

- creating datasets,
- uploading files to datasets,
- list datasets and datafiles, and
- deleting datasets.

See [here](./src/README.md) for details.

## Setup

This project uses pdm (https://pdm-project.org/latest/) as its package manager. See the webpage for installation instructions.

Tests and lints can be run with `pdm run test` and `pdm run lint`. These are also run in the CI pipe on pushes to the repository.

To run **all** checks and tests at once (ruff lint, ruff format check, pylint and
pytest with the coverage gate) using the project's `.venv`:

``` bash
scripts/check.sh          # run everything (same checks as CI)
scripts/check.sh --fix    # auto-fix ruff lint + formatting first
```

The script creates the `.venv` via `pdm install --dev` if it does not exist yet,
and can be run from any directory.

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

# Upload data files (globbing requires double quotes); dry-run first
uvx --from . dataportaltools -U 17 -s "./dataset/file*.tgz" --dryrun
uvx --from . dataportaltools -U 17 -s "./dataset/file*.tgz"

# Upload an extra (non-convention) file into a subfolder
uvx --from . dataportaltools -U 17 -s ./dataset/README.md -p metadata

# Delete dataset 17
uvx --from . dataportaltools -d 17
```

A `-t <token file>` still works and takes precedence over `PORTAL_TOKEN`:

``` bash
uvx --from . dataportaltools -L -t user.token
```

See [src/README.md](./src/README.md) for the full set of commands and options.

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

### Manual linting
prefer running pre-commit like above
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

# Old instructions
## Installation
## prerequisite

### install
``` bash
python3 -m pip install dataportaltools
```

### use

### development
#### install venv
```
./scripts/create-venv.sh
```
#### build
``` bash
python3 -m build
```
