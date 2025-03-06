import subprocess

from setuptools import setup


def version(version) -> str:
    """
    Format the version string.
    This function is called by setuptools_scm to determine the distribution version.
    """
    vers = str(version.tag).lstrip("v") if hasattr(version, "tag") else "0.0.0"

    return vers


def local_version(version) -> str:
    """
    Format the local version to include only the git commit hash.
    This function is called by setuptools_scm to determine the local version part.
    """
    try:
        # Get the short git hash
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"], capture_output=True, text=True, check=True
        )
        commit = result.stdout.strip()

        if commit:
            return f"-{commit}"
    except (subprocess.SubprocessError, FileNotFoundError):
        # Ignore errors from git commands
        pass

    return ""


# Using setuptools_scm with custom version functions
setup(
    use_scm_version={
        "version_scheme": version,
        "local_scheme": local_version,
        "fallback_version": "0.0.0",
        "relative_to": __file__,
    }
)
