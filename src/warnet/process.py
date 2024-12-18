import subprocess
from time import sleep


def run_command(command: str) -> str:
    result = subprocess.run(command, shell=True, capture_output=True, text=True, executable="bash")
    if result.returncode != 0:
        raise Exception(result.stderr)
    return result.stdout


def stream_command(command: str) -> bool:
    process = subprocess.Popen(
        ["bash", "-c", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    message = ""
    for line in iter(process.stdout.readline, ""):
        message += line
        print(line, end="")

    process.stdout.close()
    return_code = process.wait()

    if return_code != 0:
        raise Exception(message)
    return True


def wait_for_run(predicate, timeout=5 * 60, interval=5):
    print(f"Waiting for predicate with timeout {timeout}s and interval {interval}s")
    print(predicate)
    while timeout > 0:
        try:
            if run_command(predicate):
                return
        except Exception:
            pass
        sleep(interval)
        timeout -= interval
    import inspect

    raise Exception(
        f"Timed out waiting for Truth from predicate: {inspect.getsource(predicate).strip()}"
    )
