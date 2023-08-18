def parse_bitcoin_conf(file_content):
    """
    Custom parser for INI-style bitcoin.conf

    Args:
    - file_content (str): The content of the INI-style file.
 
    Returns:
    - dict: A dictionary representation of the file content.
    """
    result = {}
    current_section = None

    for line in file_content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        if line.startswith('[') and line.endswith(']'):
            current_section = line[1:-1]
            result[current_section] = {}
        elif '=' in line:
            key, value = line.split('=', 1)
            if current_section is not None:
                result[current_section][key.strip()] = value.strip()
            else:
                result[key.strip()] = value.strip()

    return result


def dump_bitcoin_conf(conf_dict):
    """
    Converts a dictionary representation of bitcoin.conf content back to INI-style string.

    Args:
    - conf_dict (dict): A dictionary representation of the file content.

    Returns:
    - str: The INI-style string representation of the input dictionary.
    """
    result = []

    for key, value in conf_dict.items():
        if isinstance(value, dict):
            # This is a section
            result.append(f'[{key}]')
            for sub_key, sub_value in value.items():
                result.append(f'{sub_key}={sub_value}')
        else:
            # This is a key-value pair at the top level
            result.append(f'{key}={value}')

    return '\n'.join(result)
