# Running Warnet

Warnet runs a server which can be used to manage multiple networks. On Kubernetes
this runs as a `statefulSet` in the cluster.

See more details in [warcli](/docs/warcli.md), examples:

To start the server run:

```bash
warcli cluster deploy
```

Start a network from a graph file:

```bash
warcli network start resources/graphs/default.graphml
```

Make sure all tanks are running with:

```bash
warcli network status
```

Check if the edges of the graph (bitcoin p2p connections) are complete:

```bash
warcli network connected
```

_Optional_ Check out the logs with:

```bash
warcli network logs -f
```

If that looks all good, give [scenarios](/docs/scenarios.md) a try.
