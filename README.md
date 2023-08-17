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
        bcli <node#> <method> <params...> Send a bitcoin-cli command to the specified node.
        log <node#>                       Output the bitcoin debug.log file for specified node.
        run <scnario name> <args...>      Run the specified warnet scenario.
        messages <src:node#> <dest:node#> Output the captured messages between two specified nodes.
        stop                              Stop warnet. Stops and removes all containers and networks.
```

### Build a Network Graph

`// TODO`

The graphml file MUST have a series of `<node>` objects.
Each `<node>` object MUST have a version element with one of the following syntax examples:

Official Bitcoin Core release version, available from https://bitcoincore.org/bin
(The binary will be downloaded and installed):

```
<data key="version">25.0</data>
```

A remote branch on GitHub (the branch will be cloned, built, and installed):

```
<data key="version">vasild/bitcoin#relay_tx_to_priv_nets</data>
```
