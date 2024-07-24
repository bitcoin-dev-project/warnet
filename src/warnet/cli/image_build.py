import importlib.resources
import subprocess

ARCHES = ["amd64", "arm64", "armhf"]


def run_command(command):
    try:
        subprocess.run(command, shell=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def build_image(
    repo: str,
    commit_sha: str,
    docker_registry: str,
    tag: str,
    build_args: str,
    arches: str,
    action: str = "load",
):
    if not build_args:
        build_args = '"--disable-tests --without-gui --disable-bench --disable-fuzz-binary --enable-suppress-external-warnings "'
    else:
        build_args = f'"{build_args}"'

    build_arches = []
    if not arches:
        build_arches.append("amd64")
    else:
        build_arches.extend(arches.split(","))

    for arch in build_arches:
        if arch not in ARCHES:
            print(f"Error: {arch} is not a supported architecture")
            return False

    print(f"{repo=:}")
    print(f"{commit_sha=:}")
    print(f"{docker_registry=:}")
    print(f"{tag=:}")
    print(f"{build_args=:}")
    print(f"{build_arches=:}")

    # Use importlib.resources to check if the templates directory exists
    template_package = "warnet.templates"
    with importlib.resources.path(template_package, "Dockerfile") as dockerfile_path:
        dockerfile_dir = dockerfile_path.parent
        if not dockerfile_dir.is_dir():
            print("Directory src/warnet/templates does not exist.")
            print("Please run this script from the project root.")
            return False

    # Setup buildkit
    builder_name = "bitcoind-builder"
    create_builder_cmd = f"docker buildx create --name {builder_name} --use"
    use_builder_cmd = f"docker buildx use --builder {builder_name}"
    cleanup_builder_cmd = f"docker buildx rm {builder_name}"

    if not run_command(create_builder_cmd):  # noqa: SIM102
        # try to use existing
        if not run_command(use_builder_cmd):
            print(f"Could not create or use builder {builder_name} and create new builder")
            return False

    image_full_name = f"{docker_registry}:{tag}"
    print(f"{image_full_name=}")

    platforms = ",".join([f"linux/{arch}" for arch in build_arches])

    build_command = (
        f"docker buildx build"
        f" --platform {platforms}"
        f" --build-arg REPO={repo}"
        f" --build-arg COMMIT_SHA={commit_sha}"
        f" --build-arg BUILD_ARGS={build_args}"
        f" --tag {image_full_name}"
        f" --file {dockerfile_path} ."
        f" --{action}"
    )
    print(f"Using {build_command=}")

    res = False
    try:
        res = run_command(build_command)
    except Exception as e:
        print(f"Error:\n{e}")
    finally:
        # Tidy up the buildx builder
        if not run_command(cleanup_builder_cmd):
            print("Warning: Failed to remove the buildx builder.")
        else:
            print("Buildx builder removed successfully.")

    return bool(res)
