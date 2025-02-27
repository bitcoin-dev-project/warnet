# Circuit Breaker Plugin

## Overview
The Circuit Breaker plugin integrates the [circuitbreaker](https://github.com/lightningequipment/circuitbreaker) tool with Warnet to protect Lightning Network nodes from being flooded with HTLCs. Circuit Breaker functions like a firewall for Lightning, allowing node operators to set limits on in-flight HTLCs and implement rate limiting on a per-peer basis.

## What is Circuit Breaker?
Circuit Breaker is to Lightning what firewalls are to the internet. It provides protection against:
- HTLC flooding attacks
- Channel slot exhaustion (max 483 slots per channel)
- DoS/spam attacks using large numbers of fast-resolving HTLCs
- Channel balance probing attacks

Circuit Breaker offers insights into HTLC traffic and provides configurable operating modes to handle excess traffic.

## Usage
In your Python virtual environment with Warnet installed and set up, create a new Warnet user folder:

```
$ warnet new user_folder
$ cd user_folder
```

Deploy a network with Circuit Breaker enabled:

```
$ warnet deploy networks/circuitbreaker
```

## Configuration in `network.yaml`
You can incorporate the Circuit Breaker plugin into your `network.yaml` file as shown below:

```yaml
nodes:
  - name: tank-0000
    addnode:
      - tank-0001
    ln:
      lnd: true

  - name: tank-0001
    addnode:
      - tank-0002
    ln:
      lnd: true

  - name: tank-0002
    addnode:
      - tank-0000
    ln:
      lnd: true

  - name: tank-0003
    addnode:
      - tank-0000
    ln:
      lnd: true
    lnd:
      channels:
        - id:
            block: 300
            index: 1
          target: tank-0004-ln
          capacity: 100000
          push_amt: 50000

plugins:
  postDeploy:
    circuitbreaker:
      entrypoint: "../../plugins/circuitbreaker"
      nodes: ["tank-0000-ln", "tank-0003-ln"]  # Nodes to apply Circuit Breaker to
      mode: "fail"  # Operating mode: fail, queue, or queue_peer_initiated
      maxPendingHtlcs: 10  # Default maximum pending HTLCs per peer
      rateLimit: 1  # Minimum seconds between HTLCs (token bucket rate limit)
```

## Plugin Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `nodes` | List of LN node names to apply Circuit Breaker to | Required |
| `mode` | Operating mode (`fail`, `queue`, or `queue_peer_initiated`) | `fail` |
| `maxPendingHtlcs` | Default maximum number of pending HTLCs per peer | `30` |
| `rateLimit` | Minimum interval in seconds between HTLCs | `0` (disabled) |
| `port` | Port to expose the Circuit Breaker UI on | `9235` |
| `trusted_peers` | Map of node pubkeys to their individual HTLC limits | `{}` |

## Operating Modes

- **fail**: Fail HTLCs when limits are exceeded. Minimizes liquidity lock-up but affects routing reputation.
- **queue**: Queue HTLCs when limits are exceeded, forwarding them when space becomes available. Penalizes upstream nodes for bad traffic.
- **queue_peer_initiated**: Queue only HTLCs from channels that the remote node initiated. Uses fail mode for channels we initiated.

**WARNING**: Queue modes require LND 0.16+ with auto-fail support to prevent force-closes.

## Accessing the UI

After deploying, you can port-forward to access the Circuit Breaker UI:

```
$ kubectl port-forward pod/circuitbreaker-tank-0000 9235:9235
```

Then open http://127.0.0.1:9235 in a browser to view and configure Circuit Breaker settings.

## Advanced Configuration Example

```yaml
plugins:
  postDeploy:
    circuitbreaker:
      entrypoint: "../../plugins/circuitbreaker"
      nodes: ["tank-0000-ln", "tank-0003-ln"]
      mode: "fail"
      maxPendingHtlcs: 15
      rateLimit: 0.5
      trusted_peers: {
        "03abcdef...": 50,
        "02123456...": 100
      }
```

<!-- ## Combining with SimLN

The Circuit Breaker plugin can be used alongside the SimLN plugin to test how Circuit Breaker behaves under various payment patterns:

```yaml
plugins:
  postDeploy:
    circuitbreaker:
      entrypoint: "../../plugins/circuitbreaker"
      nodes: ["tank-0000-ln"]
      mode: "fail"
      maxPendingHtlcs: 10
    simln:
      entrypoint: "../../plugins/simln"
      activity: '[{"source": "tank-0003-ln", "destination": "tank-0005-ln", "interval_secs": 0.1, "amount_msat": 2000}]'
``` -->

## Limitations

- Circuit Breaker is alpha quality software. Use with caution, especially on mainnet.
- LND interfaces are not optimized for this purpose, which may lead to edge cases.
- Queue modes require LND 0.16+ to prevent channel force-closes.

## Development

To build your own version of the Circuit Breaker plugin:

1. Clone the Circuit Breaker repository: `git clone https://github.com/lightningequipment/circuitbreaker.git`
2. Follow the build instructions in the repository
3. Update the plugin's `values.yaml` to point to your custom image