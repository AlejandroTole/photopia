"""
PHOTOIA - Configuration Loader
"""
from pathlib import Path
import ast
import copy
import importlib
import re

try:
    yaml = importlib.import_module("yaml")
except ModuleNotFoundError as error:
    if error.name != "yaml":
        raise
    yaml = None

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"

DEFAULT_CONFIG = {
    "models": {
        "planner": "qwen2.5vl:7b",
        "analyst": "qwen2.5:7b",
        "ollama_url": "http://127.0.0.1:11434",
    },
    "paths": {
        "darktable_cli": "C:\\Program Files\\darktable\\bin\\darktable-cli.exe",
        "work_dir": "./work",
        "output_dir": "./output",
    },
    "limits": {
        "max_iterations": 3,
        "exposure_ev": [-1.0, 1.0],
        "exposure_black": [-0.05, 0.05],
        "sigmoid_contrast": [0.8, 3.5],
        "sigmoid_skew": [-0.6, 0.6],
        "sigmoid_preserve_hue": [0.0, 100.0],
        "temperature_delta_ratio": [-0.15, 0.15],
    },
    "render": {
        "preview_width": 1920,
        "preview_height": 1280,
        "preview_hq": False,
        "export_quality": 95,
        "export_hq": True,
    },
    "safety": {
        "default_profile": "MINIMAL",
        "max_exposure_delta": 0.5,
        "max_contrast_delta": 1.0,
    },
}


def _parse_scalar(value: str):
    value = value.strip()
    lowered = value.lower()

    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "~"}:
        return None
    if re.fullmatch(r"[-+]?\d+", value):
        return int(value)
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?", value):
        return float(value)

    if value.startswith(("[", "{", "'", '"')):
        return ast.literal_eval(value)
    return value


def _parse_simple_yaml(text: str) -> dict:
    result = {}
    parents = [(-1, result)]

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())
        key, separator, value = line.strip().partition(":")
        if not separator or not key.strip():
            raise ValueError(f"YAML simple inválido en la línea {line_number}")

        while parents[-1][0] >= indent:
            parents.pop()

        parent = parents[-1][1]
        value = value.strip()
        if value:
            parent[key.strip()] = _parse_scalar(value)
        else:
            child = {}
            parent[key.strip()] = child
            parents.append((indent, child))

    return result


def load_config(path="config.yaml") -> dict:
    """
    Load configuration from YAML file and merge with defaults.
    """
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if path == "config.yaml" and not config_path.exists():
        config_path = DEFAULT_CONFIG_PATH

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            contents = f.read()

        user_cfg = yaml.safe_load(contents) if yaml is not None else _parse_simple_yaml(contents)
        user_cfg = user_cfg or {}
        if not isinstance(user_cfg, dict):
            raise ValueError(f"La configuración debe ser un mapping YAML: {config_path}")

        for section, values in user_cfg.items():
            if isinstance(values, dict) and section in cfg and isinstance(cfg[section], dict):
                cfg[section].update(values)
            else:
                cfg[section] = values
    return cfg
