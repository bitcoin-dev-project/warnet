from datetime import datetime
import pkgutil
import scenarios
import subprocess
import os
import sys
from warnet.client import (
  get_debug_log,
  get_messages,
  stop_network
)

def main():
    if len(sys.argv) == 1:
        cmd = "help"
    else:
        cmd = sys.argv[1]

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
                timestamp = datetime.utcfromtimestamp(m["time"] / 1e6).strftime('%Y-%m-%d %H:%M:%S')
                direction = ">>>" if m["outbound"] else "<<<"
                body = ""
                if "body" in m:
                    body = m["body"]
                out = out + f"{timestamp} {direction} {m['msgtype']} {body}"
            return out
        except Exception as e:
            return f"Could not get messages between nodes {src}->{dst}: {e}"

    if cmd == "run":
        if len(sys.argv) < 3:
            print("`run` requires a scenario name. Available scenarios:")
            for s in pkgutil.iter_modules(scenarios.__path__):
                m = pkgutil.resolve_name(f"scenarios.{s.name}")
                if hasattr(m, "cli_help"):
                    print(s.name.ljust(20),m.cli_help())
            return None
        dir_path = os.path.dirname(os.path.realpath(__file__))
        mod_path = os.path.join(dir_path, '..', 'scenarios', f"{sys.argv[2]}.py")
        run_cmd = [sys.executable, mod_path] + sys.argv[3:]
        return subprocess.run(run_cmd)

    if cmd == "stop":
        try:
            return stop_network()
        except Exception as e:
            return f"Could not stop warnet_network: {e}"

    # default / `help`
    help = """
      Usage: warnet-cli <command> <arg1> <arg2> ...

      Available commands:
        log <node number>               Output the bitcoin debug.log file for specified node.
        run <scnario name> <args...>    Run the specified warnet scenario.
        messages <source> <destination> Output the captured messages between two specified nodes.
        stop                            Stop warnet. Stops and removes all containers and networks.
    """
    print(help)
    exit()


if __name__ == "__main__":
    main()
