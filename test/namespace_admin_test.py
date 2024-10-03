#!/usr/bin/env python3

import os
from pathlib import Path
from typing import Callable, Optional

from test_base import TestBase

from warnet.constants import WARGAMES_NAMESPACE_PREFIX
from warnet.k8s import get_kubeconfig_value, get_static_client
from warnet.process import run_command


class NamespaceAdminTest(TestBase):
    def __init__(self):
        super().__init__()
        self.namespace_dir = (
            Path(os.path.dirname(__file__))
            / "data"
            / "admin"
            / "namespaces"
            / "two_namespaces_two_users"
        )
        self.network_dir = (
            Path(os.path.dirname(__file__)) / "data" / "admin" / "networks" / "6_node_bitcoin"
        )

    def run_test(self):
        try:
            os.chdir(self.tmpdir)
            self.log.info(f"Running test in: {self.tmpdir}")
            self.setup_namespaces()
            self.initial_context = get_kubeconfig_value("{.current-context}")
            self.setup_service_accounts()
            self.deploy_network_in_team_namespaces()
            self.authenticate_and_become_bob()
            self.return_to_intial_context()
        finally:
            self.cleanup()

    def return_to_intial_context(self):
        cmd = f"kubectl config use-context {self.initial_context}"
        self.log.info(run_command(cmd))
        self.wait_for_predicate(self.this_is_the_current_context(self.initial_context))

    def this_is_the_current_context(self, context: str) -> Callable[[], bool]:
        cmd = "kubectl config current-context"
        current_context = run_command(cmd).strip()
        self.log.info(f"Current context: {current_context} {context == current_context}")
        return lambda: current_context == context

    def setup_namespaces(self):
        self.log.info("Setting up the namespaces")
        self.log.info(self.warnet(f"deploy {self.namespace_dir}"))
        self.wait_for_predicate(self.two_namespaces_are_validated)
        self.log.info("Namespace setup complete")

    def setup_service_accounts(self):
        self.log.info("Creating service accounts...")
        self.log.info(self.warnet("admin create-kubeconfigs"))
        self.wait_for_predicate(self.service_accounts_are_validated)

    def deploy_network_in_team_namespaces(self):
        self.log.info("Deploy networks to team namespaces")
        self.log.info(self.warnet(f"deploy {self.network_dir} --to-all-users"))
        self.wait_for_all_tanks_status()
        self.log.info("Waiting for all edges")
        self.wait_for_all_edges()

    def authenticate_and_become_bob(self):
        self.log.info("Authenticating and becoming bob...")
        assert get_kubeconfig_value("{.current-context}") == self.initial_context
        self.log.info(self.warnet("auth kubeconfigs/bob-wargames-red-team-kubeconfig"))
        assert get_kubeconfig_value("{.current-context}") == "bob-wargames-red-team"

    def service_accounts_are_validated(self) -> bool:
        self.log.info("Checking service accounts")
        sclient = get_static_client()
        namespaces = sclient.list_namespace().items

        filtered_namespaces = [
            ns.metadata.name
            for ns in namespaces
            if ns.metadata.name.startswith(WARGAMES_NAMESPACE_PREFIX)
        ]
        assert len(filtered_namespaces) != 0

        maybe_service_accounts = {}

        for namespace in filtered_namespaces:
            service_accounts = sclient.list_namespaced_service_account(namespace=namespace).items
            for sa in service_accounts:
                maybe_service_accounts.setdefault(namespace, []).append(sa.metadata.name)

        expected = {
            "wargames-blue-team": ["carol", "default", "mallory"],
            "wargames-red-team": ["alice", "bob", "default"],
        }

        return maybe_service_accounts == expected

    def get_namespaces(self) -> Optional[list[str]]:
        self.log.info("Querying the namespaces...")
        resp = self.warnet("admin namespaces list")
        if resp == "No warnet namespaces found.":
            return None
        namespaces = []
        for line in resp.splitlines():
            if line.startswith("- "):
                namespaces.append(line.lstrip("- "))
        self.log.info(f"Namespaces: {namespaces}")
        return namespaces

    def two_namespaces_are_validated(self) -> bool:
        maybe_namespaces = self.get_namespaces()
        if maybe_namespaces is None:
            return False
        if len(maybe_namespaces) != 2:
            return False
        if "wargames-blue-team" not in maybe_namespaces:
            return False
        return "wargames-red-team" in maybe_namespaces


if __name__ == "__main__":
    test = NamespaceAdminTest()
    test.run_test()
