# Plugins

Plugins allow users to extend Warnet. Plugin authors can import commands from Warnet and plugin users can run plugin commands from the command line or on each invocation of `warnet deploy`.

## Activating plugins from 'network.yaml'

You can activate a plugin command by placing it in the `plugin` section at the bottom of each `network.yaml` file like so:

````yaml
nodes:
  <<snip>>

plugins:
  preNode:  # Run commands before each node launches
    - "echo This is preNode"  # This command is a simple string
  postNode:  # Run commands after each node launches
    - exec: "echo This is also postNode, but we waited for 'warnet status'"  # This command is also a simple string ...
      waitFor: "warnet status"  # ... but it will execute after this command completes successfully
    - exec: "echo This is postNode"  # Simply using 'exec' also just works
  preDeploy:  # Run commands before Warnet runs the bulk of its `deploy` code
    - "echo This is preDeploy"
  postDeploy:  # Run these commands after Warnet has finished the bulk of its `deploy` code
    - "../../plugins/simln/plugin.py launch-activity '[{\"source\": \"tank-0003-ln\", \"destination\": \"tank-0005-ln\", \"interval_secs\": 1, \"amount_msat\": 2000}]'"
    - exec: "../../plugins/simln/plugin.py list-pod-names"
      waitFor: "../../plugins/simln/plugin.py get-example-activity"
````

Warnet will execute these plugin commands after each invocation of `warnet deploy`.

## Example: SimLN

To get started with an example plugin, review the `README` of the `simln` plugin found in any initialized Warnet directory:

1. `warnet init`
2. `cd plugins/simln/`

