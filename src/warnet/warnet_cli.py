from datetime import datetime
import pkgutil
import scenarios
import subprocess
import os
import sys
from warnet.client import get_debug_log, get_bitcoin_cli, get_messages, stop_network

from jsonrpcclient import request, parse, Ok
import requests


def rpc(rpc_method, params=()):
    try:
        response = requests.post(
            "http://localhost:5000/", json=request(rpc_method, params)
        )

        parsed = parse(response.json())
        print(parsed.result)
        return
    except Exception as e:
        return f"{e}"


def main():
    if len(sys.argv) == 1:
        cmd = "help"
    else:
        cmd = sys.argv[1]

    if cmd == "run_warnet":
        return rpc("run_warnet")

    if cmd == "bcli":
        if len(sys.argv) < 4:
            print("`bcli` requires node number and bitcoin-cli command")
            return None
        node = sys.argv[2]
        method = sys.argv[3]
        params = None
        if len(sys.argv) > 3:
            params = sys.argv[4:]
        try:
            print(get_bitcoin_cli(node, method, params))
            return
        except Exception as e:
            return f"Could not get bitcoin-cli command for {node}: {e}"

    if cmd == "log":
        if len(sys.argv) < 3:
            print("`log` requires node number")
            return None
        node = sys.argv[2]
        try:
            return get_debug_log(node)
        except Exception as e:
            return f"Could not get debug log for {node}: {e}"

    if cmd == "messages":
        if len(sys.argv) < 4:
            print("`messages` requires two node numbers (source, destination)")
            return None
        src = sys.argv[2]
        dst = sys.argv[3]
        try:
            messages = get_messages(src, dst)
            out = ""
            for m in messages:
                timestamp = datetime.utcfromtimestamp(m["time"] / 1e6).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                direction = ">>>" if m["outbound"] else "<<<"
                body = ""
                if "body" in m:
                    body = m["body"]
                out = out + f"{timestamp} {direction} {m['msgtype']} {body}\n"
            print(out)
            return
        except Exception as e:
            return f"Could not get messages between nodes {src}->{dst}: {e}"

    if cmd == "run":
        if len(sys.argv) < 3:
            print("`run` requires a scenario name. Available scenarios:")
            for s in pkgutil.iter_modules(scenarios.__path__):
                m = pkgutil.resolve_name(f"scenarios.{s.name}")
                if hasattr(m, "cli_help"):
                    print(s.name.ljust(20), m.cli_help())
            return None
        dir_path = os.path.dirname(os.path.realpath(__file__))
        mod_path = os.path.join(dir_path, "..", "scenarios", f"{sys.argv[2]}.py")
        run_cmd = [sys.executable, mod_path] + sys.argv[3:]
        return subprocess.run(run_cmd)

    if cmd == "stop":
        return rpc("stop_network")

    # default / `help`
    help = """
      Usage: warnet-cli <command> <arg1> <arg2> ...

      Available commands:
        bcli <node#> <method> <params...> Send a bitcoin-cli command to the specified node.
        log <node#>                       Output the bitcoin debug.log file for specified node.
        run <scnario name> <args...>      Run the specified warnet scenario.
        messages <src:node#> <dest:node#> Output the captured messages between two specified nodes.
        stop                              Stop warnet. Stops and removes all containers and networks.
    """
    print(help)
    exit()


if __name__ == "__main__":
    main()
