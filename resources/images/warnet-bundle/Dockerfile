FROM python:3.11-alpine

# Install uv and ktop by copying from their docker images
COPY --from=ghcr.io/astral-sh/uv:0.4.12 /uv /bin/uv
COPY --from=ghcr.io/vladimirvivien/ktop:latest /ko-app/ktop /bin/ktop

RUN apk add --no-cache bash curl ca-certificates git kubectl helm k9s fish vim mc nano

# Setup venv and install warnet
ADD . /warnet
WORKDIR /warnet
RUN uv sync

# Setup autocomplete
RUN mkdir -p /root/.config/fish/completions
RUN cat <<EOF > /root/.config/fish/completions/warnet.fish
_WARNET_COMPLETE=fish_source warnet | source
EOF

# Start
CMD ["/usr/bin/fish", "-c", "source /warnet/.venv/bin/activate.fish; cd /root; exec fish"]
