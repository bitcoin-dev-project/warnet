import re
import sys
from pathlib import Path


def get_version(file_path, pattern):
    content = Path(file_path).read_text()
    match = re.search(pattern, content)
    return match.group(1) if match else None


pyproject_version = get_version("pyproject.toml", r'version\s*=\s*"([^"]+)"')
version_py_version = get_version("src/warnet/version.py", r'VERSION\s*=\s*"([^"]+)"')

if pyproject_version == version_py_version:
    print(f"Versions match: {pyproject_version}")
    sys.exit(0)
else:
    print(f"Version mismatch: pyproject.toml={pyproject_version}, version.py={version_py_version}")
    sys.exit(1)
