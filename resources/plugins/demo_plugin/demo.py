from hooks_api import pre_status


@pre_status
def print_something_first():
    print("The demo plug is enabled.")
