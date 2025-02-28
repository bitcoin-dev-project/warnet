import subprocess

from setuptools import setup


def version(version) -> str:
    """
    Format the version string.
    This function is called by setuptools_scm to determine the distribution version.
    """
    # Use base_version if available, otherwise fall back to a default
    if hasattr(version, "base_version") and version.base_version:
        vers = version.base_version
    elif hasattr(version, "tag") and version.tag:
        # If we have a tag but no base_version, try to extract from tag
        vers = str(version.tag).lstrip("v")
    else:
        # Default fallback version if nothing else is available
        vers = "0.0.0"

    return vers


def local_version(version) -> str:
    """
    Format the local version using the git hash and status of the working directory.
    If all succeeds, the returned string will be something like "63fe5aa1-dirty"
    This function is called by setuptools_scm to determine the local version part.
    """
    suffix = ""

    try:
        # Get the short git hash
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"], capture_output=True, text=True, check=True
        )
        commit = result.stdout.strip()

        if commit:
            suffix = f"{commit}"

            # Check if working directory is dirty
            status_result = subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
            )

            if status_result.stdout.strip():
                suffix += "-dirty"
    except (subprocess.SubprocessError, FileNotFoundError):
        # Ignore errors from git commands
        pass

    return suffix


# Using setuptools_scm with custom version functions
setup(
    use_scm_version={
        "version_scheme": version,
        "local_scheme": local_version,
        "fallback_version": "0.0.0",
        "relative_to": __file__,
    }
)
