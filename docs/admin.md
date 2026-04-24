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

### User roles in `namespace-defaults.yaml`

The `namespace-defaults.yaml` file controls what permissions are granted to users within each wargame namespace. The `roles` list under each user entry maps to Kubernetes RBAC roles created by the namespaces Helm chart:

```yaml
users:
  - name: warnet-user
    roles:
      - pod-viewer            # read pod logs and status
      - pod-manager           # exec into pods and manage lifecycle
      - ingress-viewer        # view ingress resources
      - ingress-controller-viewer  # view ingress controller resources
```

| Role | Grants |
|------|--------|
| `pod-viewer` | Read pod logs, status, and descriptions |
| `pod-manager` | Exec into pods, port-forward, and manage pod lifecycle |
| `ingress-viewer` | View ingress resources in the namespace |
| `ingress-controller-viewer` | View ingress controller resources |

## Managing namespaces

List all active wargame namespaces (those with the `wargames-` prefix):

```shell
$ warnet admin namespaces list
```

Destroy a specific namespace or all wargame namespaces:

```shell
# Destroy a single namespace
$ warnet admin namespaces destroy wargames-red-team

# Destroy all wargames- prefixed namespaces
$ warnet admin namespaces destroy --all
```

## Reverting authentication

To revert to the previous kubeconfig context after switching to a user context with `warnet auth`:

```shell
$ warnet auth --revert
```

This restores the kubeconfig that was in place before the most recent `warnet auth` call.
