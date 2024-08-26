![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https://raw.githubusercontent.com/bitcoin-dev-project/warnet/main/pyproject.toml)
# Warnet

Monitor and analyze the emergent behaviors of Bitcoin networks.

## Major Features

* Launch a bitcoin network with a specified number of nodes connected to each other according to a network topology from a graphml file.
* Scenarios can be run across the network which can be programmed using the Bitcoin Core functional [test_framework language](https://github.com/bitcoin/bitcoin/tree/master/test/functional).
* Nodes can have traffic shaping parameters assigned to them via the graph using [tc-netem](https://manpages.ubuntu.com/manpages/trusty/man8/tc-netem.8.html) tool.
* Data from nodes can be collected and searched including log files and p2p messages.
* Performance data from containers can be monitored and visualized.
* Lightning Network nodes can be deployed and operated.
* Networks can be deployed using Kubernetes, e.g. via MiniKube (small network graphs) or a managed cluster for larger network graphs.

## Documentation

- [Installation](/docs/install.md)
- [Quick Start](/docs/quickstart.md)
- [CLI Commands](/docs/warnet.md)
- [Scenarios](/docs/scenarios.md)
- [Monitoring](/docs/logging_monitoring.md)
- [Lightning Network](/docs/lightning.md)
- [Scaling](/docs/scaling.md)
- [Connecting to local nodes](https://github.com/bitcoin-dev-project/warnet/blob/main/docs/)

![warnet-art](https://raw.githubusercontent.com/bitcoin-dev-project/warnet/main/docs/machines.webp)
