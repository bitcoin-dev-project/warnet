#!/usr/bin/env python3

import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from subprocess import PIPE, Popen, run

import requests
from test_base import TestBase


class LoggingTest(TestBase):
    def __init__(self):
        super().__init__()
        self.graph_file_path = Path(os.path.dirname(__file__)) / "data" / "logging.graphml"
        self.scripts_dir = Path(os.path.dirname(__file__)) / ".." / "resources" / "scripts"
        self.connect_logging_process = None
        self.connect_logging_thread = None
        self.connect_logging_logger = logging.getLogger("cnct_log")

    def run_test(self):
        self.start_server()
        try:
            self.start_logging()
            self.setup_network()
            self.test_prometheus_and_grafana()
        finally:
            if self.connect_logging_process is not None:
                self.log.info("Terminating background connect_logging.sh process...")
                self.connect_logging_process.terminate()
            self.stop_server()

    def start_logging(self):
        self.log.info("Running install_logging.sh")
        # Block until complete
        run([f"{self.scripts_dir / 'install_logging.sh'}"])
        self.log.info("Running connect_logging.sh")
        # Stays alive in background
        self.connect_logging_process = Popen(
            [f"{self.scripts_dir / 'connect_logging.sh'}"],
            stdout=PIPE,
            stderr=PIPE,
            bufsize=1,
            universal_newlines=True,
        )
        self.log.info("connect_logging.sh started...")
        self.connect_logging_thread = threading.Thread(
            target=self.output_reader,
            args=(self.connect_logging_process.stdout, self.connect_logging_logger.info),
        )
        self.connect_logging_thread.daemon = True
        self.connect_logging_thread.start()

        self.log.info("Waiting for RPC")
        self.wait_for_rpc("scenarios_available")

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warcli(f"network start {self.graph_file_path}"))
        self.wait_for_all_tanks_status(target="running", timeout=10 * 60)
        self.wait_for_all_edges()

    def make_grafana_api_request(self, ds_uid, start, metric):
        self.log.info("Making Grafana request...")
        data = {
            "queries": [{"expr": metric, "datasource": {"type": "prometheus", "uid": ds_uid}}],
            "from": f"{start}",
            "to": "now",
        }
        reply = requests.post("http://localhost:3000/api/ds/query", json=data)
        assert reply.status_code == 200

        # Default ref ID is "A", only inspecting one "frame"
        return reply.json()["results"]["A"]["frames"][0]["data"]["values"]

    def test_prometheus_and_grafana(self):
        self.log.info("Starting network activity scenarios")
        self.warcli("scenarios run miner_std --allnodes --interval=5 --mature")
        self.warcli("scenarios run tx_flood --interval=1")

        prometheus_ds = requests.get("http://localhost:3000/api/datasources/name/Prometheus")
        assert prometheus_ds.status_code == 200
        prometheus_uid = prometheus_ds.json()["uid"]
        self.log.info(f"Got Prometheus data source uid from Grafana: {prometheus_uid}")

        start = int(datetime.now().timestamp() * 1000)

        def get_five_values_for_metric(metric):
            data = self.make_grafana_api_request(prometheus_uid, start, metric)
            if len(data) < 1:
                self.log.info(f"No Grafana data yet for {metric}")
                return False
            timestamps = data[0]
            values = data[1]
            self.log.info(f"Grafana data: {metric} times:  {timestamps}")
            self.log.info(f"Grafana data: {metric} values: {values}")
            return len(values) > 5

        self.wait_for_predicate(lambda: get_five_values_for_metric("blocks"))
        self.wait_for_predicate(lambda: get_five_values_for_metric("txrate"))


if __name__ == "__main__":
    test = LoggingTest()
    test.run_test()
