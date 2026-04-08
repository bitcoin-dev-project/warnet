import subprocess
import urllib.error
import urllib.request
from importlib.resources import files

ARCHES = ["amd64", "arm64"]

CMAKE_BUILD_ARGS = (
    '"-DBUILD_TESTS=OFF -DBUILD_GUI=OFF -DBUILD_BENCH=OFF'
    " -DBUILD_UTIL=ON -DBUILD_FUZZ_BINARY=OFF -DWITH_ZMQ=ON"
    ' "'
)
AUTOTOOLS_BUILD_ARGS = (
    '"--disable-tests --without-gui --disable-bench'
    " --disable-fuzz-binary --enable-suppress-external-warnings"
    ' "'
)

dockerfile_cmake = files("resources.images.bitcoin").joinpath("Dockerfile.cmake")
dockerfile_autotools = files("resources.images.bitcoin").joinpath("Dockerfile.autotools")


def detect_build_system(repo: str, commit_sha: str) -> str:
    """Detect whether a Bitcoin Core ref uses CMake or autotools.

    Probes the GitHub raw content URL for CMakeLists.txt at the given ref
    (branch, tag, or commit SHA). A 200 means cmake, a 404 means autotools.
    Any other error is logged and falls back to cmake so we don't silently
    pick the wrong build system when the probe itself misbehaves.
    """
    url = f"https://raw.githubusercontent.com/{repo}/{commit_sha}/CMakeLists.txt"
    print(f"Detecting build system: GET {url}")
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            print(f"  HTTP {resp.status} -> cmake")
            return "cmake"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  HTTP 404 -> autotools")
            return "autotools"
        print(f"Warning: HTTP {e.code} {e.reason} probing {url}; defaulting to cmake")
        return "cmake"
    except urllib.error.URLError as e:
        print(f"Warning: could not reach GitHub to detect build system: {e}; defaulting to cmake")
        return "cmake"


def run_command(command):
    try:
        subprocess.run(command, shell=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def build_image(
    repo: str,
    commit_sha: str,
    tags: str,
    build_args: str,
    arches: str,
    action: str,
):
    build_system = detect_build_system(repo, commit_sha)
    print(f"Detected build system: {build_system}")

    if build_system == "cmake":
        dockerfile_path = dockerfile_cmake
        default_build_args = CMAKE_BUILD_ARGS
    else:
        dockerfile_path = dockerfile_autotools
        default_build_args = AUTOTOOLS_BUILD_ARGS

    build_args = default_build_args if not build_args else f'"{build_args}"'

    build_arches = []
    if not arches:
        build_arches = ARCHES
    else:
        build_arches.extend(arches.split(","))

    print(f"{repo=:}")
    print(f"{commit_sha=:}")
    print(f"{tags=:}")
    print(f"{build_args=:}")
    print(f"{build_arches=:}")
    print(f"Using Dockerfile: {dockerfile_path}")

    builder_name = "bitcoind-builder"
    create_builder_cmd = f"docker buildx create --name {builder_name} --use"
    use_builder_cmd = f"docker buildx use --builder {builder_name}"
    cleanup_builder_cmd = f"docker buildx rm {builder_name}"

    if not run_command(create_builder_cmd) and not run_command(use_builder_cmd):
        print(f"Could not create or use builder {builder_name} and create new builder")
        return False

    tag_list = tags.split(",")
    tag_args = " ".join([f"--tag {tag.strip()}" for tag in tag_list])
    print(f"{tag_args=}")

    platforms = ",".join([f"linux/{arch}" for arch in build_arches])

    build_command = (
        f"docker buildx build"
        f" --platform {platforms}"
        f" --build-arg REPO={repo}"
        f" --build-arg COMMIT_SHA={commit_sha}"
        f" --build-arg BUILD_ARGS={build_args}"
        f" {tag_args}"
        f" --file {dockerfile_path}"
        f" {dockerfile_path.parent}"
        f" --{action}"
    )
    print(f"Using {build_command=}")

    res = False
    try:
        res = run_command(build_command)
    except Exception as e:
        print(f"Error:\n{e}")
    finally:
        if not run_command(cleanup_builder_cmd):
            print("Warning: Failed to remove the buildx builder.")
        else:
            print("Buildx builder removed successfully.")

    return bool(res)
