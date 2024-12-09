# Plugins

Plugins allow users to extend Warnet. Plugin authors can import commands from Warnet and plugin users can run plugin commands from the command line or on each invocation of `warnet deploy`.

## Activating plugins from 'network.yaml'

You can activate a plugin command by placing it in the `plugin` section at the bottom of each `network.yaml` file like so:

````yaml
nodes:
  <<snip>>

plugins:
  - path/to/plugin/file/relative/to/the/network/dot/yaml/file/plugin.py
````

Warnet will execute these plugin commands after each invocation of `warnet deploy`.

## Example: SimLN

To get started with an example plugin, review the `README` of the `simln` plugin found in any initialized Warnet directory:

1. `warnet init`
2. `cd plugins/simln/`

