# Release process

## Prerequisites

- [ ] Update version in pyproject.toml
- [ ] Tag git with new version
- [ ] Push tag to GitHub
    This should start an image build using the tag

## Build

```bash
# Install build dependencies
pip install -e .[build]

# Remove previous release metadata
rm -i -Rf build/ dist/

# Build wheel
python3 -m build
```

## Upload

```bash
# Upload to Pypi
# NB remove "--repository testpypi" to push to pypi.org prope
python3 -m twine upload --repository testpypi dist/*
```
