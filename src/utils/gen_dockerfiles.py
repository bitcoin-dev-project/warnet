from templates import TEMPLATES
from warnet.utils import SUPPORTED_TAGS

base_url = "ruimarinho/bitcoin-core"

dockerfile_template = """FROM {base_url}:{tag}

RUN apt-get update && apt-get install -y --no-install-recommends \\
        tor \\
        iproute2 \\
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY tor-keys/* /home/debian-tor/.tor/keys/
COPY warnet_entrypoint.sh /warnet_entrypoint.sh
"""

for tag in SUPPORTED_TAGS:
    dockerfile_content = dockerfile_template.format(base_url=base_url, tag=tag)

    with open(TEMPLATES / f"Dockerfile_{tag}", "w") as file:
        file.write(dockerfile_content)

    print(f"generated Dockerfile for tag {tag}")

print("done")
