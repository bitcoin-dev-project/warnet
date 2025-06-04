# Circuit Breaker for Warnet

## Overview

Circuit Breaker is a Lightning Network firewall that protects LND nodes from being flooded with HTLCs. When integrated with Warnet, Circuit Breaker runs as a sidecar container alongside your LND nodes.

Circuit Breaker is to Lightning what firewalls are to the internet - it allows nodes to protect themselves by setting maximum limits on in-flight HTLCs on a per-peer basis and applying rate limits to forwarded HTLCs.

* **Repository**: https://github.com/lightningequipment/circuitbreaker
* **Full Documentation**: See the main repository for detailed information about Circuit Breaker's features, operating modes, and configuration options

## Usage in Warnet

### Basic Configuration

To enable Circuit Breaker for an LND node in your `network.yaml` file, add the `circuitbreaker` section under the `lnd` configuration. When enabled, Circuit Breaker will automatically start as a sidecar container and connect to your LND node:

```yaml
nodes:
  - name: tank-0003
    addnode:
      - tank-0000
    ln:
      lnd: true
    lnd:
      config: |
        bitcoin.timelockdelta=33
      channels:
        - id:
            block: 300
            index: 1
          target: tank-0004-ln
          capacity: 100000
          push_amt: 50000
      circuitbreaker:
        enabled: true    # This enables Circuit Breaker for this node
        httpPort: 9235   # Can override default port per-node (optional)
```

### Configuration Options

- `enabled`: Set to `true` to enable Circuit Breaker for the node
- `httpPort`: Override the default HTTP port (9235) for the web UI (optional)

### Complete Example

Here's a complete `network.yaml` example with Circuit Breaker enabled on one node:

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
      config: |
        bitcoin.timelockdelta=33
      channels:
        - id:
            block: 300
            index: 1
          target: tank-0004-ln
          capacity: 100000
          push_amt: 50000
      circuitbreaker:
        enabled: true
        httpPort: 9235

  - name: tank-0004
    addnode:
      - tank-0000
    ln:
      lnd: true
    lnd:
      channels:
        - id:
            block: 300
            index: 2
          target: tank-0005-ln
          capacity: 50000
          push_amt: 25000

  - name: tank-0005
    addnode:
      - tank-0000
    ln:
      lnd: true
```

## Accessing Circuit Breaker

Circuit Breaker provides both a web-based interface and REST API endpoints for configuration and monitoring.

### Web UI Access

To access the web interface:

1. **Port Forward to the Circuit Breaker service**:
   ```bash
   kubectl port-forward pod/<node-name>-ln <local-port>:<httpPort>
   ```
   
   For example, if your node is named `tank-0003` and using the default port:
   ```bash
   kubectl port-forward pod/tank-0003-ln 9235:9235
   ```

2. **Open your browser** and navigate to:
   ```
   http://localhost:9235
   ```

3. **Configure your firewall rules** through the web interface:
   - Set per-peer HTLC limits
   - Configure rate limiting parameters
   - Choose operating modes
   - Monitor HTLC statistics

### API Access

You can also interact with Circuit Breaker programmatically using kubectl commands to access the REST API:

**Get node information:**
```bash
kubectl exec <node-name>-ln -c circuitbreaker -- wget -qO - 127.0.0.1:<httpPort>/api/info
```

**Get current limits:**
```bash
kubectl exec <node-name>-ln -c circuitbreaker -- wget -qO - 127.0.0.1:<httpPort>/api/limits
```

For example, with node `tank-0003-ln`:
```bash
kubectl exec tank-0003-ln -c circuitbreaker -- wget -qO - 127.0.0.1:9235/api/info
kubectl exec tank-0003-ln -c circuitbreaker -- wget -qO - 127.0.0.1:9235/api/limits
```

## Architecture

Circuit Breaker runs as a sidecar container alongside your LND node in Warnet:
- **LND Container**: Runs your Lightning node
- **Circuit Breaker Container**: Connects to LND via RPC and provides firewall functionality
- **Shared Volume**: Allows Circuit Breaker to access LND's TLS certificates and macaroons
- **Web Interface**: Accessible via port forwarding for configuration

## Requirements

- **LND Version**: 0.15.4-beta or above
- **Warnet**: Compatible with standard Warnet LND deployments

## Support

For issues and questions:
- Circuit Breaker Repository: https://github.com/lightningequipment/circuitbreaker
- Warnet Documentation: Refer to the Warnet installation guides [install.md](install.md)
- LND Documentation: https://docs.lightning.engineering/

---

*Circuit Breaker integration for Warnet enables sophisticated HTLC management and protection for Lightning Network nodes in test environments.*