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
Check Warnet requirements are installed


## Bitcoin

### `warcli bitcoin debug-log`
Fetch the Bitcoin Core debug log from \<node>

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| node   | Int    | yes        |           |

### `warcli bitcoin grep-logs`
Grep combined bitcoind logs using regex \<pattern>

options:
| name                | type   | required   | default   |
|---------------------|--------|------------|-----------|
| pattern             | String | yes        |           |
| show_k8s_timestamps | Bool   |            | False     |
| no_sort             | Bool   |            | False     |

### `warcli bitcoin messages`
Fetch messages sent between \<node_a> and \<node_b> in [network]

options:
| name    | type   | required   | default   |
|---------|--------|------------|-----------|
| node_a  | Int    | yes        |           |
| node_b  | Int    | yes        |           |
| network | String |            | "regtest" |

### `warcli bitcoin rpc`
Call bitcoin-cli \<method> [params] on \<node>

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| node   | Int    | yes        |           |
| method | String | yes        |           |
| params | String |            |           |

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
Build bitcoind and bitcoin-cli from \<repo> at \<commit_sha> as \<registry>:\<tag>.
    Optionally deploy to remote registry using --action=push, otherwise image is loaded to local registry.

options:
| name       | type   | required   | default   |
|------------|--------|------------|-----------|
| repo       | String | yes        |           |
| commit_sha | String | yes        |           |
| registry   | String | yes        |           |
| tag        | String | yes        |           |
| build_args | String |            |           |
| arches     | String |            |           |
| action     | String |            | "load"    |

## Network

### `warcli network connected`
Determine if all p2p conenctions defined in graph are established


### `warcli network down`
Bring down a running warnet


### `warcli network generate-yaml`
Generate a Kubernetes YAML file from a graph file for deploying warnet nodes.

options:
| name       | type   | required   | default                          |
|------------|--------|------------|----------------------------------|
| graph_file | Path   |            | resources/graphs/default.graphml |
| output     | String |            | "warnet-deployment.yaml"         |

### `warcli network logs`
Get Kubernetes logs from the RPC server

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| follow | Bool   |            | False     |

### `warcli network start`
Start a warnet with topology loaded from a \<graph_file>

options:
| name       | type   | required   | default                          |
|------------|--------|------------|----------------------------------|
| graph_file | Path   |            | resources/graphs/default.graphml |
| logging    | Bool   |            | False                            |

### `warcli network status`
Return pod status


## Network2

### `warcli network2 start2`
Start a warnet with topology loaded from \<network_name> into [network]

options:
| name         | type   | required   | default          |
|--------------|--------|------------|------------------|
| network_name | String |            | "6_node_bitcoin" |
| network      | String |            | "warnet"         |
| logging      | Bool   |            | False            |

## Scenarios

### `warcli scenarios active`
List running scenarios "name": "pid" pairs


### `warcli scenarios available`
List available scenarios in the Warnet Test Framework


### `warcli scenarios run`
Run \<scenario> from the Warnet Test Framework with optional arguments

options:
| name            | type   | required   | default   |
|-----------------|--------|------------|-----------|
| scenario        | String | yes        |           |
| additional_args | String |            |           |

### `warcli scenarios run-file`
Run \<scenario_path> from the Warnet Test Framework with optional arguments

options:
| name            | type   | required   | default   |
|-----------------|--------|------------|-----------|
| scenario_path   | String | yes        |           |
| additional_args | String |            |           |
| name            | String |            |           |


