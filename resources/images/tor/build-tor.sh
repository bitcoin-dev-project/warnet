SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"

docker buildx build \
    --platform linux/amd64,linux/arm64,linux/armhf \
    --push \
    -t bitcoindevproject/tor-da:latest \
    -f ./resources/images/tor/Dockerfile_tor_da \
    ./resources/images/tor/

docker buildx build \
    --platform linux/amd64,linux/arm64,linux/armhf \
    --push \
    -t bitcoindevproject/tor-relay:latest \
    -f ./resources/images/tor/Dockerfile_tor_relay \
    ./resources/images/tor/    