# `warcli`

The command-line interface tool for Warnet.

Once `warnet` is running it can be interacted with using the cli tool `warcli`.

Most `warcli` commands accept a `--network` option, which allows you to specify
the network you want to control. This is set by default to `--network="warnet"`
to simplify default operation.

Execute `warcli --help` or `warcli help` to see a list of command categories.

`warcli` commands are organized in a hierarchy of categories and subcommands.

## API Commands

### debug generate-compose
Generate the docker-compose file for a given <graph_file> and <--network> (default: "warnet") name and return it.

options:
| name       | type   | required   | default   |
|------------|--------|------------|-----------|
| graph_file | String | True       |           |
| network    | String | False      | warnet    |
| help       | Bool   | False      | False     |

### debug-log
Fetch the Bitcoin Core debug log from <node> in [network]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| node    | Int    | True       |           |
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### graph create
Create a graph file of type random AS graph with [params]

options:
| name         | type   | required   |   default |
|--------------|--------|------------|-----------|
| params       | String | False      |           |
| outfile      | Func   | False      |           |
| version      | String | False      |      25.1 |
| bitcoin_conf | Func   | False      |           |
| random       | Bool   | False      |       0   |
| help         | Bool   | False      |       0   |

### grep-logs
Grep combined logs via fluentd using regex [pattern]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| pattern | String | True       |           |
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### help
Display help information for the given command.
    If no command is given, display help for the main CLI.

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| command | String | False      |           |
| help    | Bool   | False      | False     |

### messages
Fetch messages sent between <node_a> and <node_b> in <network>

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| node_a  | Int    | True       |           |
| node_b  | Int    | True       |           |
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### network down
Run 'docker compose down on a warnet named <--network> (default: "warnet").

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### network export
Export all data for sim-ln to subdirectory

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### network info
Get info about a warnet named <--network> (default: "warnet").

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### network start
Start a warnet with topology loaded from a <graph_file> into <--network> (default: "warnet")

options:
| name       | type   | required   | default                                                             |
|------------|--------|------------|---------------------------------------------------------------------|
| graph_file | Path   | False      | /path/to/repo/warnet/src/graphs/default.graphml |
| force      | Bool   | False      | False                                                               |
| network    | String | False      | warnet                                                              |
| help       | Bool   | False      | False                                                               |

### network status
Get status of a warnet named <--network> (default: "warnet").

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### network up
Run 'docker compose up' on a warnet named <--network> (default: "warnet").

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### rpc
Call bitcoin-cli <method> <params> on <node> in <--network>

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| node    | Int    | True       |           |
| method  | String | False      |           |
| params  | String | False      | ()        |
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### scenarios active
List running scenarios "name": "pid" pairs

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| help   | Bool   | False      | False     |

### scenarios list
List available scenarios in the Warnet Test Framework

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| help   | Bool   | False      | False     |

### scenarios run
Run <scenario> from the Warnet Test Framework on <--network> with optional arguments

options:
| name            | type        | required   | default   |
|-----------------|-------------|------------|-----------|
| scenario        | String      | True       |           |
| additional_args | Unprocessed | False      |           |
| network         | String      | False      | warnet    |
| help            | Bool        | False      | False     |

### scenarios stop
Stop scenario with PID <pid> from running

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| pid    | Int    | True       |           |
| help   | Bool   | False      | False     |

### stop
Stop warnet.

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| help   | Bool   | False      | False     |


# Next: [Scenarios](scenarios.md)
