# SimLN Plugin

## SimLN
SimLN helps you generate lightning payment activity.

* Website: https://simln.dev/
* Github: https://github.com/bitcoin-dev-project/sim-ln

## Usage
SimLN uses "activity" definitions to create payment activity between lightning nodes. These definitions are in JSON format.

SimLN also requires access details for each node; however, the SimLN plugin will automatically generate these access details for each LND node. The access details look like this:

```` JSON
{
  "id": <node_id>,
  "address": https://<ip:port or domain:port>,
  "macaroon": <path_to_selected_macaroon>,
  "cert": <path_to_tls_cert>
}
````
SimLN plugin also supports Core Lightning (CLN).  CLN nodes connection details are transfered from the CLN node to SimLN node during launch-activity processing.
```` JSON
{
  "id": <node_id>,
  "address": https://<domain:port>,
  "ca_cert": /working/<node_id>-ca.pem,
  "client_cert": /working/<node_id>-client.pem,
  "client_key": /working/<node_id>-client-key.pem
}
````

Since SimLN already has access to those LND and CLN connection details, it means you can focus on the "activity" definitions.

### Launch activity definitions from the command line
The SimLN plugin takes "activity" definitions like so:

`./simln/plugin.py launch-activity '[{\"source\": \"tank-0003-ln\", \"destination\": \"tank-0005-ln\", \"interval_secs\": 1, \"amount_msat\": 2000}]'"''`

### Launch activity definitions from within `network.yaml`
When you initialize a new Warnet network, Warnet will create a new `network.yaml` file.  If your `network.yaml` file includes lightning nodes, then you can use SimLN to produce activity between those nodes like this:

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
      cln: true
    cln:
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

plugins:
  postDeploy:
    simln:
      entrypoint: "../../plugins/simln"  # This is the path to the simln plugin folder (relative to the network.yaml file).
      activity: '[{"source": "tank-0003-ln", "destination": "tank-0005-ln", "interval_secs": 1, "amount_msat": 2000}]'
````

</details>


## Generating your own SimLn image
The SimLN plugin fetches a SimLN docker image from dockerhub. You can generate your own docker image if you choose:

1. Clone SimLN: `git clone git@github.com:bitcoin-dev-project/sim-ln.git`
2. Follow the instructions to build a docker image as detailed in the SimLN repository.
3. Tag the resulting docker image: `docker tag IMAGEID YOURUSERNAME/sim-ln:VERSION`
4. Push the tagged image to your dockerhub account.
5. Modify the `values.yaml` file in the plugin's chart to reflect your username and version number:
```YAML
  repository: "YOURUSERNAME/sim-ln"
  tag: "VERSION"
```
