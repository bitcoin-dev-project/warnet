# Plugin Options

Plugins extend Warnet by running custom code at specific points during `warnet deploy`. They are declared in the `plugins:` section of `network.yaml` and invoked automatically.

---

## Declaring plugins in `network.yaml`

```yaml
plugins:
  <hook>:
    <plugin-name>:
      entrypoint: "../plugins/<plugin-name>"   # required: path to the plugin directory
      <key>: <value>                           # any additional plugin-specific config
```

Warnet runs `<entrypoint>/plugin.py entrypoint '<plugin-config-json>' '<warnet-context-json>'` for each declared plugin.

---

## Hooks

Hooks control *when* a plugin runs relative to the deploy sequence. All six hooks run during `warnet deploy`:

| Hook | When it runs |
|------|-------------|
| `preDeploy` | Before anything else is deployed |
| `postDeploy` | After all nodes and the network are deployed |
| `preNode` | Before each individual node is deployed *(once per node)* |
| `postNode` | After each individual node is deployed *(once per node)* |
| `preNetwork` | After logging infrastructure, before nodes are launched |
| `postNetwork` | After all node deploy threads have completed |

### Per-node hooks and `node_name`

For `preNode` and `postNode`, Warnet passes the current node's name in the context under the key `node_name`. Plugins can read this to act on a specific node. The pod name Warnet produces for a per-node plugin follows the pattern:

```
<node-name>-<pre|post>-<podName>
```

For example, with `podName: hello-pod` on node `tank-0000`:
- `tank-0000-pre-hello-pod`
- `tank-0000-post-hello-pod`

---

## Writing a plugin

A plugin is a directory containing at minimum a `plugin.py` file. The file must accept the subcommand `entrypoint` with two positional JSON arguments:

```python
import json, sys

assert sys.argv[1] == "entrypoint"
plugin_config  = json.loads(sys.argv[2])   # keys declared in network.yaml
warnet_context = json.loads(sys.argv[3])   # hook_value, namespace, annex
```

`warnet_context` always contains:

| Key | Value |
|-----|-------|
| `hook_value` | The hook that fired (`"preDeploy"`, `"postNode"`, etc.) |
| `namespace` | The Kubernetes namespace being deployed into |
| `annex.node_name` | *(preNode/postNode only)* Name of the current node |

Plugins that deploy Kubernetes resources typically use Helm:

```python
from warnet.process import run_command
from pathlib import Path

assert sys.argv[1] == "entrypoint"
plugin_config = json.loads(sys.argv[2])

command = f"helm upgrade --install my-plugin {Path(__file__).parent / 'charts' / 'my-plugin'}"
for key, value in plugin_config.items():
    command += f" --set {key}={value}"
run_command(command)
```

Start from the `hello` plugin included in every initialised project:

```sh
warnet init
cat plugins/hello/plugin.py
```

---

## Built-in plugins

The following plugins ship with Warnet in `resources/plugins/`.

### SimLN

[SimLN](https://simln.dev/) generates realistic Lightning Network payment activity between nodes. It runs as a `postDeploy` pod and supports both LND and CLN.

#### Configuration in `network.yaml`

```yaml
plugins:
  postDeploy:
    simln:
      entrypoint: "../plugins/simln"
      activity: '[{"source": "tank-0003-ln", "destination": "tank-0005-ln", "interval_secs": 1, "amount_msat": 2000}]'
```

The `activity` value is a JSON array of payment flows. Each flow specifies:

| Field | Description |
|-------|-------------|
| `source` | Pod name of the sending LND/CLN node |
| `destination` | Pod name of the receiving node |
| `interval_secs` | Seconds between payment attempts |
| `amount_msat` | Payment amount in millisatoshis |

SimLN automatically discovers node credentials (macaroons, TLS certs) for every LND and CLN node in the network.

#### CLI subcommands

The SimLN plugin exposes additional commands for interacting with running instances:

```sh
# List pod names of all running SimLN instances
python3 resources/plugins/simln/plugin.py list-pod-names

# Download results from a SimLN pod to the current directory
python3 resources/plugins/simln/plugin.py download-results <pod-name>

# Get an example activity JSON for the first two LN nodes
python3 resources/plugins/simln/plugin.py get-example-activity

# Launch a new activity from the command line
python3 resources/plugins/simln/plugin.py launch-activity '<activity-json>'

# Run a shell command inside a SimLN pod
python3 resources/plugins/simln/plugin.py sh <pod-name> <command> [args...]
```

Results written by SimLN inside the pod at `/working/results/` can also be retrieved with `kubectl cp`.

#### Custom SimLN image

To use a custom SimLN build, update `resources/plugins/simln/charts/simln/values.yaml`:

```yaml
image:
  repository: "myusername/sim-ln"
  tag: "myversion"
```

---

### Tor

The Tor plugin deploys a Tor daemon (`torda`) as a Kubernetes service, enabling Bitcoin nodes to connect over Tor.

#### Configuration in `network.yaml`

```yaml
plugins:
  preDeploy:
    tor:
      entrypoint: "../plugins/tor"
```

The Tor chart does not accept additional configuration keys beyond `entrypoint`. See `resources/plugins/tor/charts/torda/values.yaml` for defaults.

---

## Example plugins (from reference repos)

The following plugin patterns appear in Warnet-based contest repos.

### Leaderboard (`battle-of-galen-erso`)

Deploys a scoreboard web service as a `postDeploy` plugin, then exposes it on the Caddy dashboard via the `services:` key:

```yaml
plugins:
  postDeploy:
    leaderboard:
      entrypoint: "../../plugins/leaderboard"
      admin_key: "secretkey123"
      next_public_asset_prefix: "/leaderboard"

services:
  - title: Leaderboard
    path: /leaderboard/
    host: leaderboard.default
    port: 3000
```

### LnVisualizer (`wrath-of-nalo`)

Deploys a Kubernetes Service that routes traffic to LnVisualizer sidecar containers running inside the miner node's LND pod. Activated as `preDeploy` so the Service exists before the dashboard is configured:

```yaml
plugins:
  preDeploy:
    lnvisualizer:
      entrypoint: "../../plugins/lnvisualizer"
      instance: miner    # node whose LND pod hosts the sidecars
      name: lnd-ln       # Kubernetes Service name suffix

services:
  - title: LN Visualizer Web UI
    path: /lnvisualizer/
    host: lnvisualizer.default
    port: 80
```

The sidecar containers themselves are added under `lnd.extraContainers` on the `miner` node — see [LN Options](ln-options.md#extracontainers).

---

## Full hook example

```yaml
nodes:
  # ... node list ...

plugins:
  preDeploy:
    setup:
      entrypoint: "../plugins/setup"
      config_value: "foo"

  postDeploy:
    simln:
      entrypoint: "../plugins/simln"
      activity: '[{"source": "tank-0003-ln", "destination": "tank-0005-ln", "interval_secs": 1, "amount_msat": 2000}]'

  preNode:
    hello:
      entrypoint: "../plugins/hello"
      podName: "hello-pre-node"
      helloTo: "preNode!"

  postNode:
    hello:
      entrypoint: "../plugins/hello"
      podName: "hello-post-node"
      helloTo: "postNode!"

  preNetwork:
    hello:
      entrypoint: "../plugins/hello"
      podName: "hello-pre-network"
      helloTo: "preNetwork!"

  postNetwork:
    hello:
      entrypoint: "../plugins/hello"
      podName: "hello-post-network"
      helloTo: "postNetwork!"
```
