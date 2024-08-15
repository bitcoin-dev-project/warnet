# Build incantations

Run from top-level of project

## v0.21.1

```bash
docker buildx build \
  --progress=plain \
  --platform linux/amd64,linux/armhf \
  --tag bitcoindevproject/bitcoin:0.21.1 \
  --file resources/images/bitcoin/insecure/Dockerfile_v0.21.1 resources/images/bitcoin/insecure
```

## v0.20.0

```bash
docker buildx build \ \
  --platform linux/amd64,linux/armhf \
  --tag bitcoindevproject/bitcoin:0.20.0 \
  --file resources/images/bitcoin/insecure/Dockerfile_v0.20.0 resources/images/bitcoin/insecure
```

## v0.19.2

```bash
docker buildx build \
  --platform linux/amd64,linux/armhf \
  --tag bitcoindevproject/bitcoin:0.19.2 \
  --file resources/images/bitcoin/insecure/Dockerfile_v0.19.2 resources/images/bitcoin/insecure
```

## v0.17.0

```bash
docker buildx build \
  --platform linux/amd64,linux/armhf \
  --tag bitcoindevproject/bitcoin:0.17.0 \
  --file resources/images/bitcoin/insecure/Dockerfile_v0.17.0 resources/images/bitcoin/insecure
```

## v0.16.1

```bash
docker buildx build \
  --platform linux/amd64,linux/armhf \
  --tag bitcoindevproject/bitcoin:0.16.1 \
  --file resources/images/bitcoin/insecure/Dockerfile_v0.16.1 resources/images/bitcoin/insecure
```
