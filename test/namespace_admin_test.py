#!/usr/bin/env python3

import os
from pathlib import Path
from typing import Callable, Optional

import pexpect
from scenarios_test import ScenariosTest
from test_base import TestBase

from warnet.constants import KUBECONFIG, WARGAMES_NAMESPACE_PREFIX
from warnet.k8s import (
    K8sError,
    get_kubeconfig_value,
    get_static_client,
    open_kubeconfig,
    write_kubeconfig,
)
from warnet.process import run_command


class NamespaceAdminTest(ScenariosTest, TestBase):
    def __init__(self):
        super().__init__()

        self.namespace_dir = (
            Path(os.path.dirname(__file__))
            / "data"
            / "admin"
            / "namespaces"
            / "two_namespaces_two_users"
        )

        self.initial_context = None
        self.current_context = None
        self.bob_user = "bob-warnettest"
        self.bob_auth_file = "bob-warnettest-wargames-red-team-warnettest-kubeconfig"
        self.bob_context = "bob-warnettest-wargames-red-team-warnettest"

        self.blue_namespace = "wargames-blue-team-warnettest"
        self.red_namespace = "wargames-red-team-warnettest"
        self.blue_users = ["carol-warnettest", "default", "mallory-warnettest"]
        self.red_users = ["alice-warnettest", self.bob_user, "default"]

        self.bitcoin_version_slug = "Bitcoin Core version v27.0.0"

    def run_test(self):
        try:
            os.chdir(self.tmpdir)
            self.log.info(f"Running test in: {self.tmpdir}")
            self.establish_initial_context()
            self.setup_namespaces()
            self.setup_service_accounts()
            self.setup_network()
            self.admin_checks_logs()
            self.authenticate_and_become_bob()
            self.bob_checks_logs()
            self.bob_runs_scenario_tests()
        finally:
            self.return_to_initial_context()
            try:
                self.cleanup_kubeconfig()
            except K8sError as e:
                self.log.info(f"KUBECONFIG cleanup error: {e}")
            self.cleanup()

    def establish_initial_context(self):
        self.initial_context = get_kubeconfig_value("{.current-context}")
        self.log.info(f"Initial context: {self.initial_context}")
        self.current_context = self.initial_context
        self.log.info(f"Current context: {self.current_context}")

    def setup_namespaces(self):
        self.log.info("Setting up the namespaces")
        self.log.info(self.warnet(f"deploy {self.namespace_dir}"))
        self.wait_for_predicate(self.two_namespaces_are_validated)
        self.log.info("Namespace setup complete")

    def setup_service_accounts(self):
        self.log.info("Creating service accounts...")
        self.log.info(self.warnet("admin create-kubeconfigs"))
        self.wait_for_predicate(self.service_accounts_are_validated)
        self.log.info("Service accounts have been set up and validated")

    def setup_network(self):
        if self.current_context == self.bob_context:
            self.log.info(f"Allowing {self.current_context} to update the network...")
            assert self.this_is_the_current_context(self.bob_context)
            self.warnet(f"deploy {self.network_dir}")
        else:
            self.log.info("Deploy networks to team namespaces")
            assert self.this_is_the_current_context(self.initial_context)
            self.log.info(self.warnet(f"deploy {self.network_dir} --to-all-users"))
        self.wait_for_all_tanks_status()
        self.log.info("Waiting for all edges")
        self.wait_for_all_edges()

    def authenticate_and_become_bob(self):
        self.log.info("Authenticating and becoming bob...")
        self.log.info(f"Current context: {self.current_context}")
        assert self.initial_context == self.current_context
        assert get_kubeconfig_value("{.current-context}") == self.initial_context
        self.warnet(f"auth kubeconfigs/{self.bob_auth_file}")
        self.current_context = self.bob_context
        assert get_kubeconfig_value("{.current-context}") == self.current_context
        self.log.info(f"Current context: {self.current_context}")

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
            self.blue_namespace: self.blue_users,
            self.red_namespace: self.red_users,
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
        if self.blue_namespace not in maybe_namespaces:
            return False
        return self.red_namespace in maybe_namespaces

    def return_to_initial_context(self):
        cmd = f"kubectl config use-context {self.initial_context}"
        self.log.info(run_command(cmd))
        self.wait_for_predicate(self.this_is_the_current_context(self.initial_context))

    def this_is_the_current_context(self, context: str) -> Callable[[], bool]:
        cmd = "kubectl config current-context"
        current_context = run_command(cmd).strip()
        self.log.info(f"Current context: {current_context} {context == current_context}")
        return lambda: current_context == context

    def cleanup_kubeconfig(self):
        try:
            kubeconfig_data = open_kubeconfig(KUBECONFIG)
        except K8sError as e:
            raise K8sError(f"Could not open KUBECONFIG: {KUBECONFIG}") from e

        kubeconfig_data = remove_user(kubeconfig_data, self.bob_user)
        kubeconfig_data = remove_context(kubeconfig_data, self.bob_context)

        try:
            write_kubeconfig(kubeconfig_data, KUBECONFIG)
        except Exception as e:
            raise K8sError(f"Could not write to KUBECONFIG: {KUBECONFIG}") from e

    def bob_runs_scenario_tests(self):
        assert self.this_is_the_current_context(self.bob_context)
        super().run_test()
        assert self.this_is_the_current_context(self.bob_context)

    def bob_checks_logs(self):
        assert self.this_is_the_current_context(self.bob_context)
        self.log.info("Bob will check the logs")

        sut = pexpect.spawn("warnet logs", maxread=4096 * 10)
        assert expect_without_traceback("Please choose a pod", sut)
        sut.sendline("")
        assert expect_without_traceback(self.bitcoin_version_slug, sut)
        sut.close()

        sut = pexpect.spawn(f"warnet logs --namespace {self.red_namespace}", maxread=4096 * 10)
        assert expect_without_traceback("Please choose a pod", sut)
        sut.sendline("")
        assert expect_without_traceback(self.bitcoin_version_slug, sut)
        sut.close()

        sut = pexpect.spawn("warnet logs tank-0008", maxread=4096 * 10)
        assert expect_without_traceback(self.bitcoin_version_slug, sut)
        sut.close()

        sut = pexpect.spawn(
            f"warnet logs tank-0008 --namespace {self.red_namespace}", maxread=4096 * 10
        )
        assert expect_without_traceback(self.bitcoin_version_slug, sut)
        sut.close()

        sut = pexpect.spawn("warnet logs this_does_not_exist", maxread=4096 * 10)
        assert expect_without_traceback("Could not find pod in any namespaces", sut)
        sut.close()

        self.log.info("Bob has checked the logs")
        assert self.this_is_the_current_context(self.bob_context)

    def admin_checks_logs(self):
        assert self.this_is_the_current_context(self.initial_context)
        self.log.info("The admin will check the logs")

        sut = pexpect.spawn("warnet logs", maxread=4096 * 10)
        assert expect_without_traceback("Please choose a pod", sut)
        sut.sendline("")
        assert expect_without_traceback(self.bitcoin_version_slug, sut)
        sut.close()

        sut = pexpect.spawn(f"warnet logs --namespace {self.red_namespace}", maxread=4096 * 10)
        assert expect_without_traceback("Please choose a pod", sut)
        sut.sendline("")
        assert expect_without_traceback(self.bitcoin_version_slug, sut)
        sut.close()

        sut = pexpect.spawn("warnet logs tank-0008", maxread=4096 * 10)
        assert expect_without_traceback("The pod 'tank-0008' is found in these namespaces", sut)
        sut.close()

        sut = pexpect.spawn(
            f"warnet logs tank-0008 --namespace {self.red_namespace}", maxread=4096 * 10
        )
        assert expect_without_traceback(self.bitcoin_version_slug, sut)
        sut.close()

        sut = pexpect.spawn("warnet logs this_does_not_exist", maxread=4096 * 10)
        assert expect_without_traceback("Could not find pod in any namespaces", sut)
        sut.close()

        self.log.info("The admin has checked the logs")
        assert self.this_is_the_current_context(self.initial_context)


def remove_user(kubeconfig_data: dict, username: str) -> dict:
    kubeconfig_data["users"] = [
        user for user in kubeconfig_data["users"] if user["name"] != username
    ]
    return kubeconfig_data


def remove_context(kubeconfig_data: dict, context_name: str) -> dict:
    kubeconfig_data["contexts"] = [
        context for context in kubeconfig_data["contexts"] if context["name"] != context_name
    ]
    return kubeconfig_data


class StackTraceFoundException(Exception):
    """Custom exception raised when a stack trace is found in the output."""

    pass


def expect_without_traceback(expectation: str, sut: pexpect.spawn, timeout: int = 2) -> bool:
    expectation_found = False
    while True:
        try:
            sut.expect(["\r", "\n"], timeout=timeout)  # inquirer uses \r
            line = sut.before.decode("utf-8")
            if "Traceback (" in line:
                raise StackTraceFoundException
            if expectation in line:
                expectation_found = True
        except (pexpect.exceptions.EOF, pexpect.exceptions.TIMEOUT):
            break
    return expectation_found


if __name__ == "__main__":
    test = NamespaceAdminTest()
    test.run_test()
