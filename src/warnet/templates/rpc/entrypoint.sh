#!/bin/bash
set -e

SOURCE_DIR="/root/warnet"
MAX_ATTEMPTS=30
SLEEP_DURATION=1

echo "Checking for mounted source code at ${SOURCE_DIR}..."

check_setup_toml() {
    if [ -f "${SOURCE_DIR}/pyproject.toml" ]; then
        return 0
    else
        return 1
    fi
}

attempt=1
while ! check_setup_toml; do
    echo "Waiting for source code to be mounted (attempt: ${attempt}/${MAX_ATTEMPTS})..."
    sleep ${SLEEP_DURATION}
    ((attempt++))

    if [ ${attempt} -gt ${MAX_ATTEMPTS} ]; then
        echo "Source code not mounted after ${MAX_ATTEMPTS} attempts. Proceeding without installation."
        break
    fi
done

# If setup.py is found, install the package
if check_setup_toml; then
    echo "Installing package from ${SOURCE_DIR}..."
    cd ${SOURCE_DIR}
    uv pip install --system --no-cache -e .
fi

# Execute the CMD from the Dockerfile
exec "$@"
