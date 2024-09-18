FROM python:3.11-slim-bookworm

# Set versions as environment variables
ENV K9S_VERSION=v0.32.5
ENV KTOP_VERSION=v0.3.7

# Install uv from docker image
COPY --from=ghcr.io/astral-sh/uv:0.4.12 /uv /bin/uv

# Install curl. Git needed for helm plugins
RUN --mount=type=cache,target=/var/cache/apt,sharing=private \
    --mount=type=cache,target=/var/lib/apt,sharing=private \
    apt-get update && apt-get install -y --no-install-recommends curl ca-certificates git

# Install kubectl
RUN --mount=type=cache,target=/tmp \
    curl -Lo /tmp/kubectl "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x /tmp/kubectl && \
    mv /tmp/kubectl /usr/local/bin/

# Install helm
RUN curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install k9s based on arch
ARG TARGETARCH
RUN --mount=type=cache,target=/tmp,sharing=private \
    curl -Lo /tmp/k9s_linux_${TARGETARCH}.deb "https://github.com/derailed/k9s/releases/download/${K9S_VERSION}/k9s_linux_${TARGETARCH}.deb" && \
    dpkg -i /tmp/k9s_linux_${TARGETARCH}.deb && \
    rm /tmp/k9s_linux_${TARGETARCH}.deb

# Install ktop for arch
RUN --mount=type=cache,target=/tmp,sharing=private \
    curl -Lo /tmp/kubectl-ktop_${KTOP_VERSION}_linux_${TARGETARCH}.tar.gz "https://github.com/vladimirvivien/ktop/releases/download/${KTOP_VERSION}/kubectl-ktop_${KTOP_VERSION}_linux_${TARGETARCH}.tar.gz" && \
    tar xzvf /tmp/kubectl-ktop_${KTOP_VERSION}_linux_${TARGETARCH}.tar.gz -C /tmp && \
    cp /tmp/kubectl-ktop /usr/bin/ktop && \
    rm -rf /tmp/kubectl-ktop_${KTOP_VERSION}_linux_${TARGETARCH}.tar.gz /tmp/kubectl-ktop

# Setup venv and install warnet
ADD . /warnet
WORKDIR /warnet
RUN uv sync

# Start
CMD ["/bin/bash", "-c", "source /warnet/.venv/bin/activate && cd / && exec /bin/bash"]

