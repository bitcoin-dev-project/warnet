# Lightning Network

## Adding LN nodes to graph

LN nodes can be added to any Bitcoin Core node by adding a data element with key
`"ln"` to the node in the graph file. The value is the LN implementation desired.

**Currently only `lnd` is supported**

Example:

```
    <node id="0">
        <data key="ln">lnd</data>
    </node>
```

## Adding LN channels to graph

LN channels are represented in the graphml file as edges with extra data elements
that correspond to arguments to the lnd `openchannel` and `updatechanpolicy` RPC
commands. The keys are:

- `"channel_open"` (arguments added to `openchannel`)
- `"target_policy"` or `"source_policy"` (arguments added to `updatechanpolicy`)

The key `"channel_open"` is required to open a LN channel in warnet, and to
identify an edge in the graphml file as a LN channel.

Example:

```
<edge id="5" source="0" target="1">
    <data key="channel_open">--local_amt=100000</data>
    <data key="source_policy">--base_fee_msat=100  --fee_rate_ppm=5  --time_lock_delta=18</data>
    <data key="target_policy">--base_fee_msat=2200 --fee_rate_ppm=13 --time_lock_delta=20</data>
</edge>
```

A complete example graph with LN nodes and channels is included in the test
data directory: [ln.graphml](../test/data/ln.graphml)

## Running the Lightning network

When warnet is started with `warcli network start` the bitcoin containers will
be started first followed by the lightning node containers. It may require a few
automatic restarts before the lightning nodes start up and connect to their
corresponding bitcoin nodes. Use `warcli network status` to monitor container status
and wait for all containers to be `running`.

To create the lightning channels specified in the graph file, run the included
scenario:

`warcli scenarios run ln_init`

This [scenario](../src/scenarios/ln_init.py) will generate blocks, fund the wallets
in the bitcoin nodes, and open the channels from the graph. Each of these steps
requires some waiting as transactions are confirmed in the warnet blockchain
and lightning nodes gossip their channel announcements to each other.
Use `warcli scenarios active` to monitor the status of the scenario. When it is
complete the subprocess will exit and it will indicate `Active: False`. At that
point, the lightning network is ready for activity.

## sim-ln compatibility

Warnet can export data required to run [sim-ln](https://github.com/bitcoin-dev-project/sim-ln)
with a warnet network.

With a network running, execute: `warcli network export` with optional argument
`--network=<network name>` (default is "warnet"). This will copy all lightning
node credentials like SSL certificates and macaroons into a local directory as
well as generate a JSON file required by sim-ln.

Example (see sim-ln docs for exact API):

```
$ warcli network export
/Users/bitcoin-dev-project/.warnet/warnet/warnet/simln

$ ls /Users/bitcoin-dev-project/.warnet/warnet/warnet/simln
sim.json                         warnet_ln_000000_tls.cert        warnet_ln_000001_tls.cert        warnet_ln_000002_tls.cert
warnet_ln_000000_admin.macaroon  warnet_ln_000001_admin.macaroon  warnet_ln_000002_admin.macaroon

$ sim-cli --data-dir /Users/bitcoin-dev-project/.warnet/warnet/warnet/simln
2023-11-18T16:58:28.731Z INFO  [sim_cli] Connected to warnet_ln_000000 - Node ID: 031b1404744431b01ee4fa2bfc3c5caa1f1044ff5a9cb553d2c8ec6eb0f9d8040c.
2023-11-18T16:58:28.747Z INFO  [sim_cli] Connected to warnet_ln_000001 - Node ID: 02318b75bd91bf6265b30fe97f8ebbb0eda85194cf9d4467d43374de0248c7bf05.
2023-11-18T16:58:28.760Z INFO  [sim_cli] Connected to warnet_ln_000002 - Node ID: 0393aa24d777e2391b5238c485ecce08b35bd9aa4ddf4f2226016107c6829804d5.
2023-11-18T16:58:28.760Z INFO  [sim_lib] Running the simulation forever.
2023-11-18T16:58:28.815Z INFO  [sim_lib] Simulation is running on regtest.
2023-11-18T16:58:28.815Z INFO  [sim_lib] Simulating 0 activity on 3 nodes.
2023-11-18T16:58:28.815Z INFO  [sim_lib] Summary of results will be reported every 60s.
2023-11-18T16:58:28.826Z INFO  [sim_lib] Generating random activity with multiplier: 2, average payment amount: 3800000.
2023-11-18T16:58:28.826Z INFO  [sim_lib] Created network generator: network graph view with: 3 channels.
2023-11-18T16:58:28.826Z INFO  [sim_lib] Started random activity producer for warnet_ln_000000(031b14...d8040c): activity generator for capacity: 50000000 with multiplier 2: 26.31578947368421 payments per month (0.03654970760233918 per hour).
2023-11-18T16:58:28.826Z INFO  [sim_lib] Started random activity producer for warnet_ln_000001(02318b...c7bf05): activity generator for capacity: 100000000 with multiplier 2: 52.63157894736842 payments per month (0.07309941520467836 per hour).
2023-11-18T16:58:28.826Z INFO  [sim_lib] Started random activity producer for warnet_ln_000002(0393aa...9804d5): activity generator for capacity: 50000000 with multiplier 2: 26.31578947368421 payments per month (0.03654970760233918 per hour).
```
