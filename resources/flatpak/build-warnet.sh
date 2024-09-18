#!/usr/bin/env bash

set -e

# venv setup
/app/bin/uv venv /app/.venv
source /app/.venv/bin/activate

# rename the wheel properly
# uses env var from yaml manifest
mv warnet.whl "warnet-${WARNET_VERSION}-py3-none-any.whl"

# install warnet
uv pip install --no-index --find-links=wheels "warnet-${WARNET_VERSION}-py3-none-any.whl"

# Wrap it for flatpak
install -D /app/.venv/bin/warnet /app/bin/warnet
install -Dm755 warnet-wrapper.sh /app/bin/warnet-wrapper
