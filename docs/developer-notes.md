# Developer notes

## Contributing / Local Warnet Development

### Download the code repository

```bash
git clone https://github.com/bitcoin-dev-project/warnet
cd warnet
```

### Recommended: use a virtual Python environment such as `venv`

```bash
python3 -m venv .venv # Use alternative venv manager if desired
source .venv/bin/activate
```

```bash
pip install --upgrade pip
pip install -e .
```

## Formatting & linting

This project primarily uses the `uv` python packaging tool: https://docs.astral.sh/uv/ along with the sister formatter/linter `ruff` https://docs.astral.sh/ruff/

Refer to the `uv` documentation for installation methods: https://docs.astral.sh/uv/getting-started/installation/

With `uv` installed you can add/remove dependencies using `uv add <dep>` or `uv remove <dep>.
This will update the [`uv.lock`](https://docs.astral.sh/uv/guides/projects/#uvlock) file automatically.

We use ruff version 0.6.8 in this project currently. This can be installed as a stand-alone binary (see documentation), or via `uv` using:

```bash
# install
$ uv tool install ruff@0.6.8

# lint
$ uvx ruff@0.6.8 check .

# format
$ uvx ruff@0.6.8 format .
```

## Release process

Once a tag is pushed to GH this will start an image build using the tag

### Prerequisites

- [ ] Update version in pyproject.toml
- [ ] Tag git with new version
- [ ] Push tag to GitHub

### Manual Builds

```bash
# Install build dependencies
pip install -e .[build]

# Remove previous release metadata
rm -i -Rf build/ dist/

# Build wheel
python3 -m build
```

#### Upload

```bash
# Upload to Pypi
python3 -m twine upload dist/*
```
