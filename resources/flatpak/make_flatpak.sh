#!/usr/bin/env bash
# Pre-clean
rm -Rf resources/flatpak/.flatpak-builder
rm -Rf resources/flatpak/repo

# Build python wheel
rm -i -Rf build/ dist/; python3 -m build
mv "dist/warnet-${WARNET_VERSION}-py3-none-any.whl" dist/warnet.whl
cd resources/flatpak || exit

# Dump all dependencies to wheels
python -m pip wheel --wheel-dir=wheels warnet

# Build flatpak
flatpak-builder --force-clean --user --install-deps-from=flathub --repo=repo --install /tmp/warnet-flatpak org.bitcoindevproject.Warnet.yaml

# Clean up after ourselves
rm -Rf .flatpak-builder
rm -Rf repo
rm -Rf wheels
