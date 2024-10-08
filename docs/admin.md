# Admin

## Connect to your cluster

Ensure you are connected to your cluster because Warnet will use your current configuration to generate configurations for your users.

```shell
$ warnet status
```

Observe that the output of the command matches your cluster.

## Create an *admin* directory

```shell
$ mkdir admin
$ cd admin
$ warnet admin init
```

Observe that there are now two folders within the *admin* directory: *namespaces* and *networks*

## The *namespaces* directory
This directory contains a Helm chart named *two_namespaces_two_users*.

Modify this chart based on the number of teams and users you have.

Deploy the *two_namespaces_two_users* chart.

```shell
$ warnet deploy namespaces/two_namespaces_two_users
```

Observe that this creates service accounts and namespaces in the cluster:

```shell
$ kubectl get ns
$ kubectl get sa -A
```

### Creating Warnet invites
A Warnet invite is a Kubernetes config file.

Create invites for each of your users.

```shell
$ warnet admin create-kubeconfigs
```

Observe the *kubeconfigs* directory. It holds invites for each user.

### Using Warnet invites
Users can connect to your wargame using their invite.

```shell
$ warnet auth alice-wargames-red-team-kubeconfig
```

### Set up a network for your users
Before letting the users into your cluster, make sure to create a network of tanks for them to view.


```shell
$ warnet deploy networks/mynet --to-all-users
```

Observe that the *wargames-red-team* namespace now has tanks in it.

**TODO**: What's the logging approach here?
