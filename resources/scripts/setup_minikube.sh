#!/usr/bin/env bash
set -euo pipefail
set +x
set +v

if [ -z "${WAR_RPC+x}" ]; then
    echo "WAR_RPC is unset. Please provide a path to warnet RPC images."
    exit 1
fi

ERROR_CODE=0

# Colors and styles
RESET='\033[0m'
BOLD='\033[1m'

# Use colors if we can and have the color space
if command -v tput &> /dev/null; then
    ncolors=$(tput colors)
    if [ -n "$ncolors" ] && [ "$ncolors" -ge 8 ]; then
        RESET=$(tput sgr0)
        BOLD=$(tput bold)
    fi
fi

print_message() {
    local color="$1"
    local message="$2"
    local format="${3:-}"
    echo -e "${format}${color}${message}${RESET}"
}

print_partial_message() {
    local pre_message="$1"
    local formatted_part="$2"
    local post_message="$3"
    local format="${4:-}"  # Default to empty string if not provided
    local color="${5:-$RESET}"

    echo -e "${color}${pre_message}${format}${formatted_part}${RESET}${color}${post_message}${RESET}"
}

docker_path=$(command -v docker || true)
if [ -n "$docker_path" ]; then
    print_partial_message " ⭐️ Found " "docker" ": $docker_path" "$BOLD"
else
    print_partial_message " 💥 Could not find " "docker" ". Please follow this link to install Docker Engine..." "$BOLD"
    print_message "" "   https://docs.docker.com/engine/install/" "$BOLD"
    ERROR_CODE=127
fi

current_user=$(whoami)
current_context=$(docker context show)
if id -nG "$current_user" | grep -qw "docker"; then
    print_partial_message " ⭐️ Found " "$current_user" " in the docker group" "$BOLD"
elif [ "$current_context" == "rootless" ]; then
    print_message " " "⭐️ Running Docker as rootless" "$BOLD"
elif [[ "$(uname)" == "Darwin" ]]; then
    print_message " " "⭐️ Running Docker on Darwin" "$BOLD"
else
    print_partial_message " 💥 Could not find " "$current_user" " in the docker group. Please add it like this..." "$BOLD"
    print_message "" "   sudo usermod -aG docker $current_user && newgrp docker" "$BOLD"
    ERROR_CODE=1
fi

minikube_path=$(command -v minikube || true)
if [ -n "$minikube_path" ]; then
    print_partial_message " ⭐️ Found " "minikube" ": $minikube_path " "$BOLD"
else
    print_partial_message " 💥 Could not find " "minikube" ". Please follow this link to install it..." "$BOLD"
    print_message "" "   https://minikube.sigs.k8s.io/docs/start/" "$BOLD"
    ERROR_CODE=127
fi

if [ $ERROR_CODE -ne 0 ]; then
    print_message "" "There were errors in the setup process. Please fix them and try again." "$BOLD"
    exit $ERROR_CODE
fi

# Check minikube status
minikube delete

# Prepare minikube start command
MINIKUBE_CMD="minikube start --driver=docker --container-runtime=containerd --mount --mount-string=\"$PWD:/mnt/src\""

# Check for WAR_CPU and add to command if set
if [ -n "${WAR_CPU:-}" ]; then
    MINIKUBE_CMD="$MINIKUBE_CMD --cpus=$WAR_CPU"
fi

# Check for WAR_MEM and add to command if set
if [ -n "${WAR_MEM:-}" ]; then
    MINIKUBE_CMD="$MINIKUBE_CMD --memory=${WAR_MEM}m"
fi

# Start minikube with the constructed command
eval "$MINIKUBE_CMD"



echo Done...
