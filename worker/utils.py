import json

def read_config_flag(path: str, key: str) -> bool:
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return bool(data.get(key, False))
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return False