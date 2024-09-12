# Configuration value propagation

This flowchart illustrates the process of how values for the Bitcoin Core module are handled and deployed using Helm in a Kubernetes environment.

The process is similar for other modules (e.g. fork-observer), but may differ slightly in filenames.

- The process starts with the `values.yaml` file, which contains default values for the Helm chart.
- There's a decision point to check if user-provided values are available.
  These are found in the following files:
    - For config applied to all nodes: `<network_name>/node-defaults.yaml`
    - For network and per-node config: `<network_name>/network.yaml`

> [!TIP]
> `values.yaml` can be overridden by `node-defaults.yaml` which can be overridden in turn by `network.yaml`.

- If user-provided values exist, they override the defaults from `values.yaml`. If not, the default values are used.
- The resulting set of values (either default or overridden) becomes the final set of values used for deployment.
- These final values are then passed to the Helm templates.
- The templates (`configmap.yaml`, `service.yaml`, `servicemonitor.yaml`, and `pod.yaml`) use these values to generate the Kubernetes resource definitions.
- Helm renders these templates, substituting the values into the appropriate places.
- The rendering process produces the final Kubernetes manifest files.
- Helm then applies these rendered manifests to the Kubernetes cluster.
- Kubernetes processes these manifests and creates or updates the corresponding resources in the cluster.
- The process ends with the resources being deployed or updated in the Kubernetes cluster.

In the flowchart below, boxes with a red outline represent default or user-supplied configuration files, blue signifies files operated on by Helm or Helm operations, and green by Kubernetes.

```mermaid
graph TD
    A[Start]:::start --> B[values.yaml]:::config
    subgraph User Configuration [User configuration]
        C[node-defaults.yaml]:::config
        D[network.yaml]:::config
    end
    B --> C
    C -- Bottom overrides top ---D
    D --> F[Final values]:::config
    F --> I[Templates]:::helm
    I --> J[configmap.yaml]:::helm
    I --> K[service.yaml]:::helm
    I --> L[servicemonitor.yaml]:::helm
    I --> M[pod.yaml]:::helm
    J --> N[Helm renders templates]:::helm
    K & L & M --> N
    N --> O[Rendered kubernetes
    manifests]:::helm
    O --> P[Helm applies manifests to 
    kubernetes]:::helm
    P --> Q["Kubernetes 
    creates/updates resources"]:::k8s
    Q --> R["Resources 
    deployed/updated in cluster"]:::finish

    classDef start fill:#f9f,stroke:#333,stroke-width:4px
    classDef finish fill:#bbf,stroke:#f66,stroke-width:2px,color:#fff,stroke-dasharray: 5 5
    classDef config stroke:#f00
    classDef k8s stroke:#0f0
    classDef helm stroke:#00f
```

Users should only concern themselves therefore with setting configuration in the `<network_name>/[network|node-defaults].yaml` files.
