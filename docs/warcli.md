# `warcli`

The command-line interface tool for Warnet.

Once `warnet` is running it can be interacted with using the cli tool `warcli`.

Most `warcli` commands accept a `--network` option, which allows you to specify
the network you want to control. This is set by default to `--network="warnet"`
to simplify default operation.

Execute `warcli --help` or `warcli help` to see a list of command categories.

`warcli` commands are organized in a hierarchy of categories and subcommands.

## API Commands

### `warcli debug-log`
Fetch the Bitcoin Core debug log from \<node> in [network]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| node    | Int    | True       |           |
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### `warcli grep-logs`
Grep combined logs via fluentd using regex [pattern]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| pattern | String | True       |           |
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### `warcli help`
Display help information for the given command.
    If no command is given, display help for the main CLI.

options:
| name     | type   | required   | default   |
|----------|--------|------------|-----------|
| commands | String | False      |           |
| help     | Bool   | False      | False     |

### `warcli lncli`
Call lightning cli \<command> on \<node> in \<--network>

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| node    | Int    | True       |           |
| command | String | True       |           |
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### `warcli messages`
Fetch messages sent between \<node_a> and \<node_b> in \<network>

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| node_a  | Int    | True       |           |
| node_b  | Int    | True       |           |
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### `warcli rpc`
Call bitcoin-cli \<method> \<params> on \<node> in \<--network>

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| node    | Int    | True       |           |
| method  | String | False      |           |
| params  | String | False      | ()        |
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### `warcli stop`
Stop warnet.

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| help   | Bool   | False      | False     |

## Debug

### `warcli debug generate-compose`
Generate the docker-compose file for a given \<graph_file> and \<--network> (default: "warnet") name and return it.

options:
| name       | type   | required   | default   |
|------------|--------|------------|-----------|
| graph_file | String | True       |           |
| network    | String | False      | warnet    |
| help       | Bool   | False      | False     |

## Graph

### `warcli graph create`
Create a graph file of type random AS graph with [params]

options:
| name         | type   | required   |   default |
|--------------|--------|------------|-----------|
| params       | String | False      |           |
| outfile      | Func   | False      |           |
| version      | String | False      |        26 |
| bitcoin_conf | Func   | False      |           |
| random       | Bool   | False      |         0 |
| help         | Bool   | False      |         0 |

## Image

### `warcli image build`
Build bitcoind and bitcoin-cli from \<repo>/\<branch> and deploy to \<registry>
    This requires docker and buildkit to be enabled.

options:
| name       | type   | required   | default   |
|------------|--------|------------|-----------|
| registry   | String | True       |           |
| repo       | String | True       |           |
| branch     | String | True       |           |
| build_args | String | False      |           |
| arches     | String | False      |           |
| help       | Bool   | False      | False     |

## Network

### `warcli network down`
Bring down a running warnet named \<--network> (default: "warnet").

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### `warcli network export`
Export all data for sim-ln to subdirectory

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### `warcli network info`
Get info about a warnet named \<--network> (default: "warnet").

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### `warcli network start`
Start a warnet with topology loaded from a \<graph_file> into \<--network> (default: "warnet")

options:
| name       | type   | required   | default                    |
|------------|--------|------------|----------------------------|
| graph_file | Path   | False      | src/graphs/default.graphml |
| force      | Bool   | False      | False                      |
| network    | String | False      | warnet                     |
| help       | Bool   | False      | False                      |

### `warcli network status`
Get status of a warnet named \<--network> (default: "warnet").

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

### `warcli network up`
Bring up a previously-stopped warnet named \<--network> (default: "warnet").

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String | False      | warnet    |
| help    | Bool   | False      | False     |

## Scenarios

### `warcli scenarios active`
List running scenarios "name": "pid" pairs

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| help   | Bool   | False      | False     |

### `warcli scenarios available`
List available scenarios in the Warnet Test Framework

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| help   | Bool   | False      | False     |

### `warcli scenarios run`
Run \<scenario> from the Warnet Test Framework on \<--network> with optional arguments

options:
| name            | type        | required   | default   |
|-----------------|-------------|------------|-----------|
| scenario        | String      | True       |           |
| additional_args | Unprocessed | False      |           |
| network         | String      | False      | warnet    |
| help            | Bool        | False      | False     |

### `warcli scenarios stop`
Stop scenario with PID \<pid> from running

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| pid    | Int    | True       |           |
| help   | Bool   | False      | False     |
