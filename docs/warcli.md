# `warcli`

The command-line interface tool for Warnet.

Once `warnet` is running it can be interacted with using the cli tool `warcli`.

Most `warcli` commands accept a `--network` option, which allows you to specify
the network you want to control. This is set by default to `--network="warnet"`
to simplify default operation.

Execute `warcli --help` or `warcli help` to see a list of command categories.

`warcli` commands are organized in a hierarchy of categories and subcommands:

```
warcli
  + help       Display help information for a given command.
  |              ex: warcli help scenarios
  + rpc        Execute a bitcoin-cli command to a given node.
  |              ex: warcli rpc 0 -getinfo
  |                  warcli rpc 10 addnode --params=100.20.30.40 --params=add
  + debug_log  Retrieve the complete debug log from a given node.
  |              ex: warcli debug_log 5
  + messages   Display all p2p messages sent and received between two nodes.
  |              ex: warcli messages 2 3
  + stop       Shut down the Warnet server. Note this does NOT clean up Docker objects.
  |              ex: warcli stop
  + scenarios
  |   + list   List available scenarios in src/scenarios
  |   |          ex: warcli scenarios list
  |   + run    Start a scenario with options
  |   |          ex: warcli scenarios run miner_std --allnodes --interval=1
  |   + active List scenarios that are currently running along with their process ID
  |   |          ex: warcli scenarios list
  |   + stop   Terminate a running scenario by its PID number
  |              ex: warcli scenarios stop 11324
  + network
  |   + start  Build and run a new Warnet network from a graph file (default: src/templates/example.graphml)
  |   |          ex: warcli network start ~/docs/cool_network.graphml --network=sweet
  |   + up     Run "docker-compose up" on a given network
  |   |          ex: warcli network up --network=sweet
  |   + down   Run "docker-compose down" on a given network
  |              ex: warcli network down --network=sweet
  + debug
      + generate_compose
      |
      + update_dns_seed
```

# Next: [Scenarios](scenarios.md)
