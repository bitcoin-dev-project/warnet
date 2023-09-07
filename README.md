# Warnet

Monitor and analyze the emergent behaviours of Bitcoin networks.

## Major functionality

* Warnet uses docker to launch a bitcoin network of `n` nodes which are connected to each other according to a network topology from a specification file.
* Nodes are by default assigned random IP addresses in the 100.0.0.0/8 subnet which ensures randomized `addrman` binning [by Bitcoin Core](https://github.com/bitcoin/bitcoin/blob/8372ab0ea3c88308aabef476e3b9d023ba3fd4b7/src/addrman.h#L66), along with a Tor address.
* Nodes can be assigned activities which can be programmed using the Bitcoin Core function test [test_framework language](https://github.com/bitcoin/bitcoin/tree/master/test/functional).
* Nodes can have traffic shaping parameters assigned to them via the graph using [tc-netem](https://manpages.ubuntu.com/manpages/trusty/man8/tc-netem.8.html) tool.
* Log files from nodes can be accessed directly
* Some Bitcoin Core activity is polled and reported via a Graphana dashboard.

## Network topology specification

Warnet loads a Bitcoin Core network using a network topology from a [graphml](https://graphml.graphdrawing.org/specification.html) file.
The graphml file has the following specification:

```graphml
<?xml version="1.0" encoding="UTF-8"?><graphml xmlns="http://graphml.graphdrawing.org/xmlns">
<key attr.name="label" attr.type="string" for="node" id="label"/>
<key attr.name="Edge Label" attr.type="string" for="edge" id="edgelabel"/>
<key attr.name="x" attr.type="float" for="node" id="x"/>
<key attr.name="y" attr.type="float" for="node" id="y"/>
<key attr.name="version" attr.type="string" for="node" id="version"/>
<key attr.name="bitcoin_config" attr.type="string" for="node" id="bitcoin_config"/>
<key attr.name="tc_netem" attr.type="string" for="node" id="tc_netem"/>
<graph edgedefault="directed">

<!-- <nodes> -->
<!-- <edges> -->

</graph>
</graphml>

```
### Node attributes

* `id` should be a unique integer identifier
* `label` [optional] specifies the node's label
* `x` specifies the node's x position when rendered in a GUI
* `y` specifies the node's y position when rendered in a GUI
* `version` specifies the node's Bitcoin Core major version, or built branch
* `bitcoin_config` is a comma-separated list of values the node should apply to it's bitcoin.conf, using bitcoin.conf syntax

`version` should be either a version number from the pre-compiled binary list on https://bitcoincore.org/bin/ **or** a built branch using `<user>/<repo>#<branch>` syntax.

Nodes can be added to the graph as follows:

```graphml
<node id="0">
<data key="x">5.5</data>
<data key="y">2.5</data>
<data key="version">24.0</data>
<data key="bitcoin_config">uacomment=warnet0_v24,debugexclude=libevent</data>
<data key="tc_netem"></data>
</node>
```

Or for a custom built branch with traffic shaping rules applied:

```graphml
<node id="0">
<data key="x">2.5</data>
<data key="y">5.0</data>
<data key="version">vasild/bitcoin#relay_tx_to_priv_nets</data>
<data key="bitcoin_config">uacomment=warnet1_custom,debug=1</data>
<data key="tc_netem">tc qdisc add dev eth0 root netem delay 100ms</data>
</node>
```

### Edge attributes

* `edgelabel` specifies an edge's label

Edges can be added between the nodes as follows:

```graphml
<edge id="0" source="0" target="1">
</edge>
```

## Local deployment

### Dependencies

Install system dependencies:

* `docker`
* `docker-compose`

e.g. for debian-based linux distros:

```bash
apt install docker docker-compose
```

### Warnet package

Clone the repo, create a venv and install the warnet package:

```bash
git clone https://github.com/bitcoin-dev-project/warnet
cd warnet

python3 -m venv .venv # Use alternative venv manager if desired
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

## Running

Warnet runs a daemon which can be used to manage multiple warnets.
`warnet` will by default log to a file `$XDG_STATE_HOME/warnet/warnet.log` if the `$XDG_STATE_HOME` environment variable is set, otherwise it will use `$HOME/.warnet/warnet.log`.

To start `warnet` in the foreground with your venv activated simply run:

```bash
warnet
```

> [!NOTE]
> `warnetd` also accepts a `--daemon` option which runs the process in the background.

Run `warnet --help` to see a list of options.

Once `warnet` is running it can be interacted with using the cli tool `warcli`.
All `warcli` commands accept a `--network` option, which allows you to specify the warnet you want to control.
This is set by default to `--network="warnet"` to simplify default operation.

To start an example warnet, with your venv active and the server running, run the following command to use the default graph and network:

```bash
warcli network start
```

To generate a random graph, with your venv active and the server running, run the following command to create 20 nodes where each edge has a 30% chance of being connected:

```bash
warcli graph random 20 0.3
```

You can save this to a file using the `--file=` option.

To see other available commands use:

```bash
# All commands help
warcli --help

# Sub-command help
warcli help network
```

Each container is a node as described in the graph, along with various data exporters and a demo grafana dashboard.

The commands listed in `warcli help` can then be used to control and query the nodes.

###  Run scenarios on a network

Once or more nodes in a network can run a scenario, which constitutes a set of actions for one or more nodes.
Scenarios are written using the Bitcoin Core test framework for functional testing, with some modifications: most notably that `self.nodes[]` represents an array of dockerized `bitcoind` nodes.
The resultant scenario files can be run with a python interpreter and used to control many nodes in the network simultaneously.

See `/src/scenarios` for examples of how these can be written.

To see available scenarios (loaded from the default directory):

```bash
warcli scenarios list
```

Once a scenarios is selected it can be run with `warcli scenarios run <scenario_name> [--network=warnet]`, e.g.:

```bash
# Command one node to generate a wallet and fill 100 blocks with 100 txs each
warcli scenarios run tx_flood
```

This will run the run the scenario in the background until it exits or is killed by the user.

### Stopping

Currently the warnet can be stopped, but **not** stopped, persisted and continued.
Persisting the warnet during a stoppage is WIP.

To stop the warnet server:

```bash
# stop containers but retain images
warcli network down

# stop warnetd daemon
warcli stop
```

## Remote / Cloud Deployment

`// TODO`

