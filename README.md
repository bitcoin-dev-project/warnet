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
* Small networks can be deployed locally with Docker Compose, larger networks can be deployed remotely with Kubernetes

## Documentation

- [Installation](docs/install.md)
- [Running Warnet](docs/running.md)
- [Network Topology](docs/graph.md)
- [CLI Commands](docs/warcli.md)
- [Scenarios](docs/scenarios.md)
- [Data Collection](docs/data.md)
- [Monitoring](docs/monitoring.md)
- [Lightning Network](docs/lightning.md)

![warnet-art](docs/machines.webp)
