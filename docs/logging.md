# Logging Configuration

The logging behavior of the server is determined by the presence of the `$XDG_STATE_HOME` environment variable. If the variable is set, the server will log to a file located at `$XDG_STATE_HOME/warnet/warnet.log`. However, if the variable is not set, the server will default to logging to `$HOME/.warnet/warnet.log`.

## Install logging infrastructure

First make sure you have `helm` installed, then simply run the following script:

```bash
./src/templates/k8s/install_logging.sh
```

To forward port to view Grafana dashbaord:

```bash
./src/templates/k8s/connect_logging.sh
```
