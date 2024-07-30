#!/bin/bash
set -euo pipefail


is_cygwin_etal() {
    uname -s | grep -qE "CYGWIN|MINGW|MSYS"
}
is_wsl() {
    grep -qEi "(Microsoft|WSL)" /proc/version &> /dev/null
}
if is_cygwin_etal || is_wsl; then
    echo "Quick start does not support Windows"
    exit 1
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
    local format="$4"
    local color="${5:-$RESET}"

    echo -e "${color}${pre_message}${format}${formatted_part}${RESET}${color}${post_message}${RESET}"
}

print_message "" "" ""
print_message "" "   ╭───────────────────────────────────╮" ""
print_message "" "   │  Welcome to the Warnet Quickstart │" ""
print_message "" "   ╰───────────────────────────────────╯" ""
print_message "" "" ""
print_message "" "    Let's find out if your system has what it takes to run Warnet..." ""
print_message "" "" ""

minikube_path=$(command -v minikube || true)
if [ -n "$minikube_path" ]; then
    print_partial_message " ⭐️ Found " "minikube" ": $minikube_path " "$BOLD"
else
    print_partial_message " 💥 Could not find " "minikube" ". Please follow this link to install it..." "$BOLD"
    print_message "" "   https://minikube.sigs.k8s.io/docs/start/" "$BOLD"
    exit 127
fi

kubectl_path=$(command -v kubectl || true)
if [ -n "$kubectl_path" ]; then
    print_partial_message " ⭐️ Found " "kubectl" ": $kubectl_path " "$BOLD"
else
    print_partial_message " 💥 Could not find " "kubectl" ". Please follow this link to install it..." "$BOLD"
    print_message "" "   https://kubernetes.io/docs/tasks/tools/" "$BOLD"
    exit 127
fi

docker_path=$(command -v docker || true)
if [ -n "$docker_path" ]; then
    print_partial_message " ⭐️ Found " "docker" ": $docker_path" "$BOLD"
else
    print_partial_message " 💥 Could not find " "docker" ". Please follow this link to install Docker Engine..." "$BOLD"
    print_message "" "   https://docs.docker.com/engine/install/" "$BOLD"
    exit 127
fi

current_user=$(whoami)
if id -nG "$current_user" | grep -qw "docker"; then
    print_partial_message " ⭐️ Found " "$current_user" " in the docker group" "$BOLD"
else
    print_partial_message " 💥 Could not find " "$current_user" " in the docker group. Please add it like this..." "$BOLD"
    print_message "" "   sudo usermod -aG docker $current_user && newgrp docker" "$BOLD"
    exit 1
fi

helm_path=$(command -v helm || true)
if [ -n "$helm_path" ]; then
    print_partial_message " ⭐️ Found " "helm" ": $helm_path" "$BOLD"
else
    print_partial_message " 💥 Could not find " "helm" ". Please follow this link to install it..." "$BOLD"
    print_message "" "   https://helm.sh/docs/intro/install/" "$BOLD"
    exit 127
fi

just_path=$(command -v just || true)
if [ -n "$just_path" ]; then
    print_partial_message " ⭐️ Found " "just" ": $just_path " "$BOLD"
else
    print_partial_message " 💥 Could not find " "just" ". Please follow this link to install it..." "$BOLD"
    print_message "" "   https://github.com/casey/just?tab=readme-ov-file#pre-built-binaries" "$BOLD"
    exit 127
fi

python_path=$(command -v python3 || true)
if [ -n "$python_path" ]; then
    print_partial_message " ⭐️ Found " "python3" ": $python_path " "$BOLD"
else
    print_partial_message " 💥 Could not find " "python3" ". Please follow this link to install it (or use your package manager)..." "$BOLD"
    print_message "" "   https://www.python.org/downloads/" "$BOLD"
    exit 127
fi

venv_status=$(python3 -m venv --help || true)
if [ -n "$venv_status" ]; then
    print_partial_message " ⭐️ Found " "venv" ": a python3 module" "$BOLD"
else
    print_partial_message " 💥 Could not find " "venv" ". Please install it using your package manager." "$BOLD"
    exit 127
fi

bpf_status=$(grep CONFIG_BPF /boot/config-"$(uname -r)" || true)
if [ -n "$bpf_status" ]; then
    config_bpf=$(echo "$bpf_status" | grep CONFIG_BPF=y)
    if [ "$config_bpf" = "CONFIG_BPF=y" ]; then
        print_partial_message " ⭐️ Found " "BPF" ": Berkeley Packet Filters appear enabled" "$BOLD"
    else
        print_partial_message " 💥 Could not find " "BPF" ". Please figure out how to enable Berkeley Packet Filters in your kernel." "$BOLD"
        exit 1
    fi
else
    print_partial_message " 💥 Could not find " "BPF" ". Please figure out how to enable Berkeley Packet Filters in your kernel." "$BOLD"
    exit 1
fi

print_message "" "" ""
print_message "" "    Let's try to spin up a python virtual environment..." ""
print_message "" "" ""

if [ -d ".venv" ]; then
    print_message "" "    It looks like a virtual environment already exists!" ""
else
    print_message "" "    Creating a new virtual environment..." ""
    python3 -m venv .venv
fi

source .venv/bin/activate

print_message "" "" ""
print_partial_message " ⭐️ " "venv" ": The python virtual environment looks good" "$BOLD"
print_message "" "" ""
print_message "" "    Let's install warnet into that virtual environment..." ""
print_message "" "" ""

pip install --upgrade pip
pip install -e .

print_message "" "" ""
print_partial_message " ⭐️ " "warnet" ": We installed Warnet in the virtual environment" "$BOLD"
print_message "" "" ""
print_message "" "    Now, let's get the Warnet started..." ""
print_message "" "" ""

just start
just p &
sleep 1
warcli network start
sleep 1
while warcli network connected | grep -q "False"; do
    sleep 2
done
print_message "" "🥳" ""
print_message "" "Run the following command to enter into the python virtual environment..." ""
print_message "" "    source .venv/bin/activate" "$BOLD"
print_partial_message "   After that, you can run " "warcli help" " to start running Warnet commands." "$BOLD"
