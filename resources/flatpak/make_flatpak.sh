#!/usr/bin/env bash
# Setup
cd resources/flatpak || exit
rm -Rf .flatpak-builder
rm -Rf repo

# Build python wheel
rm -i -Rf build/ dist/; python3 -m build ../..
# Dump all dependencies to wheels
python -m pip wheel --wheel-dir=wheels warnet

# Build flatpak
flatpak-builder --force-clean --user --install-deps-from=flathub --repo=repo --install /tmp/warnet-flatpak org.bitcoindevproject.Warnet.yaml

# Clean up after ourselves
rm -Rf .flatpak-builder
rm -Rf repo
rm -Rf wheels
