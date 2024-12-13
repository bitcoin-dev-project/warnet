# Plugins

Plugins allow users to extend Warnet. Plugin authors can import commands from Warnet and plugin users can run plugin commands from the command line or on each invocation of `warnet deploy`.

## Activating plugins from 'network.yaml'

You can activate a plugin command by placing it in the `plugin` section at the bottom of each `network.yaml` file like so:

````yaml
nodes:
  <<snip>>

plugins:
  preDeploy:
    hello:
      entrypoint: "../plugins/hello"
      podName: "hello-pre-deploy"
      helloTo: "preDeploy!"
  postDeploy:
    simln:
      entrypoint: "../../../resources/plugins/simln"
      activity: '[{"source": "tank-0003-ln", "destination": "tank-0005-ln", "interval_secs": 1, "amount_msat": 2000}]'
    hello:
      entrypoint: "../plugins/hello"
      podName: "hello-post-deploy"
      helloTo: "postDeploy!"
  preNode:
    hello:
      entrypoint: "../plugins/hello"
      helloTo: "preNode!"
  postNode:
    hello:
      entrypoint: "../plugins/hello"
      helloTo: "postNode!"
  preNetwork:
    hello:
      entrypoint: "../plugins/hello"
      helloTo: "preNetwork!"
      podName: "hello-pre-network"
  postNetwork:
    hello:
      entrypoint: "../plugins/hello"
      helloTo: "postNetwork!"
      podName: "hello-post-network"
````

Warnet will execute these plugin commands after each invocation of `warnet deploy`.

## Example: SimLN

To get started with an example plugin, review the `README` of the `simln` plugin found in any initialized Warnet directory:

1. `warnet init`
2. `cd plugins/simln/`

