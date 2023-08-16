import sys
from warnet.client import (
  get_debug_log,
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
        return get_debug_log(node)

    if cmd == "stop":
        return stop_network()

    # default
    help = """
      Usage: warnet-cli <command> <arg1> <arg2> ...

      Available commands:
        log <node number>       Output the bitcoin debug.log file for specified node.
        stop                    Stop warnet. Stops and removes all containers and networks.
    """
    print(help)
    exit()


if __name__ == "__main__":
    main()
