# Running Warnet

Warnet runs a server which can be used to manage multiple networks.

If the `$XDG_STATE_HOME` environment variable is set, the server will log to
a file `$XDG_STATE_HOME/warnet/warnet.log`, otherwise it will use `$HOME/.warnet/warnet.log`.


To start the server in the foreground simply run:

```bash
warnet
```
# Next: [`warcli` commands](warcli.md)
