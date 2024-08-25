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

### `warcli auth`
Authenticate with a warnet cluster using a kube config file

options:
| name        | type   | required   | default   |
|-------------|--------|------------|-----------|
| kube_config | String | yes        |           |

### `warcli create`
Create a new warnet project in the specified directory

options:
| name      | type   | required   | default   |
|-----------|--------|------------|-----------|
| directory | Path   | yes        |           |

### `warcli deploy`
Deploy a warnet with topology loaded from \<directory>

options:
| name      | type   | required   | default   |
|-----------|--------|------------|-----------|
| directory | Path   | yes        |           |

### `warcli down`
Bring down a running warnet


### `warcli init`
Initialize a warnet project in the current directory


### `warcli quickstart`
Setup warnet


### `warcli run`
Run a scenario from a file

options:
| name            | type   | required   | default   |
|-----------------|--------|------------|-----------|
| scenario_file   | Path   | yes        |           |
| additional_args | String |            |           |

### `warcli status`
Display the unified status of the Warnet network and active scenarios


### `warcli stop`
Stop a running scenario or all scenarios

options:
| name          | type   | required   | default   |
|---------------|--------|------------|-----------|
| scenario_name | String |            |           |

## Admin

### `warcli admin create`
Create a new warnet project in the specified directory

options:
| name      | type   | required   | default   |
|-----------|--------|------------|-----------|
| directory | Func   | yes        |           |

### `warcli admin init`
Initialize a warnet project in the current directory


### `warcli admin namespaces`
Namespaces commands


## Bitcoin

### `warcli bitcoin debug-log`
Fetch the Bitcoin Core debug log from \<tank pod name>

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| tank   | String | yes        |           |

### `warcli bitcoin grep-logs`
Grep combined bitcoind logs using regex \<pattern>

options:
| name                | type   | required   | default   |
|---------------------|--------|------------|-----------|
| pattern             | String | yes        |           |
| show_k8s_timestamps | Bool   |            | False     |
| no_sort             | Bool   |            | False     |

### `warcli bitcoin messages`
Fetch messages sent between \<tank_a pod name> and \<tank_b pod name> in [chain]

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| tank_a | String | yes        |           |
| tank_b | String | yes        |           |
| chain  | String |            | "regtest" |

### `warcli bitcoin rpc`
Call bitcoin-cli \<method> [params] on \<tank pod name>

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| tank   | String | yes        |           |
| method | String | yes        |           |
| params | String |            |           |

## Graph

### `warcli graph import-json`
Create a cycle graph with nodes imported from lnd `describegraph` JSON file,
    and additionally include 7 extra random outbounds per node. Include lightning
    channels and their policies as well.
    Returns XML file as string with or without --outfile option.


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


