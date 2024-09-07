# Overview
Warnet is a software suite that allows its users to safely put ideas about Bitcoin to the test. It does this by using Kubernetes to simulate Bitcoin networks and providing user interaction. This document explains how Warnet does this by using design philosophies popular with Kubernetes such as Infrastructure as Code and a tendency towards Stateless Configuration and Externalized Configuration.

# Project structure
The Warnet code base has four main sections:

1. resources - these items are available during runtime and relate to configuration (crucially, Kubernetes configuration)
2. src/warnet - python source code lives here
3. test - CI testing files live here
4. docs - stores documentation available in the github repository

## Overview of resources
There are four main kinds of *resources*:

1. Kubernetes configuration files - they are the backbone of Stateless Configuration; they are *yaml* files
2. scenarios - these are python programs that users can load into Kubernetes to interact with the simulated Bitcoin network
3. images - the logic for creating bitcoin nodes and also containers for running scenarios are found here; this includes Dockerfiles
4. scripts and other configs - these are like "assets" or "one off" items which appear in Warnet.

## Overview of src/warnet
The python source code found in *src/warnet* serves to give users a way to create and interact with the simulated Bitcoin network as it exists in a Kubernetes cluster.

There are eight categories of python program files in Warnet:

1. Bitcoin images
  * image.py and image_build.py - the logic that helps the user create bitcoin node images
2. Bitcoin interaction
  * bitcoin.py - make it easy to interact with bitcoin nodes in the simulated network
3. Scenario interaction
  * control.py - launch scenarios in order to interact with the simulated Bitcoin network
4. Kubernetes
  * k8s.py - gather Kubernetes configuration data; retrieve Kubernetes resources
  * status.py - make it easy for the user to see the status of the simulated bitcoin network
5. Resource configuration pipeline
  * admin.py - copy configurations for *resources* such as namespaces and put them in the user's directory
  * deploy.py - take configurations for *resources* and put them into the Kubernetes cluster
  * network.py - copy *resources* to the users Warnet directory
  * namespaces.py - copy *resources* to the users Warnet directory; interact with namespaces in the cluster
6. User interaction
  * main.py - provide the interface for the `warnet` command line program
7. Host computer
  * process.py - provides a way to run commands on the user's host computer
8. Externalized configuration
  * constants.py - this holds values which occur repeatedly in the code base

## Overview of test
The test_base.py file forms the basis of the *test* section. Each test uses *TestBase* which in turn uses the original Bitcoin Test Framework which can be found in the *src* directory.

## The resources configuration pipeline - an example
It is important to focus on the pipeline that takes *resources*, copies them into user directories, and translates them into Kubernetes objects. To make this possible and to achieve a more stateless configuration, Warnet uses Helm which provides templating for Kubernetes configuration files.

Looking more closely at the *resources* section, for example, we can focus in on the *namespaces* directory. Inside, there is an example *namespaces.yaml* and *namespace-defaults.yaml* file. These configuration files are provided to the user when the `warcli admin init` command is invoked. This provides the user the opportunity to change those configuration files by specifying a set of participants who will have access to the simulated Bitcoin network. When `warcli deploy [namespaces_folder]` command is run by the user, it will apply the configuration data to the Helm chart found in the *charts* directory of the *resources* section. The Helm chart acts as a template through which the user's configuration data is applied. In this way, there is a pipeline which starts with the user's Stateful Data which is then piped through the Helm templating system, and then is applied to the Kubernetes cluster.
