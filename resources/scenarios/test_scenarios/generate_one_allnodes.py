#!/usr/bin/env python3

# The base class exists inside the commander container
try:
    from commander import Commander
except Exception:
    from resources.scenarios.commander import Commander


class GenOneAllNodes(Commander):
    def set_test_params(self):
        self.num_nodes = 1

    def add_options(self, parser):
        parser.description = (
            "Attempt to generate one block on every node the scenario has access to"
        )
        parser.usage = "warnet run /path/to/generate_one_allnodes.py"

    def run_test(self):
        for node in self.nodes:
            wallet = self.ensure_miner(node)
            addr = wallet.getnewaddress("bech32")
            self.log.info(f"node: {node.tank}")
            self.log.info(self.generatetoaddress(node, 1, addr))


def main():
    GenOneAllNodes().main()


if __name__ == "__main__":
    main()
