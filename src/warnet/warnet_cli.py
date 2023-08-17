from datetime import datetime
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
            print("log requires node number")
            exit()
        node = sys.argv[2]
        try:
            return get_debug_log(node)
        except Exception as e:
            return f"Could not get debug log for {node}: {e}"

    if cmd == "messages":
        if len(sys.argv) < 4:
            print("log requires two node numbers (source, destination)")
            exit()
        src = sys.argv[2]
        dst = sys.argv[3]
        try:
            messages = get_messages(src, dst)
            for m in messages:
                timestamp = datetime.utcfromtimestamp(m["time"] / 1e6).strftime('%Y-%m-%d %H:%M:%S')
                direction = ">>>" if m["outbound"] else "<<<"
                body = ""
                if "body" in m:
                    body = m["body"]
                print(f"{timestamp} {direction} {m['msgtype']} {body}")
            return
        except Exception as e:
            return f"Could not get messages between nodes {src}->{dst}: {e}"

    if cmd == "stop":
        try:
            return stop_network()
        except Exception as e:
            return f"Could not stop warnet_network: {e}"

    # default
    help = """
      Usage: warnet-cli <command> <arg1> <arg2> ...

      Available commands:
        log <node number>               Output the bitcoin debug.log file for specified node.
        messages <source> <destination> Output the captured messages between two specified nodes.
        stop                            Stop warnet. Stops and removes all containers and networks.
    """
    print(help)
    exit()


if __name__ == "__main__":
    main()
