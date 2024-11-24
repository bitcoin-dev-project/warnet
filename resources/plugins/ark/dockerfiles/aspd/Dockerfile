FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y jq && rm -rf /var/lib/apt/lists/*

COPY aspd /usr/local/bin/aspd

RUN chmod +x /usr/local/bin/aspd

ENTRYPOINT ["/usr/local/bin/aspd"]
