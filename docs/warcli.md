# `warcli`

The command-line interface tool for Warnet.

Once `warnet` is running it can be interacted with using the cli tool `warcli`.

Most `warcli` commands accept a `--network` option, which allows you to specify
the network you want to control. This is set by default to `--network="warnet"`
to simplify default operation.

Execute `warcli --help` or `warcli help` to see a list of command categories.

Help text is provided, with optional parameters in [square brackets] and required
parameters in <angle brackets>.

`warcli` commands are organized in a hierarchy of categories and subcommands.

## API Commands

### `warcli help`
Display help information for the given [command] (and sub-command).
    If no command is given, display help for the main CLI.

options:
| name     | type   | required   | default   |
|----------|--------|------------|-----------|
| commands | String |            |           |

### `warcli setup`
Run the Warnet quick start setup script


## Bitcoin

### `warcli bitcoin debug-log`
Fetch the Bitcoin Core debug log from \<node> in [network]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| node    | Int    | yes        |           |
| network | String |            | "warnet"  |

### `warcli bitcoin grep-logs`
Grep combined logs via fluentd using regex \<pattern>

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| pattern | String | yes        |           |
| network | String |            | "warnet"  |

### `warcli bitcoin messages`
Fetch messages sent between \<node_a> and \<node_b> in [network]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| node_a  | Int    | yes        |           |
| node_b  | Int    | yes        |           |
| network | String |            | "warnet"  |

### `warcli bitcoin rpc`
Call bitcoin-cli \<method> [params] on \<node> in [network]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| node    | Int    | yes        |           |
| method  | String | yes        |           |
| params  | String |            |           |
| network | String |            | "warnet"  |

## Cluster

### `warcli cluster port-start`
Port forward (runs as a detached process)


### `warcli cluster port-stop`
Stop the port forwarding process


### `warcli cluster start`
Setup and start Warnet with minikube


### `warcli cluster stop`
Stop the warnet server and tear down the cluster


## Graph

### `warcli graph create`
Create a cycle graph with \<number> nodes, and include 7 extra random outbounds per node.
    Returns XML file as string with or without --outfile option

options:
| name         | type   | required   | default   |
|--------------|--------|------------|-----------|
| number       | Int    | yes        |           |
| outfile      | Path   |            |           |
| version      | String |            | "27.0"    |
| bitcoin_conf | Path   |            |           |
| random       | Bool   |            | False     |

### `warcli graph import-json`
Create a cycle graph with nodes imported from lnd `describegraph` JSON file,
    and additionally include 7 extra random outbounds per node. Include lightning
    channels and their policies as well.
    Returns XML file as string with or without --outfile option.

options:
| name     | type   | required   | default   |
|----------|--------|------------|-----------|
| infile   | Path   | yes        |           |
| outfile  | Path   |            |           |
| cb       | String |            |           |
| ln_image | String |            |           |

### `warcli graph validate`
Validate a \<graph file> against the schema.

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| graph  | Path   | yes        |           |

## Image

### `warcli image build`
Build bitcoind and bitcoin-cli from \<repo>/\<branch> as \<registry>:\<tag>.
    Optionally deploy to remote registry using --action=push, otherwise image is loaded to local registry.

options:
| name       | type   | required   | default   |
|------------|--------|------------|-----------|
| repo       | String | yes        |           |
| branch     | String | yes        |           |
| registry   | String | yes        |           |
| tag        | String | yes        |           |
| build_args | String |            |           |
| arches     | String |            |           |
| action     | String |            |           |

## Ln

### `warcli ln pubkey`
Get lightning node pub key on \<node> in [network]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| node    | Int    | yes        |           |
| network | String |            | "warnet"  |

### `warcli ln rpc`
Call lightning cli rpc \<command> on \<node> in [network]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| node    | Int    | yes        |           |
| command | String | yes        |           |
| network | String |            | "warnet"  |

## Network

### `warcli network connected`
Indicate whether the all of the edges in the gaph file are connected in [network]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String |            | "warnet"  |

### `warcli network down`
Bring down a running warnet named [network]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String |            | "warnet"  |

### `warcli network export`
Export all [network] data for a "simln" service running in a container
    on the network. Optionally add JSON string [activity] to simln config.
    Optionally provide a list of tank indexes to [exclude].
    Returns True on success.

options:
| name     | type   | required   | default   |
|----------|--------|------------|-----------|
| network  | String |            | "warnet"  |
| activity | String |            |           |
| exclude  | String |            | "[]"      |

### `warcli network info`
Get info about a warnet named [network]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String |            | "warnet"  |

### `warcli network start`
Start a warnet with topology loaded from a \<graph_file> into [network]

options:
| name       | type   | required   | default                           |
|------------|--------|------------|-----------------------------------|
| graph_file | Path   |            | src/warnet/graphs/default.graphml |
| force      | Bool   |            | False                             |
| network    | String |            | "warnet"                          |

### `warcli network status`
Get status of a warnet named [network]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String |            | "warnet"  |

### `warcli network up`
Bring up a previously-stopped warnet named [network]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| network | String |            | "warnet"  |

## Scenarios

### `warcli scenarios active`
List running scenarios "name": "pid" pairs


### `warcli scenarios available`
List available scenarios in the Warnet Test Framework


### `warcli scenarios run`
Run \<scenario> from the Warnet Test Framework on [network] with optional arguments

options:
| name            | type   | required   | default   |
|-----------------|--------|------------|-----------|
| scenario        | String | yes        |           |
| additional_args | String |            |           |
| network         | String |            | "warnet"  |

### `warcli scenarios run-file`
Run \<scenario_path> from the Warnet Test Framework on [network] with optional arguments

options:
| name            | type   | required   | default   |
|-----------------|--------|------------|-----------|
| scenario_path   | String | yes        |           |
| additional_args | String |            |           |
| name            | String |            |           |
| network         | String |            | "warnet"  |

### `warcli scenarios stop`
Stop scenario with PID \<pid> from running

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| pid    | Int    | yes        |           |


