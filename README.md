# Warnet

## Monitor and analyze the emergent behaviours of Bitcoin networks

### Local Deployment

1. Requirements

Make sure to have docker and docker-compose installed

For macOS, a bridge to the docker subnet is required, such as
https://github.com/chipmk/docker-mac-net-connect

```bash
# Install via Homebrew
brew install chipmk/tap/docker-mac-net-connect

# Run the service and register it to launch at boot
sudo brew services start chipmk/tap/docker-mac-net-connect
```

2. Install the dependencies

It is recommended to create a virtual environment, like so:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

and then install the dependencies with `setuptools`:

```bash
pip install -e .
```

3. Start the docker containers

Each container is a node as described in the graph.

```bash
warnet
```

4. Manually run scenarios

See `/src/scenarios` for examples. Scenarios are written using the Bitcoin Core
test framework for functional testing with some modifications (most notably that
`self.nodes[]` represents an array dockerized bitcoind nodes)

Example:

```bash
# Command one node to generate a wallet and fill 100 blocks with 100 txs each
python src/scenarios/tx-flood.py
```

### Remote / Cloud Deployment

`// TODO`

### Command-line Tools

```
      Usage: warnet-cli <command> <arg1> <arg2> ...

      Available commands:
        log <node number>               Output the bitcoin debug.log file for specified node.
        messages <source> <destination> Output the captured messages between two specified nodes.
        stop                            Stop warnet. Stops and removes all containers and networks.
```
