#!/usr/bin/env python3

from test_base import TestBase

base = TestBase()

base.start_server()

print(base.warcli("network start"))
base.wait_for_all_tanks_status(target="running")

print(base.warcli("network info"))
print(base.warcli("network status"))

print(base.warcli("rpc 11 -netinfo 4"))

base.stop_server()
