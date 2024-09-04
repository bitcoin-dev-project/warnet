#!/bin/bash
set -x  # Enable debugging
echo "Starting entrypoint.sh"

# Loop through all files in /wbin
for file in /wbin/*; do
    echo "Found file: $file"
    cp "$file" "/command"
    chmod +x "/command"
    # Exit the loop after copying the first file
    break
done

echo "Files present:"
ls -al
echo "Command file:"
stat /command
echo "Args passed to entrypoint.sh:"
printf '%s\n' "$@"

# Try to split the arguments
IFS=' ' read -ra ARGS <<< "$*"
echo "Split arguments:"
printf '  %s\n' "${ARGS[@]}"

echo "Executing command with args:"
echo "/command" "${ARGS[@]}"

# Execute the command with split arguments
"/command" "${ARGS[@]}"

echo "Command execution completed"

# DEBUG: Keep the container running after failure
# tail -f /dev/null
