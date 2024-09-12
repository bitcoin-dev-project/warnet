![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https://raw.githubusercontent.com/bitcoin-dev-project/warnet/main/pyproject.toml)
# Warnet

Monitor and analyze the emergent behaviors of Bitcoin networks.

## Major Features

* Launch a bitcoin network with a specified number of nodes connected to each other according to a network topology.
* Run scenarios of network behavior across the network which can be programmed using the Bitcoin Core functional [test_framework language](https://github.com/bitcoin/bitcoin/tree/master/test/functional).
* Collect and search data from nodes including log files and p2p messages.
* Monitor and visualize performance data from Bitcoin nodes.
* Connect to a large network running in a remote cluster, or a smaller network running locally.

## Documentation

- [Design](/DESIGN.md)
- [Installation](/docs/install.md)
- [CLI Commands](/docs/warnet.md)
- [Network configuration with yaml files](/docs/config.md)
- [Scenarios](/docs/scenarios.md)
- [Monitoring](/docs/logging_monitoring.md)
- [Snapshots](/docs/snapshots.md)
- [Connecting to local nodes outside the cluster](/docs/connecting-local-nodes.md)
- [Scaling](/docs/scaling.md)
- [Contributing](/docs/developer-notes.md)

![warnet-art](https://raw.githubusercontent.com/bitcoin-dev-project/warnet/main/docs/machines.webp)
