def create_cycle_graph(n: int, version: str, bitcoin_conf: str | None, random_version: bool):
    raise NotImplementedError("create_cycle_graph function is not implemented")


def parse_bitcoin_conf(file_content):
    """
    Custom parser for INI-style bitcoin.conf

    Args:
    - file_content (str): The content of the INI-style file.

    Returns:
    - dict: A dictionary representation of the file content.
            Key-value pairs are stored as tuples so one key may have
            multiple values. Sections are represented as arrays of these tuples.
    """
    current_section = None
    result = {current_section: []}

    for line in file_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1]
            result[current_section] = []
        elif "=" in line:
            key, value = line.split("=", 1)
            result[current_section].append((key.strip(), value.strip()))

    return result


def dump_bitcoin_conf(conf_dict, for_graph=False):
    """
    Converts a dictionary representation of bitcoin.conf content back to INI-style string.

    Args:
    - conf_dict (dict): A dictionary representation of the file content.

    Returns:
    - str: The INI-style string representation of the input dictionary.
    """
    result = []

    # Print global section at the top first
    values = conf_dict[None]
    for sub_key, sub_value in values:
        result.append(f"{sub_key}={sub_value}")

    # Then print any named subsections
    for section, values in conf_dict.items():
        if section is not None:
            result.append(f"\n[{section}]")
        else:
            continue
        for sub_key, sub_value in values:
            result.append(f"{sub_key}={sub_value}")

    if for_graph:
        return ",".join(result)

    # Terminate file with newline
    return "\n".join(result) + "\n"
