# Warnet Scenarios

Scenarios are written using the Bitcoin Core test framework for functional testing,
with some modifications: most notably that `self.nodes[]` represents an array of
containerized `bitcoind` nodes ("tanks").

Scenario files are run with a python interpreter inside their own pod called a "commander"
in kubernetes and many can be run simultaneously. The Commander is provided with
a JSON file describing the Bitcoin nodes it has access to via RPC.

See [`resources/scenarios/`](../resources/scenarios/) for examples of how these can be written.
When creating a new network default scenarios will be copied into your project directory for convenience.

A scenario can be run with `warnet run <path_to_scenario_file> [optional_params]`.

The [`miner_std`](../resources/scenarios/miner_std.py) scenario is a good one to start with as it automates block generation:

```bash
₿ warnet run build55/scenarios/miner_std.py  --allnodes --interval=10
configmap/warnetjson configured
configmap/scenariopy configured
pod/commander-minerstd-1724708498 created
Successfully started scenario: miner_std
Commander pod name: commander-minerstd-1724708498

₿ warnet status
╭──────────────────── Warnet Overview ────────────────────╮
│                                                         │
│                      Warnet Status                      │
│ ┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓ │
│ ┃ Component ┃ Name                          ┃ Status  ┃ │
│ ┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩ │
│ │ Tank      │ tank-0001                     │ running │ │
│ │ Tank      │ tank-0002                     │ running │ │
│ │ Tank      │ tank-0003                     │ running │ │
│ │ Tank      │ tank-0004                     │ running │ │
│ │ Tank      │ tank-0005                     │ running │ │
│ │ Tank      │ tank-0006                     │ running │ │
│ │           │                               │         │ │
│ │ Scenario  │ commander-minerstd-1724708498 │ pending │ │
│ └───────────┴───────────────────────────────┴─────────┘ │
│                                                         │
╰─────────────────────────────────────────────────────────╯

Total Tanks: 6 | Active Scenarios: 1

₿ warnet stop commander-minerstd-1724708498
pod "commander-minerstd-1724708498" deleted
Successfully stopped scenario: commander-minerstd-1724708498

₿ warnet status
╭─────────────── Warnet Overview ───────────────╮
│                                               │
│                 Warnet Status                 │
│ ┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓ │
│ ┃ Component ┃ Name                ┃ Status  ┃ │
│ ┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩ │
│ │ Tank      │ tank-0001           │ running │ │
│ │ Tank      │ tank-0002           │ running │ │
│ │ Tank      │ tank-0003           │ running │ │
│ │ Tank      │ tank-0004           │ running │ │
│ │ Tank      │ tank-0005           │ running │ │
│ │ Tank      │ tank-0006           │ running │ │
│ │ Scenario  │ No active scenarios │         │ │
│ └───────────┴─────────────────────┴─────────┘ │
│                                               │
╰───────────────────────────────────────────────╯

Total Tanks: 6 | Active Scenarios: 0
```

## Running a custom scenario

You can write your own scenario file and run it in the same way.
