# Overview

Warnet is designed for Bitcoin developers, researchers, and enthusiasts who want to safely experiment with and test ideas related to Bitcoin networks. By leveraging Kubernetes, Warnet enables users to deploy and simulate large-scale Bitcoin networks in a controlled and reproducible environment.

## Table of Contents

1. [Overview](#overview)
   - [Key Features](#key-features)
   - [Target Audience](#target-audience)
   - [Benefits](#benefits)

2. [Philosophy](#philosophy)

3. [Kubernetes and Helm in Warnet](#kubernetes-and-helm-in-warnet)
   - [Kubernetes](#kubernetes)
   - [Helm](#helm)
   - [Why Helm is Preferred in Warnet](#why-helm-is-preferred-in-warnet)

4. [Project Structure](#project-structure)
   - [Overview of Resources](#overview-of-resources)
   - [Overview of src/warnet](#overview-of-srcwarnet)
   - [Overview of Test](#overview-of-test)

5. [Operating in the Network with "Scenarios"/Commanders](#operating-in-the-network-with-scenarioscommanders)

6. [The Resources Configuration Pipeline - An Example](#the-resources-configuration-pipeline---an-example)

## Key Features:
- Safe simulation of Bitcoin networks
- Kubernetes-based deployment for scalability and ease of management
- User interaction capabilities through custom scenarios
- Infrastructure as Code (IaC) approach for reproducibility

## Target Audience:
- Bitcoin core developers
- Bitcoin researchers
- Network security specialists
- Bitcoin protocol testers
- Bitcoin application developers
- Lightning developers
- Students of bitcoin
- And more!

## Benefits:
1. Scalability: Simulate networks of various sizes to understand behaviour at scale
2. Reproducibility: Easily recreate test environments using IaC principles
3. Flexibility: Customize network configurations and scenarios to test specific hypotheses
4. Risk-free experimentation: Test new ideas without affecting real Bitcoin networks
5. Educational: Learn about Bitcoin network behaviour in a controlled setting

## Philosophy

The implementation should follow a native Kubernetes (via Helm) approach wherever possible (see [Kubernetes and Helm in Warnet](#kubernetes-and-helm-in-warnet) for more information on these applications). This simplifies development in this project, and offloads responsibility over (often) non-trivial components to the Kubernetes development team. Ideologically this means that all Warnet components should be thought of as "Kubernetes resources which are to be controlled (installed/uninstalled) using Helm", wherever possible.

This philosophy applies to the implementation in this codebase: there are often multiple possible ways of implementing a new feature and developers should first seek out the way this is usually achieved on Kubernetes (natively) and encode this in a Helm chart, before falling back to a custom solution if this is not viable.

For example, a new logging component could be added in multiple possible ways to Warnet:

1. Run a process on the local host which connects in to the cluster via a forwarded port and performs customised logging.

2. Launch a standardised logging application (e.g. Grafana) via executing a `kubectl` command on a *.yaml* file.

  ```python
  subprocess.run("kubectl apply -f grafana.yaml --namespace=grafana")
  ```

3. Create a helm chart (or use an [already-available](https://github.com/grafana/helm-charts) one) for the Grafana component and install using helm.

  ```python
  subprocess.run("helm upgrade --install --namespace logging promtail grafana/promtail")
  ```

Out of these three options, the third should be preferred where possible, followed by the second, with the first only being used in extreme cases.

## Kubernetes and Helm in Warnet

<div style="display: flex; justify-content: space-around; align-items: center; margin: 20px 0;">
  <img src="/img/kubernetes.svg" alt="Kubernetes logo" style="width: 100px; height: 100px;" />
  <img src="/img/helm.svg" alt="Helm logo" style="width: 100px; height: 100px;" />
</div>

Warnet leverages [Kubernetes](https://kubernetes.io/) for deploying and managing simulated Bitcoin networks, with [Helm](https://helm.sh/) serving as the preferred method for managing Kubernetes resources. Understanding the relationship between these technologies is helpful for grasping Warnet's architecture and deployment strategy.

### Kubernetes
[Kubernetes](https://kubernetes.io/) is an open-source container orchestration platform that automates the deployment, scaling, and management of containerized applications. In Warnet, Kubernetes provides the underlying infrastructure for running simulated Bitcoin nodes and related services.

Key benefits of using Kubernetes in Warnet:
- Scalability: Easily scale the number of simulated nodes
- Resource management: Efficiently allocate computational resources
- Service discovery: Automatically manage network connections between nodes

### Helm
[Helm](https://helm.sh/) is a package manager for Kubernetes that simplifies the process of defining, installing, and upgrading complex Kubernetes applications. Warnet prefers Helm for managing Kubernetes resources due to its powerful templating and package management capabilities.

Advantages of using Helm in Warnet:
- Templating: Define reusable Kubernetes resource templates
- Packaging: Bundle related Kubernetes resources into a single unit (chart)
- Simplified deployment: Use a single command to deploy complex applications

### Why Helm is Preferred in Warnet
1. Reproducibility: Helm charts ensure consistent deployments across different environments.
2. Customization: Users can easily modify network configurations by adjusting Helm chart values.
3. Modularity: New components can be added to Warnet by creating or integrating existing Helm charts.
4. Simplified management: Helm's release management makes it easy to install, upgrade, rollback, or delete entire simulated networks.

By leveraging Kubernetes with Helm, Warnet achieves a flexible, scalable, and easily manageable architecture for simulating Bitcoin networks. This approach aligns with the project's philosophy of using native Kubernetes solutions and following best practices in cloud-native application deployment.

## Project structure
The Warnet code base has four main sections:

1. *resources* - these items are available during runtime and relate to configuration (crucially, Kubernetes configuration)
2. *src/warnet* - python source code lives here
3. *test* - CI testing files live here
4. *docs* - stores documentation available in the github repository

### Overview of resources
There are four main kinds of *resources*:

1. Kubernetes configuration files - they are the backbone of Stateless Configuration; they are *yaml* files.
  > [!NOTE]
  > Whilst native Kubernetes *yaml* configuration files can and do exist here, Helm charts are the preferred way to configure Kubernetes resources.
2. scenarios - these are python programs that users can load into the cluster to interact with the simulated Bitcoin network
3. images - the logic for creating bitcoin nodes and also containers for running scenarios are found here; this includes Dockerfiles
4. scripts and other configs - these are like "assets" or "one off" items which appear in Warnet.

### Overview of src/warnet
The python source code found in *src/warnet* serves to give users a way to create and interact with the simulated Bitcoin network as it exists in a Kubernetes cluster.

There are eight categories of python program files in Warnet:

1. Bitcoin images
  * *image.py* and *image_build.py* - the logic that helps the user create bitcoin node images
2. Bitcoin interaction
  * *bitcoin.py* - make it easy to interact with bitcoin nodes in the simulated network
3. Scenario interaction
  * *control.py* - launch scenarios in order to interact with the simulated Bitcoin network
4. Kubernetes
  * *k8s.py* - gather Kubernetes configuration data; retrieve Kubernetes resources
  * *status.py* - make it easy for the user to see the status of the simulated bitcoin network
5. Resource configuration pipeline
  * *admin.py* - copy configurations for *resources* such as namespaces and put them in the user's directory
  * *deploy.py* - take configurations for *resources* and put them into the Kubernetes cluster
  * *network.py* - copy *resources* to the users Warnet directory
  * *namespaces.py* - copy *resources* to the users Warnet directory; interact with namespaces in the cluster
6. User interaction
  * *main.py* - provide the interface for the `warnet` command line program
7. Host computer
  * *process.py* - provides a way to run commands on the user's host computer
8. Externalized configuration
  * *constants.py* - this holds values which occur repeatedly in the code base

### Overview of test
The *test_base.py* file forms the basis of the *test* section. Each test uses *TestBase* which controls the test running framework.

### Operating in the network with "scenarios"/Commanders
Warnet includes the capability to run "scenarios" on the network. These are python files which can be found in *resources/scenarios*, or copied by default into a new project directory.

These scenarios use a base class called `Commander` which ultimately inherits from the Bitcoin Test Framework. This means that scenarios can be written and controlled using the familiar Bitcoin Core functional test language. The `self.nodes[index]` property has been patched to automatically direct commands to a running bitcoin node of the same index in the network.

Once a scenario has been written, it can be loaded into the cluster and run using `warnet run <file>`.

### The resources configuration pipeline - an example
It is important to focus on the pipeline that takes *resources*, copies them into user directories, and translates them into Kubernetes objects. To make this possible and to achieve a more stateless configuration, Warnet uses Helm which provides templating for Kubernetes configuration files.

Looking more closely at the *resources/charts* section, for example, we can focus in on the *bitcoincore* directory. Inside, there is an example *namespaces.yaml* and *namespace-defaults.yaml* file. These configuration files are provided to the user in their project directory when the `warnet init` command is invoked.

This provides the user the opportunity to change those configuration files and modify both configuration defaults for all nodes, along with specific node settings. When `warnet deploy [project-dir]` command is run by the user, it will apply the configuration data to the Helm chart found in the *charts* directory of the *resources* section. The Helm chart acts as a template through which the user's configuration data is applied.

In this way, there is a pipeline which starts with the user's Stateful Data which is then piped through the Helm templating system, and then is applied to the Kubernetes cluster.

> [!TIP]
> Along with the python source code, all resources found in the *resources* directory are also included in the `warnet` python package.
> In this way default resources such as helm charts are available to the CLI application via the `importlib.resources` module.

> [!TIP]
> To learn more about the resources configuration pipeline used in Warnet see the [configuration](docs/config.md) overview.
