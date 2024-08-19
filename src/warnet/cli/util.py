import os
import subprocess


def run_command(command, stream_output=False, env=None):
    # Merge the current environment with the provided env
    full_env = os.environ.copy()
    if env:
        # Convert all env values to strings (only a safeguard)
        env = {k: str(v) for k, v in env.items()}
        full_env.update(env)

    if stream_output:
        process = subprocess.Popen(
            ["/bin/bash", "-c", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=full_env,
        )

        for line in iter(process.stdout.readline, ""):
            print(line, end="")

        process.stdout.close()
        return_code = process.wait()

        if return_code != 0:
            print(f"Command failed with return code {return_code}")
            return False
        return True
    else:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, executable="/bin/bash"
        )
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return False
        print(result.stdout)
        return True
