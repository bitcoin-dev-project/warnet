#!/usr/bin/env python3

import json

from commander import Commander


class LNBasic(Commander):
    def set_test_params(self):
        self.num_nodes = None

    def add_options(self, parser):
        parser.description = "Open a channel between two LN nodes using REST + macaroon"
        parser.usage = "warnet run /path/to/ln_init.py"

    def run_test(self):
        info = json.loads(self.lns["tank-0003-ln"].get("/v1/getinfo"))
        uri = info["uris"][0]
        pk3, host = uri.split("@")

        print(
            self.lns["tank-0002-ln"].post("/v1/peers", data={"addr": {"pubkey": pk3, "host": host}})
        )

        print(
            self.lns["tank-0002-ln"].post(
                "/v1/channels/stream",
                data={"local_funding_amount": 100000, "node_pubkey": self.hex_to_b64(pk3)},
            )
        )

        # Mine it ourself
        self.wait_until(lambda: self.tanks["tank-0002"].getmempoolinfo()["size"] == 1)
        print(self.tanks["tank-0002"].generate(5, invalid_call=False))


def main():
    LNBasic().main()


if __name__ == "__main__":
    main()
