# Hello Plugin

## Hello World!
*Hello* is an example plugin to demonstrate the features of Warnet's plugin architecture. It uses each of the hooks available in the `warnet deploy` command (see the example below for details).

## Usage
In your python virtual environment with Warnet installed and setup, create a new Warnet user folder (follow the prompts):

`$ warnet new user_folder`

`$ cd user_folder`

Deploy the *hello* network.

`$ warnet deploy networks/hello`

While that is launching, take a look inside the `networks/hello/network.yaml` file. You can also see the copy below which includes commentary on the structure of plugins in the `network.yaml` file.

Also, take a look at the `plugins/hello/plugin.py` file to see how plugins work and to find out how to author your own plugin.

Once `deploy` completes, view the pods of the *hello* network by invoking `kubectl get all -A`.

To view the various "Hello World!" messages, run `kubectl logs pod/POD_NAME`

### A `network.yaml` example
When you initialize a new Warnet network, Warnet will create a new `network.yaml` file. You can modify these files to fit your needs.

For example, the `network.yaml` file below includes the *hello* plugin, lightning nodes, and the *simln* plugin.

<details>
<summary>network.yaml</summary>

````yaml
nodes:
  - name: tank-0000
    addnode:
      - tank-0001
    ln:
      lnd: true

  - name: tank-0001
    addnode:
      - tank-0002
    ln:
      lnd: true

  - name: tank-0002
    addnode:
      - tank-0000
    ln:
      lnd: true

  - name: tank-0003
    addnode:
      - tank-0000
    ln:
      lnd: true
    lnd:
      config: |
        bitcoin.timelockdelta=33
      channels:
        - id:
            block: 300
            index: 1
          target: tank-0004-ln
          capacity: 100000
          push_amt: 50000

  - name: tank-0004
    addnode:
      - tank-0000
    ln:
      lnd: true
    lnd:
      channels:
        - id:
            block: 300
            index: 2
          target: tank-0005-ln
          capacity: 50000
          push_amt: 25000

  - name: tank-0005
    addnode:
      - tank-0000
    ln:
      lnd: true

plugins:  # Each plugin section has a number of hooks available (preDeploy, postDeploy, etc)
  preDeploy:  # For example, the preDeploy hook means it's plugin will run before all other deploy code 
    hello:
      entrypoint: "../../plugins/hello"  # This entrypoint path is relative to the network.yaml file
      podName: "hello-pre-deploy"
      helloTo: "preDeploy!"
  postDeploy:
    hello:
      entrypoint: "../../plugins/hello"
      podName: "hello-post-deploy"
      helloTo: "postDeploy!"
    simln:  # You can have multiple plugins per hook
      entrypoint: "../../plugins/simln"
      activity: '[{"source": "tank-0003-ln", "destination": "tank-0005-ln", "interval_secs": 1, "amount_msat": 2000}]'      
  preNode:  # preNode plugins run before each node is deployed
    hello:
      entrypoint: "../../plugins/hello"
      helloTo: "preNode!"
  postNode:
    hello:
      entrypoint: "../../plugins/hello"
      helloTo: "postNode!"
  preNetwork:
    hello:
      entrypoint: "../../plugins/hello"
      helloTo: "preNetwork!"
      podName: "hello-pre-network"
  postNetwork:
    hello:
      entrypoint: "../../plugins/hello"
      helloTo: "postNetwork!"
      podName: "hello-post-network"
````

</details>

