#!/usr/bin/env python3

import socket

# The base class exists inside the commander container when deployed,
# but requires a relative path inside the python source code for other functions.
try:
    from commander import Commander
except Exception:
    from resources.scenarios.commander import Commander

# The entire Bitcoin Core test_framework directory is available as a library
from test_framework.messages import MSG_TX, CInv, msg_getdata
from test_framework.p2p import P2PInterface


# This message is provided to the user when they describe the scenario
def cli_help():
    return "Demonstrate network reconnaissance using a scenario and P2PInterface"


# The actual scenario is a class like a Bitcoin Core functional test.
# Commander is a subclass of BitcoinTestFramework instide Warnet
# that allows to operate on containerized nodes instead of local nodes.
class Reconnaissance(Commander):
    def set_test_params(self):
        # This setting is ignored but still required as
        # a sub-class of BitcoinTestFramework
        self.num_nodes = 1

    # Scenario entrypoint
    def run_test(self):
        self.log.info("Getting peer info")

        # Just like a typical Bitcoin Core functional test, this executes an
        # RPC on a node in the network. The actual node at self.nodes[0] may
        # be different depending on the user deploying the scenario. Users in
        # Warnet may have different namepsace access but everyone should always
        # have access to at least one node.
        peerinfo = self.nodes[0].getpeerinfo()
        for peer in peerinfo:
            # You can print out the the scenario logs with `warnet logs`
            # which have a list of all this node's peers' addresses and version
            self.log.info(f"{peer['addr']} {peer['subver']}")

        # We pick a node on the network to attack
        victim = peerinfo[0]

        # The victim's address could be an explicit IP address with port
        # OR a kubernetes hostname (with default chain p2p port)
        if ":" in victim["addr"]:
            dstaddr, dstport = victim["addr"].split(":")
        else:
            dstaddr = socket.gethostbyname(victim["addr"])
            dstport = 18444

        # Now we will use a python-based Bitcoin p2p node to send very specific,
        # unusual or non-standard messages to a "victim" node.
        attacker = P2PInterface()
        attacker.peer_connect(dstaddr=dstaddr, dstport=dstport, net="regtest", timeout_factor=1)()
        attacker.wait_until(lambda: attacker.is_connected, check_connected=False)

        # Send a harmless network message we expect a response to and wait for it
        # Ask for TX with a 0 hash
        msg = msg_getdata()
        msg.inv.append(CInv(t=MSG_TX, h=0))
        attacker.send_and_ping(msg)
        attacker.wait_until(lambda: attacker.message_count["notfound"] > 0)


if __name__ == "__main__":
    Reconnaissance().main()
