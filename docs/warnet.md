# `warnet`

The command-line interface tool for Warnet.

Once `warnet` is running it can be interacted with using the cli tool `warnet`.

Execute `warnet --help` to see a list of command categories.

Help text is provided, with optional parameters in [square brackets] and required
parameters in <angle brackets>.

`warnet` commands are organized in a hierarchy of categories and subcommands.

## API Commands

### `warnet auth`
Authenticate with a Warnet cluster using a kubernetes config file

options:
| name        | type   | required   | default   |
|-------------|--------|------------|-----------|
| revert      | Bool   |            | False     |
| auth_config | String |            |           |

### `warnet create`
Create a new warnet network


### `warnet dashboard`
Open the Warnet dashboard in default browser


### `warnet deploy`
Deploy a warnet with topology loaded from \<directory>

options:
| name         | type   | required   | default   |
|--------------|--------|------------|-----------|
| directory    | Path   | yes        |           |
| debug        | Bool   |            | False     |
| namespace    | String |            |           |
| to_all_users | Bool   |            | False     |

### `warnet down`
Bring down a running warnet quickly

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| force  | Bool   |            | False     |

### `warnet import-network`
Create a network from an imported lightning network graph JSON

options:
| name            | type   | required   | default   |
|-----------------|--------|------------|-----------|
| graph_file_path | Path   | yes        |           |
| output_path     | Path   | yes        |           |

### `warnet init`
Initialize a warnet project in the current directory


### `warnet logs`
Show the logs of a pod

options:
| name      | type   | required   | default   |
|-----------|--------|------------|-----------|
| pod_name  | String |            | ""        |
| follow    | Bool   |            | False     |
| namespace | String |            | "default" |

### `warnet new`
Create a new warnet project in the specified directory

options:
| name      | type   | required   | default   |
|-----------|--------|------------|-----------|
| directory | Path   | yes        |           |

### `warnet run`
Run a scenario from a file.
    Pass `-- --help` to get individual scenario help

options:
| name            | type   | required   | default   |
|-----------------|--------|------------|-----------|
| scenario_file   | Path   | yes        |           |
| debug           | Bool   |            | False     |
| source_dir      | Path   |            |           |
| additional_args | String |            |           |
| admin           | Bool   |            | False     |
| namespace       | String |            |           |

### `warnet setup`
Setup warnet


### `warnet snapshot`
Create a snapshot of a tank's Bitcoin data or snapshot all tanks

options:
| name         | type   | required   | default            |
|--------------|--------|------------|--------------------|
| tank_name    | String |            |                    |
| snapshot_all | Bool   |            | False              |
| output       | Path   |            | ./warnet-snapshots |
| filter       | String |            |                    |

### `warnet status`
Display the unified status of the Warnet network and active scenarios


### `warnet stop`
Stop a running scenario or all scenarios

options:
| name          | type   | required   | default   |
|---------------|--------|------------|-----------|
| scenario_name | String |            |           |

### `warnet version`
Display the installed version of warnet


## Admin

### `warnet admin create-kubeconfigs`
Create kubeconfig files for ServiceAccounts

options:
| name           | type   | required   | default       |
|----------------|--------|------------|---------------|
| kubeconfig_dir | String |            | "kubeconfigs" |
| token_duration | Int    |            | 172800        |

### `warnet admin init`
Initialize a warnet project in the current directory


### `warnet admin namespaces`
Namespaces commands


## Bitcoin

### `warnet bitcoin debug-log`
Fetch the Bitcoin Core debug log from \<tank pod name>

options:
| name      | type   | required   | default   |
|-----------|--------|------------|-----------|
| tank      | String | yes        |           |
| namespace | String |            |           |

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

    Optionally, include a namespace like so: tank-name.namespace

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| tank_a | String | yes        |           |
| tank_b | String | yes        |           |
| chain  | String |            | "regtest" |

### `warnet bitcoin rpc`
Call bitcoin-cli \<method> [params] on \<tank pod name>

options:
| name      | type   | required   | default   |
|-----------|--------|------------|-----------|
| tank      | String | yes        |           |
| method    | String | yes        |           |
| params    | String |            |           |
| namespace | String |            |           |

## Graph

## Image

### `warnet image build`
Build a Bitcoin Core Docker image with specified parameters.

    
    Usage Examples:
        # Build an image for Warnet repository
            warnet image build --repo bitcoin/bitcoin --commit-sha d6db87165c6dc2123a759c79ec236ea1ed90c0e3 --tags bitcoindevproject/bitcoin:v29.0-rc2 --arches amd64,arm64,armhf --action push
        # Build an image for local testing
            warnet image build --repo bitcoin/bitcoin --commit-sha d6db87165c6dc2123a759c79ec236ea1ed90c0e3 --tags bitcoindevproject/bitcoin:v29.0-rc2 --action load

options:
| name       | type   | required   | default   |
|------------|--------|------------|-----------|
| repo       | String | yes        |           |
| commit_sha | String | yes        |           |
| tags       | String | yes        |           |
| build_args | String |            |           |
| arches     | String |            |           |
| action     | String |            | "load"    |

## Ln

### `warnet ln host`
Get lightning node host from \<ln pod name>

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| pod    | String | yes        |           |

### `warnet ln pubkey`
Get lightning node pub key from \<ln pod name>

options:
| name   | type   | required   | default   |
|--------|--------|------------|-----------|
| pod    | String | yes        |           |

### `warnet ln rpc`
Call lightning cli rpc \<command> on \<ln pod name>

options:
| name      | type   | required   | default   |
|-----------|--------|------------|-----------|
| pod       | String | yes        |           |
| method    | String | yes        |           |
| params    | String |            |           |
| namespace | String |            |           |


