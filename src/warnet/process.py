import re
import subprocess


def run_command(command: str) -> str:
    result = subprocess.run(command, shell=True, capture_output=True, text=True, executable="bash")
    if result.returncode != 0:
        raise Exception(result.stderr)
    return result.stdout


def stream_command(command: str, grep_pattern: str = "") -> bool:
    """Stream output and apply an optional pattern filter."""
    process = subprocess.Popen(
        ["bash", "-c", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    pattern = re.compile(grep_pattern) if grep_pattern else None
    message = ""
    # Only display lines matching the pattern if grep is specified
    for line in iter(process.stdout.readline, ""):
        message += line
        if pattern:
            if pattern.search(line):
                print(line, end="")
        else:
            print(line, end="")

    process.stdout.close()
    return_code = process.wait()

    if return_code != 0:
        raise Exception(message)
    return True
