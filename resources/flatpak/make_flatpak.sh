#!/usr/bin/env bash
set -ex

# Pre-clean
rm -Rf resources/flatpak/.flatpak-builder
rm -Rf resources/flatpak/repo

# Build python wheel
rm -i -Rf build/ dist/
python3 -m build
ls -al dist
mv dist/warnet-*-py3-none-any.whl dist/warnet.whl
cd resources/flatpak || exit

# Dump all dependencies to wheels
python -m pip wheel --wheel-dir=wheels warnet

# Setup flatpak output dir
if [ -n "$GITHUB_REF" ]; then
    export LOCATION=warnet_flatpak
else
    export LOCATION=/tmp/warnet-flatpak/
fi
echo Location set to: "$LOCATION"

mkdir -p "$LOCATION"
rm -Rf "${LOCATION:?}"/*
mkdir -p "$LOCATION/repo"

# Build flatpak
flatpak-builder --force-clean --user --install-deps-from=flathub --repo="${LOCATION}/repo" --install "${LOCATION}" org.bitcoindevproject.Warnet.yaml

# Clean up after ourselves
rm -Rf .flatpak-builder
rm -Rf wheels
