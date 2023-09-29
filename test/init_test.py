#!/usr/bin/env python3


from pathlib import Path
from subprocess import Popen, run, PIPE
from tempfile import mkdtemp
from time import sleep
from warnet.cli.rpc import rpc_call
from warnet.utils import exponential_backoff

# Warnet server stdout gets logged here
tmpdir = Path(mkdtemp(prefix="warnet_test_"))
network_name = tmpdir.name
logfilepath = tmpdir / "warnet.log"

# Execute a warcli RPC using command line (always returns string)
def warcli(str):
    cmd = ["warcli"] + str.split()
    proc = run(
        cmd,
        stdout=PIPE,
        stderr=PIPE)
    return proc.stdout.decode()

# Execute a warnet RPC API call directly (may return dict or list)
@exponential_backoff()
def rpc(method, params = []):
    return rpc_call(method, params)

print(f"\nStarting Warnet server, logging to: {logfilepath}")
server = Popen(
    f"warnet > {logfilepath}",
    shell=True)

print("\nWaiting for RPC")
rpc("list") # doesn't require anything docker-related
logfile = open(logfilepath, "r")

print("\nBuilding network")
print(warcli(f"network start --network {network_name}"))

print("\nWaiting for build")
timeout = 20 * 60 # If we aren't built in 20 minutes, abort
interval = 5 # seconds between health checks
while True:
    try:
        tanks = rpc("status", {"network": network_name})
        stats = {
            "total": len(tanks)
        }
        for tank in tanks:
            status = tank["status"] if tank["status"] is not None else "none"
            if status not in stats:
                stats[status] = 0
            stats[status] += 1
        print(stats)
        print(logfile.read())
        if "running" in stats and stats["running"] == stats["total"]:
            break

    except Exception as e:
        print(f"Could not get network status: {e}")
    sleep(interval)
    timeout -= interval
    if timeout < 0:
        raise Exception("Network build timed out")

print("\nStopping network")
warcli(f"network down --network {network_name}")

print("\nStopping server:", warcli("stop"))

print("\nRemaining server output:")
print(logfile.read())
logfile.close()

# TODO: Optionally clean up temp dir in ~/.warnet and warnet server log
