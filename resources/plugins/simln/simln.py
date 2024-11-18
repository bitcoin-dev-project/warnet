from hooks_api import post_status, pre_status


@pre_status
def print_something_first():
    print("The simln plugin is enabled.")


@post_status
def print_something_afterwards():
    print("The simln plugin executes after `status` has run.")


def run():
    print("Running the simln plugin")
