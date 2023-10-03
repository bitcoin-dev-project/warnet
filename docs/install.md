# Install Warnet

## Dependencies

Install system dependencies:

* `docker`
* `docker-compose`

e.g. for debian-based linux distros:

```bash
apt install docker docker-compose
```

### Using Docker

If you have never used Docker before you may need to take a few more steps to
run the Docker daemon on your system. The Docker daemon MUST be running
before stating Warnet.

#### Linux

- [Check Docker user/group permissions](https://stackoverflow.com/a/48957722/1653320)
- or [`chmod` the Docker UNIX socket](https://stackoverflow.com/a/51362528/1653320)

#### macOS

On macOS, a bridge to the docker subnet is required, such as
https://github.com/chipmk/docker-mac-net-connect


```bash
# Install via Homebrew
brew install chipmk/tap/docker-mac-net-connect

# Run the service and register it to launch at boot
sudo brew services start chipmk/tap/docker-mac-net-connect
```

## Download Warnet

```bash
git clone https://github.com/bitcoin-dev-project/warnet
cd warnet
```

## Install Warnet

### Optional: use a virtual Python environment such as `venv`

```bash
python3 -m venv .venv # Use alternative venv manager if desired
source .venv/bin/activate
```

```bash
pip install --upgrade pip
pip install -e .
```


# Next: [Running Warnet](running.md)
