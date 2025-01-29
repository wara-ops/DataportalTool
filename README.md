# WARA-Ops DataportalTools

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


## Issues
