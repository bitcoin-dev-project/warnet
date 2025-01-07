# Plugins

Plugins extend Warnet. Plugin authors can import commands from Warnet and interact with the kubernetes cluster, and plugin users can run plugins from the command line or from the `network.yaml` file.

## Activating plugins from `network.yaml`

You can activate a plugin command by placing it in the `plugins` section at the bottom of each `network.yaml` file like so:

````yaml
nodes:
  <<snip>>

plugins:  # This marks the beginning of the plugin section
  preDeploy:  # This is a hook. This particular hook will call plugins before deploying anything else.
    hello:  # This is the name of the plugin.
      entrypoint: "../plugins/hello"  # Every plugin must specify a path to its entrypoint.
      podName: "hello-pre-deploy"  # Plugins can have their own particular configurations, such as how to name a pod.
      helloTo: "preDeploy!"  # This configuration tells the hello plugin who to say "hello" to.
````

## Many kinds of hooks
There are many hooks to the Warnet `deploy` command. The example below specifies them:

````yaml
nodes:
  <<snip>>

plugins:
  preDeploy:  # Plugins will run before any other `deploy` code.
    hello:
      entrypoint: "../plugins/hello"
      podName: "hello-pre-deploy"
      helloTo: "preDeploy!"
  postDeploy:  # Plugins will run after all the `deploy` code has run.
    simln:
      entrypoint: "../plugins/simln"
      activity: '[{"source": "tank-0003-ln", "destination": "tank-0005-ln", "interval_secs": 1, "amount_msat": 2000}]'
    hello:
      entrypoint: "../plugins/hello"
      podName: "hello-post-deploy"
      helloTo: "postDeploy!"
  preNode:  # Plugins will run before `deploy` launches a node (once per node).
    hello:
      entrypoint: "../plugins/hello"
      helloTo: "preNode!"
  postNode:  # Plugins will run after `deploy` launches a node (once per node).
    hello:
      entrypoint: "../plugins/hello"
      helloTo: "postNode!"
  preNetwork:  # Plugins will run before `deploy` launches the network (essentially between logging and when nodes are deployed)
    hello:
      entrypoint: "../plugins/hello"
      helloTo: "preNetwork!"
      podName: "hello-pre-network"
  postNetwork:  # Plugins will run after the network deploy threads have been joined.
    hello:
      entrypoint: "../plugins/hello"
      helloTo: "postNetwork!"
      podName: "hello-post-network"
````

Warnet will execute these plugin commands during each invocation of `warnet deploy`.



## A "hello" example

To get started with an example plugin, review the `README` of the `hello` plugin found in any initialized Warnet directory:

1. `warnet init`
2. `cd plugins/hello/`

