from templates import TEMPLATES

# Tags
tags = [
    "23.0",
    "22.0",
    "0.21.1",
    "0.20.1",
    "0.19.1",
    "0.18.1",
    "0.17.1",
    "0.16.3",
    "0.15.1",
]

base_url = "ruimarinho/bitcoin-core"

dockerfile_template = """FROM {base_url}:{tag}

RUN apt-get update && apt-get install -y --no-install-recommends \\
        python3 \\
        vim \\
        tor \\
        iproute2; \\
    apt-get clean;

COPY tor-keys/* /home/debian-tor/.tor/keys/
COPY warnet_entrypoint.sh /warnet_entrypoint.sh
"""

for tag in tags:
    dockerfile_content = dockerfile_template.format(base_url=base_url, tag=tag)

    with open(TEMPLATES / f"Dockerfile_{tag}", "w") as file:
        file.write(dockerfile_content)

    print(f"generated Dockerfile for tag {tag}")

print("done")
