# Warnet Scenarios

Scenarios are written using the Bitcoin Core test framework for functional testing,
with some modifications: most notably that `self.nodes[]` represents an array of
dockerized `bitcoind` nodes. Scenario files can be run with a python interpreter
or from `warcli` commands and used to control many nodes in the network simultaneously.

See [`src/scenarios`](../src/scenarios) for examples of how these can be written.

To see available scenarios (loaded from the default directory):

```bash
warcli scenarios list
```

Once a scenarios is selected it can be run with `warcli scenarios run [--network=warnet] <scenario_name> [scenario_params]`, e.g.:

```bash
# Have all nodes generate a block 5 seconds apart in a round-robin
warcli scenarios run miner_std --allnodes --interval=5
```

This will run the run the scenario in the background until it exits or is stopped by the user.

Active scenarios can be listed and terminated by PID:

```bash
$ warcli scenarios list
miner_std           Generate blocks over time. Options: [--allnodes | --interval=<number>]
sens_relay          Send a transaction using sensitive relay
tx_flood            Generate 100 blocks with 100 TXs each

$ warcli scenarios run tx_flood
Running scenario tx_flood with PID 14683 in the background...

$ warcli scenarios active
        PID     Command                                                          Network   Active
        14683   tx_flood                                                         warnet    True

$ warcli scenarios stop 14683
Stopped scenario with PID 14683.
```

## Add scenarios

To add your own scenario make a copy of one of the existing python tests in src/scenarios/ and write the desired scenario.
Save this file back into the same src/scenarios/ directory and it will be listed and available for running using the aforementioned commands.

# Next: [Network Topology](graph.md)
