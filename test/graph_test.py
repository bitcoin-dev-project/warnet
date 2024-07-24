#!/usr/bin/env python3

import json
import os
import tempfile
import uuid
from pathlib import Path

from test_base import TestBase
from warnet.lnd import LNDNode
from warnet.utils import DEFAULT_TAG


class GraphTest(TestBase):
    def __init__(self):
        super().__init__()
        self.graph_file_path = Path(os.path.dirname(__file__)) / "data" / "services.graphml"
        self.json_file_path = Path(os.path.dirname(__file__)) / "data" / "LN_10.json"
        self.NUM_IMPORTED_NODES = 10
        self.test_dir = tempfile.TemporaryDirectory()
        self.tf_create = f"{self.test_dir.name}/{str(uuid.uuid4())}.graphml"
        self.tf_import = f"{self.test_dir.name}/{str(uuid.uuid4())}.graphml"

    def run_test(self):
        self.test_graph_creation_and_import()
        self.validate_graph_schema()

        self.start_server()
        try:
            self.test_graph_with_optional_services()
            self.test_created_graph()
            self.test_imported_graph()
        finally:
            self.stop_server()

    def test_graph_creation_and_import(self):
        self.log.info(f"CLI tool creating test graph file: {self.tf_create}")
        self.log.info(
            self.warcli(
                f"graph create 10 --outfile={self.tf_create} --version={DEFAULT_TAG}", network=False
            )
        )
        self.wait_for_predicate(lambda: Path(self.tf_create).exists())

        self.log.info(f"CLI tool importing json and writing test graph file: {self.tf_import}")
        self.log.info(
            self.warcli(
                f"graph import-json {self.json_file_path} --outfile={self.tf_import} --ln_image=carlakirkcohen/lnd:attackathon --cb=carlakirkcohen/circuitbreaker:attackathon-test",
                network=False,
            )
        )
        self.wait_for_predicate(lambda: Path(self.tf_import).exists())

    def validate_graph_schema(self):
        self.log.info("Validating graph schema")
        assert "invalid" not in self.warcli(f"graph validate {Path(self.tf_create)}", False)
        assert "invalid" not in self.warcli(f"graph validate {Path(self.tf_import)}", False)
        assert "invalid" not in self.warcli(f"graph validate {self.graph_file_path}", False)

    def test_graph_with_optional_services(self):
        self.log.info("Testing graph with optional services...")
        self.log.info(self.warcli(f"network start {self.graph_file_path}"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()
        self.warcli("bitcoin rpc 0 getblockcount")

        self.log.info("Checking services...")
        self.warcli("network down")
        self.wait_for_all_tanks_status(target="stopped")

    def test_created_graph(self):
        self.log.info("Testing created graph...")
        self.log.info(self.warcli(f"network start {Path(self.tf_create)} --force"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()
        self.warcli("bitcoin rpc 0 getblockcount")
        self.warcli("network down")
        self.wait_for_all_tanks_status(target="stopped")

    def test_imported_graph(self):
        self.log.info("Testing imported graph...")
        self.log.info(self.warcli(f"network start {Path(self.tf_import)} --force"))
        self.wait_for_all_tanks_status(target="running")
        self.wait_for_all_edges()
        self.warcli("bitcoin rpc 0 getblockcount")
        self.warcli("scenarios run ln_init")
        self.wait_for_all_scenarios()

        self.verify_ln_channel_policies()

    def verify_ln_channel_policies(self):
        self.log.info("Ensuring warnet LN channel policies match imported JSON description")
        with open(self.json_file_path) as file:
            actual = json.loads(self.warcli("ln rpc 0 describegraph"))["edges"]
            expected = json.loads(file.read())["edges"]
            expected = sorted(expected, key=lambda chan: int(chan["channel_id"]))
            for chan_index, actual_chan_json in enumerate(actual):
                expected_chan = LNDNode.lnchannel_from_json(expected[chan_index])
                actual_chan = LNDNode.lnchannel_from_json(actual_chan_json)
                if not expected_chan.channel_match(actual_chan):
                    self.log.info(
                        f"Channel {chan_index} policy mismatch, testing flipped channel: {actual_chan.short_chan_id}"
                    )
                    if not expected_chan.channel_match(actual_chan.flip()):
                        raise Exception(
                            f"Channel policy doesn't match source: {actual_chan.short_chan_id}\n"
                            + f"Actual:\n{actual_chan}\n"
                            + f"Expected:\n{expected_chan}\n"
                        )


if __name__ == "__main__":
    test = GraphTest()
    test.run_test()
