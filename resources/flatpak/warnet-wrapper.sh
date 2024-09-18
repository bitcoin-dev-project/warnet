#!/bin/bash
export PATH="/app/bin:$PATH"
export PYTHONPATH="/app/.venv/lib/python3.11/site-packages:$PYTHONPATH"

if [ "$(basename "$0")" = "warnet-flatpak" ]; then
    exec /app/.venv/bin/warnet "$@"
else
    exec /app/.venv/bin/warnet "$@"
fi
