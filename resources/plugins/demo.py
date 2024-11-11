from hooks_api import post_status, pre_status


@pre_status
def print_something_wonderful():
    print("This has been a very pleasant day.")


@post_status
def print_something_afterwards():
    print("Status has run!")
