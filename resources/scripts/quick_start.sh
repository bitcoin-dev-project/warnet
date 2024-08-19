#!/bin/bash
set -euo pipefail

ERROR_CODE=0

is_cygwin_etal() {
    uname -s | grep -qE "CYGWIN|MINGW|MSYS"
}
is_wsl() {
    grep -qEi "(Microsoft|WSL)" /proc/version &> /dev/null
}
if is_cygwin_etal || is_wsl; then
    echo "Quick start does not support Windows"
    ERROR_CODE=1
fi


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

prompt_user() {
    local prompt="$1"
    tput bold  # Make the prompt bold
    echo "$prompt"
    tput sgr0   # Reset formatting
}

print_message "" "" ""
print_message "" "   ╭───────────────────────────╮" ""
print_message "" "   │  Welcome to Warnet Setup  │" ""
print_message "" "   ╰───────────────────────────╯" ""
print_message "" "" ""
print_message "" "    Let's find out if your system has what it takes to run Warnet..." ""
print_message "" "" ""

prompt_user "Use [1] minikube (Default) or [2] docker-desktop? Enter 1 or 2: "
read -r choice

if [[ "$choice" == "1" || -z "$choice" ]]; then
   choice=1
elif ! [[ "$choice" == "2" ]]; then
   echo "    Please enter 1 for minikube or 2 for docker-desktop."
   exit 1
fi

if [[ "$choice" == "1" || -z "$choice" ]]; then
   approach="minikube"
elif [[ "$choice" == "2" ]]; then
   approach="docker-desktop"
fi

print_partial_message " ⭐️ You chose " ""$approach"" "." "$BOLD"

docker_path=$(command -v docker || true)
if [ -n "$docker_path" ]; then
    print_partial_message " ⭐️ Found " "docker" ": $docker_path" "$BOLD"
else
    print_partial_message " 💥 Could not find " "docker" ". Please follow this link to install Docker Engine..." "$BOLD"
    print_message "" "   https://docs.docker.com/engine/install/" "$BOLD"
    ERROR_CODE=127
fi

current_user=$(whoami)
if [ -n "$docker_path" ]; then
    current_context=$(docker context show)
    if id -nG "$current_user" | grep -qw "docker"; then
        print_partial_message " ⭐️ Found " "$current_user" " in the docker group" "$BOLD"
    elif [ "$current_context" == "rootless" ]; then
        print_message " " "⭐️ Docker is set to rootless" "$BOLD"
    elif [[ "$(uname)" == "Darwin" ]]; then
        print_message " " "⭐️ Found Docker on Darwin" "$BOLD"
    else
        print_partial_message " 💥 Could not find " "$current_user" " in the docker group. Please add it like this..." "$BOLD"
        print_message "" "   sudo usermod -aG docker $current_user && newgrp docker" "$BOLD"
        ERROR_CODE=1
    fi

    if docker info >/dev/null 2>&1; then
        print_partial_message " ⭐️" " Docker" " is running" "$BOLD"
    else
        print_message " " "💥 Docker is not running. Please start docker." "$BOLD"
        ERROR_CODE=1
    fi

    if [[ "$approach" == "docker-desktop" && -n "$docker_path" ]]; then
        if docker context ls | grep -q "docker-desktop"; then
            print_message " ⭐️ Found " "Docker Desktop" "$BOLD"
        else
            print_partial_message " 💥 Could not find " "docker-desktop" ". Please follow this link to install it..." "$BOLD"
            print_message "" "   https://www.docker.com/products/docker-desktop/" "$BOLD"
            ERROR_CODE=127
        fi
    fi
fi

if [[ "$approach" == "minikube" ]]; then
    minikube_path=$(command -v minikube || true)
    if [[ "$(uname)" == "Darwin" ]] && command -v minikube &> /dev/null && [[ "$(minikube version --short)" == "v1.33.1" ]]; then
        print_partial_message " 💥 Could not find " "minikube version > 1.33.1" ". Please upgrade..." "$BOLD"
        print_message "" "   https://minikube.sigs.k8s.io/docs/start/" "$BOLD"
        ERROR_CODE=127
    elif [ -n "$minikube_path" ]; then
        print_partial_message " ⭐️ Found " "minikube" ": $minikube_path " "$BOLD"
    else
        print_partial_message " 💥 Could not find " "minikube" ". Please follow this link to install it..." "$BOLD"
        print_message "" "   https://minikube.sigs.k8s.io/docs/start/" "$BOLD"
        ERROR_CODE=127
    fi
fi

kubectl_path=$(command -v kubectl || true)
if [ -n "$kubectl_path" ]; then
    print_partial_message " ⭐️ Found " "kubectl" ": $kubectl_path " "$BOLD"
else
    print_partial_message " 💥 Could not find " "kubectl" ". Please follow this link to install it..." "$BOLD"
    print_message "" "   https://kubernetes.io/docs/tasks/tools/" "$BOLD"
    ERROR_CODE=127
fi

helm_path=$(command -v helm || true)
if [ -n "$helm_path" ]; then
    print_partial_message " ⭐️ Found " "helm" ": $helm_path" "$BOLD"
else
    print_partial_message " 💥 Could not find " "helm" ". Please follow this link to install it..." "$BOLD"
    print_message "" "   https://helm.sh/docs/intro/install/" "$BOLD"
    ERROR_CODE=127
fi

just_path=$(command -v just || true)
if [ -n "$just_path" ]; then
    print_partial_message " ⭐️ Found " "just" ": $just_path " "$BOLD"
else
    print_partial_message " 💥 Could not find " "just" ". Please follow this link to install it..." "$BOLD"
    print_message "" "   https://github.com/casey/just?tab=readme-ov-file#pre-built-binaries" "$BOLD"
    ERROR_CODE=127
fi

if [ $ERROR_CODE -ne 0 ]; then
    print_message "" "There were errors in the setup process. Please fix them and try again." "$BOLD"
    exit $ERROR_CODE
fi
