import subprocess


def run_command(command: str) -> str:
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, executable="/bin/bash"
    )
    if result.returncode != 0:
        raise Exception(result.stderr)
    return result.stdout


def stream_command(command: str) -> bool:
    process = subprocess.Popen(
        ["/bin/bash", "-c", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    for line in iter(process.stdout.readline, ""):
        print(line, end="")

    process.stdout.close()
    return_code = process.wait()

    if return_code != 0:
        raise Exception(process.stderr)
    return True
