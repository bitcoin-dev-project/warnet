# Warnet Network Topology

Warnet creates a Bitcoin network using a network topology from a [graphml](https://graphml.graphdrawing.org/specification.html) file.

Before any scenarios or RPC commands can be executed, a Warnet network must be started from a graph.
See [warcli.md](warcli.md) for more details on these commands.

To start a network called `"warnet"` from the [default graph file](../src/graphs/default.graphml):
```
warcli network start
```

To start a network with custom configurations:
```
warcli network start <path/to/file.graphml> --network="network_name"
```

## Creating graphs automatically

Graphs can be created via the graph menu:

```bash
# show graph commands
warcli graph --help

# Create a cycle graph of 12 nodes using default Bitcoin Core version (v26.0)
warcli graph create 12 --outfile=./12_x_v26.0.graphml

# Start network with default name "warnet"
warcli network start ./12_x_v26.0.graphml
```

## Warnet graph nodes and edges

Nodes in a Warnet graph MUST have either a `"version"` key or an `"image"` key.
These dictate what version of Bitcoin Core to deploy in a fiven tank.

Edges without additional properties are interpreted as Bitcoin p2p connections.
If an edge has additional key-value properties, it will be interpreted as a
lightning network channel (see [lightning.md](lightning.md)).

## GraphML file specification

### GraphML file format and headers
```xml
<?xml version="1.0" encoding="UTF-8"?><graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="services"        attr.name="services"         attr.type="string"   for="graph" />
  <key id="version"         attr.name="version"          attr.type="string"   for="node" />
  <key id="image"           attr.name="image"            attr.type="string"   for="node" />
  <key id="bitcoin_config"  attr.name="bitcoin_config"   attr.type="string"   for="node" />
  <key id="tc_netem"        attr.name="tc_netem"         attr.type="string"   for="node" />
  <key id="exporter"        attr.name="exporter"         attr.type="boolean"  for="node" />
  <key id="collect_logs"    attr.name="collect_logs"     attr.type="boolean"  for="node" />
  <key id="build_args"      attr.name="build_args"       attr.type="string"   for="node" />
  <key id="ln"              attr.name="ln"               attr.type="string"   for="node" />
  <key id="ln_image"        attr.name="ln_image"         attr.type="string"   for="node" />
  <key id="ln_cb_image"     attr.name="ln_cb_image"      attr.type="string"   for="node" />
  <key id="ln_config"       attr.name="ln_config"        attr.type="string"   for="node" />
  <key id="channel_open"    attr.name="channel_open"     attr.type="string"   for="edge" />
  <key id="source_policy"   attr.name="source_policy"    attr.type="string"   for="edge" />
  <key id="target_policy"   attr.name="target_policy"    attr.type="string"   for="edge" />
  <graph edgedefault="directed">
    <!-- <nodes> -->
    <!-- <edges> -->
  </graph>
</graphml>
```

| key            | for   | type    | default   | explanation                                                                                                                                                         |
|----------------|-------|---------|-----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| services       | graph | string  |           | A space-separated list of extra service containers to deploy in the network. See [docs/services.md](services.md) for complete list of available services            |
| version        | node  | string  |           | Bitcoin Core version with an available Warnet tank image on Dockerhub. May also be a GitHub repository with format user/repository:branch to build from source code |
| image          | node  | string  |           | Bitcoin Core Warnet tank image on Dockerhub with the format repository/image:tag                                                                                    |
| bitcoin_config | node  | string  |           | A string of Bitcoin Core options in command-line format, e.g. '-debug=net -blocksonly'                                                                              |
| tc_netem       | node  | string  |           | A tc-netem command as a string beginning with 'tc qdisc add dev eth0 root netem'                                                                                    |
| exporter       | node  | boolean | False     | Whether to attach a Prometheus data exporter to the tank                                                                                                            |
| collect_logs   | node  | boolean | False     | Whether to collect Bitcoin Core debug logs with Promtail                                                                                                            |
| build_args     | node  | string  |           | A string of configure options used when building Bitcoin Core from source code, e.g. '--without-gui --disable-tests'                                                |
| ln             | node  | string  |           | Attach a lightning network node of this implementation (currently only supports 'lnd')                                                                              |
| ln_image       | node  | string  |           | Specify a lightning network node image from Dockerhub with the format repository/image:tag                                                                          |
| ln_cb_image    | node  | string  |           | Specify a lnd Circuit Breaker image from Dockerhub with the format repository/image:tag                                                                             |
| ln_config      | node  | string  |           | A string of arguments for the lightning network node in command-line format, e.g. '--protocol.wumbo-channels --bitcoin.timelockdelta=80'                            |
| channel_open   | edge  | string  |           | Indicate that this edge is a lightning channel with these arguments passed to lnd openchannel                                                                       |
| source_policy  | edge  | string  |           | Update the channel originator policy by passing these arguments passed to lnd updatechanpolicy                                                                      |
| target_policy  | edge  | string  |           | Update the channel partner policy by passing these arguments passed to lnd updatechanpolicy                                                                         |
