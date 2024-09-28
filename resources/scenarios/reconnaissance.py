#!/usr/bin/env python3

import socket

from commander import Commander

# The entire Bitcoin Core test_framework directory is available as a library
from test_framework.messages import MSG_TX, CInv, hash256, msg_getdata
from test_framework.p2p import MAGIC_BYTES, P2PInterface


def get_signet_network_magic_from_node(node):
    template = node.getblocktemplate({"rules": ["segwit", "signet"]})
    challenge = template["signet_challenge"]
    challenge_bytes = bytes.fromhex(challenge)
    data = len(challenge_bytes).to_bytes() + challenge_bytes
    digest = hash256(data)
    return digest[0:4]


# The actual scenario is a class like a Bitcoin Core functional test.
# Commander is a subclass of BitcoinTestFramework instide Warnet
# that allows to operate on containerized nodes instead of local nodes.
class Reconnaissance(Commander):
    def set_test_params(self):
        # This setting is ignored but still required as
        # a sub-class of BitcoinTestFramework
        self.num_nodes = 1

    def add_options(self, parser):
        parser.description = "Demonstrate network reconnaissance using a scenario and P2PInterface"
        parser.usage = "warnet run /path/to/reconnaissance.py"

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

        # regtest or signet
        chain = self.nodes[0].chain

        # The victim's address could be an explicit IP address
        # OR a kubernetes hostname (use default chain p2p port)
        if ":" in victim["addr"]:
            dstaddr = victim["addr"].split(":")[0]
        else:
            dstaddr = socket.gethostbyname(victim["addr"])
        if chain == "regtest":
            dstport = 18444
        if chain == "signet":
            dstport = 38333
            MAGIC_BYTES["signet"] = get_signet_network_magic_from_node(self.nodes[0])

        # Now we will use a python-based Bitcoin p2p node to send very specific,
        # unusual or non-standard messages to a "victim" node.
        self.log.info(f"Attacking {dstaddr}:{dstport}")
        attacker = P2PInterface()
        attacker.peer_connect(dstaddr=dstaddr, dstport=dstport, net=chain, timeout_factor=1)()
        attacker.wait_until(lambda: attacker.is_connected, check_connected=False)

        # Send a harmless network message we expect a response to and wait for it
        # Ask for TX with a 0 hash
        msg = msg_getdata()
        msg.inv.append(CInv(t=MSG_TX, h=0))
        attacker.send_and_ping(msg)
        attacker.wait_until(lambda: attacker.message_count["notfound"] > 0)
        self.log.info(f"Got notfound message from {dstaddr}:{dstport}")


def main():
    Reconnaissance().main()


if __name__ == "__main__":
    main()
