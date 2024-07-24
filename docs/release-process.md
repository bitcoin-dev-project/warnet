# Release process

Once a tag is pushed to GH this will start an image build using the tag

## Prerequisites

- [ ] Update version in pyproject.toml
- [ ] Tag git with new version
- [ ] Push tag to GitHub

## Manual Builds

```bash
# Install build dependencies
pip install -e .[build]

# Remove previous release metadata
rm -i -Rf build/ dist/

# Build wheel
python3 -m build
```

### Upload

```bash
# Upload to Pypi
python3 -m twine upload dist/*
```
