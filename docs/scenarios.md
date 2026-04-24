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

Pass `-- --help` after the scenario file path to see that scenario's own argument help without launching a pod:

```bash
warnet run resources/scenarios/miner_std.py -- --help
```

The [`miner_std`](../resources/scenarios/miner_std.py) scenario is a good one to start with as it automates block generation:

```bash
₿ warnet run resources/scenarios/miner_std.py --allnodes --interval=10
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

### Sharing helper modules with `--source_dir`

If your scenario imports other local modules (e.g. utilities in the same directory), pass the directory that should be bundled into the commander pod:

```bash
warnet run my_scenarios/my_scenario.py --source_dir=my_scenarios/
```

### Running with admin privileges

By default a commander pod can only interact with nodes in the namespace it was launched in. Pass `--admin` to give the scenario access to nodes across all namespaces (requires admin kubeconfig context):

```bash
warnet run resources/scenarios/reconnaissance.py --admin
```

### Scenario status

Scenarios appear in `warnet status` with one of the following statuses:

| Status    | Meaning                                   |
|-----------|-------------------------------------------|
| pending   | Pod is starting up                        |
| running   | Scenario is executing                     |
| succeeded | Scenario completed without errors         |
| failed    | Scenario exited with a non-zero exit code |

`warnet status` reports **Active Scenarios** as the count of scenarios that are currently `running` or `pending`.
