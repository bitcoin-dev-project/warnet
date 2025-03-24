#!/usr/bin/env python
import subprocess
import sys

import yaml

# developers can use this tool to verify all repo workflow test execute to completion
#
# execute from repo root like this to execute all tests
#  python test/local_test_runner.py
#
# add optional argument to just execute any matching tests
#  python test/local_test_runner.py [ln_ | graph]


def has_key_path(d, key_path, separator="."):
    """Check if a nested key path (dotted notation) exists in a dictionary."""
    keys = key_path.split(separator)
    for key in keys:
        if not isinstance(d, dict) or key not in d:
            return False
        d = d[key]
    return True


# Load the workflow file
with open(".github/workflows/test.yml") as file:
    workflow = yaml.safe_load(file)

tests_total = 0
tests_skipped = 0
tests_completed = 0

for job_details in workflow.get("jobs", {}).values():
    if has_key_path(job_details, "strategy.matrix.test"):
        print("Found test strategy job, starting serial execution of each test")
        tests = job_details["strategy"]["matrix"]["test"]

        for test in tests:
            tests_total += 1
            if len(sys.argv) > 1 and sys.argv[1] not in test:
                print("skipping test as requested:", test)
                tests_skipped += 1
                continue
            command = f"python test/{test}"
            print(
                "###################################################################################################"
            )
            print("############## executing:", command)
            print(
                "###################################################################################################"
            )
            process = subprocess.run(command, shell=True)
            if process.returncode != 0:
                print("******** testing failed")
                if process.stdout:
                    print("stdout:", process.stdout)
                if process.stderr:
                    print("stderr:", process.stderr)
                sys.exit(1)
            tests_completed += 1

print(
    "###################################################################################################"
)
print("testing complete")
print(f"{tests_completed} of {tests_total} complete - skipped: {tests_skipped} tests")
print(
    "###################################################################################################"
)
