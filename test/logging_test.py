#!/usr/bin/env python3

import os
from datetime import datetime
from pathlib import Path

import requests
from test_base import TestBase

GRAFANA_URL = "http://localhost:2019/grafana/"


class LoggingTest(TestBase):
    def __init__(self):
        super().__init__()
        self.network_dir = Path(os.path.dirname(__file__)) / "data" / "logging"
        self.scripts_dir = Path(os.path.dirname(__file__)) / ".." / "resources" / "scripts"

    def run_test(self):
        try:
            self.setup_network()
            self.wait_for_endpoint_ready()
            self.test_prometheus_and_grafana()
        finally:
            self.cleanup()

    def setup_network(self):
        self.log.info("Setting up network")
        self.log.info(self.warnet(f"deploy {self.network_dir}"))
        self.wait_for_all_tanks_status(target="running", timeout=10 * 60)
        self.wait_for_all_edges()

    def wait_for_endpoint_ready(self):
        self.log.info("Waiting for Grafana to be ready to receive API calls...")

        def check_endpoint():
            try:
                response = requests.get(f"{GRAFANA_URL}login")
                return response.status_code == 200
            except requests.RequestException:
                return False

        self.wait_for_predicate(check_endpoint, timeout=120)
        self.log.info("Grafana login endpoint returned status code 200")

    def make_grafana_api_request(self, ds_uid, start, metric):
        self.log.info("Making Grafana request...")
        data = {
            "queries": [{"expr": metric, "datasource": {"type": "prometheus", "uid": ds_uid}}],
            "from": f"{start}",
            "to": "now",
        }
        reply = requests.post(f"{GRAFANA_URL}api/ds/query", json=data)
        if reply.status_code != 200:
            self.log.error(f"Grafana API request failed with status code {reply.status_code}")
            self.log.error(f"Response content: {reply.text}")
            return None

        # Default ref ID is "A", only inspecting one "frame"
        return reply.json()["results"]["A"]["frames"][0]["data"]["values"]

    def test_prometheus_and_grafana(self):
        self.log.info("Starting network activity scenarios")

        miner_file = "resources/scenarios/miner_std.py"
        tx_flood_file = "resources/scenarios/tx_flood.py"
        self.warnet(f"run {miner_file} --allnodes --interval=5 --mature")
        self.warnet(f"run {tx_flood_file} --interval=1")

        prometheus_ds = requests.get(f"{GRAFANA_URL}api/datasources/name/Prometheus")
        assert prometheus_ds.status_code == 200
        prometheus_uid = prometheus_ds.json()["uid"]
        self.log.info(f"Got Prometheus data source uid from Grafana: {prometheus_uid}")

        start = int(datetime.now().timestamp() * 1000)

        def get_five_values_for_metric(metric):
            data = self.make_grafana_api_request(prometheus_uid, start, metric)
            if data is None:
                self.log.info(f"Failed to get Grafana data for {metric}")
                return False
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

        # Verify default dashboard exists
        dbs = requests.get(f"{GRAFANA_URL}api/search").json()
        assert dbs[0]["title"] == "Default Warnet Dashboard"


if __name__ == "__main__":
    test = LoggingTest()
    test.run_test()
