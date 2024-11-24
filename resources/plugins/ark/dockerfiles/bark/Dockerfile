FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y jq && rm -rf /var/lib/apt/lists/*

COPY bark /usr/local/bin/bark

RUN chmod +x /usr/local/bin/bark

ENTRYPOINT ["/usr/local/bin/bark"]
