# Warnet Network Topology

Warnet creates a Bitcoin network using a network topology from a [graphml](https://graphml.graphdrawing.org/specification.html) file.
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
## Node attributes

* `id` should be a unique integer identifier
* `label` [optional] specifies the node's label
* `x` specifies the node's x position when rendered in a GUI
* `y` specifies the node's y position when rendered in a GUI
* `version` specifies the node's Bitcoin Core release version, or GitHub branch
* `bitcoin_config` is a comma-separated list of values the node should apply to it's bitcoin.conf, using bitcoin.conf syntax
* `tc_netem` is a `tc-netem` command as a string beginning with "tc qdisc add dev eth0 root netem"

`version` should be either a version number from the pre-compiled binary list on https://bitcoincore.org/bin/ **or** a branch to be compiled from GitHub using `<user>/<repo>#<branch>` syntax.

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

`x`, `y`, `version`, `bitcoin_config` and `tc_netem` datafields are optional for all nodes.

## Edge attributes

* `edgelabel` specifies an edge's label

Edges can be added between the nodes as follows:

```graphml
<edge id="0" source="0" target="1">
</edge>
```

## Example

[example.graphml](../src/templates/example.graphml)

