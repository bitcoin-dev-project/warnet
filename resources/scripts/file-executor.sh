#!/bin/bash

# Check if inotifywait is installed
if ! command -v inotifywait &> /dev/null; then
  echo "inotifywait could not be found. Please install inotify-tools."
  exit 1
fi

# Check we have a directory to watch
if [ $# -eq 0 ]; then
  echo "Please provide a directory to watch"
  exit 1
fi

WATCH_DIR="$1"
MAX_CONCURRENT=5
declare -A RUNNING_PROCESSES

watch_directory() {
  inotifywait -m "$WATCH_DIR" -e create -e moved_to |
    while read -r path action file; do
      full_path="$path$file"
      if [[ -x "$full_path" ]]; then
        case "$action" in
        CREATE)
          echo "New executable created: $full_path"
          ;;
        MOVED_TO)
          echo "Executable moved into directory: $full_path"
          ;;
        esac
        run_executable "$full_path" &
      fi
    done
}

run_executable() {
  local executable="$1"
  while [[ ${#RUNNING_PROCESSES[@]} -ge $MAX_CONCURRENT ]]; do
    sleep 1
    for pid in "${!RUNNING_PROCESSES[@]}"; do
      if ! kill -0 "$pid" 2>/dev/null; then
        unset "RUNNING_PROCESSES[$pid]"
      fi
    done
  done

  "$executable" &
  local pid=$!
  RUNNING_PROCESSES[$pid]=$executable
  wait $pid
  unset "RUNNING_PROCESSES[$pid]"
}

cleanup() {
  echo "Cleaning up..."
  for pid in "${!RUNNING_PROCESSES[@]}"; do
    kill "$pid" 2>/dev/null
  done
  exit 0
}

trap cleanup SIGINT SIGTERM

watch_directory
