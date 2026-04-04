from pathlib import Path
from typing import Any

import yaml
from loguru import logger


def read_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return it as a dict."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to read YAML file {path}: {e}")
        raise
