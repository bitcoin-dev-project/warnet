# Warnet

Monitor and analyze the emergent behaviors of Bitcoin networks.

## Major Features

* Launch a bitcoin network with a specified number of nodes connected to each other according to a network topology from a specification file.
* Nodes are assigned random "reachable" IP addresses in the 100.0.0.0/8 subnet which ensures randomized `addrman` bucketing [by Bitcoin Core.](https://github.com/bitcoin/bitcoin/blob/8372ab0ea3c88308aabef476e3b9d023ba3fd4b7/src/addrman.h#L66)
* A local Tor authority provides an internal onion network and each node is reachable by a Tor V3 address.
* Scenarios can be run across the network which can be programmed using the Bitcoin Core functional [test_framework language](https://github.com/bitcoin/bitcoin/tree/master/test/functional).
* Nodes can have traffic shaping parameters assigned to them via the graph using [tc-netem](https://manpages.ubuntu.com/manpages/trusty/man8/tc-netem.8.html) tool.
* Log files from nodes can be accessed directly.
* Some Bitcoin Core activity is polled and reported via a Graphana dashboard.
* P2P messages between any two nodes can be retrieved in chronological order.

## Documentation

- [Installation](docs/install.md)
- [Running Warnet](docs/running.md)
- [CLI Commands](docs/warcli.md)
- [Scenarios](docs/scenarios.md)
- [Network Topology](docs/graph.md)

![warnet-art](docs/machines.webp)