# Creating a Network

A Warnet network is defined by two YAML files that live together in a directory under `networks/`:

- **`network.yaml`** — the node list, topology, and top-level services
- **`node-defaults.yaml`** — default values applied to every node

Once these files exist you deploy the network with:

```sh
warnet deploy networks/<name>
```

There are three ways to produce them. All three result in the same YAML files — the choice is about how much control and scale you need.

For the full list of options available in those files, see:
- [Tank Options](tank-options.md) — all Bitcoin Core node keys
- [LN Options](ln-options.md) — LND and CLN configuration
- [Plugin Options](plugins.md) — hooks, built-in plugins, writing your own

---

## Method 1: `warnet create` (interactive wizard)

The easiest starting point. Run it from inside an initialised Warnet project:

```sh
warnet init          # creates the project directory structure
warnet create        # launches the interactive wizard
```

The wizard walks you through:

1. **Network name** — becomes the directory `networks/<name>/`
2. **Node groups** — add one or more groups, each specifying:
   - Bitcoin Core version (choose from the supported list or provide a custom `repo/image:tag`)
   - Number of nodes in the group
   - Number of connections per node
3. **Fork Observer** — whether to enable it and how often it polls (seconds)
4. **Grafana logging** — whether to enable log and metrics collection

The wizard generates a round-robin + random connection topology and writes `network.yaml` and `node-defaults.yaml` into `networks/<name>/`. It then prints the `warnet deploy` command to run.

**Best for:** small to medium Bitcoin-only networks with standard node versions.

**Limitations:**
- Bitcoin Core only — no Lightning, no custom images beyond a single tag per group
- No per-node overrides (resources, custom probes, sidecar containers, etc.)
- Topology is limited to the built-in round-robin + random model

---

## Method 2: Hand-written YAML

For full control over every node, write `network.yaml` and `node-defaults.yaml` directly. This is practical for networks up to ~20 nodes. Beyond that, maintaining `addnode` lists and generating unique secrets by hand becomes error-prone.

### Minimal example

```yaml
# networks/my_net/network.yaml
nodes:
  - name: tank-0000
    image:
      tag: "27.0"
    addnode:
      - tank-0001

  - name: tank-0001
    image:
      tag: "25.1"
    addnode:
      - tank-0000

fork_observer:
  enabled: true
  configQueryInterval: 20

caddy:
  enabled: true
```

```yaml
# networks/my_net/node-defaults.yaml
chain: regtest
```

### Topology considerations

Every node listed in `addnode` will establish an outbound connection to that peer on startup. A common pattern is a **ring** (each node connects to the next) plus a few random cross-links:

```yaml
nodes:
  - name: tank-0000
    addnode: [tank-0001, tank-0003]   # ring + random
  - name: tank-0001
    addnode: [tank-0002, tank-0000]
  - name: tank-0002
    addnode: [tank-0003, tank-0001]
  - name: tank-0003
    addnode: [tank-0000, tank-0002]
```

For all available per-node keys (`global:`, `resources:`, `startupProbe:`, `lnd:`, etc.) see [Tank Options](tank-options.md) and [LN Options](ln-options.md).

**Best for:** small bespoke networks, learning the schema, one-off experiments.

**Not recommended** for networks larger than ~20 nodes — use a script instead.

---

## Method 3: Script-generated YAML

For large or complex networks (many node types, signet key generation, per-node macaroons, varied topologies) the most maintainable approach is to write a Python script that constructs the network data as Python objects and serialises them to YAML.

Both reference contest repos use this pattern in `scripts/fleet.py`. The approach is:

1. Define node types as Python classes with a `to_obj()` method that returns the YAML dict
2. Orchestrate node creation, connections, and signet key generation in a `Game` (or similar) class
3. Call `yaml.dump()` to write the output files

### Pattern from `battle-of-galen-erso/scripts/fleet.py`

This script generates multiple network sizes (signet_large with 100+ nodes across 13 teams, plus smaller regtest variants) from the same class hierarchy:

```python
class Node:
    def __init__(self, game, name):
        self.name = name
        self.rpcpassword = secrets.token_hex(16)   # unique per node
        self.addnode = []

    def to_obj(self):
        return {
            "name": self.name,
            "image": self.bitcoin_image,
            "global": {
                "rpcpassword": self.rpcpassword,
                "chain": self.game.chain,
            },
            "addnode": self.addnode,
            "config": f"maxconnections=1000\nuacomment={self.name}\n",
        }

class VulnNode(Node):
    """A target node: adds metrics export and resource limits."""
    def to_obj(self):
        obj = super().to_obj()
        obj.update({
            "collectLogs": True,
            "metricsExport": True,
            "metrics": 'blocks=getblockcount() mempool_size=getmempoolinfo()["size"]',
            "resources": {
                "limits":   {"cpu": "4000m", "memory": "1000Mi"},
                "requests": {"cpu": "100m",  "memory": "200Mi"},
            },
        })
        return obj

class Miner(Node):
    """Miner node: startup probe initialises the wallet."""
    def to_obj(self):
        obj = super().to_obj()
        obj["startupProbe"] = {
            "exec": {"command": ["/bin/sh", "-c",
                f"bitcoin-cli createwallet miner && "
                f"bitcoin-cli importdescriptors {self.game.desc_string}"]},
            "failureThreshold": 10,
            "periodSeconds": 30,
            "timeoutSeconds": 60,
        }
        return obj
```

Connections are added programmatically to ensure a ring plus random cross-links:

```python
def add_connections(self):
    for i, node in enumerate(self.nodes):
        node.addnode.append(self.nodes[(i + 1) % len(self.nodes)].name)  # ring
        for _ in range(4):
            node.addnode.append(random.choice(self.nodes).name)           # random
```

Signet requires a signing key. The script generates one with the Bitcoin Core test framework and embeds the `signetchallenge` directly into every node's config:

```python
def generate_signet(self):
    secret = secrets.token_bytes(32)
    privkey = ECKey()
    privkey.set(secret, True)
    pubkey = privkey.get_pubkey().get_bytes()
    self.signetchallenge = key_to_p2wpkh_script(pubkey).hex()
    # also builds self.desc_string for the miner wallet
```

Finally, `write()` serialises everything to the correct directory structure:

```python
def write(self):
    network = {
        "nodes": [n.to_obj() for n in self.nodes],
        "caddy": {"enabled": True},
        "fork_observer": {"enabled": True, "configQueryInterval": 20},
        "services": [{"title": "Leaderboard", "path": "/leaderboard/", ...}],
        "plugins": {...},
    }
    # writes battlefields/<name>/network.yaml + node-defaults.yaml
    self.write_network_yaml_dir("battlefields", network)
    # writes armadas/<name>/network.yaml (attacker nodes)
    self.write_armada(3)
    # writes armies/<name>/namespaces.yaml + namespace-defaults.yaml
    self.write_armies(len(TEAMS))
```

Generating all network sizes is then just a few lines:

```python
g = Game("signet_large", "signet")
g.add_nodes(len(TEAMS), len(VERSIONS))
g.add_miner()
g.add_connections()
g.write()
```

### Pattern from `wrath-of-nalo/scripts/fleet.py`

The Lightning Network variant extends this pattern with additional complexity:

- **Per-node macaroon generation** via `lncli bakemacaroon` — each LND node gets a deterministic `adminMacaroon` and `macaroonRootKey`, enabling pre-wired metric exporters and scenario scripts to authenticate without a wallet unlock step
- **Channel topology** — a channel registry tracks which pairs have open channels and assigns pre-mined transaction slots (`block`/`index` IDs) to avoid collisions
- **Specialised node subclasses** — `SpenderNode`, `RoutingNode`, `RecipientNode`, and `GossipVulnNode` each override `to_obj()` to add the metrics, `extraContainers`, or `restartPolicy` relevant to their role
- **Circuit Breaker variants** — a parallel set of payment-route nodes (`cb-spender`, `cb-router`, `cb-recipient`) are created with `circuitbreaker: enabled: true` to test HTLC mitigation

```python
class SpenderNode(MetricsNode):
    def to_obj(self):
        obj = super().to_obj()
        obj["lnd"]["extraContainers"][0]["env"][0]["value"] += "failed_payments=FAILED_PAYMENTS "
        return obj

def add_payment_routes(self, n):
    for i in range(n):
        spender  = SpenderNode(self, f"{TEAMS[i]}-spender")
        router   = RoutingNode(self, f"{TEAMS[i]}-router")
        recipient = RecipientNode(self, f"{TEAMS[i]}-recipient")
        self.nodes += [spender, router, recipient]
        self.add_channel(spender, router,   int(2e8))
        self.add_channel(router,  recipient, int(2e8))
```

### When to write a fleet script

Use a script when any of the following are true:

- The network has more than ~20 nodes
- Nodes need unique per-node secrets (rpcpassword, LND macaroons, signet keys)
- Multiple network sizes or variants share the same node definitions
- The topology (connections, channels) follows rules that are easier to express in code than YAML
- The network will need to be regenerated with different parameters in the future

**Best for:** large test networks, wargame infrastructure, reproducible multi-variant deployments.
