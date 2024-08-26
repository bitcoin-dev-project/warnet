# `warnet`

The command-line interface tool for Warnet.

Once `warnet` is running it can be interacted with using the cli tool `warnet`.

Execute `warnet --help` to see a list of command categories.

Help text is provided, with optional parameters in [square brackets] and required
parameters in <angle brackets>.

`warnet` commands are organized in a hierarchy of categories and subcommands.

## API Commands

### `warnet auth`
Authenticate with a warnet cluster using a kube config file

options:
| name        | type   | required   | default   |
|-------------|--------|------------|-----------|
| kube_config | String | yes        |           |

### `warnet create`
Create a new warnet project in the specified directory

options:
| name      | type   | required   | default   |
|-----------|--------|------------|-----------|
| directory | Path   | yes        |           |

### `warnet deploy`
Deploy a warnet with topology loaded from \<directory>

options:
| name      | type   | required   | default   |
|-----------|--------|------------|-----------|
| directory | Path   | yes        |           |

### `warnet down`
Bring down a running warnet


### `warnet init`
Initialize a warnet project in the current directory


### `warnet quickstart`
Setup warnet


### `warnet run`
Run a scenario from a file

options:
| name            | type   | required   | default   |
|-----------------|--------|------------|-----------|
| scenario_file   | Path   | yes        |           |
| additional_args | String |            |           |

### `warnet status`
Display the unified status of the Warnet network and active scenarios


### `warnet stop`
Stop a running scenario or all scenarios

options:
| name          | type   | required   | default   |
|---------------|--------|------------|-----------|
| scenario_name | String |            |           |

## Admin

### `warnet admin create`
Create a new warnet project in the specified directory

options:
| name      | type   | required   | default   |
|-----------|--------|------------|-----------|
| directory | Func   | yes        |           |

### `warnet admin init`
Initialize a warnet project in the current directory


### `warnet admin namespaces`
Namespaces commands


## Bitcoin

### `warnet bitcoin debug-log`
Fetch the Bitcoin Core debug log from \<tank pod name>

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| tank   | String | yes        |           |

### `warnet bitcoin grep-logs`
Grep combined bitcoind logs using regex \<pattern>

options:
| name                | type   | required   | default   |
|---------------------|--------|------------|-----------|
| pattern             | String | yes        |           |
| show_k8s_timestamps | Bool   |            | False     |
| no_sort             | Bool   |            | False     |

### `warnet bitcoin messages`
Fetch messages sent between \<tank_a pod name> and \<tank_b pod name> in [chain]

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| tank_a | String | yes        |           |
| tank_b | String | yes        |           |
| chain  | String |            | "regtest" |

### `warnet bitcoin rpc`
Call bitcoin-cli \<method> [params] on \<tank pod name>

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| tank   | String | yes        |           |
| method | String | yes        |           |
| params | String |            |           |

## Graph

### `warnet graph import-json`
Create a cycle graph with nodes imported from lnd `describegraph` JSON file,
    and additionally include 7 extra random outbounds per node. Include lightning
    channels and their policies as well.
    Returns XML file as string with or without --outfile option.


## Image

### `warnet image build`
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


