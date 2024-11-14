from hooks_api import post_status, pre_status


@pre_status
def print_something_first():
    print("The ark plugin is enabled.")


@post_status
def print_something_afterwards():
    print("The ark plugin executes after `status` has run.")


def run():
    print("Running the ark plugin")
