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

## Lint

This project primarily uses the `uv` python packaging tool: https://docs.astral.sh/uv/ along with the sister formatter/linter `ruff` https://docs.astral.sh/ruff/

With `uv` installed you can add/remove dependencies using `uv add <dep>` or `uv remove <dep>.
This will update the [`uv.lock`](https://docs.astral.sh/uv/guides/projects/#uvlock) file automatically.


`uv` can also run tools (like `ruff`) without external installation, simply run `uvx ruff check .` or `uvx ruff format .` to use a uv-managed format/lint on the project.

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