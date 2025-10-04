#!/usr/bin/env python3

import json
import os
import subprocess
from pathlib import Path
from time import sleep

from test_base import TestBase

from warnet.process import stream_command


class LNBasicTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "ln"
        self.scen_dir = Path(os.path.dirname(__file__)).parent / "resources" / "scenarios"
        self.lns = [
            "tank-0000-ln",
            "tank-0001-ln",
            "tank-0002-ln",
            "tank-0003-ln",
            "tank-0004-ln",
            "tank-0005-ln",
        ]

        self.cb_port = 9235
        self.cb_node = "tank-0003-ln"
        self.port_forward = None

    def run_test(self):
        try:
            # Wait for all nodes to wake up. ln_init will start automatically
            self.setup_network()

            # Test pyln-proto package in scenario
            self.test_pyln_scenario()

            # Test manually configured macroons
            self.test_admin_macaroons()

            # Test circuit breaker API
            self.test_circuit_breaker_api()

            # Send a payment across channels opened automatically by ln_init
            self.pay_invoice(sender="tank-0005-ln", recipient="tank-0003-ln")

            # Manually open two more channels between first three nodes
            # and send a payment using warnet RPC
            self.manual_open_channels()
            self.wait_for_gossip_sync(self.lns[:3], 2 + 2)
            self.pay_invoice(sender="tank-0000-ln", recipient="tank-0002-ln")

        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        stream_command(f"warnet deploy {self.network_dir}")

    def test_pyln_scenario(self):
        self.log.info("Running pyln_connect scenario")
        scenario_file = self.scen_dir / "test_scenarios" / "pyln_connect.py"
        self.log.info(f"Running scenario from: {scenario_file}")
        stream_command(f"warnet run {scenario_file} --source_dir={self.scen_dir} --debug")

    def test_admin_macaroons(self):
        self.log.info("Testing lnd nodes with same macaroon root key can query each other")
        # These tanks all use the same default macaroon root key, meaning the macaroons
        # generated at ~/.lnd/.../admin.macaroon in each lnd container are authorized
        # to make requests to each other.
        info = json.loads(
            self.warnet("ln rpc tank-0001-ln --rpcserver=tank-0002-ln.default:10009 getinfo")
        )
        assert info["alias"] == "tank-0002-ln.default"
        info = json.loads(
            self.warnet("ln rpc tank-0002-ln --rpcserver=tank-0005-ln.default:10009 getinfo")
        )
        assert info["alias"] == "tank-0005-ln.default"

        self.log.info("Testing lnd nodes with unique macaroon root key can NOT query each other")
        # These tanks are configured with unique macaroon root keys
        try:
            self.warnet("ln rpc tank-0001-ln --rpcserver=tank-0003-ln.default:10009 getinfo")
            raise AssertionError("That should not have worked!")
        except Exception as e:
            assert "verification failed: signature mismatch after caveat verification" in str(e)
        try:
            self.warnet("ln rpc tank-0001-ln --rpcserver=tank-0004-ln.default:10009 getinfo")
            raise AssertionError("That should not have worked!")
        except Exception as e:
            assert "verification failed: signature mismatch after caveat verification" in str(e)
        try:
            self.warnet("ln rpc tank-0003-ln --rpcserver=tank-0004-ln.default:10009 getinfo")
            raise AssertionError("That should not have worked!")
        except Exception as e:
            assert "verification failed: signature mismatch after caveat verification" in str(e)

    def fund_wallets(self):
        for ln in self.lns:
            if ln == "tank-0000-ln":
                # cln
                addr = json.loads(self.warnet(f"ln rpc {ln} newaddr p2tr"))["p2tr"]
            else:
                # lnd
                addr = json.loads(self.warnet(f"ln rpc {ln} newaddress p2tr"))["address"]
            self.warnet(f"bitcoin rpc tank-0000 sendtoaddress {addr} 10")
        self.wait_for_predicate(
            lambda: json.loads(self.warnet("bitcoin rpc tank-0000 getmempoolinfo"))["size"]
            == len(self.lns)
        )
        self.warnet("bitcoin rpc tank-0000 -generate 1")
        # cln takes a long time to register its own balance?
        self.wait_for_predicate(
            lambda: len(
                json.loads(self.warnet("ln rpc tank-0000-ln bkpr-listbalances"))["accounts"][0][
                    "balances"
                ]
            )
            > 0
        )

    def manual_open_channels(self):
        self.fund_wallets()
        # 0 -> 1 -> 2
        pk1 = self.warnet("ln pubkey tank-0001-ln")
        pk2 = self.warnet("ln pubkey tank-0002-ln")

        host1 = ""
        host2 = ""

        while not host1 or not host2:
            if not host1:
                host1 = self.warnet("ln host tank-0001-ln")
            if not host2:
                host2 = self.warnet("ln host tank-0002-ln")
            sleep(1)

        print(self.warnet(f"ln rpc tank-0000-ln connect {pk1} {host1}"))
        print(self.warnet(f"ln rpc tank-0000-ln fundchannel {pk1} 100000"))

        print(
            self.warnet(
                f"ln rpc tank-0001-ln openchannel --node_key {pk2} --local_amt 100000 --connect {host2}"
            )
        )

        self.wait_for_predicate(
            lambda: json.loads(self.warnet("bitcoin rpc tank-0000 getmempoolinfo"))["size"] == 2
        )

        self.warnet("bitcoin rpc tank-0000 -generate 10")

    def wait_for_gossip_sync(self, nodes, expected):
        while len(nodes) > 0:
            for node in nodes:
                if node == "tank-0000-ln":
                    # cln
                    chs = json.loads(self.warnet(f"ln rpc {node} listchannels"))["channels"]
                    chs = [ch for ch in chs if ch["direction"] == 1]
                else:
                    # lnd
                    chs = json.loads(self.warnet(f"ln rpc {node} describegraph"))["edges"]
                if len(chs) >= expected:
                    nodes.remove(node)
            sleep(1)

    def pay_invoice(self, sender: str, recipient: str):
        init_balance = int(json.loads(self.warnet(f"ln rpc {recipient} channelbalance"))["balance"])
        inv = json.loads(self.warnet(f"ln rpc {recipient} addinvoice --amt 1000"))
        print(inv)
        if sender == "tank-0000-ln":
            # cln
            print(self.warnet(f"ln rpc {sender} pay {inv['payment_request']}"))
        else:
            # lnd
            print(self.warnet(f"ln rpc {sender} payinvoice -f {inv['payment_request']}"))

        def wait_for_success():
            return (
                int(json.loads(self.warnet(f"ln rpc {recipient} channelbalance"))["balance"])
                == init_balance + 1000
            )

        self.wait_for_predicate(wait_for_success)

    def test_circuit_breaker_api(self):
        self.log.info("Testing Circuit Breaker API with direct kubectl commands")

        # Test /info endpoint
        info_cmd = f"kubectl exec {self.cb_node} -c circuitbreaker -- wget -qO - 127.0.0.1:{self.cb_port}/api/info"
        info = json.loads(subprocess.check_output(info_cmd, shell=True).decode())
        assert "nodeKey" in info, "Circuit breaker info missing nodeKey"
        self.log.info(f"Got node info: {info}")

        # Test /limits endpoint
        limits_cmd = f"kubectl exec {self.cb_node} -c circuitbreaker -- wget -qO - 127.0.0.1:{self.cb_port}/api/limits"
        limits = json.loads(subprocess.check_output(limits_cmd, shell=True).decode())
        assert "limits" in limits, "Circuit breaker limits missing"
        self.log.info(f"Got limits: {limits}")

        self.log.info("✅ Circuit Breaker API tests passed")


if __name__ == "__main__":
    test = LNBasicTest()
    test.run_test()
