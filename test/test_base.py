import json
import logging
import logging.config
import os
import re
import threading
from pathlib import Path
from subprocess import run
from tempfile import mkdtemp
from time import sleep

from warnet import SRC_DIR
from warnet.k8s import get_pod_exit_status
from warnet.network import _connected as network_connected
from warnet.status import _get_deployed_scenarios as scenarios_deployed
from warnet.status import _get_tank_status as network_status


class TestBase:
    def __init__(self):
        self.setup_environment()
        self.setup_logging()
        self.log_expected_msgs: None | [str] = None
        self.log_unexpected_msgs: None | [str] = None
        self.log_msg_assertions_passed = False
        self.log.info("Warnet test base initialized")

    def setup_environment(self):
        self.tmpdir = Path(mkdtemp(prefix="warnet-test-"))
        os.environ["XDG_STATE_HOME"] = str(self.tmpdir)
        self.logfilepath = self.tmpdir / "warnet.log"
        self.stop_threads = threading.Event()
        self.network = True

    def setup_logging(self):
        with open(SRC_DIR / "logging_config.json") as f:
            logging_config = json.load(f)
        logging_config["handlers"]["file"]["filename"] = str(self.logfilepath)
        logging.config.dictConfig(logging_config)
        self.log = logging.getLogger("test")
        self.log.info("Logging started")
        self.log.info(f"Testdir: {self.tmpdir}")

    def cleanup(self, signum=None, frame=None):
        try:
            self.log.info("Stopping network")
            if self.network:
                self.warnet("down --force")
                self.wait_for_all_tanks_status(target="stopped", timeout=60, interval=1)
        except Exception as e:
            self.log.error(f"Error bringing network down: {e}")
        finally:
            self.stop_threads.set()

    def _print_and_assert_msgs(self, message):
        print(message)
        if (self.log_expected_msgs or self.log_unexpected_msgs) and assert_log(
            message, self.log_expected_msgs, self.log_unexpected_msgs
        ):
            self.log_msg_assertions_passed = True

    def assert_log_msgs(self):
        assert (
            self.log_msg_assertions_passed
        ), f"Log assertion failed. Expected message not found: {self.log_expected_msgs}"
        self.log_msg_assertions_passed = False

    def warnet(self, cmd):
        self.log.debug(f"Executing warnet command: {cmd}")
        command = ["warnet"] + cmd.split()
        proc = run(command, capture_output=True)
        if proc.stderr:
            raise Exception(proc.stderr.decode().strip())
        return proc.stdout.decode().strip()

    def output_reader(self, pipe, func):
        while not self.stop_threads.is_set():
            line = pipe.readline().strip()
            if line:
                func(line)

    def wait_for_predicate(self, predicate, timeout=5 * 60, interval=5):
        self.log.debug(f"Waiting for predicate with timeout {timeout}s and interval {interval}s")
        while timeout > 0:
            try:
                if predicate():
                    return
            except Exception:
                pass
            sleep(interval)
            timeout -= interval
        import inspect

        raise Exception(
            f"Timed out waiting for Truth from predicate: {inspect.getsource(predicate).strip()}"
        )

    def get_tank(self, index):
        # TODO
        return None

    def wait_for_all_tanks_status(self, target="running", timeout=20 * 60, interval=5):
        """Poll the warnet server for container status
        Block until all tanks are running
        """

        def check_status():
            tanks = network_status()
            stats = {"total": 0}
            # "Probably" means all tanks are stopped and deleted
            if len(tanks) == 0:
                return True
            for tank in tanks:
                status = tank["status"]
                stats["total"] += 1
                stats[status] = stats.get(status, 0) + 1
            self.log.info(f"Waiting for all tanks to reach '{target}': {stats}")
            return target in stats and stats[target] == stats["total"]

        self.wait_for_predicate(check_status, timeout, interval)

    def wait_for_all_edges(self, timeout=20 * 60, interval=5):
        """Ensure all tanks have all the connections they are supposed to have
        Block until all success
        """
        self.wait_for_predicate(network_connected, timeout, interval)

    def wait_for_all_scenarios(self):
        def check_scenarios():
            scns = scenarios_deployed()
            if len(scns) == 0:
                return True
            for s in scns:
                exit_status = get_pod_exit_status(s["name"], s["namespace"])
                self.log.debug(f"Scenario {s['name']} exited with code {exit_status}")
                if exit_status != 0:
                    return False
            return True

        self.wait_for_predicate(check_scenarios)

    def get_scenario_return_code(self, scenario_name):
        scns = self.rpc("scenarios_list_running")
        scns = [scn for scn in scns if scn["cmd"].strip() == scenario_name]
        if len(scns) == 0:
            raise Exception(f"Scenario {scenario_name} not found in running scenarios")
        return scns[0]["return_code"]


def assert_equal(thing1, thing2, *args):
    if thing1 != thing2 or any(thing1 != arg for arg in args):
        raise AssertionError(
            "not({})".format(" == ".join(str(arg) for arg in (thing1, thing2) + args))
        )


def assert_log(log_message, expected_msgs, unexpected_msgs=None) -> bool:
    if unexpected_msgs is None:
        unexpected_msgs = []
    assert_equal(type(expected_msgs), list)
    assert_equal(type(unexpected_msgs), list)

    found = True
    for unexpected_msg in unexpected_msgs:
        if re.search(re.escape(unexpected_msg), log_message, flags=re.MULTILINE):
            raise AssertionError(f"Unexpected message found in log: {unexpected_msg}")
    for expected_msg in expected_msgs:
        if re.search(re.escape(expected_msg), log_message, flags=re.MULTILINE) is None:
            found = False
    return found
